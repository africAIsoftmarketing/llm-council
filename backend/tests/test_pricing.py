"""Unit tests for the dynamic pricing module (backend/pricing.py).

Pure unit tests: OpenRouter is not called. We seed the in-memory pricing cache
directly so the estimates are deterministic. Async helpers are driven via
asyncio.run to avoid a pytest-asyncio dependency.
"""
import time
import asyncio

import pricing


CHEAP = {"prompt": 0.0000001, "completion": 0.0000002}   # gemini-flash-ish
EXPENSIVE = {"prompt": 0.00001, "completion": 0.00003}    # gpt-4o-ish


def _seed_cache(mapping):
    pricing._PRICING_CACHE = dict(mapping)
    pricing._PRICING_CACHE_TS = time.time()  # fresh -> no network refresh


def _run(coro):
    return asyncio.run(coro)


# ============================ Token estimation ============================

def test_total_api_calls_4_models():
    assert pricing.estimate_tokens_for_run(4)["total_api_calls"] == 10  # 2*4 + 2


def test_total_api_calls_2_models():
    assert pricing.estimate_tokens_for_run(2)["total_api_calls"] == 6  # 2*2 + 2


def test_vision_increases_input_tokens():
    no_vision = pricing.estimate_tokens_for_run(3, has_vision=False)
    vision = pricing.estimate_tokens_for_run(3, has_vision=True)
    assert vision["s1_prompt_per_model"] > no_vision["s1_prompt_per_model"]


# ============================ USD → credits ============================

def test_usd_to_credits_basic():
    assert _run(pricing.usd_to_credits(0.01, 500.0)) == 5


def test_usd_to_credits_rounds_up():
    assert _run(pricing.usd_to_credits(0.001, 500.0)) == 1  # ceil(0.5) with min 1


def test_usd_to_credits_minimum_floor():
    assert _run(pricing.usd_to_credits(0.0, 500.0, minimum=2)) == 2


# ============================ Full estimation ============================

def test_estimate_run_credits_positive():
    _seed_cache({
        "a/model": EXPENSIVE,
        "b/model": EXPENSIVE,
        "google/gemini-2.5-flash": CHEAP,
    })
    r = _run(pricing.estimate_run_credits(["a/model", "b/model"], "a/model"))
    assert r["cost"] > 0
    assert r["total_api_calls"] == 6
    assert len(r["per_model_credits"]) >= 1


def test_more_models_cost_more():
    _seed_cache({
        "m1": EXPENSIVE, "m2": EXPENSIVE, "m3": EXPENSIVE,
        "m4": EXPENSIVE, "m5": EXPENSIVE, "m6": EXPENSIVE,
        "google/gemini-2.5-flash": CHEAP,
    })
    small = _run(pricing.estimate_run_credits(["m1", "m2"], "m1"))
    big = _run(pricing.estimate_run_credits(["m1", "m2", "m3", "m4", "m5", "m6"], "m1"))
    assert big["estimated_usd"] > small["estimated_usd"]
    assert big["cost"] >= small["cost"]


def test_expensive_models_cost_more_than_cheap():
    _seed_cache({
        "exp/1": EXPENSIVE, "exp/2": EXPENSIVE,
        "cheap/1": CHEAP, "cheap/2": CHEAP,
        "google/gemini-2.5-flash": CHEAP,
    })
    cheap_run = _run(pricing.estimate_run_credits(["cheap/1", "cheap/2"], "cheap/1"))
    exp_run = _run(pricing.estimate_run_credits(["exp/1", "exp/2"], "exp/1"))
    assert exp_run["estimated_usd"] > cheap_run["estimated_usd"]
    assert exp_run["cost"] > cheap_run["cost"]


def test_fallback_default_pricing_when_cache_empty():
    # Empty cache but fresh timestamp -> get_model_pricing returns the conservative
    # default instead of trying (and failing) a network refresh.
    _seed_cache({})
    r = _run(pricing.estimate_run_credits(["unknown/model", "unknown/model2"], "unknown/model"))
    assert r["cost"] > 0
    assert r["estimated_usd"] > 0
