from typing import TypedDict, List, Optional

class GraphState(TypedDict):
    query: str
    max_reviews: int
    retrieved_content: List[dict]
    relevant_ids: List[str]
    reviews: List[dict]           # Final, verified reviews
    temp_reviews: List[dict]      # Currently being processed (extract -> repair -> verify)
    found_review_urls: List[str]  # Queue for BFS discovery
    visited_urls: List[str]       # History of processed URLs
    relevance_results: List[dict] # Audit log of URLs checked
    step_metrics: List[dict]      # GPU/Time metrics
