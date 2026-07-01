"""3-stage LLM Council orchestration with dynamic configuration.

Improvements over original:
1. Aggregate rankings injected into chairman prompt (weighted synthesis)
2. Forced JSON output schema for chairman (sentiment, fair_value, confidence, dissent)
3. Post-chairman validation guardrail (fair_value coherence check)
4. Confluence extraction pre-processing (structured levels table for chairman)
5. Temperature parameter support for chairman (lower = more faithful)
6. Proper data flow: aggregate_rankings passed through to stage3
"""

from typing import List, Dict, Any, Tuple, Optional
import re
import json
import logging

logger = logging.getLogger(__name__)

try:
    from .openrouter import query_models_parallel, query_model
    from .config_manager import get_council_models, get_chairman_model
except ImportError:
    from openrouter import query_models_parallel, query_model
    from config_manager import get_council_models, get_chairman_model


# ---------------------------------------------------------------------------
# Stage 1 — Collect individual responses
# ---------------------------------------------------------------------------

async def stage1_collect_responses(
    user_query: str,
    vision_images: list = None,
    advanced_config: dict = None
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question
        vision_images: Optional list of vision images with base64 data
        advanced_config: Advanced configuration from frontend

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    council_models = get_council_models()

    # Build messages with optional vision content
    if vision_images:
        content = [{"type": "text", "text": user_query}]
        for img in vision_images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img['base64_data']}"
                }
            })
        messages = [{"role": "user", "content": content}]
    else:
        messages = [{"role": "user", "content": user_query}]

    responses = await query_models_parallel(
        council_models, messages, advanced_config=advanced_config
    )

    stage1_results = []
    for model, response in responses.items():
        if response is not None:
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })

    return stage1_results


# ---------------------------------------------------------------------------
# Stage 2 — Peer rankings
# ---------------------------------------------------------------------------

async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    advanced_config: dict = None
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    council_models = get_council_models()

    labels = [chr(65 + i) for i in range(len(stage1_results))]

    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    responses = await query_models_parallel(
        council_models, messages, advanced_config=advanced_config
    )

    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model


# ---------------------------------------------------------------------------
# Stage 2.5 — Confluence extraction (NEW)
# ---------------------------------------------------------------------------

