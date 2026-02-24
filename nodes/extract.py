from monitor import TrackStep
import os
import json
import requests
from typing import List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from langsmith import traceable
from const import (HTML_CACHE_DIR, CACHE_INDEX_FILE, 
                   MAX_FILTER_SNIPPET, MAX_EXTRACT_SNIPPET, MAX_DETECT_SNIPPET,
                   DEFAULT_MAX_REVIEWS, FETCH_TIMEOUT_SECONDS, USER_AGENT_STRING)
from helpers import load_prompt, get_llm, get_cache_path
from nodes.state import GraphState
from nodes.models import PageRelevanceResult, Review, ExtractionResult, ReviewLinksDetection
url_cache = {}
global_cache_index = None


def get_cache_index():
    """Loads the URL-to-file index from disk, once per run ideally."""
    global global_cache_index
    if global_cache_index is not None:
        return global_cache_index

    if os.path.exists(CACHE_INDEX_FILE):
        try:
            with open(CACHE_INDEX_FILE, "r", encoding="utf-8") as f:
                global_cache_index = json.load(f)
                return global_cache_index
        except:
            global_cache_index = {}
            return global_cache_index
    global_cache_index = {}
    return global_cache_index


def save_to_cache_index(url: str, filename: str):
    """Saves a URL-to-file mapping to the disk index and global variable."""
    index = get_cache_index()
    index[url] = filename
    with open(CACHE_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)


def fetch_content(url: str):
    """Fetches URL content with disk and in-memory caching."""
    if url in url_cache:
        return url_cache[url]

    # Check disk index and path
    index = get_cache_index()
    cache_path = get_cache_path(url)
    filename = os.path.basename(cache_path)

    # If the URL is in the index OR the hash file exists, it's a hit
    if url in index and os.path.exists(cache_path):
        print(f"  Cache hit (index) for {url}")
        with open(cache_path, "r", encoding="utf-8") as f:
            content = f.read()
            url_cache[url] = content
            return content
    elif os.path.exists(cache_path):
        # Already exists from previous hash-only logic, let's index it now
        print(f"  Cache hit (file) for {url}, indexing...")
        save_to_cache_index(url, filename)
        with open(cache_path, "r", encoding="utf-8") as f:
            content = f.read()
            url_cache[url] = content
            return content

    print(f"  Fetching {url}...")
    try:
        res = requests.get(url, timeout=FETCH_TIMEOUT_SECONDS, headers={
                           "User-Agent": USER_AGENT_STRING})
        if res.status_code == 200:
            content = res.text
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Update index
            save_to_cache_index(url, filename)

            url_cache[url] = content
            return content
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
    return None


