import time
from langsmith import traceable
from helpers import search_wrapper
from nodes.state import GraphState
from monitor import TrackStep
from const import DEFAULT_RETRIEVER_MAX_RESULTS


@traceable(run_type="retriever")
def retrieval_node(state: GraphState):
    with TrackStep("Retrieval") as tracker:
        print("--- RETRIEVAL ---")
        query = state["query"]
        config = state.get("config", {})

        # Retrieval setting from config
        max_results = config.get("retriever_max_results", DEFAULT_RETRIEVER_MAX_RESULTS)
        forbidden_urls = [f.lower().strip() for f in config.get("forbidden_urls", [])]

        results = []
        max_retries = 3
        wait_seconds = 2

        for attempt in range(1, max_retries + 1):
            try:
                print(f"  Attempting search (Attempt {attempt}/{max_retries})...")
                results = search_wrapper.results(query, max_results=max_results)
                if results:
                    break
            except Exception as e:
                print(f"  [SEARCH ERROR] Attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    print(f"    - Rate limit or connection issue suspected. Waiting {wait_seconds}s before retry...")
                    time.sleep(wait_seconds)
                    wait_seconds *= 2  # Exponential backoff
                else:
                    print(f"    - [CRITICAL] All DuckDuckGo attempts failed. Returning empty results.")
                    results = []

        print(f"DuckDuckGo found {len(results)} results.")
        for idx, r in enumerate(results):
            print(f"  {idx+1}. {r['link']}")

        filtered_results = []
        for r in results:
            link = r['link'].lower()
            # Hardcoded exclusions + user exclusions
            if "tripadvisor" in link:
                continue
            
            if any(forbidden in link for forbidden in forbidden_urls if forbidden):
                print(f"  [FILTERED] Excluding forbidden URL: {r['link']}")
                continue
            
            filtered_results.append(r)

        print(f"Remaining after filter: {len(filtered_results)}")

        relevant_ids = []
        found_review_urls = []
        for idx, result in enumerate(filtered_results):
            rid = f"result_{idx+1}"
            result["id"] = rid
            relevant_ids.append(rid)
            found_review_urls.append(result['link'])

    metrics = state.get("step_metrics", [])
    metrics.append(tracker.result)

    return {
        "retrieved_content": filtered_results,
        "relevant_ids": relevant_ids,
        "seed_urls": found_review_urls,
        "found_review_urls": found_review_urls,
        "step_metrics": metrics
    }
