"""
Aura v2.0 — Enrichment Completeness Scoring
Weighted scoring of enrichment data quality.
"""

from config import ENRICHMENT_WEIGHTS


def calculate_completeness(enrichment_dict: dict) -> int:
    """Calculate a 0-100 completeness score for enrichment data.

    Weights from config.ENRICHMENT_WEIGHTS:
      email=40, decision_maker=20, pain_points=15, tech_stack=10, phone=15

    Args:
        enrichment_dict: Dict of enrichment fields (from EnrichmentData row or dict)

    Returns:
        int score 0-100
    """
    score = 0

    # Email (40 points) — check lead email or gmaps_phone as proxy
    email = enrichment_dict.get("email", "")
    if email and "@" in str(email):
        score += ENRICHMENT_WEIGHTS.get("email", 40)

    # Decision maker (20 points)
    dm_name = enrichment_dict.get("decision_maker_name", "")
    if dm_name and str(dm_name).strip():
        score += ENRICHMENT_WEIGHTS.get("decision_maker", 20)

    # Pain points (15 points)
    pain = enrichment_dict.get("pain_points", "")
    if pain and str(pain).strip() and str(pain) != "[]":
        score += ENRICHMENT_WEIGHTS.get("pain_points", 15)

    # Tech stack (10 points)
    tech = enrichment_dict.get("tech_stack", "")
    if tech and str(tech).strip() and str(tech) != "[]":
        score += ENRICHMENT_WEIGHTS.get("tech_stack", 10)

    # Phone (15 points) — from lead or gmaps
    phone = enrichment_dict.get("phone", "") or enrichment_dict.get("gmaps_phone", "")
    if phone and str(phone).strip():
        score += ENRICHMENT_WEIGHTS.get("phone", 15)

    return min(100, score)
