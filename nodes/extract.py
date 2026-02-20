import os
import json
import requests
from typing import List, Optional
from pydantic import BaseModel, Field
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from langsmith import traceable
from config import llm, llm_reasoning, load_prompt, HTML_CACHE_DIR, get_cache_path, CACHE_INDEX_FILE
from nodes.state import GraphState

# In-memory dictionary to speed up URL checks within a run
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

class PageRelevanceResult(BaseModel):
    is_relevant: bool = Field(description="True if the webpage is relevant to the research query")

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
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
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

class Review(BaseModel):
    review_title: Optional[str] = Field(description="Title of the review", default=None)
    review_text: str = Field(description="Content of the review")
    stars: Optional[int] = Field(description="Star rating", default=None)
    found_via_discovery: bool = Field(description="True if the review was found on a discovered link, not directly from initial search results", default=False)

class ExtractionResult(BaseModel):
    reviews: List[Review] = Field(description="List of extracted reviews")

class ReviewLinksDetection(BaseModel):
    urls: List[str] = Field(description="List of detected URLs for more reviews")

from monitor import TrackStep

@traceable(run_type="chain", name="Extract-and-Discover Node")
def extract_and_detect_node(state: GraphState):
    with TrackStep("Extract and Detect") as tracker:
        print("--- EXTRACT AND DETECT ---")
        query = state["query"]
        max_reviews = state.get("max_reviews", 50)
        relevant_ids = state.get("relevant_ids", [])
        results = state.get("retrieved_content", [])
        
        # We maintain a queue and a visited set
        initial_urls = [r['link'] for r in results if r['id'] in relevant_ids]
        queue = list(initial_urls)
        visited_urls = state.get("visited_urls", []) or []
        all_found_urls = state.get("found_review_urls", []) or []
        all_reviews = state.get("reviews", []) or []
        relevance_results = state.get("relevance_results", []) or []
        
        # Templates
        extract_template = load_prompt("extract_reviews.txt")
        detect_template = load_prompt("detect_review_links.txt")
        filter_page_template = load_prompt("filter_page.txt")
        
        extract_schema = json.dumps(ExtractionResult.model_json_schema(), indent=2)
        detect_schema = json.dumps(ReviewLinksDetection.model_json_schema(), indent=2)
        filter_page_schema = json.dumps(PageRelevanceResult.model_json_schema(), indent=2)
        
        structured_llm_extract = llm.with_structured_output(ExtractionResult)
        structured_llm_detect = llm.with_structured_output(ReviewLinksDetection)
        structured_llm_filter = llm_reasoning.with_structured_output(PageRelevanceResult)
        
        # Current candidates
        candidates = list(set(queue + all_found_urls))
        to_check = [u for u in candidates if u and u.startswith('http') and u not in visited_urls]

        while to_check and len(all_reviews) < max_reviews:
            url = to_check.pop(0)
            if not url or url in visited_urls:
                continue
                
            is_pagi = url not in initial_urls
            print(f"Processing (Discovery={is_pagi}): {url}")
            
            content = fetch_content(url)
            visited_urls.append(url)
                
            if content:
                # Save cache id
                cache_path = get_cache_path(url)
                cache_id = os.path.basename(cache_path)

                soup = BeautifulSoup(content, "html.parser")
                
                # Remove noise elements to clean the text
                removed_tags = ["script", "style", "header", "footer", "nav", "aside", "iframe", "svg"]
                for element in soup(removed_tags):
                    element.decompose()
                    
                # Use newline separator to preserve basic visual structure
                page_text = soup.get_text(separator="\n", strip=True)
                
                # 0. Check Page Relevance (NEW)
                print("  Checking page relevance...")
                filter_prompt = filter_page_template.format(query=query, page_snippet=page_text[:30000], json_schema=filter_page_schema)
                try:
                    relevance_response = structured_llm_filter.invoke(filter_prompt, config={"run_name": "Check-Page-Relevance"})
                    is_rel = relevance_response and relevance_response.is_relevant
                    relevance_results.append({"url": url, "is_relevant": is_rel, "cache_id": cache_id})
                    
                    if not is_rel:
                        print(f"  [PAGE NOT RELEVANT] Skipping: {url}")
                        continue
                    print("  [PAGE RELEVANT] Proceeding with extraction...")
                except Exception as e:
                    print(f"  Warning: Page relevance check failed for {url}: {e}. Proceeding anyway.")
                
                # 1. Extract Reviews
                print("  Extracting reviews...")
                extract_prompt = extract_template.format(page_text=page_text[:40000], json_schema=extract_schema)
                extract_response = structured_llm_extract.invoke(extract_prompt, config={"run_name": "Extract-Reviews"})
                if extract_response and extract_response.reviews:
                    for rev in extract_response.reviews:
                        if len(all_reviews) >= max_reviews:
                            break
                        rev_dict = rev.model_dump()
                        rev_dict["website_url"] = url
                        rev_dict["cache_id"] = cache_id
                        rev_dict["found_via_discovery"] = is_pagi
                        all_reviews.append(rev_dict)
                    print(f"  Found {len(extract_response.reviews)} reviews (Total: {len(all_reviews)}).")
                else:
                    print("  No reviews extracted or LLM failed.")
                
                if len(all_reviews) >= max_reviews:
                    print(f"  Reached max reviews limit ({max_reviews}). Stopping discovery.")
                    break

                # 2. Detect Links (for discovery)
                print("  Detecting links...")
                detect_prompt = detect_template.format(page_text=page_text[:30000], base_url=url, json_schema=detect_schema)
                detect_response = structured_llm_detect.invoke(detect_prompt, config={"run_name": "Discover-Review-Links"})
                
                if detect_response and detect_response.urls:
                    new_links = []
                    for l in detect_response.urls:
                        if not l: continue
                        full_url = urljoin(url, l)
                        if full_url.startswith('http') and full_url not in visited_urls and full_url not in to_check:
                            new_links.append(full_url)
                    
                    to_check.extend(new_links)
                    all_found_urls.extend(new_links)
                    print(f"  Found {len(new_links)} new links.")
                else:
                    print("  No new links discovered.")
        
    metrics = state.get("step_metrics", [])
    metrics.append(tracker.result)
    
    return {
        "reviews": all_reviews, 
        "found_review_urls": list(set(all_found_urls)), 
        "visited_urls": visited_urls,
        "relevance_results": relevance_results,
        "step_metrics": metrics
    }
