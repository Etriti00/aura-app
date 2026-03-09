"""
Aura v2.0 — Layer 2: Free API Enrichment
Google Maps Places, Clearbit free, BuiltWith free.
Daily counter gates to respect free tier limits.
"""

import json
from datetime import date

import httpx

from config import GMAPS_FREE_DAILY_LIMIT, CLEARBIT_FREE_DAILY_LIMIT
from utils.logger import get_logger

logger = get_logger(__name__)

# Daily counters (reset per-process; for real persistence, use DB)
_daily_counters: dict[str, dict] = {}


def _check_daily_limit(source: str, limit: int) -> bool:
    """Check if we've exceeded the daily limit for a source."""
    today = date.today().isoformat()
    if source not in _daily_counters or _daily_counters[source].get("date") != today:
        _daily_counters[source] = {"date": today, "count": 0}
    return _daily_counters[source]["count"] < limit


def _increment_counter(source: str):
    today = date.today().isoformat()
    if source not in _daily_counters or _daily_counters[source].get("date") != today:
        _daily_counters[source] = {"date": today, "count": 0}
    _daily_counters[source]["count"] += 1


async def enrich_layer2(domain: str, business_name: str = "",
                        city: str = "") -> dict:
    """Run Layer 2 enrichment: free APIs with daily limits.

    Args:
        domain: Business domain
        business_name: Business name for search
        city: City for Google Maps search

    Returns:
        dict with gmaps_*, company_size_estimate, industry_tag, linkedin_url
    """
    result = {}

    # Google Maps Places (free tier)
    if business_name and _check_daily_limit("gmaps", GMAPS_FREE_DAILY_LIMIT):
        gmaps_data = await _search_gmaps(business_name, city)
        result.update(gmaps_data)
        _increment_counter("gmaps")

    # Clearbit free logo/company API
    if domain and _check_daily_limit("clearbit", CLEARBIT_FREE_DAILY_LIMIT):
        clearbit_data = await _clearbit_free(domain)
        result.update(clearbit_data)
        _increment_counter("clearbit")

    return result


async def _search_gmaps(business_name: str, city: str = "") -> dict:
    """Search Google Maps Places API (free text search)."""
    result = {}
    query = f"{business_name} {city}".strip()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Using the free Places text search (requires API key in real use)
            # For now, structure the data format
            logger.debug(f"Google Maps search: {query}")
            # Placeholder — real implementation needs GMAPS_API_KEY
            return result
    except Exception as e:
        logger.debug(f"Google Maps search failed: {e}")
    return result


async def _clearbit_free(domain: str) -> dict:
    """Query Clearbit's free company API."""
    result = {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://company.clearbit.com/v2/companies/find?domain={domain}",
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("metrics", {}).get("employees"):
                    emp = data["metrics"]["employees"]
                    result["company_size_estimate"] = _employees_to_range(emp)
                if data.get("category", {}).get("industry"):
                    result["industry_tag"] = data["category"]["industry"][:100]
                if data.get("linkedin", {}).get("handle"):
                    result["linkedin_url"] = f"https://linkedin.com/company/{data['linkedin']['handle']}"
    except Exception as e:
        logger.debug(f"Clearbit lookup failed for {domain}: {e}")
    return result


def _employees_to_range(count) -> str:
    """Convert employee count to range string."""
    try:
        n = int(count)
    except (TypeError, ValueError):
        return ""
    if n <= 10:
        return "1-10"
    if n <= 50:
        return "11-50"
    if n <= 200:
        return "51-200"
    if n <= 500:
        return "201-500"
    if n <= 1000:
        return "501-1000"
    return "1000+"
