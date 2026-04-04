"""
Load balancer for throttling LLM requests to local LM Studio servers.
Prevents laptop freeze by controlling request concurrency and adding delays.
"""

import asyncio
from typing import List, Dict, Any, Optional, Callable, Coroutine
from dataclasses import dataclass


@dataclass
class ThrottleConfig:
    """Configuration for request throttling."""
    max_concurrent: int = 1          # Max simultaneous requests (1 = fully sequential)
    delay_between_requests: float = 0.5   # Seconds to wait between starting each request
    request_timeout: float = 300.0   # Per-request timeout in seconds (longer for local models)
    retry_on_timeout: bool = False   # Whether to retry timed-out requests


def get_throttle_config(advanced_config: Optional[Dict] = None) -> ThrottleConfig:
    """
    Extract throttle configuration from advanced_config.
    Falls back to safe defaults for local mode.
    
    Args:
        advanced_config: Advanced configuration dict from frontend
        
    Returns:
        ThrottleConfig with appropriate settings for the mode
    """
    if not advanced_config:
        # No config = OpenRouter mode, parallelize freely
        return ThrottleConfig(max_concurrent=4, delay_between_requests=0.0, request_timeout=120.0)
    
    mode = advanced_config.get('mode', 'openrouter')
    throttle_cfg = advanced_config.get('throttle', {})
    
    if mode == 'openrouter':
        # OpenRouter is a cloud API — parallelize freely
        return ThrottleConfig(
            max_concurrent=throttle_cfg.get('maxConcurrent', 4),
            delay_between_requests=throttle_cfg.get('delayBetweenRequests', 0.0),
            request_timeout=throttle_cfg.get('requestTimeout', 120.0)
        )
    elif mode in ('lmstudio', 'hybrid'):
        # Local models: conservative defaults to avoid freeze
        return ThrottleConfig(
            max_concurrent=throttle_cfg.get('maxConcurrent', 1),
            delay_between_requests=throttle_cfg.get('delayBetweenRequests', 1.0),
            request_timeout=throttle_cfg.get('requestTimeout', 300.0)
        )
    
    return ThrottleConfig()


async def execute_with_throttle(
    tasks_with_keys: List[tuple],   # List of (key, coroutine)
    config: ThrottleConfig,
    on_result: Optional[Callable] = None  # Optional callback per result (key, result)
) -> Dict[str, Any]:
    """
    Execute a list of coroutines with controlled concurrency.
    
    Uses a semaphore to limit concurrent executions and adds delays
    between starting each task to prevent overwhelming local resources.
    
    Args:
        tasks_with_keys: List of (key, coroutine) tuples
        config: Throttle configuration
        on_result: Optional async callback called as each result arrives
    
    Returns:
        Dict mapping key -> result, preserving insertion order
    """
    results = {}
    semaphore = asyncio.Semaphore(config.max_concurrent)
    
    async def run_one(key: str, coro: Coroutine, delay: float = 0.0):
        """Run a single coroutine with delay and semaphore control."""
        if delay > 0:
            await asyncio.sleep(delay)
        
        async with semaphore:
            try:
                result = await asyncio.wait_for(coro, timeout=config.request_timeout)
            except asyncio.TimeoutError:
                print(f"[LoadBalancer] Timeout after {config.request_timeout}s for: {key}")
                result = None
            except Exception as e:
                print(f"[LoadBalancer] Error for {key}: {e}")
                result = None
            
            results[key] = result
            
            if on_result:
                try:
                    await on_result(key, result)
                except Exception as cb_err:
                    print(f"[LoadBalancer] Callback error for {key}: {cb_err}")
            
            return key, result
    
    # Stagger task starts by delay_between_requests
    task_list = [
        run_one(key, coro, delay=i * config.delay_between_requests)
        for i, (key, coro) in enumerate(tasks_with_keys)
    ]
    
    await asyncio.gather(*task_list)
    return results


def get_throttle_info(advanced_config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Get human-readable throttle info for display in UI.
    
    Args:
        advanced_config: Advanced configuration dict
        
    Returns:
        Dict with mode, max_concurrent, is_sequential, etc.
    """
    config = get_throttle_config(advanced_config)
    mode = advanced_config.get('mode', 'openrouter') if advanced_config else 'openrouter'
    
    return {
        'mode': mode,
        'max_concurrent': config.max_concurrent,
        'delay_between_requests': config.delay_between_requests,
        'request_timeout': config.request_timeout,
        'is_sequential': config.max_concurrent == 1,
        'is_throttled': mode in ('lmstudio', 'hybrid'),
    }
