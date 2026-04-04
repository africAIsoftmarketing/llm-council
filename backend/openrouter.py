"""OpenRouter API client for making LLM requests with dynamic configuration."""

import httpx
from typing import List, Dict, Any, Optional

try:
    from .config_manager import get_api_key, get_lm_studio_url_for_model
    from .config import LMSTUDIO_BASE_URL
    from .load_balancer import get_throttle_config, execute_with_throttle
except ImportError:
    from config_manager import get_api_key, get_lm_studio_url_for_model
    from config import LMSTUDIO_BASE_URL
    from load_balancer import get_throttle_config, execute_with_throttle

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_LMSTUDIO_URL = "http://localhost:1234/v1"


def get_model_source(model: str, advanced_config: Optional[Dict] = None) -> tuple:
    """
    Determine which source to use for a model based on advanced config.
    
    New structure:
    {
        "mode": "openrouter" | "lmstudio" | "hybrid",
        "openrouter": { "apiKey": "" },
        "models": {
            "openai/gpt-4o": {
                "source": "openrouter" | "lmstudio",
                "endpointUrl": "http://localhost:1234/v1",
                "localModelName": "mistral-7b"
            }
        },
        "chairman": { ... }
    }
    
    Returns:
        Tuple of (source_type, endpoint_url, local_model_name)
        where source_type is 'openrouter' or 'lmstudio'
    """
    if not advanced_config:
        # Fallback legacy: check lm_studio_urls in config.json
        lm_studio_url = get_lm_studio_url_for_model(model)
        if lm_studio_url:
            return ('lmstudio', lm_studio_url, model.split('/')[-1])
        return ('openrouter', None, None)
    
    mode = advanced_config.get('mode', 'openrouter')
    models_config = advanced_config.get('models', {})
    model_cfg = models_config.get(model, {})
    openrouter_config = advanced_config.get('openrouter', {})
    
    if mode == 'openrouter':
        # All models go to OpenRouter unless model has source='lmstudio' explicitly
        if model_cfg.get('source') == 'lmstudio':
            url = model_cfg.get('endpointUrl') or DEFAULT_LMSTUDIO_URL
            name = model_cfg.get('localModelName') or model.split('/')[-1]
            return ('lmstudio', url, name)
        return ('openrouter', openrouter_config, None)
    
    elif mode == 'lmstudio':
        # All models go to LM Studio with their own URL
        url = model_cfg.get('endpointUrl') or DEFAULT_LMSTUDIO_URL
        name = model_cfg.get('localModelName') or model.split('/')[-1]
        return ('lmstudio', url, name)
    
    elif mode == 'hybrid':
        source = model_cfg.get('source', 'openrouter')
        if source == 'lmstudio':
            url = model_cfg.get('endpointUrl') or DEFAULT_LMSTUDIO_URL
            name = model_cfg.get('localModelName') or model.split('/')[-1]
            return ('lmstudio', url, name)
        return ('openrouter', openrouter_config, None)
    
    return ('openrouter', None, None)


def get_chairman_source(advanced_config: Optional[Dict] = None) -> tuple:
    """
    Determine which source to use for the Chairman model based on advanced config.
    
    Returns:
        Tuple of (source_type, endpoint_url, local_model_name)
        where source_type is 'openrouter' or 'lmstudio'
    """
    if not advanced_config:
        return ('openrouter', None, None)
    
    chairman_cfg = advanced_config.get('chairman', {})
    openrouter_config = advanced_config.get('openrouter', {})
    source = chairman_cfg.get('source', 'openrouter')
    
    # In lmstudio mode, chairman always uses lmstudio
    mode = advanced_config.get('mode', 'openrouter')
    if mode == 'lmstudio':
        url = chairman_cfg.get('endpointUrl') or DEFAULT_LMSTUDIO_URL
        name = chairman_cfg.get('localModelName') or ''
        return ('lmstudio', url, name)
    
    if source == 'lmstudio':
        url = chairman_cfg.get('endpointUrl') or DEFAULT_LMSTUDIO_URL
        name = chairman_cfg.get('localModelName') or ''
        return ('lmstudio', url, name)
    
    return ('openrouter', openrouter_config, None)


async def query_lm_studio(
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 300.0    # 5 minutes for local models (they can be slow)
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
    
    # Use model name as-is, or extract from path if it looks like provider/model
    model_name = model.split('/')[-1] if '/' in model else model
    # If model is empty or 'default', let LM Studio auto-select
    if not model_name or model_name == 'default':
        model_name = ''
    
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
        advanced_config: Advanced configuration from frontend
        is_chairman: Whether this is a chairman query

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    # Determine which source to use based on advanced config
    if is_chairman:
        source_type, source_data, lmstudio_model_name = get_chairman_source(advanced_config)
    else:
        source_type, source_data, lmstudio_model_name = get_model_source(model, advanced_config)
    
    # Use LM Studio if configured
    if source_type == 'lmstudio':
        base_url = source_data if isinstance(source_data, str) else DEFAULT_LMSTUDIO_URL
        actual_model = lmstudio_model_name or 'default'
        print(f"Using LM Studio at {base_url} for model '{model}' -> LM Studio model: '{actual_model}'")
        return await query_lm_studio(base_url, actual_model, messages, timeout)
    
    # Check if this model has an LM Studio URL configured in settings (legacy support)
    if not advanced_config:
        lm_studio_url = get_lm_studio_url_for_model(model)
        if lm_studio_url:
            print(f"Using LM Studio at {lm_studio_url} for model {model} (from legacy settings)")
            return await query_lm_studio(lm_studio_url, model, messages, timeout)
    
    # Otherwise, use OpenRouter
    # Try to get API key from advanced config first, then fall back to env
    api_key = None
    if isinstance(source_data, dict) and source_data.get('apiKey'):
        api_key = source_data.get('apiKey')
    
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
    Query multiple models with throttle-aware concurrency control.
    
    Uses sequential execution with delays for local LM Studio models
    to prevent laptop freeze. Uses parallel execution for OpenRouter
    cloud models.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
        advanced_config: Advanced configuration from frontend

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    # Get throttle configuration based on mode
    throttle = get_throttle_config(advanced_config)
    
    mode = advanced_config.get('mode', 'openrouter') if advanced_config else 'openrouter'
    if mode in ('lmstudio', 'hybrid'):
        print(f"[LoadBalancer] Using throttled execution: max_concurrent={throttle.max_concurrent}, "
              f"delay={throttle.delay_between_requests}s, timeout={throttle.request_timeout}s")
    
    # Build (model_id, coroutine) pairs
    # Note: We create the coroutines here, they will be awaited by execute_with_throttle
    tasks = [
        (model, query_model(model, messages, advanced_config=advanced_config))
        for model in models
    ]
    
    # Execute with throttling
    results = await execute_with_throttle(tasks, throttle)
    return results
