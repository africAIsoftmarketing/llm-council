"""3-stage LLM Council orchestration with dynamic configuration.

Improvements over original:
1. Aggregate rankings injected into chairman prompt (weighted synthesis)
2. Adaptive output format: prose (default) vs structured JSON (trading/signal mode)
3. Post-chairman validation guardrail (format-aware)
4. Confluence extraction pre-processing for trading mode (Stage 2.5)
5. Temperature parameter support for chairman
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
# Output mode detection
# ---------------------------------------------------------------------------

def _strip_json_blocks(text: str) -> str:
    """Strip JSON code blocks and bare JSON objects from a response.

    Used in prose mode to prevent the chairman from mimicking JSON format
    seen in Stage 1 responses. Replaces JSON with a prose summary of
    key-value pairs extracted from the JSON.

    Example:
        '```json\n{"sentiment": -1, "reason": "bearish"}\n```'
        → '[Extracted data: sentiment = -1, reason = bearish]'
    """
    def _json_to_prose(match: re.Match) -> str:
        raw = match.group(0)
        # Strip fences
        clean = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        clean = re.sub(r'\s*```$', '', clean)
        try:
            obj = json.loads(clean)
            if isinstance(obj, dict):
                pairs = ", ".join(f"{k} = {v}" for k, v in obj.items())
                return f"[Extracted data: {pairs}]"
        except (json.JSONDecodeError, TypeError):
            pass
        return raw

    # Replace fenced JSON blocks: ```json ... ```
    result = re.sub(
        r'```json\s*\{.*?\}\s*```',
        _json_to_prose,
        text,
        flags=re.DOTALL
    )

    # Replace bare JSON objects that look like full responses
    # (starts at line beginning, has "sentiment" or "fair_value" keys)
    def _bare_json_to_prose(match: re.Match) -> str:
        raw = match.group(0)
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and len(obj) >= 2:
                pairs = ", ".join(f"{k} = {v}" for k, v in obj.items())
                return f"[Extracted data: {pairs}]"
        except (json.JSONDecodeError, TypeError):
            pass
        return raw

    result = re.sub(
        r'^\s*\{[^{}]*(?:"sentiment"|"fair_value")[^{}]*\}\s*$',
        _bare_json_to_prose,
        result,
        flags=re.MULTILINE | re.DOTALL
    )

    return result


def _is_json_response(text: str) -> bool:
    """Check if a response is primarily a JSON object (not prose).

    Returns True if the entire response (after stripping whitespace and
    markdown fences) is a single JSON object. A response that contains
    JSON embedded within prose paragraphs returns False.
    """
    clean = text.strip()
    clean = re.sub(r'^```(?:json)?\s*', '', clean)
    clean = re.sub(r'\s*```$', '', clean)
    clean = clean.strip()

    if not (clean.startswith('{') and clean.endswith('}')):
        return False

    try:
        json.loads(clean)
        # It's valid JSON — but is the ENTIRE response just this JSON?
        # Check if there's meaningful prose around the JSON block
        non_json = text.strip()
        non_json = re.sub(r'```json\s*\{.*?\}\s*```', '', non_json, flags=re.DOTALL)
        non_json = re.sub(r'\{[^{}]*\}', '', non_json)
        non_json = non_json.strip()
        # If less than 100 chars of non-JSON content, it's a JSON response
        return len(non_json) < 100
    except json.JSONDecodeError:
        return False

# Trading-signal keywords that trigger structured JSON mode
_TRADING_SIGNAL_INDICATORS = [
    'fair_value_estimate', 'sentiment', 'bearish', 'bullish',
    'OB ', 'FVG', 'POC', 'VWAP', 'VAL', 'VAH',
    'BOS', 'CHOCH', 'MSS', 'OTE', 'ICT', 'SMC',
    'PDH', 'PDL', 'liquidity', 'Naked POC',
]


def detect_output_mode(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    advanced_config: dict = None
) -> str:
    """
    Detect whether the chairman should output structured JSON or prose.

    Priority:
    1. Explicit override via advanced_config['chairman_output_mode']
       → 'json' | 'prose'
    2. Auto-detect from user query + Stage 1 responses:
       - If trading/signal indicators are found → 'json'
       - Otherwise → 'prose' (default, preserves user's format)

    Returns:
        'json' or 'prose'
    """
    # 1. Explicit override
    if advanced_config:
        explicit = advanced_config.get('chairman_output_mode')
        if explicit in ('json', 'prose'):
            return explicit

    # 2. Auto-detect: check user query + first few responses for trading signals
    corpus = user_query.lower()
    for result in stage1_results[:3]:
        corpus += " " + result.get('response', '').lower()

    hit_count = sum(
        1 for indicator in _TRADING_SIGNAL_INDICATORS
        if indicator.lower() in corpus
    )

    # Require at least 4 trading indicators to trigger JSON mode
    if hit_count >= 4:
        logger.info(
            "Auto-detected trading/signal mode (%d indicators). "
            "Chairman will output structured JSON.", hit_count
        )
        return 'json'

    return 'prose'


# ---------------------------------------------------------------------------
# Stage 1 — Collect individual responses (FIXED: individual framing)
# ---------------------------------------------------------------------------

def _sniff_image_media_type(b64: str) -> str:
    """Detect image media type from base64 magic bytes.

    Falls back to image/png if the format can't be determined.
    """
    if b64.startswith('/9j/'):
        return 'image/jpeg'
    if b64.startswith('iVBORw0KGgo'):
        return 'image/png'
    if b64.startswith('R0lGOD'):
        return 'image/gif'
    if b64.startswith('UklGR'):
        return 'image/webp'
    return 'image/png'


# System message injected in Stage 1 to prevent each model from acting
# as the entire "council". Without this, prompts like "You are a council
# of 5 experts..." cause every model to produce a full synthesis instead
# of its own individual perspective.
#
# NOTE: This is NOT injected when the user's prompt itself defines an
# explicit multi-agent pipeline (e.g. AGENT 1, AGENT 2, ... with distinct
# roles). In that case each model is SUPPOSED to run the full pipeline and
# produce a complete multi-agent output, and the peers rank those complete
# pipeline runs against each other.
STAGE1_SYSTEM_MESSAGE = (
    "You are one individual AI model providing your own independent, "
    "comprehensive response to the user's question. "
    "Other AI models are also answering this same question separately. "
    "Your response will later be evaluated, ranked by peers, and then "
    "synthesized by a chairman into a single final answer.\n\n"
    "IMPORTANT: Even if the user's prompt asks you to act as a group, "
    "a council, or multiple experts, provide YOUR single best answer "
    "as one unified voice. Do NOT simulate multiple personas or produce "
    "a synthesis — that synthesis step will happen later in the pipeline. "
    "Focus on giving the most thorough, accurate, and well-structured "
    "answer you can from your own perspective."
)

# Indicators that the user prompt defines an explicit multi-agent pipeline.
# When detected, each model runs the full pipeline itself (no anti-persona
# framing), because the pipeline IS the intended output.
_AGENT_PIPELINE_INDICATORS = [
    'AGENT 1', 'AGENT 2', 'AGENT 3', 'AGENT 4', 'AGENT 5',
    'AGENT_1', 'AGENT_2',
    'SENTIMENT_SYSTEM', 'SIGNAL_SYSTEM', 'RISK_SYSTEM',
    'SUMMARY_SYSTEM', 'MM_SYSTEM',
    'pipeline d\'agents', 'multi-agent pipeline',
    'Agent 1', 'Agent 2', 'Agent 3',
]


def _user_prompt_defines_agent_pipeline(user_query: str) -> bool:
    """Detect whether the user's prompt itself defines a distinct-role
    agent pipeline that each model should execute in full.

    Requires at least 2 distinct agent markers to avoid false positives
    from a passing mention of the word "agent".
    """
    hits = sum(1 for ind in _AGENT_PIPELINE_INDICATORS if ind in user_query)
    return hits >= 2


async def stage1_collect_responses(
    user_query: str,
    vision_images: list = None,
    advanced_config: dict = None
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Each model receives a system message framing it as an individual
    contributor. This prevents prompts with council/group framing
    from causing each model to produce a full synthesis.

    Args:
        user_query: The user's question
        vision_images: Optional list of vision images with base64 data
        advanced_config: Advanced configuration from frontend

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    council_models = get_council_models()

    # Only inject the anti-persona framing if the user prompt does NOT
    # define its own multi-agent pipeline. When the prompt defines agents
    # 1..N with distinct roles, each model must run the full pipeline.
    pipeline_mode = _user_prompt_defines_agent_pipeline(user_query)
    if pipeline_mode:
        logger.info(
            "Stage 1: user prompt defines an agent pipeline — each model "
            "will execute the full pipeline (no anti-persona framing)."
        )
        base_messages = []
    else:
        base_messages = [{"role": "system", "content": STAGE1_SYSTEM_MESSAGE}]

    if vision_images:
        content = [{"type": "text", "text": user_query}]
        for img in vision_images:
            # Robust base64 extraction: support multiple key conventions
            b64 = (
                img.get('base64_data')
                or img.get('base64')
                or img.get('data')
                or img.get('content')
            )
            if not b64:
                logger.warning(
                    "Vision image skipped: no base64 data found. Keys present: %s",
                    list(img.keys())
                )
                continue

            # Detect media type: explicit field, data-URI prefix, or default
            media_type = img.get('media_type') or img.get('mime_type')
            if not media_type:
                if b64.startswith('data:'):
                    # Already a full data URI — use as-is
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": b64}
                    })
                    continue
                # Sniff from base64 magic bytes
                media_type = _sniff_image_media_type(b64)

            # Strip any accidental data-URI prefix before re-wrapping
            if b64.startswith('data:'):
                b64 = b64.split(',', 1)[-1]

            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{b64}"
                }
            })

        logger.info(
            "Stage 1: sending %d vision image(s) to %d models",
            len(content) - 1, len(council_models)
        )
        messages = base_messages + [{"role": "user", "content": content}]
    else:
        messages = base_messages + [{"role": "user", "content": user_query}]

    responses = await query_models_parallel(
        council_models, messages, advanced_config=advanced_config
    )

    stage1_results = []
    failed_models = []
    for model, response in responses.items():
        if response is not None:
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })
        else:
            failed_models.append(model)

    if failed_models:
        logger.warning(
            "Stage 1: %d model(s) failed to respond: %s",
            len(failed_models), ", ".join(failed_models)
        )

    return stage1_results


# ---------------------------------------------------------------------------
# Stage 2 — Peer rankings (unchanged)
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
# Stage 2.5 — Confluence extraction (trading mode only)
# ---------------------------------------------------------------------------

def extract_key_levels(response_text: str) -> Dict[str, Any]:
    """
    Extract structured SMC/ICT key levels from a model's response text.

    Parses JSON blocks and known patterns to surface:
    - fair_value_estimate, sentiment
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
    Used only in trading/JSON mode.

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
# Stage 3 — Chairman synthesis (ADAPTIVE)
# ---------------------------------------------------------------------------

CHAIRMAN_JSON_SCHEMA = """{
  "sentiment": <int, -1 or 0 or 1>,
  "fair_value_estimate": <float, the synthesized target price>,
  "confidence": <float 0.0-1.0, your confidence in this estimate>,
  "reason": "<string, multi-sentence justification citing specific confluences>",
  "dissenting_views": "<string or null, note any significant alternative targets proposed by minority models and why they were overridden or accepted>"
}"""


def _build_chairman_prompt_prose(
    user_query: str,
    stage1_text: str,
    stage2_text: str,
    rankings_text: str
) -> str:
    """Build the chairman prompt for PROSE mode (default).

    The chairman produces a comprehensive, format-faithful synthesis that
    mirrors the structure and depth expected by the original question.
    """
    return f"""You are the Chairman of an LLM Council. Multiple AI models have independently answered a user's question, then evaluated and ranked each other's responses. Your job is to synthesize their work into the single best possible answer.

══════════════════════════════════════════
ORIGINAL QUESTION:
{user_query}
══════════════════════════════════════════

AGGREGATE PEER RANKINGS (lower avg = better):
{rankings_text if rankings_text else "  (not available)"}

══════════════════════════════════════════

STAGE 1 — INDIVIDUAL MODEL RESPONSES:
{stage1_text}

══════════════════════════════════════════

STAGE 2 — PEER EVALUATIONS AND RANKINGS:
{stage2_text}

══════════════════════════════════════════

CRITICAL FORMAT RULES:

⛔ DO NOT respond with JSON. DO NOT respond with a JSON object. DO NOT wrap your answer in curly braces.
⛔ DO NOT output fields like "sentiment", "fair_value_estimate", "confidence", or "reason" as a JSON structure.
⛔ Even if the Stage 1 responses contain JSON blocks, your synthesis must be PROSE TEXT — paragraphs, sections, numbered items, headings — NOT JSON.

✅ Your response must be rich, structured PROSE TEXT that directly answers the original question using the format the user requested.

YOUR SYNTHESIS INSTRUCTIONS:

1. RE-READ THE ORIGINAL QUESTION above. Identify the output format the user expects (numbered models? detailed sections? a ranking at the end? specific fields?). Your synthesis MUST mirror that exact structure.

2. ANCHOR on the top-ranked response(s). Use them as your primary source of structure, depth, and content quality. Do NOT simplify or reduce their level of detail.

3. ENRICH with valuable insights from lower-ranked responses that the top response missed. Peer evaluations will tell you what each response did well and poorly — use this.

4. RESOLVE DISAGREEMENTS explicitly. When models contradict each other on facts, figures, or recommendations, state which position you adopt and briefly justify why (citing peer evaluations or logical reasoning).

5. QUALITY FLOOR: Your synthesis must be AT LEAST as detailed and comprehensive as the best individual response. You are synthesizing, not summarizing. The council's collective answer should be strictly better than any single model's answer.

6. Respond in the SAME LANGUAGE as the original question.

Remember: your output is PROSE, not JSON. Write your synthesis now:"""


def _build_chairman_prompt_json(
    user_query: str,
    stage1_text: str,
    stage2_text: str,
    rankings_text: str,
    confluence_table: str
) -> str:
    """Build the chairman prompt for JSON/trading-signal mode.

    The chairman produces a structured JSON output with sentiment, fair value,
    confidence, reason, and dissenting views.
    """
    return f"""You are the Chairman of an LLM Council. Multiple AI models have provided trading signal responses to a user's question, and then ranked each other's responses. Your job is to synthesize the BEST possible signal by weighting higher-ranked responses more heavily.

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
Synthesize all of the above into a single definitive trading signal. Consider:
- The aggregate rankings: the top-ranked model's analysis should anchor your synthesis
- The confluence table: identify where models agree and disagree on key levels
- Any divergence in fair_value_estimate: analyze which target has stronger confluence support
- The peer evaluations: what strengths and weaknesses did evaluators identify

You MUST respond with ONLY a valid JSON object matching this exact schema:
{CHAIRMAN_JSON_SCHEMA}

Rules:
- fair_value_estimate must be justified by at least 2 confluent levels
- reason must cite specific price levels (OB, FVG, POC, VWAP, etc.)
- If models proposed different fair_value targets, dissenting_views must explain which alternatives were considered and why
- Do NOT wrap the JSON in markdown code fences
- Do NOT add any text before or after the JSON object"""


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

    Adaptive output mode:
    - 'prose' (default): Full, structured synthesis mirroring the original
      question's expected format. No format reduction.
    - 'json' (auto-detected for trading/signal queries): Structured JSON
      with sentiment, fair_value, confidence, dissenting_views.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        aggregate_rankings: Pre-calculated aggregate rankings (best → worst)
        advanced_config: Advanced configuration from frontend
        chairman_temperature: Optional temperature override

    Returns:
        Dict with 'model', 'response', 'validation', and 'output_mode' keys
    """
    chairman_model = get_chairman_model()

    # --- Detect output mode ---
    output_mode = detect_output_mode(user_query, stage1_results, advanced_config)
    logger.info("Chairman output mode: %s", output_mode)

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

    # --- Stage 1 full text ---
    if output_mode == 'prose':
        # Strip JSON blocks from Stage 1 responses to prevent chairman
        # from mimicking JSON format (the #1 cause of format contamination)
        stage1_text = "\n\n".join([
            f"Model: {result['model']}\nResponse: {_strip_json_blocks(result['response'])}"
            for result in stage1_results
        ])
    else:
        stage1_text = "\n\n".join([
            f"Model: {result['model']}\nResponse: {result['response']}"
            for result in stage1_results
        ])

    # --- Stage 2 evaluations ---
    stage2_text = "\n\n".join([
        f"Evaluator: {result['model']}\nEvaluation: {result['ranking']}"
        for result in stage2_results
    ])

    # --- Build mode-specific prompt ---
    extracted_levels = []

    if output_mode == 'json':
        # Trading mode: build confluence table (Stage 2.5)
        confluence_table, extracted_levels = build_confluence_table(stage1_results)
        chairman_prompt = _build_chairman_prompt_json(
            user_query, stage1_text, stage2_text, rankings_text, confluence_table
        )
    else:
        # Prose mode (default): no confluence table, format-faithful synthesis
        chairman_prompt = _build_chairman_prompt_prose(
            user_query, stage1_text, stage2_text, rankings_text
        )

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
            "output_mode": output_mode,
            "validation": {"status": "error", "reason": "chairman_no_response"}
        }

    raw_content = response.get('content', '')

    # --- Post-chairman validation ---
    if output_mode == 'json':
        validation = validate_chairman_json(
            raw_content, extracted_levels, aggregate_rankings
        )
    else:
        validation = validate_chairman_prose(
            raw_content, stage1_results, aggregate_rankings
        )

        # --- RETRY: if chairman returned JSON in prose mode, re-query ---
        if _is_json_response(raw_content):
            logger.warning(
                "Chairman returned JSON in prose mode. Retrying with "
                "correction prompt (attempt 2/2)."
            )
            correction_prompt = (
                f"Your previous response was a JSON object, but the user "
                f"expects a detailed PROSE answer — paragraphs, numbered "
                f"sections, headings — NOT JSON.\n\n"
                f"Here is the original question again:\n\n{user_query}\n\n"
                f"And here is your JSON response that needs to be rewritten "
                f"as rich, structured prose:\n\n{raw_content}\n\n"
                f"Now rewrite this as a comprehensive prose response that "
                f"follows the format requested in the original question. "
                f"DO NOT output JSON. Write detailed paragraphs and sections."
            )
            retry_messages = [{"role": "user", "content": correction_prompt}]
            retry_response = await query_model(
                chairman_model, retry_messages, **query_kwargs
            )

            if retry_response is not None:
                retry_content = retry_response.get('content', '')
                if not _is_json_response(retry_content) and len(retry_content) > len(raw_content):
                    raw_content = retry_content
                    validation = validate_chairman_prose(
                        raw_content, stage1_results, aggregate_rankings
                    )
                    validation['retried'] = True
                    logger.info("Chairman retry succeeded — prose response obtained.")
                else:
                    validation['warnings'].append(
                        "Chairman retry also returned JSON or shorter response. "
                        "Consider changing the chairman model."
                    )
                    validation['retried'] = True
                    validation['retry_failed'] = True

    return {
        "model": chairman_model,
        "response": raw_content,
        "output_mode": output_mode,
        "validation": validation
    }


# ---------------------------------------------------------------------------
# Post-chairman validation — JSON mode (trading)
# ---------------------------------------------------------------------------

def validate_chairman_json(
    chairman_response: str,
    extracted_levels: List[Dict[str, Any]],
    aggregate_rankings: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Validate the chairman's JSON response for coherence with council data.

    Checks:
    1. Valid JSON with required fields
    2. fair_value_estimate matches a model's proposed value
    3. Alignment with top-ranked model (or justified deviation)
    """
    validation = {
        "status": "ok",
        "warnings": [],
        "parsed_json": None
    }

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

    # Check required fields
    required_fields = ['sentiment', 'fair_value_estimate', 'reason']
    for field in required_fields:
        if field not in parsed:
            validation['warnings'].append(f"Missing required field: {field}")
            validation['status'] = 'warning'

    chairman_fv = parsed.get('fair_value_estimate')
    if chairman_fv is None:
        return validation

    # Check fair_value coherence
    model_fair_values = {}
    for level_data in extracted_levels:
        model = level_data.get('model', 'unknown')
        fv = level_data.get('fair_value_estimate')
        if fv is not None:
            model_fair_values[model] = fv

    if model_fair_values:
        all_fvs = set(model_fair_values.values())

        if chairman_fv not in all_fvs:
            validation['warnings'].append(
                f"Chairman fair_value {chairman_fv} does not match any model's "
                f"proposed values: {dict(model_fair_values)}"
            )

        if aggregate_rankings:
            top_model = aggregate_rankings[0]['model']
            top_fv = model_fair_values.get(top_model)
            if top_fv is not None and chairman_fv != top_fv:
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
# Post-chairman validation — Prose mode (general)
# ---------------------------------------------------------------------------

def validate_chairman_prose(
    chairman_response: str,
    stage1_results: List[Dict[str, Any]],
    aggregate_rankings: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Validate the chairman's prose response for quality and completeness.

    Checks:
    1. Response is not trivially short (quality floor)
    2. Response is at least as long as the longest Stage 1 response
    3. Response is not accidentally JSON-only when prose was expected
    """
    validation = {
        "status": "ok",
        "warnings": []
    }

    response_len = len(chairman_response.strip())

    # Check if chairman returned JSON when prose was expected
    clean = chairman_response.strip()
    if clean.startswith('{') and clean.endswith('}'):
        try:
            json.loads(clean)
            validation['status'] = 'warning'
            validation['warnings'].append(
                "Chairman returned JSON in prose mode. The synthesis should be "
                "a comprehensive text response matching the original question's "
                "expected format. Consider re-running Stage 3 or adjusting the "
                "chairman model."
            )
            logger.warning("Chairman produced JSON in prose mode — likely format mismatch.")
            return validation
        except json.JSONDecodeError:
            pass  # Not valid JSON, that's fine for prose

    # Quality floor: chairman synthesis should be at least as detailed as the
    # best individual response
    if stage1_results:
        longest_stage1 = max(len(r['response']) for r in stage1_results)
        # Allow some slack (80% of longest) since synthesis can be more
        # efficient than raw responses
        quality_floor = int(longest_stage1 * 0.8)

        if response_len < quality_floor:
            validation['status'] = 'warning'
            validation['warnings'].append(
                f"Chairman response ({response_len} chars) is shorter than 80% "
                f"of the longest Stage 1 response ({longest_stage1} chars). "
                f"The synthesis may have lost detail. Consider a chairman model "
                f"with higher output capacity."
            )
            logger.warning(
                "Chairman prose too short: %d chars vs quality floor %d",
                response_len, quality_floor
            )

    # Minimum absolute length
    if response_len < 200:
        validation['status'] = 'warning'
        validation['warnings'].append(
            f"Chairman response is very short ({response_len} chars). "
            f"Expected a comprehensive synthesis."
        )

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
    - aggregate_rankings passed to stage3_synthesize_final
    - Adaptive output mode (prose vs JSON) auto-detected
    - stage3_result includes validation + output_mode metadata

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
            "output_mode": "prose",
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

    # Stage 3: Synthesize final answer (with aggregate_rankings + adaptive mode)
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
        "chairman_output_mode": stage3_result.get('output_mode', 'prose'),
        "chairman_validation": stage3_result.get('validation', {})
    }

    return stage1_results, stage2_results, stage3_result, metadata