@traceable(run_type="chain", name="Extract-and-Discover Node")
def extract_and_detect_node(state: GraphState):
    with TrackStep("Extract and Detect") as tracker:
        print("--- EXTRACT AND DETECT ---")
        query = state["query"]
        config = state.get("config", {})
        max_reviews = state.get("max_reviews", config.get("max_reviews", DEFAULT_MAX_REVIEWS))
        all_reviews = state.get("reviews", []) or []

        if len(all_reviews) >= max_reviews:
            print(
                f"  [LIMIT] Already reached {len(all_reviews)}/{max_reviews}. Stopping.")
            # Clear queue to stop graph
            return {"temp_reviews": [], "found_review_urls": []}

        # We process ONE URL from the queue
        queue = state.get("found_review_urls", [])
        visited_urls = state.get("visited_urls", []) or []
        relevance_results = state.get("relevance_results", []) or []

        # If queue is empty, we are done
        if not queue:
            print("  Queue is empty. Moving on.")
            return {"temp_reviews": []}

        url = queue.pop(0)
        if not url or url in visited_urls:
            print(f"  Skipping (already visited or empty): {url}")
            return {"found_review_urls": queue, "temp_reviews": []}

        # Safety check for forbidden URLs
        forbidden_urls = [f.lower().strip() for f in config.get("forbidden_urls", [])]
        if any(forbidden in url.lower() for forbidden in forbidden_urls if forbidden):
            print(f"  [FORBIDDEN] Skip forbidden URL: {url}")
            # Mark it as visited to avoid redundant checks
            new_visited = visited_urls + [url]
            return {"found_review_urls": queue, "visited_urls": new_visited, "temp_reviews": []}

        # Determine if URL was discovered via BFS or was part of seed/initial search
        is_discovery = url not in state.get("seed_urls", [])

        print(f"Processing URL: {url} (Discovery: {is_discovery})")
        content = fetch_content(url)
        visited_urls.append(url)

        new_batch = []
        updated_queue = list(queue)

        if content:
            # Save cache id
            cache_path = get_cache_path(url)
            cache_id = os.path.basename(cache_path)

            soup = BeautifulSoup(content, "html.parser")

            removed_tags = ["script", "style", "header",
                            "footer", "nav", "aside", "iframe", "svg"]
            for element in soup(removed_tags):
                element.decompose()

            page_text = soup.get_text(separator="\n", strip=True)

            # Templates & LLM
            filter_page_template = load_prompt("02_filter_page.md")
            filter_page_schema = json.dumps(
                PageRelevanceResult.model_json_schema(), indent=2)

            # Dynamic LLM for filtering
            llm_reasoning = get_llm(config, use_reasoning=True)
            structured_llm_filter = llm_reasoning.with_structured_output(
                PageRelevanceResult)

            # 0. Check Page Relevance
            print("  Checking page relevance...")
            filter_prompt = filter_page_template.format(
                query=query, page_snippet=page_text[:MAX_FILTER_SNIPPET], json_schema=filter_page_schema)
            try:
                relevance_response = structured_llm_filter.invoke(
                    filter_prompt, config={"run_name": "Check-Page-Relevance"})
                is_rel = relevance_response and relevance_response.is_relevant
                relevance_results.append(
                    {"url": url, "is_relevant": is_rel, "cache_id": cache_id})

                if not is_rel:
                    print(f"  [PAGE NOT RELEVANT] Skipping: {url}")
                    return {"found_review_urls": updated_queue, "visited_urls": visited_urls, "relevance_results": relevance_results, "temp_reviews": []}
                print("  [PAGE RELEVANT] Proceeding...")
            except Exception as e:
                print(f"  Warning: Relevance check failed: {e}. Proceeding.")
                relevance_results.append(
                    {"url": url, "is_relevant": True, "cache_id": cache_id})

            # 1. Extract Reviews
            extract_template = load_prompt("03_extract_reviews.md")
            extract_schema = json.dumps(
                ExtractionResult.model_json_schema(), indent=2)

            # Standard LLM for extraction
            llm = get_llm(config)
            structured_llm_extract = llm.with_structured_output(
                ExtractionResult)

            print("  Extracting reviews...")
            extract_prompt = extract_template.format(
                page_text=page_text[:MAX_EXTRACT_SNIPPET], json_schema=extract_schema)
            extract_response = structured_llm_extract.invoke(
                extract_prompt, config={"run_name": "Extract-Reviews"})

            if extract_response and extract_response.reviews:
                for rev in extract_response.reviews:
                    rev_dict = rev.model_dump()
                    rev_dict["website_url"] = url
                    rev_dict["cache_id"] = cache_id
                    # Manual assignment - not predicted by LLM
                    rev_dict["found_via_discovery"] = is_discovery
                    new_batch.append(rev_dict)
                print(f"  Extracted {len(new_batch)} new reviews.")
            else:
                print("  No reviews found on this page.")

            # 2. Detect Links (optional check via config)
            if state["config"].get("disable_discovery"):
                print("  Link discovery is disabled in config.")
            else:
                detect_template = load_prompt("04_detect_review_links.md")
                detect_schema = json.dumps(
                    ReviewLinksDetection.model_json_schema(), indent=2)

                # Standard LLM for detection
                llm = get_llm(config)
                structured_llm_detect = llm.with_structured_output(
                    ReviewLinksDetection)

                print("  Detecting links...")
                detect_prompt = detect_template.format(
                    page_text=page_text[:MAX_DETECT_SNIPPET], base_url=url, json_schema=detect_schema)
                detect_response = structured_llm_detect.invoke(
                    detect_prompt, config={"run_name": "Discover-Review-Links"})

                if detect_response and detect_response.urls:
                    for l in detect_response.urls:
                        if not l:
                            continue
                        full_url = urljoin(url, l)
                        if full_url.startswith('http') and full_url not in visited_urls and full_url not in updated_queue:
                            # Respect forbidden URLs
                            if not any(f in full_url.lower() for f in forbidden_urls):
                                updated_queue.append(full_url)
                    print(f"  Updated queue size: {len(updated_queue)}")

    metrics = state.get("step_metrics", [])
    metrics.append(tracker.result)

    return {
        "temp_reviews": new_batch,
        "found_review_urls": updated_queue,
        "visited_urls": visited_urls,
        "relevance_results": relevance_results,
        "step_metrics": metrics
    }
