import os
import hashlib
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

# Load environment variables
load_dotenv()

# Configuration
LLM_MODEL = "gemma3:27b"
LLM_REASONING_MODEL = "gpt-oss:20b"
LLM_URL = "http://132.199.137.208:11434"
LLM_TEMPERATURE = 0
RETRIEVER_MAX_RESULTS = 100
HTML_CACHE_DIR = "_html_cache"
CACHE_INDEX_FILE = os.path.join(HTML_CACHE_DIR, "cache_index.json")

# LLM Configuration
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

search_wrapper = DuckDuckGoSearchAPIWrapper()

def load_prompt(filename):
    path = f"prompt_template/{filename}"
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return ""

def get_cache_path(url: str):
    """Generate a deterministic filename for a URL caching."""
    if not os.path.exists(HTML_CACHE_DIR):
        os.makedirs(HTML_CACHE_DIR)
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(HTML_CACHE_DIR, f"cache_{url_hash}.html")
