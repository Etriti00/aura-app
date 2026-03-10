"""
Aura v2.0 — Layer 1: LLM-Based Extraction (Ollama/Router)
Extracts structured business intelligence from webpage content.
"""

import json

from utils.logger import get_logger

logger = get_logger(__name__)


async def enrich_layer1(html_content: str, business_name: str,
                        router_engine=None) -> dict:
    """Use LLM to extract structured data from webpage HTML.

    Args:
        html_content: Raw HTML or cleaned text of the business website
        business_name: Name of the business for context
        router_engine: RouterEngine instance for LLM calls

    Returns:
        dict with decision_maker, description, pain_points, icp_fit_score
    """
    if not router_engine:
        logger.debug("No router_engine available for Layer 1 enrichment")
        return {}

    if not html_content:
        return {}

    # Truncate to avoid huge prompts
    content = html_content[:8000]

    prompt = (
        f"Analyze this business website content for '{business_name}' and extract:\n"
        f"1. decision_maker_name: The name of the owner/CEO/decision maker (or null)\n"
        f"2. decision_maker_title: Their title (or null)\n"
        f"3. company_description: One-sentence description of what they do\n"
        f"4. pain_points: JSON list of 2-4 business pain points they likely have\n"
        f"5. icp_fit_score: 0-100 score of how well they fit as a B2B sales prospect\n\n"
        f"Respond ONLY with valid JSON:\n"
        f'{{"decision_maker_name": ..., "decision_maker_title": ..., '
        f'"company_description": ..., "pain_points": [...], "icp_fit_score": ...}}\n\n'
        f"Website content:\n{content}"
    )

    try:
        response = await router_engine.route_task(
            task_type="extract_structured_data",
            payload={"prompt": prompt},
        )
        if response and response.get("success"):
            text = response.get("result", "")
            return _parse_extraction(text)
    except Exception as e:
        logger.debug(f"Layer 1 LLM extraction failed: {e}")

    return {}


def enrich_layer1_sync(html_content: str, business_name: str,
                       router_engine=None) -> dict:
    """Synchronous Layer 1 enrichment using router_engine.route()."""
    if not router_engine or not html_content:
        return {}

    content = html_content[:8000]
    prompt = (
        f"Analyze this business website content for '{business_name}' and extract:\n"
        f"1. decision_maker_name: The name of the owner/CEO/decision maker (or null)\n"
        f"2. decision_maker_title: Their title (or null)\n"
        f"3. company_description: One-sentence description of what they do\n"
        f"4. pain_points: JSON list of 2-4 business pain points they likely have\n"
        f"5. icp_fit_score: 0-100 score of how well they fit as a B2B sales prospect\n\n"
        f"Respond ONLY with valid JSON:\n"
        f'{{"decision_maker_name": ..., "decision_maker_title": ..., '
        f'"company_description": ..., "pain_points": [...], "icp_fit_score": ...}}\n\n'
        f"Website content:\n{content}"
    )
    try:
        response = router_engine.route("extract_structured_data", prompt)
        if response and response.get("success"):
            text = response.get("data", "") or response.get("result", "")
            return _parse_extraction(text)
    except Exception as e:
        logger.debug(f"Layer 1 sync extraction failed: {e}")
    return {}


def _parse_extraction(text: str) -> dict:
    """Parse LLM JSON response into enrichment fields."""
    result = {}
    try:
        # Find JSON in response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            if data.get("decision_maker_name"):
                result["decision_maker_name"] = str(data["decision_maker_name"])[:255]
            if data.get("decision_maker_title"):
                result["decision_maker_title"] = str(data["decision_maker_title"])[:255]
            if data.get("company_description"):
                result["company_description"] = str(data["company_description"])[:2000]
            if data.get("pain_points"):
                pts = data["pain_points"]
                if isinstance(pts, list):
                    result["pain_points"] = json.dumps(pts[:10])
            if data.get("icp_fit_score") is not None:
                score = int(data["icp_fit_score"])
                result["icp_fit_score"] = max(0, min(100, score))
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.debug(f"Failed to parse Layer 1 extraction: {e}")
    return result
