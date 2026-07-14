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
        if model_cfg.get('source') == 'lmstudio':
            url = model_cfg.get('endpointUrl') or DEFAULT_LMSTUDIO_URL
            name = model_cfg.get('localModelName') or model.split('/')[-1]
            return ('lmstudio', url, name)
        return ('openrouter', openrouter_config, None)
    
    elif mode == 'lmstudio':
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
    timeout: float = 300.0
) -> Optional[Dict[str, Any]]:
    """
    Query an LM Studio server directly using OpenAI-compatible API.
    
    Note: tools parameter is intentionally not supported — LM Studio
    local models don't expose a web_search capability.
    """
    base_url = base_url.rstrip('/')
    
    if base_url.endswith('/v1'):
        api_url = f"{base_url}/chat/completions"
    elif '/v1' in base_url:
        api_url = f"{base_url}/chat/completions"
    else:
        api_url = f"{base_url}/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
    }
    
    model_name = model.split('/')[-1] if '/' in model else model
    if not model_name or model_name in ('default', 'local'):
        model_name = ''
    
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
    }
    
    print(f"[LM Studio] POST {api_url} | model='{model_name}' | messages={len(messages)} | timeout={timeout}s")
    
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
            
            reasoning = message.get('reasoning_content') or message.get('reasoning_details')
            
            content = message.get('content', '')
            print(f"[LM Studio] Success: {api_url} | response_length={len(content)} chars")
            
            return {
                'content': content,
                'reasoning_details': reasoning,
                'source': 'lm_studio',
                'lm_studio_url': base_url,
                'model_used': data.get('model', model_name),
            }
    
    except httpx.TimeoutException:
        print(f"[LM Studio] Timeout after {timeout}s for {api_url}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"[LM Studio] HTTP error {e.response.status_code} for {api_url}: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"[LM Studio] Error querying {api_url} for model {model}: {e}")
        return None


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    advanced_config: Optional[Dict] = None,
    is_chairman: bool = False,
    tools: Optional[List[Dict]] = None
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API or LM Studio based on configuration.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
        advanced_config: Advanced configuration from frontend
        is_chairman: Whether this is a chairman query
        tools: Optional list of tool descriptors (e.g. web_search).
               Passed to OpenRouter only — ignored for LM Studio.

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    if is_chairman:
        source_type, source_data, lmstudio_model_name = get_chairman_source(advanced_config)
    else:
        source_type, source_data, lmstudio_model_name = get_model_source(model, advanced_config)
    
    # LM Studio — tools not supported, silently ignored
    if source_type == 'lmstudio':
        base_url = source_data if isinstance(source_data, str) else DEFAULT_LMSTUDIO_URL
        actual_model = lmstudio_model_name or 'default'
        print(f"Using LM Studio at {base_url} for model '{model}' -> LM Studio model: '{actual_model}'")
        return await query_lm_studio(base_url, actual_model, messages, timeout)
    
    if not advanced_config:
        lm_studio_url = get_lm_studio_url_for_model(model)
        if lm_studio_url:
            print(f"Using LM Studio at {lm_studio_url} for model {model} (from legacy settings)")
            return await query_lm_studio(lm_studio_url, model, messages, timeout)
    
    # OpenRouter
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

    # Inject tools only for OpenRouter (web_search, etc.)
    if tools:
        payload["tools"] = tools

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
    advanced_config: Optional[Dict] = None,
    tools: Optional[List[Dict]] = None
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models with throttle-aware concurrency control.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
        advanced_config: Advanced configuration from frontend
        tools: Optional list of tool descriptors forwarded to each query_model call.

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    throttle = get_throttle_config(advanced_config)
    
    mode = advanced_config.get('mode', 'openrouter') if advanced_config else 'openrouter'
    if mode in ('lmstudio', 'hybrid'):
        print(f"[LoadBalancer] Using throttled execution: max_concurrent={throttle.max_concurrent}, "
              f"delay={throttle.delay_between_requests}s, timeout={throttle.request_timeout}s")
    
    request_timeout = throttle.request_timeout
    
    async def make_query(model_id: str):
        return await query_model(
            model_id,
            messages,
            timeout=request_timeout,
            advanced_config=advanced_config,
            tools=tools
        )
    
    tasks = [(model, make_query(model)) for model in models]
    
    results = await execute_with_throttle(tasks, throttle)
    return results
