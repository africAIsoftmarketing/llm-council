"""3-stage LLM Council orchestration with dynamic configuration.

Improvements over original:
1. Aggregate rankings injected into chairman prompt (weighted synthesis)
2. ALL output is prose — trading queries get a structured consensus report
3. Post-chairman validation guardrail (format-aware)
4. Confluence extraction pre-processing for trading mode (Stage 2.5)
5. Temperature parameter support for chairman
6. Proper data flow: aggregate_rankings passed through to stage3

v2.1 — Removed JSON output mode. The chairman now ALWAYS produces a
structured prose consensus report, even for trading/signal queries.
Trading queries get an enriched prompt with the confluence table and
explicit sections (Entry, SL, TP, R:R, Dissent) but the output remains
human-readable prose, not JSON.

v2.2 — Added web_search tool support. Stage 1 models and the chairman
can now search the web when their reasoning requires up-to-date data.
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
# Web search tool descriptor
# ---------------------------------------------------------------------------

def _build_web_search_tool() -> dict:
    """Return the web_search tool descriptor for the OpenRouter/Anthropic API."""
    return {
        "type": "web_search_20250305",
        "name": "web_search"
    }


# ---------------------------------------------------------------------------
# Output mode detection → Trading query detection (boolean)
# ---------------------------------------------------------------------------

def _strip_json_blocks(text: str) -> str:
    """Strip JSON code blocks and bare JSON objects from a response."""
    def _json_to_prose(match: re.Match) -> str:
        raw = match.group(0)
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

    result = re.sub(
        r'```json\s*\{.*?\}\s*```',
        _json_to_prose,
        text,
        flags=re.DOTALL
    )

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
    """Check if a response is primarily a JSON object (not prose)."""
    clean = text.strip()
    clean = re.sub(r'^```(?:json)?\s*', '', clean)
    clean = re.sub(r'\s*```$', '', clean)
    clean = clean.strip()

    if not (clean.startswith('{') and clean.endswith('}')):
        return False

    try:
        json.loads(clean)
        non_json = text.strip()
        non_json = re.sub(r'```json\s*\{.*?\}\s*```', '', non_json, flags=re.DOTALL)
        non_json = re.sub(r'\{[^{}]*\}', '', non_json)
        non_json = non_json.strip()
        return len(non_json) < 100
    except json.JSONDecodeError:
        return False


_TRADING_QUERY_INDICATORS = [
    'stop loss', 'stop-loss', 'take profit', 'take-profit',
    'risk/reward', 'R:R', 'R/R',
    'plan de trading', 'trading plan', 'exit plan',
    'fair_value_estimate', 'fair value estimate',
    'position size', 'taille de position',
    'j\'ai acheté', 'j\'ai vendu', 'i bought', 'i sold',
    'mon entrée', 'my entry', 'prix d\'entrée', 'entry price',
    'OTE ', 'Naked POC',
]

_TRADING_TECHNICAL_INDICATORS = [
    'OB ', 'FVG', 'POC', 'VWAP', 'VAL', 'VAH',
    'BOS', 'CHOCH', 'MSS', 'ICT', 'SMC',
    'PDH', 'PDL', 'liquidity',
    'sentiment', 'bearish', 'bullish',
]


def _is_trading_query(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    advanced_config: dict = None
) -> bool:
    """Detect whether the query is a trading/signal analysis."""
    if advanced_config:
        explicit = advanced_config.get('chairman_output_mode')
        if explicit == 'json':
            return True

    query_lower = user_query.lower()
    tier1_hits = sum(
        1 for ind in _TRADING_QUERY_INDICATORS
        if ind.lower() in query_lower
    )

    if tier1_hits >= 2:
        logger.info(
            "Trading query detected: %d Tier-1 indicators in user query.",
            tier1_hits
        )
        return True

    if tier1_hits == 0:
        return False

    response_corpus = ""
    for result in stage1_results[:3]:
        response_corpus += " " + result.get('response', '').lower()

    tier2_hits = sum(
        1 for ind in _TRADING_TECHNICAL_INDICATORS
        if ind.lower() in response_corpus
    )

    if tier2_hits >= 3:
        logger.info(
            "Trading query detected: %d Tier-1 in query + %d Tier-2 "
            "in responses (confirmed).", tier1_hits, tier2_hits
        )
        return True

    logger.debug(
        "Trading detection: %d Tier-1, %d Tier-2 — below threshold, "
        "treating as general query.", tier1_hits, tier2_hits
    )
    return False


# ---------------------------------------------------------------------------
# Stage 1 — Collect individual responses
# ---------------------------------------------------------------------------

def _sniff_image_media_type(b64: str) -> str:
    """Detect image media type from base64 magic bytes."""
    if b64.startswith('/9j/'):
        return 'image/jpeg'
    if b64.startswith('iVBORw0KGgo'):
        return 'image/png'
    if b64.startswith('R0lGOD'):
        return 'image/gif'
    if b64.startswith('UklGR'):
        return 'image/webp'
    return 'image/png'


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
    agent pipeline that each model should execute in full."""
    hits = sum(1 for ind in _AGENT_PIPELINE_INDICATORS if ind in user_query)
    return hits >= 2


