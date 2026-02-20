import json
from pydantic import BaseModel, Field
from langsmith import traceable
from config import llm, load_prompt
from nodes.state import GraphState

from monitor import TrackStep

class SearchQuery(BaseModel):
    optimized_query: str = Field(description="The optimized search query for the search engine")

@traceable(run_type="llm")
def generate_query_node(state: GraphState):
    with TrackStep("Generate Query") as tracker:
        print("--- GENERATE QUERY ---")
        query = state["query"]
        
        template = load_prompt("generate_query.txt")
        schema_str = json.dumps(SearchQuery.model_json_schema(), indent=2)
        prompt = template.format(query=query, json_schema=schema_str)
        
        structured_llm = llm.with_structured_output(SearchQuery)
        response = structured_llm.invoke(prompt)
        
        refined_query = response.optimized_query
        
        # Remove any unwanted quotes if LLM produced them inside the JSON string
        refined_query = refined_query.replace('"', '').replace("'", "")
        
        print(f"Optimized Query: {refined_query}")
        
    metrics = state.get("step_metrics", [])
    metrics.append(tracker.result)
    
    return {"query": refined_query, "step_metrics": metrics}
