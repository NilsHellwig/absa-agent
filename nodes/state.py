from typing import TypedDict, List, Optional

class GraphState(TypedDict):
    query: str
    max_reviews: int           # Max reviews to extract in total
    retrieved_content: List[dict]
    relevant_ids: List[str]
    reviews: List[dict]
    found_review_urls: List[str] # New: URLs found for reviews
    visited_urls: List[str]      # New: Keep track to avoid loops
    relevance_results: List[dict] # New: [{url, is_relevant}]
    step_metrics: List[dict]      # New: [{step, duration, gpu_wattage_avg}]
    relevance_results: List[dict] # New: URLs checked and their relevance
    step_logs: List[dict]         # New: Timing and GPU logs for each step