async def stage1_collect_responses(
    user_query: str,
    vision_images: list = None,
    advanced_config: dict = None
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Web search is enabled for all models so they can retrieve
    up-to-date information when needed.
    """
    council_models = get_council_models()

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

            media_type = img.get('media_type') or img.get('mime_type')
            if not media_type:
                if b64.startswith('data:'):
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": b64}
                    })
                    continue
                media_type = _sniff_image_media_type(b64)

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

    # Pass web_search tool so models can fetch live data when needed
    responses = await query_models_parallel(
        council_models,
        messages,
        advanced_config=advanced_config,
        tools=[_build_web_search_tool()]
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
    """Stage 2: Each model ranks the anonymized responses."""
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
# Stage 2.5 — Confluence extraction (trading enrichment)
# ---------------------------------------------------------------------------

def extract_key_levels(response_text: str) -> Dict[str, Any]:
    """Extract structured SMC/ICT key levels from a model's response text."""
    levels = {}

    json_match = re.search(r'\{[^{}]*"sentiment"[^{}]*\}', response_text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            levels['sentiment'] = parsed.get('sentiment')
            levels['fair_value_estimate'] = parsed.get('fair_value_estimate')
            levels['reason'] = parsed.get('reason', '')
        except json.JSONDecodeError:
            pass

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
    """Build a structured confluence comparison table from Stage 1 responses."""
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
# Stage 3 — Chairman synthesis (ALWAYS PROSE)
# ---------------------------------------------------------------------------

def _build_chairman_prompt_prose(
    user_query: str,
    stage1_text: str,
    stage2_text: str,
    rankings_text: str
) -> str:
    """Build the chairman prompt for general prose mode (default)."""
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

7. If images are attached to this message, use them as reference material. Cross-verify the council members' claims against the visual evidence. If a claim is not supported by the images, note it.

Remember: your output is PROSE, not JSON. Write your synthesis now:"""


def _build_chairman_prompt_trading_prose(
    user_query: str,
    stage1_text: str,
    stage2_text: str,
    rankings_text: str,
    confluence_table: str
) -> str:
    """Build the chairman prompt for TRADING queries — prose consensus report."""
    return f"""You are the Chairman of an LLM Council specialized in trading analysis. Multiple AI models have independently analyzed a trading question, then evaluated and ranked each other's responses. Your job is to synthesize their work into a single, actionable CONSENSUS TRADING REPORT.

══════════════════════════════════════════
ORIGINAL QUESTION:
{user_query}
══════════════════════════════════════════

AGGREGATE PEER RANKINGS (lower avg = better):
{rankings_text if rankings_text else "  (not available)"}

IMPORTANT: Weight your synthesis toward the highest-ranked response(s). If you deviate from the top-ranked model's analysis, you MUST justify why.
══════════════════════════════════════════

STRUCTURED CONFLUENCE TABLE (key levels extracted from all models):
{confluence_table}
══════════════════════════════════════════

STAGE 1 — FULL INDIVIDUAL MODEL RESPONSES:
{stage1_text}

══════════════════════════════════════════

STAGE 2 — PEER EVALUATIONS AND RANKINGS:
{stage2_text}

══════════════════════════════════════════

CRITICAL FORMAT RULES:

⛔ DO NOT respond with JSON. DO NOT output a JSON object. DO NOT wrap your answer in curly braces.
⛔ Even if the Stage 1 responses contain JSON blocks (sentiment, fair_value_estimate, etc.), your report MUST be PROSE TEXT — structured paragraphs and sections, NOT JSON.
✅ Your response must be a clear, structured, human-readable TRADING CONSENSUS REPORT.

YOUR REPORT MUST FOLLOW THIS EXACT STRUCTURE:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## CONSENSUS DU COUNCIL

Write 2-3 sentences summarizing the overall consensus: what direction the council agrees on, the level of agreement, and the general sentiment (bullish/bearish/neutral). State how many models out of the total agree on the direction.

## ANALYSE DE L'ENTRÉE

Analyze the entry point from the original question. Cite the specific price levels (OB, FVG, POC, VWAP, etc.) that validate or invalidate the entry. Reference which models identified these levels and whether the confluence table confirms alignment.

## STOP LOSS — RECOMMANDATION DU COUNCIL

State the consensus Stop Loss level with a clear price. Explain why by citing the specific support levels, liquidity zones, or structural points (IBL, PDL, VAL, etc.) that multiple models identified. If models proposed different SL levels, state the range and explain which one the council recommends and why.

## TAKE PROFIT — RECOMMANDATION DU COUNCIL

State the consensus Take Profit target(s) with clear prices. For each target:
- TP1 (primary): the level where the majority of models converge, with the confluence evidence (resistance zones, liquidity pools, Weak High, etc.)
- TP2 (extended, if applicable): secondary target identified by at least 2 models
- State the probability or confidence level if models provided one

## RATIO RISQUE/RENDEMENT

Calculate and state the R:R ratio based on the recommended SL and TP levels relative to the entry price. Comment on whether this ratio meets the council's threshold for a valid trade.

## AVIS DIVERGENTS

If any model proposed significantly different levels or a contrarian view, describe it here. Explain why the majority consensus prevailed over the dissenting opinion, or note if the dissenting view has merit worth monitoring.

## RECOMMANDATION ACTIONABLE

In 2-3 sentences, give the final clear recommendation: hold/close/trail/partial exit, with specific prices. This should be directly executable by the trader.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ADDITIONAL INSTRUCTIONS:

1. ANCHOR on the top-ranked response(s) from the aggregate rankings. Their analysis should form the backbone of your report.

2. USE THE CONFLUENCE TABLE to identify where models agree and disagree on key levels. Agreement = high confidence. Divergence = must be addressed.

3. CITE SPECIFIC PRICE LEVELS throughout. Never say "around X" without giving the exact level identified by the models.

4. Respond in the SAME LANGUAGE as the original question.

5. QUALITY FLOOR: Your report must be at least as detailed as the best individual model response. You are synthesizing, not summarizing.

6. CROSS-VERIFY WITH CHARTS: If chart images are attached to this message, use them to validate the council members' claims. If a model cites a level (OB, FVG, POC, etc.) that is NOT visible on the chart, flag it in your report. If the chart shows a structure that NO model identified, mention it as a missed opportunity.

Write your consensus trading report now:"""


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    aggregate_rankings: List[Dict[str, Any]] = None,
    advanced_config: dict = None,
    chairman_temperature: float = None,
    vision_images: list = None
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response — ALWAYS PROSE.

    Web search is enabled for the chairman so it can verify or
    supplement council data with live information when needed.
    """
    chairman_model = get_chairman_model()

    is_trading = _is_trading_query(user_query, stage1_results, advanced_config)
    output_mode = 'prose'
    logger.info(
        "Chairman output mode: prose (trading enrichment: %s)", is_trading
    )

    rankings_text = ""
    if aggregate_rankings:
        rankings_lines = []
        for i, entry in enumerate(aggregate_rankings, 1):
            rankings_lines.append(
                f"  #{i} {entry['model']} — avg rank {entry['average_rank']} "
                f"({entry['rankings_count']} votes)"
            )
        rankings_text = "\n".join(rankings_lines)

    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {_strip_json_blocks(result['response'])}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Evaluator: {result['model']}\nEvaluation: {result['ranking']}"
        for result in stage2_results
    ])

    if is_trading:
        confluence_table, extracted_levels = build_confluence_table(stage1_results)
        chairman_prompt = _build_chairman_prompt_trading_prose(
            user_query, stage1_text, stage2_text, rankings_text, confluence_table
        )
    else:
        chairman_prompt = _build_chairman_prompt_prose(
            user_query, stage1_text, stage2_text, rankings_text
        )

    if vision_images:
        chairman_content = [{"type": "text", "text": chairman_prompt}]
        for img in vision_images:
            b64 = (
                img.get('base64_data')
                or img.get('base64')
                or img.get('data')
                or img.get('content')
            )
            if not b64:
                continue

            media_type = img.get('media_type') or img.get('mime_type')
            if not media_type:
                if b64.startswith('data:'):
                    chairman_content.append({
                        "type": "image_url",
                        "image_url": {"url": b64}
                    })
                    continue
                media_type = _sniff_image_media_type(b64)

            if b64.startswith('data:'):
                b64 = b64.split(',', 1)[-1]

            chairman_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{b64}"
                }
            })

        messages = [{"role": "user", "content": chairman_content}]
        logger.info(
            "Stage 3: chairman receives %d vision image(s) for cross-verification",
            len(chairman_content) - 1
        )
    else:
        messages = [{"role": "user", "content": chairman_prompt}]

    temperature = chairman_temperature
    if temperature is None and advanced_config:
        temperature = advanced_config.get('chairman_temperature')

    # Pass web_search tool so the chairman can verify live data when needed
    query_kwargs = dict(
        advanced_config=advanced_config,
        is_chairman=True,
        tools=[_build_web_search_tool()]
    )
    if temperature is not None:
        query_kwargs['temperature'] = temperature

    response = await query_model(chairman_model, messages, **query_kwargs)

    if response is None:
        return {
            "model": chairman_model,
            "response": "Error: Unable to generate final synthesis.",
            "output_mode": output_mode,
            "is_trading": is_trading,
            "validation": {"status": "error", "reason": "chairman_no_response"}
        }

    raw_content = response.get('content', '')

    validation = validate_chairman_prose(
        raw_content, stage1_results, aggregate_rankings
    )

    if _is_json_response(raw_content):
        logger.warning(
            "Chairman returned JSON despite prose instructions. "
            "Retrying with correction prompt (attempt 2/2)."
        )

        if is_trading:
            correction_prompt = (
                f"Your previous response was a JSON object, but the council "
                f"requires a STRUCTURED PROSE TRADING CONSENSUS REPORT — "
                f"with clear sections: Consensus du Council, Analyse de "
                f"l'Entrée, Stop Loss, Take Profit, Ratio Risque/Rendement, "
                f"Avis Divergents, Recommandation Actionable.\n\n"
                f"Here is the original question again:\n\n{user_query}\n\n"
                f"And here is your JSON response that must be rewritten as "
                f"a detailed prose trading report:\n\n{raw_content}\n\n"
                f"⛔ DO NOT output JSON. DO NOT wrap anything in curly braces.\n"
                f"✅ Write a comprehensive, structured PROSE report with the "
                f"sections listed above. Cite specific price levels throughout. "
                f"Respond in the same language as the original question."
            )
        else:
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
        "is_trading": is_trading,
        "validation": validation
    }


