import json
from typing import List
from pydantic import BaseModel, Field
from langsmith import traceable
from config import llm, load_prompt
from nodes.state import GraphState
from monitor import TrackStep

class ReviewVerification(BaseModel):
    is_authentic: bool = Field(description="True if the text is a genuine individually-authored customer review")

@traceable(run_type="chain", name="Review Verification Node")
def verify_reviews_node(state: GraphState):
    with TrackStep("Verify Reviews") as tracker:
        print("--- VERIFY REVIEWS AGENT ---")
        query = state["query"]
        reviews = state.get("reviews", [])
        
        if not reviews:
            return {"reviews": []}
            
        template = load_prompt("verify_reviews.txt")
        json_schema = json.dumps(ReviewVerification.model_json_schema(), indent=2)
        
        # Use a reasoning model if needed, but standard should suffice for filtering noise
        structured_llm = llm.with_structured_output(ReviewVerification)
        
        final_reviews = []
        rejected_count = 0
        
        for rev in reviews:
            prompt = template.format(
                query=query,
                review_text=rev["review_text"],
                json_schema=json_schema
            )
            
            try:
                res = structured_llm.invoke(prompt, config={"run_name": "Verify-Review-Authenticity"})
                if res.is_authentic:
                    final_reviews.append(rev)
                else:
                    print(f"  [REJECTED] Non-review text detected: {rev['review_text'][:50]}...")
                    rejected_count += 1
            except Exception as e:
                # On error, keep the review to avoid data loss
                print(f"  [ERROR] Verification failed for snippet, keeping original: {e}")
                final_reviews.append(rev)
                
        print(f"\nFinal Verification results: {len(final_reviews)} authentic, {rejected_count} rejected.")
        
    metrics = state.get("step_metrics", [])
    metrics.append(tracker.result)
    
    return {"reviews": final_reviews, "step_metrics": metrics}
