"""
Aura — Apollo.io Engine
People search, email finder, and company enrichment via Apollo's API.
All requests route through APIQueue for rate limiting.
"""

from typing import Optional, List, Dict
from database.db_manager import DatabaseManager
from core.key_vault import KeyVault
from utils.logger import get_logger

logger = get_logger("apollo_engine")

APOLLO_BASE_URL = "https://api.apollo.io"


class ApolloEngine:
    """Apollo.io API integration for people search, enrichment, and company lookup."""

    def __init__(self, db_manager: DatabaseManager, key_vault: KeyVault, api_queue=None):
        self.db_manager = db_manager
        self.key_vault = key_vault
        self.api_queue = api_queue

    def _get_api_key(self) -> Optional[str]:
        """Decrypt Apollo API key at moment of use."""
        try:
            from database.schema import Settings
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings and settings.apollo_key_enc:
                    return self.key_vault.decrypt(settings.apollo_key_enc)
        except Exception as e:
            logger.error(f"Failed to decrypt Apollo key: {e}")
        return None

    def _headers(self, api_key: str) -> dict:
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": api_key,
        }

    def search_people(self, niche: str = "", city: str = "",
                      company_size_max: int = 50,
                      title_keywords: List[str] = None,
                      limit: int = 50) -> dict:
        """
        Search Apollo for people matching criteria.
        Returns: {"success": bool, "data": [person_dicts], "error": str|None}
        """
        api_key = self._get_api_key()
        if not api_key:
            return {"success": False, "data": [], "error": "Apollo API key not configured"}

        if not self.api_queue:
            return {"success": False, "data": [], "error": "API queue not initialized"}

        # Build search payload
        payload = {
            "per_page": min(limit, 100),
            "page": 1,
        }

        if title_keywords:
            payload["person_titles"] = title_keywords

        if city:
            payload["organization_locations"] = [city]

        if niche:
            payload["q_keywords"] = niche

        if company_size_max:
            # Apollo expects ranges like "1,10", "11,50", etc.
            if company_size_max <= 10:
                payload["organization_num_employees_ranges"] = ["1,10"]
            elif company_size_max <= 50:
                payload["organization_num_employees_ranges"] = ["1,10", "11,50"]
            elif company_size_max <= 200:
                payload["organization_num_employees_ranges"] = ["1,10", "11,50", "51,200"]
            else:
                payload["organization_num_employees_ranges"] = ["1,10", "11,50", "51,200", "201,500"]

        result = self.api_queue.request(
            service="apollo",
            method="POST",
            url=f"{APOLLO_BASE_URL}/v1/mixed_people/search",
            headers=self._headers(api_key),
            json_data=payload,
        )

        if not result["success"]:
            return {"success": False, "data": [], "error": result.get("error", "Apollo API error")}

        people = result.get("data", {}).get("people", [])
        return {"success": True, "data": people, "error": None}

    def enrich_person(self, email: str = None, linkedin_url: str = None) -> dict:
        """
        Enrich a person via Apollo people match.
        Returns: {"success": bool, "data": {enriched_record}, "error": str|None}
        """
        api_key = self._get_api_key()
        if not api_key:
            return {"success": False, "data": {}, "error": "Apollo API key not configured"}

        if not self.api_queue:
            return {"success": False, "data": {}, "error": "API queue not initialized"}

        payload = {}
        if email:
            payload["email"] = email
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url

        if not payload:
            return {"success": False, "data": {}, "error": "Provide email or linkedin_url"}

        result = self.api_queue.request(
            service="apollo",
            method="POST",
            url=f"{APOLLO_BASE_URL}/v1/people/match",
            headers=self._headers(api_key),
            json_data=payload,
        )

        if not result["success"]:
            return {"success": False, "data": {}, "error": result.get("error")}

        person = result.get("data", {}).get("person", {})
        return {"success": True, "data": person or {}, "error": None}

    def search_organizations(self, niche: str = "", city: str = "",
                              employee_max: int = 50) -> dict:
        """
        Search Apollo for organizations.
        Returns: {"success": bool, "data": [org_dicts], "error": str|None}
        """
        api_key = self._get_api_key()
        if not api_key:
            return {"success": False, "data": [], "error": "Apollo API key not configured"}

        if not self.api_queue:
            return {"success": False, "data": [], "error": "API queue not initialized"}

        payload = {"per_page": 50, "page": 1}

        if niche:
            payload["q_keywords"] = niche
        if city:
            payload["organization_locations"] = [city]
        if employee_max:
            if employee_max <= 50:
                payload["organization_num_employees_ranges"] = ["1,10", "11,50"]
            else:
                payload["organization_num_employees_ranges"] = ["1,10", "11,50", "51,200"]

        result = self.api_queue.request(
            service="apollo",
            method="POST",
            url=f"{APOLLO_BASE_URL}/v1/mixed_companies/search",
            headers=self._headers(api_key),
            json_data=payload,
        )

        if not result["success"]:
            return {"success": False, "data": [], "error": result.get("error")}

        orgs = result.get("data", {}).get("organizations", [])
        return {"success": True, "data": orgs, "error": None}

    def map_to_lead(self, apollo_record: dict) -> dict:
        """
        Convert a raw Apollo person record to Aura's Lead field format.
        Compatible with scraper_engine output so same qualification pipeline applies.
        """
        org = apollo_record.get("organization", {}) or {}
        return {
            "business_name": org.get("name", apollo_record.get("organization_name", "")),
            "category": org.get("industry", ""),
            "address": "",
            "city": org.get("city", ""),
            "country": org.get("country", ""),
            "phone": (apollo_record.get("phone_numbers") or [{}])[0].get("sanitized_number", "")
                     if apollo_record.get("phone_numbers") else "",
            "email": apollo_record.get("email", ""),
            "source_url": apollo_record.get("linkedin_url", ""),
            "source_platform": "apollo",
            "has_website": bool(org.get("website_url")),
            "website_url": org.get("website_url", ""),
            "snippet": f"{apollo_record.get('title', '')} at {org.get('name', '')}",
            "apollo_person_id": apollo_record.get("id", ""),
        }
