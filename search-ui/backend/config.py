"""Configuration for the search API."""
from pathlib import Path
import os

# Database path - relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "db" / "crawlify.sqlite"

# Embedding model
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"

# API settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Search defaults
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
