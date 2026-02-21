import os
import json
import argparse
import uuid
from langgraph.graph import StateGraph, END
from nodes.state import GraphState
from nodes.generate_query import generate_query_node
from nodes.retrieval import retrieval_node
from nodes.extract import extract_and_detect_node
from nodes.repair import repair_reviews_node
from nodes.verify import verify_reviews_node
from dotenv import load_dotenv

# Graph Construction
def create_graph():
    workflow = StateGraph(GraphState)
    
    # Adding nodes
    workflow.add_node("generate_query", generate_query_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("extract", extract_and_detect_node)
    workflow.add_node("repair", repair_reviews_node)
    workflow.add_node("verify", verify_reviews_node)

    # Entry
    workflow.set_entry_point("generate_query")
    workflow.add_edge("generate_query", "retrieval")
    workflow.add_edge("retrieval", "extract")
    
    # Check if we have something to repair/verify
    def check_extraction_results(state: GraphState):
        if not state.get("temp_reviews"):
            return "skip_to_router"
        return "process_reviews"

    workflow.add_conditional_edges(
        "extract",
        check_extraction_results,
        {
            "process_reviews": "repair",
            "skip_to_router": "verify" # We go to verify node because it handles merging (even if empty)
        }
    )
    
    workflow.add_edge("repair", "verify")
    
    # Logic to continue or stop
    def router(state: GraphState):
        current_count = len(state.get("reviews", []))
        max_req = state.get("max_reviews", 50)
        
        if current_count >= max_req:
            print(f"--- LIMIT REACHED ({current_count}/{max_req}). STOPPING. ---")
            return END
            
        if not state.get("found_review_urls"):
            print("--- QUEUE EMPTY. STOPPING. ---")
            return END
            
        return "continue"

    workflow.add_conditional_edges(
        "verify",
        router,
        {
            "continue": "extract",
            END: END
        }
    )
    
    return workflow.compile()

def save_results(state, session_id):
    """Saves the final reviews, relevance scores, and metrics to the results folder."""
    reviews = state.get("reviews", [])
    relevance_results = state.get("relevance_results", [])
    step_metrics = state.get("step_metrics", [])
    
    folder_path = f"results/results_{session_id}"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path, exist_ok=True)
    
    # 1. Save reviews.json (with cache_id and step metrics included)
    reviews_file = os.path.join(folder_path, "reviews.json")
    with open(reviews_file, "w", encoding="utf-8") as f:
        json.dump({
            "reviews": reviews,
            "metrics": step_metrics,
            "summary": {
                "total_reviews": len(reviews),
                "total_duration": sum(m["duration"] for m in step_metrics) if step_metrics else 0,
                "total_avg_wattage": sum(m["avg_gpu_power_watts"] for m in step_metrics) / len(step_metrics) if step_metrics else 0
            }
        }, f, indent=4, ensure_ascii=False)
    
    # 2. Save relevance_url.json
    relevance_file = os.path.join(folder_path, "relevance_url.json")
    with open(relevance_file, "w", encoding="utf-8") as f:
        json.dump(relevance_results, f, indent=4, ensure_ascii=False)
    
    print(f"\n--- SUCCESS ---")
    print(f"Reviews & Metrics saved to: {reviews_file}")
    print(f"Relevance data saved to: {relevance_file}")
    print(f"Total reviews: {len(reviews)}")

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="ABSA Agent - Review Content Crawler")
    parser.add_argument("query", type=str, help="The search query for reviews (e.g., 'Apple Store Berlin reviews')")
    parser.add_argument("--id", type=str, default=None, help="Optional session ID for the results folder")
    parser.add_argument("--max_reviews", type=int, default=50, help="Maximum number of reviews to extract total (default: 50)")
    
    args = parser.parse_args()
    
    # use provided ID or generate a new one
    session_id = args.id or str(uuid.uuid4())[:8]
    
    print(f"Starting agent for query: '{args.query}' (ID: {session_id}, Max Reviews: {args.max_reviews})")
    
    # Initialize state
    initial_state = {
        "query": args.query,
        "max_reviews": args.max_reviews,
        "retrieved_content": [],
        "relevant_ids": [],
        "reviews": [],
        "temp_reviews": [],
        "found_review_urls": [],
        "visited_urls": [],
        "relevance_results": [],
        "step_metrics": []
    }
    
    # Create and run graph
    app = create_graph()
    final_state = app.invoke(initial_state)
    
    # Save results
    save_results(final_state, session_id)

if __name__ == "__main__":
    main()
