import os
import json
import argparse
import uuid
from typing import List, Optional
from langgraph.graph import StateGraph, END
from nodes.state import GraphState
from nodes.generate_query import generate_query_node
from nodes.retrieval import retrieval_node
from nodes.extract import extract_and_detect_node
from nodes.repair import repair_reviews_node
from nodes.verify import verify_reviews_node
from helpers import save_json
from const import (DEFAULT_LLM_URL, DEFAULT_LLM_MODEL, DEFAULT_REASONING_MODEL, 
                   DEFAULT_TEMPERATURE, DEFAULT_MAX_REVIEWS, DEFAULT_RETRIEVER_MAX_RESULTS)
from dotenv import load_dotenv

# Load explicitly
load_dotenv()

# Standard Configurations with Environment Variable Integration
# This dictionary serves as the central configuration for all agents
DEFAULT_CONFIG = {
    "llm_model": os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
    "llm_reasoning_model": os.getenv("LLM_REASONING_MODEL", DEFAULT_REASONING_MODEL),
    "llm_url": os.getenv("LLM_URL", DEFAULT_LLM_URL),
    "llm_temperature": float(os.getenv("LLM_TEMPERATURE", DEFAULT_TEMPERATURE)),
    "retriever_max_results": int(os.getenv("RETRIEVER_MAX_RESULTS", DEFAULT_RETRIEVER_MAX_RESULTS)),
    "max_reviews": int(os.getenv("MAX_REVIEWS", DEFAULT_MAX_REVIEWS)),
    "skip_reformulation": False,
    "initial_urls": [],
    "disable_discovery": False
}


def create_graph(config_dict: dict):
    """Constructs the agentic LangGraph workflow based on the provided configuration."""
    workflow = StateGraph(GraphState)

    # Adding nodes
    workflow.add_node("generate_query", generate_query_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("extract", extract_and_detect_node)
    workflow.add_node("repair", repair_reviews_node)
    workflow.add_node("verify", verify_reviews_node)

    # Building Flow using config-driven entry points
    if config_dict.get("initial_urls"):
        # If seed URLs are provided, we start directly at the extraction/discovery phase
        workflow.set_entry_point("extract")
    elif config_dict.get("skip_reformulation"):
        # If reformulation is disabled, we skip the query optimization agent
        workflow.set_entry_point("retrieval")
    else:
        # Standard flow: Reformulate -> Search -> Extract
        workflow.set_entry_point("generate_query")
        workflow.add_edge("generate_query", "retrieval")

    # Connect retrieval result to the loop
    workflow.add_edge("retrieval", "extract")

    def check_extraction_results(state: GraphState):
        """Routing logic: If no reviews extracted, skip repair and go to verification side-effects."""
        if not state.get("temp_reviews"):
            return "skip_to_router"
        return "process_reviews"

    workflow.add_conditional_edges(
        "extract",
        check_extraction_results,
        {
            "process_reviews": "repair",
            "skip_to_router": "verify"
        }
    )

    workflow.add_edge("repair", "verify")

    def router(state: GraphState):
        """BFS termination logic: Stop if limit reached or discovery queue is empty."""
        current_count = len(state.get("reviews", []))
        max_req = state.get("max_reviews", state["config"].get("max_reviews", DEFAULT_MAX_REVIEWS))

        if current_count >= max_req:
            print(
                f"--- LIMIT REACHED ({current_count}/{max_req}). STOPPING. ---")
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
    """Saves the final results using the helper utility."""
    reviews = state.get("reviews", [])
    relevance_results = state.get("relevance_results", [])
    step_metrics = state.get("step_metrics", [])

    folder_path = f"results/results_{session_id}"

    # Structure of the output matches the previous version but uses save_json helper
    save_json({
        "reviews": reviews,
        "metrics": step_metrics,
        "summary": {
            "total_reviews": len(reviews),
            "total_duration": sum(m["duration"] for m in step_metrics) if step_metrics else 0,
            "total_avg_wattage": sum(m["avg_gpu_power_watts"] for m in step_metrics) / len(step_metrics) if step_metrics else 0
        }
    }, folder_path, "reviews.json")

    save_json(relevance_results, folder_path, "relevance_url.json")
    print(f"\n--- SUCCESS: Results saved to {folder_path} ---")


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous ABSA Scraper Agent")
    parser.add_argument(
        "topic", help="The research topic or entity to scrape reviews for")
    parser.add_argument(
        "--id", help="Session ID for result folder naming", default=uuid.uuid4().hex[:8])
    parser.add_argument("--max_reviews", type=int, default=DEFAULT_CONFIG["max_reviews"],
                        help="Target number of reviews to collect")
    parser.add_argument(
        "--urls", nargs="+", help="Seed URLs to start with (bypasses search engine)", default=[])
    parser.add_argument("--skip_refinement", action="store_true",
                        help="Skip LLM query reformulation step")
    parser.add_argument("--disable_discovery", action="store_true",
                        help="Disable hyperlink/pagination discovery")

    # Advanced LLM overrides
    parser.add_argument(
        "--model", help="Override default LLM model (e.g. llama3)")
    parser.add_argument("--temp", type=float,
                        help="Override LLM temperature (0.0 to 1.0)")

    args = parser.parse_args()

    # Consolidate configuration
    config = DEFAULT_CONFIG.copy()
    if args.urls:
        config["initial_urls"] = args.urls
    if args.skip_refinement:
        config["skip_reformulation"] = True
    if args.disable_discovery:
        config["disable_discovery"] = True
    if args.model:
        config["llm_model"] = args.model
    if args.temp is not None:
        config["llm_temperature"] = args.temp

    # Compile the graph with current config
    app = create_graph(config)

    # Initialize state with consolidated settings
    initial_state = {
        "query": args.topic,
        "max_reviews": args.max_reviews,
        "retrieved_content": [],
        "relevant_ids": [],
        "reviews": [],
        "temp_reviews": [],
        "seed_urls": config["initial_urls"],         # Track origins
        "found_review_urls": config["initial_urls"],  # Seed queue
        "visited_urls": [],
        "relevance_results": [],
        "step_metrics": [],
        "config": config  # Pass config to nodes via state
    }

    # Execute workflow
    print(f"--- STARTING RUN ({args.id}) ---")
    final_state = app.invoke(initial_state)

    # Persist data
    save_results(final_state, args.id)


if __name__ == "__main__":
    main()
