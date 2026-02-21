from langsmith import traceable
from helpers import search_wrapper
from nodes.state import GraphState

from monitor import TrackStep


@traceable(run_type="retriever")
def retrieval_node(state: GraphState):
    with TrackStep("Retrieval") as tracker:
        print("--- RETRIEVAL ---")
        query = state["query"]
        config = state.get("config", {})

        # Retrieval setting from config
        max_results = config.get("retriever_max_results", 5)

        results = search_wrapper.results(
            query, max_results=max_results)

        print(f"DuckDuckGo found {len(results)} results.")
        for idx, r in enumerate(results):
            print(f"  {idx+1}. {r['link']}")

        filtered_results = [
            r for r in results if "tripadvisor" not in r['link'].lower()]
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
