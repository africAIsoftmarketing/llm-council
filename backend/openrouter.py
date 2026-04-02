"""OpenRouter API client for making LLM requests with dynamic configuration."""

import httpx
from typing import List, Dict, Any, Optional

try:
    from .config_manager import get_api_key, get_lm_studio_url_for_model
    from .config import LMSTUDIO_BASE_URL
except ImportError:
    from config_manager import get_api_key, get_lm_studio_url_for_model
    from config import LMSTUDIO_BASE_URL

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def get_model_source(model: str, advanced_config: Optional[Dict] = None) -> tuple:
    """
    Determine which source to use for a model based on advanced config.
    
    Returns:
        Tuple of (source_type, config_data) where source_type is 'openrouter' or 'lmstudio'
    """
    if not advanced_config:
        return ('openrouter', None)
    
    mode = advanced_config.get('mode', 'openrouter')
    
    if mode == 'openrouter':
        return ('openrouter', advanced_config.get('openrouter', {}))
    
    elif mode == 'lmstudio':
        return ('lmstudio', advanced_config.get('lmstudio', {}))
    
    elif mode == 'hybrid':
        hybrid_config = advanced_config.get('hybrid', {})
        council_sources = hybrid_config.get('councilModelSources', {})
        model_source = council_sources.get(model, 'openrouter')
        
        if model_source == 'lmstudio':
            return ('lmstudio', advanced_config.get('lmstudio', {}))
        else:
            return ('openrouter', advanced_config.get('openrouter', {}))
    
    return ('openrouter', None)


def get_chairman_source(advanced_config: Optional[Dict] = None) -> tuple:
    """
    Determine which source to use for the Chairman model based on advanced config.
    
    Returns:
        Tuple of (source_type, config_data) where source_type is 'openrouter' or 'lmstudio'
    """
    if not advanced_config:
        return ('openrouter', None)
    
    mode = advanced_config.get('mode', 'openrouter')
    
    if mode == 'openrouter':
        return ('openrouter', advanced_config.get('openrouter', {}))
    
    elif mode == 'lmstudio':
        return ('lmstudio', advanced_config.get('lmstudio', {}))
    
    elif mode == 'hybrid':
        hybrid_config = advanced_config.get('hybrid', {})
        chairman_source = hybrid_config.get('chairmanSource', 'openrouter')
        
        if chairman_source == 'lmstudio':
            return ('lmstudio', advanced_config.get('lmstudio', {}))
        else:
            return ('openrouter', advanced_config.get('openrouter', {}))
    
    return ('openrouter', None)


async def query_lm_studio(
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query an LM Studio server directly using OpenAI-compatible API.
    
    Args:
        base_url: LM Studio server URL (e.g., http://localhost:1234/v1)
        model: Model name/identifier to use
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
    
    Returns:
        Response dict with 'content', or None if failed
    """
    # Normalize URL
    base_url = base_url.rstrip('/')
    if not base_url.endswith('/v1'):
        base_url = base_url + '/v1'
    
    api_url = f"{base_url}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
    }
    
    # Extract model name - for LM Studio, we might want to use a simpler model name
    # If the model is like "openai/gpt-4", we just use the last part or let LM Studio use its loaded model
    model_name = model.split('/')[-1] if '/' in model else model
    
    payload = {
        "model": model_name,
        "messages": messages,
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                api_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            message = data['choices'][0]['message']
            
            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details'),
                'source': 'lm_studio',
                'lm_studio_url': base_url
            }
    
    except Exception as e:
        print(f"Error querying LM Studio at {api_url} for model {model}: {e}")
        return None


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    advanced_config: Optional[Dict] = None,
    is_chairman: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API or LM Studio based on configuration.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
        advanced_config: Advanced configuration from frontend (mode, openrouter, lmstudio, hybrid)
        is_chairman: Whether this is a chairman query (affects hybrid mode routing)

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    # Determine which source to use based on advanced config
    if is_chairman:
        source_type, source_config = get_chairman_source(advanced_config)
    else:
        source_type, source_config = get_model_source(model, advanced_config)
    
    # Use LM Studio if configured
    if source_type == 'lmstudio':
        lmstudio_config = source_config or {}
        base_url = lmstudio_config.get('baseUrl', LMSTUDIO_BASE_URL)
        lmstudio_model = lmstudio_config.get('model', 'default')
        print(f"Using LM Studio at {base_url} for model {model} (LM Studio model: {lmstudio_model})")
        return await query_lm_studio(base_url, lmstudio_model, messages, timeout)
    
    # Check if this model has an LM Studio URL configured in settings (legacy support)
    if not advanced_config:
        lm_studio_url = get_lm_studio_url_for_model(model)
        if lm_studio_url:
            print(f"Using LM Studio at {lm_studio_url} for model {model} (from settings)")
            return await query_lm_studio(lm_studio_url, model, messages, timeout)
    
    # Otherwise, use OpenRouter
    # Try to get API key from advanced config first, then fall back to env
    api_key = None
    if source_config and source_config.get('apiKey'):
        api_key = source_config.get('apiKey')
    
    if not api_key:
        api_key = get_api_key()
    
    if not api_key:
        print(f"Error querying model {model}: No API key configured")
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details'),
                'source': 'openrouter'
            }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    advanced_config: Optional[Dict] = None
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
        advanced_config: Advanced configuration from frontend

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages, advanced_config=advanced_config) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