# ---------------------------------------------------------------------------
# Post-chairman validation — Prose mode (all queries)
# ---------------------------------------------------------------------------

def validate_chairman_prose(
    chairman_response: str,
    stage1_results: List[Dict[str, Any]],
    aggregate_rankings: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Validate the chairman's prose response for quality and completeness."""
    validation = {
        "status": "ok",
        "warnings": []
    }

    response_len = len(chairman_response.strip())

    clean = chairman_response.strip()
    if clean.startswith('{') and clean.endswith('}'):
        try:
            json.loads(clean)
            validation['status'] = 'warning'
            validation['warnings'].append(
                "Chairman returned JSON instead of prose. The synthesis "
                "should be a comprehensive text response. Consider "
                "re-running Stage 3 or adjusting the chairman model."
            )
            logger.warning("Chairman produced JSON instead of prose.")
            return validation
        except json.JSONDecodeError:
            pass

    if stage1_results:
        longest_stage1 = max(len(r['response']) for r in stage1_results)
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
    """Parse the FINAL RANKING section from the model's response."""
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
    """Calculate aggregate rankings across all models."""
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
    """Generate a short title for a conversation based on the first user message."""
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
# Full council orchestrator (unchanged)
# ---------------------------------------------------------------------------

async def run_full_council(
    user_query: str,
    vision_images: list = None,
    advanced_config: dict = None
) -> Tuple[List, List, Dict, Dict]:
    """Run the complete 3-stage council process."""
    stage1_results = await stage1_collect_responses(
        user_query, vision_images=vision_images, advanced_config=advanced_config
    )

    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please check your API key and try again.",
            "output_mode": "prose",
            "is_trading": False,
            "validation": {"status": "error", "reason": "no_stage1_responses"}
        }, {}

    stage2_results, label_to_model = await stage2_collect_rankings(
        user_query, stage1_results, advanced_config=advanced_config
    )

    aggregate_rankings = calculate_aggregate_rankings(
        stage2_results, label_to_model
    )

    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        aggregate_rankings=aggregate_rankings,
        advanced_config=advanced_config,
        vision_images=vision_images
    )

    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "chairman_output_mode": "prose",
        "is_trading_query": stage3_result.get('is_trading', False),
        "chairman_validation": stage3_result.get('validation', {})
    }

    return stage1_results, stage2_results, stage3_result, metadata
