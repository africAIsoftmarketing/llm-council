"""Configuration management for LLM Council."""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx


def get_base_data_dir():
    """Get the base data directory path - uses AppData on Windows."""
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


# Base data directory
BASE_DATA_DIR = get_base_data_dir()

# Configuration file path
CONFIG_FILE = os.path.join(BASE_DATA_DIR, "config.json")

# Default configuration
DEFAULT_CONFIG = {
    "openrouter_api_key": "",
    "council_models": [
        "openai/gpt-4o",
        "google/gemini-2.0-flash-exp",
        "anthropic/claude-3.5-sonnet",
        "x-ai/grok-2"
    ],
    "chairman_model": "google/gemini-2.0-flash-exp",
    # LM Studio URLs for each model (model_id -> base_url mapping)
    # When a model has an LM Studio URL configured, it will be queried directly
    # instead of going through OpenRouter
    "lm_studio_urls": {},
    "advanced_config": {},
    "backend_port": 8001,
    "frontend_port": 5173,
    "auto_credit_reminder": True,
    "credit_reminder_threshold": 5.0,
    "document_settings": {
        "max_file_size_mb": 50,
        "auto_delete_days": 30,
        "supported_extensions": [".pdf", ".docx", ".txt", ".rtf", ".pptx", ".png", ".jpg", ".jpeg", ".md"]
    },
    "storage_location": "data",
    "theme": "light"
}

