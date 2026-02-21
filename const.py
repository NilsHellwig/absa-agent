import os

# Computational constants
NUM_CTX = 2048 * 8

# Environment fallbacks (Defaults, preferably defined in .env)
DEFAULT_LLM_URL = "http://127.0.0.1:11434"
DEFAULT_LLM_MODEL = "gemma3:27b"
DEFAULT_REASONING_MODEL = "gpt-oss:20b"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_REVIEWS = 50
DEFAULT_RETRIEVER_MAX_RESULTS = 50

# Caching & Storage
HTML_CACHE_DIR = "_html_cache"
CACHE_INDEX_FILE = os.path.join(HTML_CACHE_DIR, "cache_index.json")

# Token/Character Limits
MAX_REPAIR_CONTEXTS = 5
MAX_REPAIR_CHARS = 5000
MAX_SNIPPET_LEN = 15000
MAX_FILTER_SNIPPET = 30000
MAX_EXTRACT_SNIPPET = 40000
MAX_DETECT_SNIPPET = 30000
