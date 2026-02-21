from typing import TypedDict, List, Optional, Any


class GraphState(TypedDict):
    query: str
    max_reviews: int
    retrieved_content: List[dict]
    relevant_ids: List[str]
    reviews: List[dict]           # Final, verified reviews
    # Currently being processed (extract -> repair -> verify)
    temp_reviews: List[dict]
    found_review_urls: List[str]  # Queue for BFS discovery
    visited_urls: List[str]       # History of processed URLs
    relevance_results: List[dict]  # Audit log of URLs checked
    step_metrics: List[dict]      # GPU/Time metrics
    config: dict                  # Global settings from CLI/Env
