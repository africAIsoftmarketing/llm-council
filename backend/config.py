"""Configuration for the LLM Council."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Determine the data directory based on environment or OS
def get_data_dir():
    """Get the data directory path - uses AppData on Windows, or DATA_DIR env var."""
    # First check environment variable
    env_data_dir = os.environ.get("DATA_DIR")
    if env_data_dir:
        return env_data_dir
    
    # On Windows, use AppData
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(appdata, "LLM Council", "data")
    
    # On other platforms, use local data folder
    return "data"

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# LM Studio default URL
LMSTUDIO_BASE_URL = "http://localhost:1234/v1"

# Data directory for conversation storage
DATA_DIR = os.path.join(get_data_dir(), "conversations")

# Ensure data directory exists on import
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
