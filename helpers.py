import os
import hashlib
import json
from langchain_ollama import ChatOllama
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from const import HTML_CACHE_DIR, NUM_CTX, DEFAULT_LLM_URL

# Search Instance
search_wrapper = DuckDuckGoSearchAPIWrapper()


def get_llm(config: dict, use_reasoning: bool = False):
    """Factory to create LLM instances dynamically from the state config."""
    model_key = "llm_reasoning_model" if use_reasoning else "llm_model"
    # Provide defaults in case config is partial
    model_name = config.get(
        model_key, "gpt-oss:20b" if use_reasoning else "gemma3:27b")
    base_url = config.get("llm_url", DEFAULT_LLM_URL)
    temp = config.get("llm_temperature", 0.0)

    return ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=temp,
        format="json",
        num_ctx=NUM_CTX
    )


def load_prompt(filename):
    """Loads text from a template file in the prompt_template folder."""
    path = f"prompt_template/{filename}"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def get_cache_path(url: str):
    """Generates a deterministic filename for a URL caching."""
    if not os.path.exists(HTML_CACHE_DIR):
        os.makedirs(HTML_CACHE_DIR)
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(HTML_CACHE_DIR, f"cache_{url_hash}.html")


def save_json(data, folder_path, filename):
    """Utility to save JSON data to a specific folder."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path, exist_ok=True)
    full_path = os.path.join(folder_path, filename)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
