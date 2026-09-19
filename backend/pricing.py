"""Dynamic credit pricing based on OpenRouter model costs and council composition.

Fetches per-model pricing from the OpenRouter public catalogue, estimates the
token footprint of a 3-stage council run, converts the estimated USD cost into
credits using a configurable rate, and returns the credit cost to display in the
pre-flight modal.
"""

import time
import math
from typing import Dict, List, Tuple

import httpx

# ─── Cached OpenRouter model catalogue with pricing ───────────────────

_PRICING_CACHE: Dict[str, dict] = {}   # model_id -> {"prompt": float, "completion": float}
_PRICING_CACHE_TS: float = 0.0
_PRICING_TTL: float = 600.0             # 10 min


async def _refresh_pricing_cache():
    """Fetch the full OpenRouter model catalogue and extract per-token pricing."""
    global _PRICING_CACHE, _PRICING_CACHE_TS
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get("https://openrouter.ai/api/v1/models")
        if r.status_code != 200:
            return
        for m in r.json().get("data", []):
            pricing = m.get("pricing") or {}
            try:
                prompt_cost = float(pricing.get("prompt") or 0)
                completion_cost = float(pricing.get("completion") or 0)
            except (TypeError, ValueError):
                prompt_cost, completion_cost = 0.0, 0.0
            _PRICING_CACHE[m["id"]] = {
                "prompt": prompt_cost,
                "completion": completion_cost,
            }
        _PRICING_CACHE_TS = time.time()
    except Exception as e:
        print(f"[pricing] Failed to refresh OpenRouter pricing cache: {e}")


async def get_model_pricing(model_id: str) -> dict:
    """Return {"prompt": float, "completion": float} for a model (USD per token).
    Falls back to a conservative default if the model isn't found."""
    if time.time() - _PRICING_CACHE_TS > _PRICING_TTL:
        await _refresh_pricing_cache()
    return _PRICING_CACHE.get(model_id, {"prompt": 0.000015, "completion": 0.00006})


# ─── Token estimation constants (conservative) ───────────────────────

DEFAULT_INPUT_TOKENS = 500
VISION_INPUT_EXTRA = 1000       # extra tokens when images are attached

STAGE1_OUTPUT_PER_MODEL = 800   # each model's individual response
STAGE2_OUTPUT_PER_MODEL = 600   # each model's ranking evaluation
STAGE3_OUTPUT = 1000            # chairman synthesis
TITLE_INPUT = 100
TITLE_OUTPUT = 20


def estimate_tokens_for_run(
    n_models: int,
    user_input_tokens: int = DEFAULT_INPUT_TOKENS,
    has_vision: bool = False,
) -> dict:
    """Estimate total prompt and completion tokens for a full 3-stage council run."""
    input_base = user_input_tokens + (VISION_INPUT_EXTRA if has_vision else 0)

    s1_prompt_per_model = input_base
    s1_completion_per_model = STAGE1_OUTPUT_PER_MODEL

    s2_prompt_per_model = input_base + (n_models * STAGE1_OUTPUT_PER_MODEL)
    s2_completion_per_model = STAGE2_OUTPUT_PER_MODEL

    s3_prompt = input_base + (n_models * STAGE1_OUTPUT_PER_MODEL) + (n_models * STAGE2_OUTPUT_PER_MODEL)
    s3_completion = STAGE3_OUTPUT

    return {
        "s1_prompt_per_model": s1_prompt_per_model,
        "s1_completion_per_model": s1_completion_per_model,
        "s2_prompt_per_model": s2_prompt_per_model,
        "s2_completion_per_model": s2_completion_per_model,
        "s3_prompt": s3_prompt,
        "s3_completion": s3_completion,
        "title_prompt": TITLE_INPUT,
        "title_completion": TITLE_OUTPUT,
        "total_api_calls": (2 * n_models) + 2,
    }


# ─── USD cost estimation per model ────────────────────────────────────

async def estimate_model_usd_cost(
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Estimate the USD cost of one API call to the given model."""
    pricing = await get_model_pricing(model_id)
    return (prompt_tokens * pricing["prompt"]) + (completion_tokens * pricing["completion"])


async def estimate_run_usd(
    council_models: List[str],
    chairman_model: str,
    has_vision: bool = False,
    user_input_tokens: int = DEFAULT_INPUT_TOKENS,
) -> Tuple[float, List[dict]]:
    """Estimate the total USD cost of a full council run."""
    n = len(council_models)
    tok = estimate_tokens_for_run(n, user_input_tokens, has_vision)
    breakdown = []
    total = 0.0

    for model in council_models:
        s1_cost = await estimate_model_usd_cost(
            model, tok["s1_prompt_per_model"], tok["s1_completion_per_model"]
        )
        breakdown.append({"model": model, "stage": "stage1", "usd": s1_cost})
        total += s1_cost

        s2_cost = await estimate_model_usd_cost(
            model, tok["s2_prompt_per_model"], tok["s2_completion_per_model"]
        )
        breakdown.append({"model": model, "stage": "stage2", "usd": s2_cost})
        total += s2_cost

    s3_cost = await estimate_model_usd_cost(
        chairman_model, tok["s3_prompt"], tok["s3_completion"]
    )
    breakdown.append({"model": chairman_model, "stage": "stage3", "usd": s3_cost})
    total += s3_cost

    title_cost = await estimate_model_usd_cost(
        "google/gemini-2.5-flash", tok["title_prompt"], tok["title_completion"]
    )
    breakdown.append({"model": "google/gemini-2.5-flash", "stage": "title", "usd": title_cost})
    total += title_cost

    return total, breakdown


# ─── USD → Credits conversion ────────────────────────────────────────

async def usd_to_credits(
    usd: float,
    credits_per_usd: float,
    minimum: int = 1,
) -> int:
    """Convert a USD cost to credits, rounding up. Never returns less than minimum."""
    return max(minimum, math.ceil(usd * credits_per_usd))


async def estimate_run_credits(
    council_models: List[str],
    chairman_model: str,
    has_vision: bool = False,
    credits_per_usd: float = 500.0,
    minimum_credits: int = 2,
    user_input_tokens: int = DEFAULT_INPUT_TOKENS,
) -> dict:
    """Full estimation: models → USD → credits."""
    total_usd, breakdown = await estimate_run_usd(
        council_models, chairman_model, has_vision, user_input_tokens
    )
    total_credits = await usd_to_credits(total_usd, credits_per_usd, minimum_credits)

    n = len(council_models)
    tok = estimate_tokens_for_run(n, user_input_tokens, has_vision)

    model_usd: Dict[str, float] = {}
    for entry in breakdown:
        model_usd[entry["model"]] = model_usd.get(entry["model"], 0.0) + entry["usd"]

    per_model_credits = []
    for model, usd in model_usd.items():
        mc = max(1, math.ceil(usd * credits_per_usd)) if usd > 0 else 0
        per_model_credits.append({"model": model, "credits": mc, "usd": round(usd, 8)})
    per_model_credits.sort(key=lambda x: x["credits"], reverse=True)

    for entry in breakdown:
        entry["usd"] = round(entry["usd"], 8)

    return {
        "cost": total_credits,
        "estimated_usd": round(total_usd, 8),
        "credits_per_usd": credits_per_usd,
        "total_api_calls": tok["total_api_calls"],
        "breakdown": breakdown,
        "per_model_credits": per_model_credits,
    }
