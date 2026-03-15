"""OpenRouter API client for making LLM requests with dynamic configuration."""

import httpx
from typing import List, Dict, Any, Optional

try:
    from .config_manager import get_api_key, get_lm_studio_url_for_model
except ImportError:
    from config_manager import get_api_key, get_lm_studio_url_for_model

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


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
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API or LM Studio if configured.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    # Check if this model has an LM Studio URL configured
    lm_studio_url = get_lm_studio_url_for_model(model)
    
    if lm_studio_url:
        # Query LM Studio directly
        print(f"Using LM Studio at {lm_studio_url} for model {model}")
        return await query_lm_studio(lm_studio_url, model, messages, timeout)
    
    # Otherwise, use OpenRouter
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
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
