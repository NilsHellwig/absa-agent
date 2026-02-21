from helpers import load_prompt, get_cache_path
import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

# Load explicitly
load_dotenv()

# Standard environment variables with sensible defaults
LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:27b")
LLM_REASONING_MODEL = os.getenv("LLM_REASONING_MODEL", "gpt-oss:20b")
LLM_URL = os.getenv("LLM_URL", "http://132.199.137.208:11434")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.0))
RETRIEVER_MAX_RESULTS = int(os.getenv("RETRIEVER_MAX_RESULTS", 5))

# Global Search Wrapper
search_wrapper = DuckDuckGoSearchAPIWrapper()

# LLM Instances (Standard and Reasoning)
llm = ChatOllama(
    model=LLM_MODEL,
    base_url=LLM_URL,
    temperature=LLM_TEMPERATURE,
    format="json",
    num_ctx=2048 * 8
)

llm_reasoning = ChatOllama(
    model=LLM_REASONING_MODEL,
    base_url=LLM_URL,
    temperature=LLM_TEMPERATURE,
    format="json",
    num_ctx=2048 * 8
)

# Constants & Helpers
HTML_CACHE_DIR = "_html_cache"
CACHE_INDEX_FILE = os.path.join(HTML_CACHE_DIR, "cache_index.json")

# Re-exporting from helpers
