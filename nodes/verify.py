import json
from typing import List
from langsmith import traceable
from helpers import load_prompt, get_llm
from nodes.state import GraphState
from nodes.models import ReviewVerification
from monitor import TrackStep
from const import DEFAULT_MAX_REVIEWS


@traceable(run_type="chain", name="Review Verification Node")
def verify_reviews_node(state: GraphState):
    with TrackStep("Verify Reviews") as tracker:
        print("--- VERIFY REVIEWS AGENT ---")
        query = state["query"]
        config = state.get("config", {})
        temp_reviews = state.get("temp_reviews", [])
        all_reviews = state.get("reviews", []) or []

        if not temp_reviews:
            return {"temp_reviews": []}

        template = load_prompt("verify_reviews.txt")
        json_schema = json.dumps(
            ReviewVerification.model_json_schema(), indent=2)

        # Dynamic LLM for verification
        llm = get_llm(config)
        structured_llm = llm.with_structured_output(ReviewVerification)

        verified_batch = []
        rejected_count = 0

        for rev in temp_reviews:
            prompt = template.format(
                query=query,
                review_text=rev["review_text"],
                json_schema=json_schema
            )

            try:
                res = structured_llm.invoke(
                    prompt, config={"run_name": "Verify-Review-Authenticity"})
                if res.is_authentic:
                    verified_batch.append(rev)
                else:
                    print(
                        f"  [REJECTED] Non-review text detected: {rev['review_text'][:50]}...")
                    rejected_count += 1
            except Exception as e:
                print(f"  [ERROR] Verification failed, keeping original: {e}")
                verified_batch.append(rev)

        print(
            f"\nFinal Verification results: {len(verified_batch)} authentic, {rejected_count} rejected.")

    # Merge verified batch into global reviews (Respecting limit precisely)
    config = state.get("config", {})
    max_req = state.get("max_reviews", config.get("max_reviews", DEFAULT_MAX_REVIEWS))
    current_count = len(all_reviews)
    remaining_slots = max_req - current_count

    if remaining_slots <= 0:
        actual_to_add = []
    else:
        actual_to_add = verified_batch[:remaining_slots]

    updated_reviews = all_reviews + actual_to_add

    if len(verified_batch) > remaining_slots and remaining_slots > 0:
        print(
            f"  [LIMIT] Capped additions to {remaining_slots} to respect max_reviews.")

    metrics = state.get("step_metrics", [])
    metrics.append(tracker.result)

    return {"reviews": updated_reviews, "temp_reviews": [], "step_metrics": metrics}
