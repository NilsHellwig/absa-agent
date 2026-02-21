import json
import os
import re
from typing import List, Optional
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from langsmith import traceable
from helpers import load_prompt, get_llm, get_cache_path
from monitor import TrackStep
from nodes.state import GraphState
from const import MAX_REPAIR_CONTEXTS, MAX_REPAIR_CHARS, MAX_SNIPPET_LEN


class RepairCheck(BaseModel):
    is_incomplete: bool = Field(
        description="True if the review is truncated/a snippet and needs reconstruction from HTML source, False if it is complete. Possible values: [true, false]")


class RepairSearch(BaseModel):
    search_term: str = Field(
        description="A unique and representative sequence of characters (a substring) from the review snippet to locate its position in the HTML source code.")


class RepairResult(BaseModel):
    fixed_text: str = Field(
        description="The reconstructed original full text (verbatim) from the webpage source.")
    is_complete: bool = Field(
        description="True if the text is successfully reconstructed and complete, False if it remain truncated. Possible values: [true, false]")


def get_contexts_for_term(soup: BeautifulSoup, term: str, max_results: int = MAX_REPAIR_CONTEXTS, max_chars: int = MAX_REPAIR_CHARS) -> List[str]:
    """Finds up to max_results contexts around a specific unique term in the soup."""
    if not term:
        return []

    # Search for all text nodes containing this specific term
    matches = soup.find_all(string=re.compile(re.escape(term), re.IGNORECASE))

    if not matches:
        return []

    contexts = []
    for match in matches[:max_results]:
        parent = match.parent

        # Go up a few levels to get the whole review block context
        depth = 0
        while parent and depth < 3 and len(parent.get_text()) < 2500:
            parent = parent.parent
            depth += 1

        if parent:
            contexts.append(parent.get_text(
                separator="\n", strip=True)[:max_chars])

    return contexts


@traceable(run_type="chain", name="Intelligent Repair Node")
def repair_reviews_node(state: GraphState):
    with TrackStep("Repair") as tracker:
        print("--- INTELLIGENT REPAIR AGENT (5-Attempt Loop) ---")
        query = state["query"]
        config = state.get("config", {})
        temp_reviews = state.get("temp_reviews", [])

        if not temp_reviews:
            return {"temp_reviews": []}

        check_template = load_prompt("review_completeness.txt")
        search_template = load_prompt("repair_search_query.txt")
        repair_template = load_prompt("repair_review.txt")

        # Dynamic LLMs
        llm = get_llm(config)
        llm_reasoning = get_llm(config, use_reasoning=True)

        check_llm = llm_reasoning.with_structured_output(RepairCheck)
        search_llm = llm.with_structured_output(RepairSearch)
        repair_llm = llm.with_structured_output(RepairResult)

        repaired_batch = []
        repaired_count = 0
        discarded_count = 0

        for rev in temp_reviews:
            url = rev.get("website_url")
            cache_path = get_cache_path(url)

            if not os.path.exists(cache_path):
                repaired_batch.append(rev)
                continue

            with open(cache_path, "r", encoding="utf-8") as f:
                html_content = f.read()
                soup = BeautifulSoup(html_content, "html.parser")

                # Clean soup once per URL in repair
                for element in soup(["script", "style", "header", "footer", "nav"]):
                    element.decompose()

            # 1. CHECK: Is it incomplete?
            page_snippet = soup.get_text(separator="\n", strip=True)[
                :MAX_SNIPPET_LEN]
            check_prompt = check_template.format(
                query=query,
                page_text=page_snippet,
                review_text=rev["review_text"],
                json_schema=json.dumps(
                    RepairCheck.model_json_schema(), indent=2)
            )

            try:
                check_res = check_llm.invoke(
                    check_prompt, config={"run_name": "Check-Review-Completeness"})
                if not check_res.is_incomplete:
                    repaired_batch.append(rev)
                    continue
            except Exception:
                if "..." not in rev["review_text"] and len(rev["review_text"]) > 150:
                    repaired_batch.append(rev)
                    continue

            # 2. LOOP: Intelligent Search & Repair (up to 5 attempts)
            print(f"  Repairing snippet: {rev['review_text'][:30]}...")
            current_text = rev["review_text"]
            failed_terms = []
            success = False

            for attempt in range(1, 6):
                print(f"    - Attempt {attempt}/5...")

                history_str = ", ".join(
                    [f'"{t}"' for t in failed_terms]) if failed_terms else "None"
                search_prompt = search_template.format(
                    review_text=current_text,
                    history=history_str,
                    json_schema=json.dumps(
                        RepairSearch.model_json_schema(), indent=2)
                )
                search_res = search_llm.invoke(
                    search_prompt, config={"run_name": f"Search-Attempt-{attempt}"})
                term = search_res.search_term

                contexts = get_contexts_for_term(soup, term)

                if not contexts:
                    print(f"      [Search Term '{term}' not found in HTML]")
                    failed_terms.append(term)
                    continue

                # Pass all identified contexts to the LLM (Up to 5)
                context_str = "\n---\n".join(
                    [f"Source Segment {i+1}:\n{ctx}" for i, ctx in enumerate(contexts)])

                repair_prompt = repair_template.format(
                    query=query,
                    page_text=context_str,
                    snippets=f"- {current_text}",
                    json_schema=json.dumps(
                        RepairResult.model_json_schema(), indent=2)
                )

                try:
                    repair_res = repair_llm.invoke(
                        repair_prompt, config={"run_name": f"Repair-Attempt-{attempt}"})
                    current_text = repair_res.fixed_text

                    if repair_res.is_complete:
                        rev["review_text"] = current_text
                        repaired_batch.append(rev)
                        repaired_count += 1
                        success = True
                        print(
                            f"      [SUCCESS] Review repaired on attempt {attempt}.")
                        break
                    else:
                        print(
                            f"      [CONTINUE] Text still incomplete after attempt {attempt}.")
                except Exception as e:
                    print(
                        f"      [ERROR] Repair failed on attempt {attempt}: {e}")

            if not success:
                discarded_count += 1
                print(f"    - [DISCARDED] Could not repair after 5 attempts.")

        print(
            f"\nFinal Repair results: {repaired_count} repaired, {discarded_count} discarded, {len(repaired_batch)} kept.")

    metrics = state.get("step_metrics", [])
    metrics.append(tracker.result)

    return {"temp_reviews": repaired_batch, "step_metrics": metrics}
