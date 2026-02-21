import os

# --- LLM & Computational Constants ---
# Global context window size for Ollama models (2048 * 8 = 16k tokens)
NUM_CTX = 2048 * 8

# --- Environment Fallbacks & Defaults ---
# Default Ollama instance URL (fallback if LLM_URL env is missing)
DEFAULT_LLM_URL = "http://127.0.0.1:11434"
# Primary model used for standard extraction and query optimization
DEFAULT_LLM_MODEL = "gemma3:27b"
# Specialized reasoning model used for Verification and Repair (fallback if LLM_REASONING_MODEL env is missing)
DEFAULT_REASONING_MODEL = "gpt-oss:20b"
# Deterministic temperature (0.0) ensures consistent structured outputs
DEFAULT_TEMPERATURE = 0.0
# Target number of reviews to collect before stopping (unless queue is empty)
DEFAULT_MAX_REVIEWS = 50
# Initial amount of search results requested by the 'Retrieval' node
DEFAULT_RETRIEVER_MAX_RESULTS = 50

# --- Caching & Storage ---
# Directory where raw HTML content is persisted to avoid redundant fetching
HTML_CACHE_DIR = "_html_cache"
# JSON file mapping URLs to deterministic filenames in the cache directory
CACHE_INDEX_FILE = os.path.join(HTML_CACHE_DIR, "cache_index.json")

# --- Character Limits for LLM Context Windows ---
# Max number of HTML fragments sent to the 'Repair' node to prevent context overflow
MAX_REPAIR_CONTEXTS = 5
# Max total characters allowed for repair context snippets
MAX_REPAIR_CHARS = 5000
# Max text length passed to the Intelligent Repair 'Check' phase
MAX_SNIPPET_LEN = 15000
# Text sample size used by the 'Extract' node to determine if a page is relevant
MAX_FILTER_SNIPPET = 30000
# Max page content size passed to the actual Extraction LLM
MAX_EXTRACT_SNIPPET = 40000
# Content size used for Hyperlink/Pagination discovery in the 'Extract' node
MAX_DETECT_SNIPPET = 30000

# --- Intelligent Repair Algorithm Constants ---
# Maximum attempts the 'Repair' node makes to find a missing fragment in HTML
MAX_REPAIR_ATTEMPTS = 5
# Number of search matches the repair engine tries to verify per fragment
REPAIR_SEARCH_DEPTH = 3
# Minimal character count to ensure context blocks are large enough to contain the full review (forces parent-element traversal)
REPAIR_CONTEXT_MIN_CHARS = 2500
# Minimal length of a review fragment before we consider it "scrappable" for repair
MIN_REPAIR_LENGTH = 150

# --- Networking & Scraping (Extract Node) ---
# Network timeout in seconds for fetching website content
FETCH_TIMEOUT_SECONDS = 10
# Standard headers to bypass basic anti-bot detection during scraping
USER_AGENT_STRING = "Mozilla/5.0"
