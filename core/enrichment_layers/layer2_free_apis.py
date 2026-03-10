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


def enrich_layer2_sync(domain: str, business_name: str = "",
                       city: str = "", gmaps_api_key: str = "",
                       db_manager=None) -> dict:
    """Synchronous Layer 2 enrichment using httpx.Client."""
    result = {}

    if domain and _check_daily_limit_db("clearbit", CLEARBIT_FREE_DAILY_LIMIT, db_manager):
        result.update(_clearbit_free_sync(domain))
        _increment_counter_db("clearbit", db_manager)

    if business_name and _check_daily_limit_db("gmaps", GMAPS_FREE_DAILY_LIMIT, db_manager):
        result.update(_search_gmaps_sync(business_name, city, gmaps_api_key))
        _increment_counter_db("gmaps", db_manager)

    return result


def _clearbit_free_sync(domain: str) -> dict:
    """Synchronous Clearbit free company API."""
    result = {}
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"https://company.clearbit.com/v2/companies/find?domain={domain}",
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("metrics", {}).get("employees"):
                    result["company_size_estimate"] = _employees_to_range(data["metrics"]["employees"])
                if data.get("category", {}).get("industry"):
                    result["industry_tag"] = data["category"]["industry"][:100]
                if data.get("linkedin", {}).get("handle"):
                    result["linkedin_url"] = f"https://linkedin.com/company/{data['linkedin']['handle']}"
    except Exception as e:
        logger.debug(f"Clearbit sync failed for {domain}: {e}")
    return result


def _search_gmaps_sync(business_name: str, city: str = "",
                       api_key: str = "") -> dict:
    """Search Google Maps Places API for business data."""
    if not api_key:
        return {}
    result = {}
    query = f"{business_name} {city}".strip()
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
                params={
                    "input": query,
                    "inputtype": "textquery",
                    "fields": "formatted_phone_number,rating,user_ratings_total,types,business_status",
                    "key": api_key,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    c = candidates[0]
                    if c.get("formatted_phone_number"):
                        result["gmaps_phone"] = c["formatted_phone_number"]
                    if c.get("rating"):
                        result["google_maps_rating"] = c["rating"]
                    if c.get("user_ratings_total"):
                        result["google_maps_review_count"] = c["user_ratings_total"]
                    if c.get("types"):
                        result["gmaps_category"] = ", ".join(c["types"][:3])
    except Exception as e:
        logger.debug(f"Google Maps sync search failed: {e}")
    return result


def _check_daily_limit_db(source: str, limit: int, db_manager=None) -> bool:
    """Check daily limit using DB persistence, falling back to in-memory."""
    if not db_manager:
        return _check_daily_limit(source, limit)
    try:
        from database.schema import Settings
        with db_manager.session_scope() as session:
            settings = session.query(Settings).first()
            if not settings:
                return True
            counter_field = f"enrichment_{source}_count"
            date_field = f"enrichment_{source}_date"
            current_date = date.today().isoformat()

            count = getattr(settings, counter_field, 0) or 0
            stored_date = getattr(settings, date_field, "") or ""

            if stored_date != current_date:
                return True  # new day
            return count < limit
    except Exception:
        return _check_daily_limit(source, limit)


def _increment_counter_db(source: str, db_manager=None):
    """Increment daily counter in DB, falling back to in-memory."""
    _increment_counter(source)  # always update in-memory too
    if not db_manager:
        return
    try:
        from database.schema import Settings
        with db_manager.session_scope() as session:
            settings = session.query(Settings).first()
            if not settings:
                return
            counter_field = f"enrichment_{source}_count"
            date_field = f"enrichment_{source}_date"
            current_date = date.today().isoformat()

            stored_date = getattr(settings, date_field, "") or ""
            if stored_date != current_date:
                setattr(settings, counter_field, 1)
                setattr(settings, date_field, current_date)
            else:
                count = getattr(settings, counter_field, 0) or 0
                setattr(settings, counter_field, count + 1)
    except Exception as e:
        logger.debug(f"Failed to persist counter for {source}: {e}")


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