# Available models from OpenRouter (commonly used)
AVAILABLE_MODELS = [
    # OpenAI
    {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
    {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "OpenAI"},
    {"id": "openai/gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "provider": "OpenAI"},
    {"id": "openai/o1-preview", "name": "O1 Preview", "provider": "OpenAI"},
    {"id": "openai/o1-mini", "name": "O1 Mini", "provider": "OpenAI"},
    {"id": "openai/gpt-5.1", "name": "GPT-5.1", "provider": "OpenAI"},
    
    # Anthropic
    {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic"},
    {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus", "provider": "Anthropic"},
    {"id": "anthropic/claude-3-sonnet", "name": "Claude 3 Sonnet", "provider": "Anthropic"},
    {"id": "anthropic/claude-3-haiku", "name": "Claude 3 Haiku", "provider": "Anthropic"},
    {"id": "anthropic/claude-sonnet-4.5", "name": "Claude Sonnet 4.5", "provider": "Anthropic"},
    
    # Google
    {"id": "google/gemini-2.0-flash-exp", "name": "Gemini 2.0 Flash", "provider": "Google"},
    {"id": "google/gemini-pro", "name": "Gemini Pro", "provider": "Google"},
    {"id": "google/gemini-pro-vision", "name": "Gemini Pro Vision", "provider": "Google"},
    {"id": "google/gemini-1.5-pro", "name": "Gemini 1.5 Pro", "provider": "Google"},
    {"id": "google/gemini-1.5-flash", "name": "Gemini 1.5 Flash", "provider": "Google"},
    {"id": "google/gemini-3-pro-preview", "name": "Gemini 3 Pro Preview", "provider": "Google"},
    {"id": "google/gemini-2.5-flash", "name": "Gemini 2.5 Flash", "provider": "Google"},
    
    # xAI
    {"id": "x-ai/grok-2", "name": "Grok 2", "provider": "xAI"},
    {"id": "x-ai/grok-beta", "name": "Grok Beta", "provider": "xAI"},
    {"id": "x-ai/grok-4", "name": "Grok 4", "provider": "xAI"},
    
    # Meta
    {"id": "meta-llama/llama-3.2-90b-vision-instruct", "name": "Llama 3.2 90B Vision", "provider": "Meta"},
    {"id": "meta-llama/llama-3.1-405b-instruct", "name": "Llama 3.1 405B", "provider": "Meta"},
    {"id": "meta-llama/llama-3.1-70b-instruct", "name": "Llama 3.1 70B", "provider": "Meta"},
    
    # Mistral
    {"id": "mistralai/mistral-large", "name": "Mistral Large", "provider": "Mistral"},
    {"id": "mistralai/mistral-medium", "name": "Mistral Medium", "provider": "Mistral"},
    {"id": "mistralai/mixtral-8x7b-instruct", "name": "Mixtral 8x7B", "provider": "Mistral"},
    
    # Cohere
    {"id": "cohere/command-r-plus", "name": "Command R+", "provider": "Cohere"},
    {"id": "cohere/command-r", "name": "Command R", "provider": "Cohere"},
    
    # DeepSeek
    {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat", "provider": "DeepSeek"},
    {"id": "deepseek/deepseek-coder", "name": "DeepSeek Coder", "provider": "DeepSeek"},
]


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(BASE_DATA_DIR).mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """Load configuration from file, or return defaults."""
    ensure_data_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]):
    """Save configuration to file."""
    ensure_data_dir()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def get_config() -> Dict[str, Any]:
    """Get current configuration (without API key for security)."""
    config = load_config()
    # Mask API key for security
    if config.get("openrouter_api_key"):
        key = config["openrouter_api_key"]
        if len(key) > 10:
            config["openrouter_api_key_masked"] = key[:8] + "..." + key[-4:]
        else:
            config["openrouter_api_key_masked"] = "*" * len(key) if key else ""
        config["has_api_key"] = True
    else:
        config["openrouter_api_key_masked"] = ""
        config["has_api_key"] = False
    
    # Remove actual key from response
    del config["openrouter_api_key"]
    
    # Add real storage paths for frontend display
    config["storage_paths"] = {
        "config_file": CONFIG_FILE,
        "data_dir": BASE_DATA_DIR,
        "conversations_dir": os.path.join(BASE_DATA_DIR, "conversations"),
        "documents_dir": os.path.join(BASE_DATA_DIR, "documents"),
    }
    
    return config


def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update configuration with provided values."""
    config = load_config()
    
    # Apply updates (only for allowed keys)
    allowed_keys = [
        "openrouter_api_key", "council_models", "chairman_model",
        "lm_studio_urls", "advanced_config", "backend_port", "frontend_port", "auto_credit_reminder",
        "credit_reminder_threshold", "document_settings",
        "storage_location", "theme"
    ]
    
    for key in allowed_keys:
        if key in updates:
            config[key] = updates[key]
    
    save_config(config)
    return get_config()


def get_api_key() -> str:
    """Get the OpenRouter API key (for internal use only)."""
    config = load_config()
    return config.get("openrouter_api_key", "")


def get_council_models() -> List[str]:
    """Get the list of council model IDs."""
    config = load_config()
    return config.get("council_models", DEFAULT_CONFIG["council_models"])


def get_chairman_model() -> str:
    """Get the chairman model ID."""
    config = load_config()
    return config.get("chairman_model", DEFAULT_CONFIG["chairman_model"])


def get_lm_studio_urls() -> Dict[str, str]:
    """Get the LM Studio URLs mapping (model_id -> base_url)."""
    config = load_config()
    return config.get("lm_studio_urls", {})


def get_lm_studio_url_for_model(model_id: str) -> Optional[str]:
    """Get the LM Studio URL for a specific model, if configured."""
    urls = get_lm_studio_urls()
    return urls.get(model_id)


def get_advanced_config() -> Dict[str, Any]:
    """Get the advanced config from config.json."""
    config = load_config()
    return config.get("advanced_config", {})


def save_advanced_config(advanced_config: Dict[str, Any]) -> Dict[str, Any]:
    """Save advanced config to config.json."""
    config = load_config()
    config["advanced_config"] = advanced_config
    save_config(config)
    return advanced_config


async def test_lm_studio_connection(base_url: str, model_name: str = None) -> Dict[str, Any]:
    """
    Test connection to an LM Studio server.
    
    Args:
        base_url: The base URL of the LM Studio server (e.g., http://localhost:1234/v1)
        model_name: Optional model name to test with
    
    Returns:
        Dict with test results
    """
    if not base_url:
        return {"success": False, "error": "URL is empty"}
    
    # Normalize URL - ensure it ends with /v1 if not present
    base_url = base_url.rstrip('/')
    if not base_url.endswith('/v1'):
        base_url = base_url + '/v1'
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # First try to get models list
            models_url = f"{base_url}/models"
            response = await client.get(models_url)
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                model_ids = [m.get("id", "unknown") for m in models]
                
                return {
                    "success": True,
                    "url": base_url,
                    "models_available": model_ids,
                    "message": f"Connected successfully. Found {len(model_ids)} model(s)."
                }
            else:
                return {
                    "success": False,
                    "error": f"Server returned status {response.status_code}",
                    "url": base_url
                }
                
    except httpx.ConnectError:
        return {"success": False, "error": "Could not connect to server. Is LM Studio running?", "url": base_url}
    except httpx.TimeoutException:
        return {"success": False, "error": "Connection timed out", "url": base_url}
    except Exception as e:
        return {"success": False, "error": str(e), "url": base_url}


async def validate_api_key(api_key: str) -> Dict[str, Any]:
    """Validate an OpenRouter API key by making a test request."""
    if not api_key:
        return {"valid": False, "error": "API key is empty"}
    
    if not api_key.startswith("sk-or-"):
        return {"valid": False, "error": "Invalid API key format. OpenRouter keys start with 'sk-or-'"}
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Try to get credits/balance info
            response = await client.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "valid": True,
                    "data": data.get("data", {})
                }
            elif response.status_code == 401:
                return {"valid": False, "error": "Invalid or expired API key"}
            else:
                return {"valid": False, "error": f"API error: {response.status_code}"}
    except httpx.TimeoutException:
        return {"valid": False, "error": "Connection timeout - please check your internet connection"}
    except Exception as e:
        return {"valid": False, "error": str(e)}


def get_available_models() -> List[Dict[str, str]]:
    """Get list of available models."""
    return AVAILABLE_MODELS


def add_custom_model(model_id: str, model_name: str, provider: str) -> Dict[str, str]:
    """Add a custom model to the available models list."""
    global AVAILABLE_MODELS
    new_model = {"id": model_id, "name": model_name, "provider": provider}
    
    # Check if already exists
    for model in AVAILABLE_MODELS:
        if model["id"] == model_id:
            return model
    
    AVAILABLE_MODELS.append(new_model)
    return new_model


def apply_config_to_env():
    """Apply configuration to environment variables and update config.py."""
    config = load_config()
    
    # Update environment variable for the current process
    if config.get("openrouter_api_key"):
        os.environ["OPENROUTER_API_KEY"] = config["openrouter_api_key"]
