import json
from langsmith import traceable
from langchain_ollama import ChatOllama
from monitor import TrackStep
from helpers import load_prompt
from nodes.state import GraphState
from nodes.models import SearchQuery
from const import NUM_CTX, DEFAULT_LLM_MODEL, DEFAULT_LLM_URL


@traceable(run_type="llm")
def generate_query_node(state: GraphState):
    with TrackStep("Generate Query") as tracker:
        print("--- GENERATE QUERY ---")
        query = state["query"]
        config = state.get("config", {})

        template = load_prompt("01_generate_query.md")
        schema_str = json.dumps(SearchQuery.model_json_schema(), indent=2)
        prompt = template.format(query=query, json_schema=schema_str)

        # Dynamic LLM configuration from state
        llm = ChatOllama(
            model=config.get("llm_model", DEFAULT_LLM_MODEL),
            base_url=config.get("llm_url", DEFAULT_LLM_URL),
            temperature=config.get("llm_temperature", 0),
            format="json",
            num_ctx=NUM_CTX
        )

        structured_llm = llm.with_structured_output(SearchQuery)
        
        try:
            response = structured_llm.invoke(prompt)
            refined_query = response.optimized_query
            # Remove any unwanted quotes if LLM produced them inside the JSON string
            refined_query = refined_query.replace('"', '').replace("'", "")
        except Exception as e:
            print(f"  [REFINEMENT ERROR] LLM failed: {e}. Falling back to original query.")
            refined_query = query

        print(f"Optimized Query: {refined_query}")

    metrics = state.get("step_metrics", [])
    metrics.append(tracker.result)

    return {"query": refined_query, "step_metrics": metrics}
