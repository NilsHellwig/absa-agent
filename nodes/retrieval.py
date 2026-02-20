from langsmith import traceable
from config import search_wrapper, RETRIEVER_MAX_RESULTS
from nodes.state import GraphState

from monitor import TrackStep

@traceable(run_type="retriever")
def retrieval_node(state: GraphState):
    with TrackStep("Retrieval") as tracker:
        print("--- RETRIEVAL ---")
        query = state["query"]
        results = search_wrapper.results(query, max_results=RETRIEVER_MAX_RESULTS)
        
        print(f"DuckDuckGo found {len(results)} results.")
        for idx, r in enumerate(results):
            print(f"  {idx+1}. {r['link']}")

        filtered_results = [r for r in results if "tripadvisor" not in r['link'].lower()]
        print(f"Remaining after filter: {len(filtered_results)}")
        
        relevant_ids = []
        for idx, result in enumerate(filtered_results):
            rid = f"result_{idx+1}"
            result["id"] = rid
            relevant_ids.append(rid)
    
    metrics = state.get("step_metrics", [])
    metrics.append(tracker.result)
    
    return {"retrieved_content": filtered_results, "relevant_ids": relevant_ids, "step_metrics": metrics}
