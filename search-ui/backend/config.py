"""Configuration for the search API."""
from pathlib import Path
import os

# Database path - env override for Docker, else relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = Path(os.getenv("DB_PATH", str(PROJECT_ROOT / "data" / "db" / "crawlify.sqlite")))

# API settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Search defaults
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