def extract_key_levels(response_text: str) -> Dict[str, Any]:
    """
    Extract structured SMC/ICT key levels from a model's response text.

    Parses JSON blocks and known patterns to surface:
    - fair_value_estimate
    - sentiment
    - Named levels: OB, FVG, POC, VAL, VWAP, PDH, PDL, etc.

    Returns:
        Dict of extracted levels and metadata
    """
    levels = {}

    # --- Try to extract JSON block first ---
    json_match = re.search(r'\{[^{}]*"sentiment"[^{}]*\}', response_text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            levels['sentiment'] = parsed.get('sentiment')
            levels['fair_value_estimate'] = parsed.get('fair_value_estimate')
            levels['reason'] = parsed.get('reason', '')
        except json.JSONDecodeError:
            pass

    # --- Extract named price levels via regex ---
    level_patterns = {
        'OB_high':    r'(?:bearish\s+)?OB\s*(?:at|:)?\s*(\d+\.\d+)\s*[-–]\s*(\d+\.\d+)',
        'FVG':        r'FVG\s*(?:bearish\s+)?(?:at|:)?\s*(\d+\.\d+)\s*[-–]\s*(\d+\.\d+)',
        'POC':        r'(?:session\s+)?POC\s*(?:at|:)?\s*(\d+\.\d+)',
        'Naked_POC':  r'Naked\s+POC\s*(?:at|:)?\s*(\d+\.\d+)',
        'VAL':        r'VAL\s*(?:at|:)?\s*(\d+\.\d+)',
        'VAH':        r'VAH\s*(?:at|:)?\s*(\d+\.\d+)',
        'VWAP':       r'VWAP\s*(?:at|:)?\s*(\d+\.\d+)',
        'PDH':        r'PDH\s*(?:at|:)?\s*(\d+\.\d+)',
        'PDL':        r'PDL\s*(?:at|:)?\s*(\d+\.\d+)',
    }

    for key, pattern in level_patterns.items():
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            levels[key] = [g for g in match.groups()]

    return levels


def build_confluence_table(
    stage1_results: List[Dict[str, Any]]
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Build a structured confluence comparison table from Stage 1 responses.

    Returns:
        Tuple of (formatted table string, list of per-model extracted levels)
    """
    all_levels = []
    rows = []

    for result in stage1_results:
        extracted = extract_key_levels(result['response'])
        extracted['model'] = result['model']
        all_levels.append(extracted)

        row_parts = [f"  Model: {result['model']}"]
        if extracted.get('sentiment') is not None:
            row_parts.append(f"    Sentiment: {extracted['sentiment']}")
        if extracted.get('fair_value_estimate') is not None:
            row_parts.append(f"    Fair Value: {extracted['fair_value_estimate']}")
        for key in ('POC', 'Naked_POC', 'VAL', 'VAH', 'VWAP', 'PDH', 'PDL'):
            if key in extracted:
                vals = extracted[key]
                row_parts.append(f"    {key}: {' - '.join(vals)}")
        for key in ('OB_high', 'FVG'):
            if key in extracted:
                vals = extracted[key]
                row_parts.append(f"    {key}: {vals[0]} – {vals[1]}")
        if extracted.get('reason'):
            reason_short = extracted['reason'][:200]
            row_parts.append(f"    Reason: {reason_short}")

        rows.append("\n".join(row_parts))

    table = "\n\n".join(rows)

    # --- Detect divergences ---
    fair_values = [
        (l['model'], l['fair_value_estimate'])
        for l in all_levels if l.get('fair_value_estimate') is not None
    ]
    divergence_note = ""
    if len(fair_values) >= 2:
        vals = [fv for _, fv in fair_values]
        if len(set(vals)) > 1:
            divergence_note = (
                "\n\nDIVERGENCE DETECTED on fair_value_estimate:\n"
                + "\n".join(f"  - {m}: {v}" for m, v in fair_values)
                + "\nYou MUST address this divergence explicitly in your synthesis."
            )

    return table + divergence_note, all_levels


# ---------------------------------------------------------------------------
# Stage 3 — Chairman synthesis (IMPROVED)
# ---------------------------------------------------------------------------

CHAIRMAN_JSON_SCHEMA = """{
  "sentiment": <int, -1 or 0 or 1>,
  "fair_value_estimate": <float, the synthesized target price>,
  "confidence": <float 0.0-1.0, your confidence in this estimate>,
  "reason": "<string, multi-sentence justification citing specific confluences>",
  "dissenting_views": "<string or null, note any significant alternative targets proposed by minority models and why they were overridden or accepted>"
}"""


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    aggregate_rankings: List[Dict[str, Any]] = None,
    advanced_config: dict = None,
    chairman_temperature: float = None
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Improvements:
    - Receives aggregate_rankings and injects them into prompt
    - Builds a structured confluence table (Stage 2.5)
    - Forces a JSON output schema with dissenting_views
    - Supports explicit temperature override for chairman

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        aggregate_rankings: Pre-calculated aggregate rankings (best → worst)
        advanced_config: Advanced configuration from frontend
        chairman_temperature: Optional temperature override (lower = more faithful)

    Returns:
        Dict with 'model', 'response', and 'validation' keys
    """
    chairman_model = get_chairman_model()

    # --- Build confluence table (Stage 2.5) ---
    confluence_table, extracted_levels = build_confluence_table(stage1_results)

    # --- Format aggregate rankings ---
    rankings_text = ""
    if aggregate_rankings:
        rankings_lines = []
        for i, entry in enumerate(aggregate_rankings, 1):
            rankings_lines.append(
                f"  #{i} {entry['model']} — avg rank {entry['average_rank']} "
                f"({entry['rankings_count']} votes)"
            )
        rankings_text = "\n".join(rankings_lines)

    # --- Stage 1 full text (kept for context) ---
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    # --- Stage 2 evaluation excerpts (trimmed to reduce noise) ---
    stage2_text = "\n\n".join([
        f"Evaluator: {result['model']}\nEvaluation: {result['ranking']}"
        for result in stage2_results
    ])

    # --- Build improved chairman prompt ---
    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses. Your job is to synthesize the BEST possible answer by weighting higher-ranked responses more heavily.

Original Question: {user_query}

══════════════════════════════════════════
AGGREGATE PEER RANKINGS (lower avg = better):
{rankings_text if rankings_text else "  (not available)"}

IMPORTANT: Weight your synthesis toward the highest-ranked response(s). If you deviate from the top-ranked model's fair_value_estimate, you MUST justify why.
══════════════════════════════════════════

STRUCTURED CONFLUENCE TABLE (extracted key levels):
{confluence_table}

══════════════════════════════════════════

STAGE 1 — FULL INDIVIDUAL RESPONSES:
{stage1_text}

══════════════════════════════════════════

STAGE 2 — PEER EVALUATIONS:
{stage2_text}

══════════════════════════════════════════

YOUR TASK:
Synthesize all of the above into a single, definitive answer. Consider:
- The aggregate rankings: the top-ranked model's analysis should anchor your synthesis
- The confluence table: identify where models agree and disagree on key levels
- Any divergence in fair_value_estimate: if models disagree, analyze which target has stronger confluence support
- The peer evaluations: what strengths and weaknesses did evaluators identify

You MUST respond with ONLY a valid JSON object matching this exact schema:
{CHAIRMAN_JSON_SCHEMA}

Rules:
- fair_value_estimate must be justified by at least 2 confluent levels
- reason must cite specific price levels (OB, FVG, POC, VWAP, etc.)
- If models proposed different fair_value targets, the dissenting_views field must explain which alternatives were considered and why
- Do NOT wrap the JSON in markdown code fences
- Do NOT add any text before or after the JSON object"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # --- Determine temperature ---
    temperature = chairman_temperature
    if temperature is None and advanced_config:
        temperature = advanced_config.get('chairman_temperature')

    # Query the chairman model
    query_kwargs = dict(
        advanced_config=advanced_config,
        is_chairman=True
    )
    if temperature is not None:
        query_kwargs['temperature'] = temperature

    response = await query_model(chairman_model, messages, **query_kwargs)

    if response is None:
        return {
            "model": chairman_model,
            "response": "Error: Unable to generate final synthesis.",
            "validation": {"status": "error", "reason": "chairman_no_response"}
        }

    raw_content = response.get('content', '')

    # --- Post-chairman validation (Improvement #3) ---
    validation = validate_chairman_response(raw_content, extracted_levels, aggregate_rankings)

    return {
        "model": chairman_model,
        "response": raw_content,
        "validation": validation
    }


# ---------------------------------------------------------------------------
# Post-chairman validation guardrail (NEW)
# ---------------------------------------------------------------------------

def validate_chairman_response(
    chairman_response: str,
    extracted_levels: List[Dict[str, Any]],
    aggregate_rankings: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Validate the chairman's response for coherence with council data.

    Checks:
    1. Is the response valid JSON?
    2. Does fair_value_estimate match a value proposed by at least one model?
    3. If not, does it match the TOP-ranked model's value?
    4. Are required fields present?

    Returns:
        Dict with validation status, warnings, and parsed data
    """
    validation = {
        "status": "ok",
        "warnings": [],
        "parsed_json": None
    }

    # --- Try to parse JSON ---
    # Strip markdown fences if present
    clean = chairman_response.strip()
    clean = re.sub(r'^```(?:json)?\s*', '', clean)
    clean = re.sub(r'\s*```$', '', clean)

    try:
        parsed = json.loads(clean)
        validation['parsed_json'] = parsed
    except json.JSONDecodeError as e:
        validation['status'] = 'warning'
        validation['warnings'].append(f"Chairman response is not valid JSON: {e}")
        logger.warning("Chairman response failed JSON parse: %s", e)
        return validation

    # --- Check required fields ---
    required_fields = ['sentiment', 'fair_value_estimate', 'reason']
    for field in required_fields:
        if field not in parsed:
            validation['warnings'].append(f"Missing required field: {field}")
            validation['status'] = 'warning'

    chairman_fv = parsed.get('fair_value_estimate')
    if chairman_fv is None:
        return validation

    # --- Check fair_value coherence ---
    model_fair_values = {}
    for level_data in extracted_levels:
        model = level_data.get('model', 'unknown')
        fv = level_data.get('fair_value_estimate')
        if fv is not None:
            model_fair_values[model] = fv

    if model_fair_values:
        all_fvs = set(model_fair_values.values())

        # Check if chairman's value matches any proposed value
        if chairman_fv not in all_fvs:
            validation['warnings'].append(
                f"Chairman fair_value {chairman_fv} does not match any model's "
                f"proposed values: {dict(model_fair_values)}"
            )

        # Check alignment with top-ranked model
        if aggregate_rankings:
            top_model = aggregate_rankings[0]['model']
            top_fv = model_fair_values.get(top_model)
            if top_fv is not None and chairman_fv != top_fv:
                # Check if dissenting_views explains the deviation
                dissent = parsed.get('dissenting_views', '') or ''
                if not dissent.strip():
                    validation['status'] = 'warning'
                    validation['warnings'].append(
                        f"Chairman chose {chairman_fv} over top-ranked "
                        f"{top_model}'s value {top_fv} without dissenting_views "
                        f"explanation. Consider re-running Stage 3."
                    )
                    logger.warning(
                        "Chairman FV %s deviates from top-ranked %s (%s) "
                        "without justification.",
                        chairman_fv, top_model, top_fv
                    )

    if validation['warnings']:
        validation['status'] = 'warning'

    return validation


# ---------------------------------------------------------------------------
# Ranking parser (unchanged)
# ---------------------------------------------------------------------------

def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Returns:
        List of response labels in ranked order
    """
    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            numbered_matches = re.findall(
                r'\d+\.\s*Response [A-Z]', ranking_section
            )
            if numbered_matches:
                return [
                    re.search(r'Response [A-Z]', m).group()
                    for m in numbered_matches
                ]
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


# ---------------------------------------------------------------------------
# Aggregate ranking calculator (unchanged)
# ---------------------------------------------------------------------------

def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    aggregate.sort(key=lambda x: x['average_rank'])
    return aggregate


# ---------------------------------------------------------------------------
# Title generation (unchanged)
# ---------------------------------------------------------------------------

async def generate_conversation_title(
    user_query: str,
    advanced_config: dict = None
) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    title_timeout = 60.0
    if advanced_config:
        throttle_cfg = advanced_config.get('throttle', {})
        title_timeout = min(
            throttle_cfg.get('requestTimeout', 300) / 2, 120.0
        )

    if advanced_config and advanced_config.get('mode') in ('lmstudio', 'hybrid'):
        council_models = get_council_models()
        title_model = council_models[0] if council_models else "google/gemini-2.5-flash"
        response = await query_model(
            title_model, messages,
            timeout=title_timeout, advanced_config=advanced_config
        )
    else:
        response = await query_model(
            "google/gemini-2.5-flash", messages, timeout=30.0
        )

    if response is None:
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()
    title = title.strip('"\'')
    if len(title) > 50:
        title = title[:47] + "..."

    return title


# ---------------------------------------------------------------------------
# Full council orchestrator (IMPROVED)
# ---------------------------------------------------------------------------

async def run_full_council(
    user_query: str,
    vision_images: list = None,
    advanced_config: dict = None
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Improvements:
    - aggregate_rankings is now passed to stage3_synthesize_final
    - stage3_result includes validation metadata
    - Metadata includes validation status for downstream consumers

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(
        user_query, vision_images=vision_images, advanced_config=advanced_config
    )

    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please check your API key and try again.",
            "validation": {"status": "error", "reason": "no_stage1_responses"}
        }, {}

    # Stage 2: Collect rankings
    stage2_results, label_to_model = await stage2_collect_rankings(
        user_query, stage1_results, advanced_config=advanced_config
    )

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(
        stage2_results, label_to_model
    )

    # Stage 3: Synthesize final answer (NOW with aggregate_rankings)
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        aggregate_rankings=aggregate_rankings,
        advanced_config=advanced_config
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "chairman_validation": stage3_result.get('validation', {})
    }

    return stage1_results, stage2_results, stage3_result, metadata
