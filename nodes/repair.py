import json
import os
import re
from typing import List, Optional
from bs4 import BeautifulSoup
from langsmith import traceable
from helpers import load_prompt, get_llm, get_cache_path
from monitor import TrackStep
from nodes.state import GraphState
from nodes.models import RepairCheck, RepairSearch, RepairResult
from const import (MAX_REPAIR_CONTEXTS, MAX_REPAIR_CHARS, MAX_REPAIR_TOTAL_CHARS,
                   MAX_SNIPPET_LEN, MAX_REPAIR_ATTEMPTS, REPAIR_SEARCH_DEPTH,
                   REPAIR_CONTEXT_MIN_CHARS, MIN_REPAIR_LENGTH)


def get_contexts_for_term(soup: BeautifulSoup, term: str, max_results: int = MAX_REPAIR_CONTEXTS, max_chars: int = MAX_REPAIR_CHARS) -> List[str]:
    """Finds up to max_results contexts around a specific unique term in the soup."""
    if not term:
        return []

    # Search for all text nodes containing this specific term
    matches = soup.find_all(string=re.compile(re.escape(term), re.IGNORECASE))

    if not matches:
        return []

    contexts = []
    for match in matches[:max_results]:
        parent = match.parent

        # Go up a few levels to get the whole review block context
        depth = 0
        while parent and depth < 3 and len(parent.get_text()) < 2500:
            parent = parent.parent
            depth += 1

        if parent:
            # Return raw HTML as per user request (instead of get_text)
            contexts.append(str(parent)[:max_chars])

    return contexts


@traceable(run_type="chain", name="Intelligent Repair Node")
def repair_reviews_node(state: GraphState):
    with TrackStep("Repair") as tracker:
        print("--- INTELLIGENT REPAIR AGENT (5-Attempt Loop) ---")
        query = state["query"]
        config = state.get("config", {})
        temp_reviews = state.get("temp_reviews", [])

        if not temp_reviews:
            return {"temp_reviews": []}

        check_template = load_prompt("05_review_completeness.md")
        search_template = load_prompt("06_repair_search_query.md")
        repair_template = load_prompt("07_repair_review.md")

        # Dynamic LLMs
        llm = get_llm(config)
        llm_reasoning = get_llm(config, use_reasoning=True)

        check_llm = llm_reasoning.with_structured_output(RepairCheck)
        search_llm = llm.with_structured_output(RepairSearch)
        repair_llm = llm.with_structured_output(RepairResult)

        repaired_batch = []
        repaired_count = 0
        discarded_count = 0

        for rev in temp_reviews:
            url = rev.get("website_url")
            cache_path = get_cache_path(url)

            if not os.path.exists(cache_path):
                repaired_batch.append(rev)
                continue

            with open(cache_path, "r", encoding="utf-8") as f:
                html_content = f.read()
                soup = BeautifulSoup(html_content, "html.parser")

                # Clean soup once per URL in repair
                for element in soup(["script", "style", "header", "footer", "nav"]):
                    element.decompose()

            # 1. CHECK: Is it incomplete?
            page_snippet = soup.get_text(separator="\n", strip=True)[
                :MAX_SNIPPET_LEN]
            check_prompt = check_template.format(
                query=query,
                page_text=page_snippet,
                review_text=rev["review_text"],
                json_schema=json.dumps(
                    RepairCheck.model_json_schema(), indent=2)
            )

            try:
                check_res = check_llm.invoke(
                    check_prompt, config={"run_name": "Check-Review-Completeness"})
                if check_res.complete:
                    repaired_batch.append(rev)
                    continue
            except Exception:
                if "..." not in rev["review_text"] and len(rev["review_text"]) > 150:
                    repaired_batch.append(rev)
                    continue

            # 2. LOOP: Intelligent Search & Repair (up to constants.MAX_REPAIR_ATTEMPTS attempts)
            print(f"  Repairing snippet: {rev['review_text'][:30]}...")
            current_text = rev["review_text"]
            failed_terms = []
            success = False

            for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
                print(f"    - Attempt {attempt}/{MAX_REPAIR_ATTEMPTS}...")

                history_str = ", ".join(
                    [f'"{t}"' for t in failed_terms]) if failed_terms else "None"
                search_prompt = search_template.format(
                    review_text=current_text,
                    history=history_str,
                    json_schema=json.dumps(
                        RepairSearch.model_json_schema(), indent=2)
                )
                search_res = search_llm.invoke(
                    search_prompt, config={"run_name": f"Search-Attempt-{attempt}"})
                term = search_res.search_term

                contexts = get_contexts_for_term(soup, term)

                if not contexts:
                    print(f"      [Search Term '{term}' not found in HTML]")
                    failed_terms.append(term)
                    continue

                # Filter contexts to respect total character limit
                filtered_contexts = []
                total_chars = 0
                for ctx in contexts:
                    if total_chars + len(ctx) > MAX_REPAIR_TOTAL_CHARS:
                        print(f"      Total limit ({MAX_REPAIR_TOTAL_CHARS}) reached. Skipping remaining contexts.")
                        break
                    filtered_contexts.append(ctx)
                    total_chars += len(ctx)

                # Use filtered contexts (Up to MAX_REPAIR_CONTEXTS)
                context_str = "\n---\n".join(
                    [f"Source Segment {i+1}:\n{ctx}" for i, ctx in enumerate(filtered_contexts)])

                repair_prompt = repair_template.format(
                    query=query,
                    html_segments=context_str,
                    current_review_text=current_text,
                    json_schema=json.dumps(
                        RepairResult.model_json_schema(), indent=2)
                )

                try:
                    repair_res = repair_llm.invoke(
                        repair_prompt, config={"run_name": f"Repair-Attempt-{attempt}"})
                    current_text = repair_res.fixed_text

                    if repair_res.complete:
                        rev["review_text"] = current_text
                        repaired_batch.append(rev)
                        repaired_count += 1
                        success = True
                        print(
                            f"      [SUCCESS] Review repaired on attempt {attempt}.")
                        break
                    else:
                        print(
                            f"      [CONTINUE] Text still incomplete after attempt {attempt}.")
                except Exception as e:
                    print(
                        f"      [ERROR] Repair failed on attempt {attempt}: {e}")

            if not success:
                discarded_count += 1
                print(f"    - [DISCARDED] Could not repair after 5 attempts.")

        print(
            f"\nFinal Repair results: {repaired_count} repaired, {discarded_count} discarded, {len(repaired_batch)} kept.")

    metrics = state.get("step_metrics", [])
    metrics.append(tracker.result)

    return {"temp_reviews": repaired_batch, "step_metrics": metrics}
