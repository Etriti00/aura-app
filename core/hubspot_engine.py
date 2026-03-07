"""
Aura — HubSpot Engine
Contact search, company lookup, and contact enrichment via HubSpot CRM API.
All requests route through APIQueue for rate limiting.
"""

from typing import Optional, List, Dict
from database.db_manager import DatabaseManager
from core.key_vault import KeyVault
from utils.logger import get_logger

logger = get_logger("hubspot_engine")

HUBSPOT_BASE_URL = "https://api.hubapi.com"


class HubSpotEngine:
    """HubSpot CRM API integration for contact search and enrichment."""

    def __init__(self, db_manager: DatabaseManager, key_vault: KeyVault, api_queue=None):
        self.db_manager = db_manager
        self.key_vault = key_vault
        self.api_queue = api_queue

    def _get_api_key(self) -> Optional[str]:
        """Decrypt HubSpot API key at moment of use."""
        try:
            from database.schema import Settings
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings and settings.hubspot_key_enc:
                    return self.key_vault.decrypt(settings.hubspot_key_enc)
        except Exception as e:
            logger.error(f"Failed to decrypt HubSpot key: {e}")
        return None

    def _headers(self, api_key: str) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    def search_contacts(self, niche: str = "", city: str = "",
                        company_name: str = "", limit: int = 50) -> dict:
        """
        Search HubSpot CRM for contacts matching criteria.
        Uses the CRM Search API v3.
        Returns: {"success": bool, "data": [contact_dicts], "error": str|None}
        """
        api_key = self._get_api_key()
        if not api_key:
            return {"success": False, "data": [], "error": "HubSpot API key not configured"}

        if not self.api_queue:
            return {"success": False, "data": [], "error": "API queue not initialized"}

        # Build filter groups
        filter_groups = []
        filters = []

        if city:
            filters.append({
                "propertyName": "city",
                "operator": "CONTAINS_TOKEN",
                "value": city,
            })

        if company_name:
            filters.append({
                "propertyName": "company",
                "operator": "CONTAINS_TOKEN",
                "value": company_name,
            })

        if niche:
            filters.append({
                "propertyName": "jobtitle",
                "operator": "CONTAINS_TOKEN",
                "value": niche,
            })

        if filters:
            filter_groups.append({"filters": filters})

        payload = {
            "limit": min(limit, 100),
            "properties": [
                "firstname", "lastname", "email", "phone", "company",
                "jobtitle", "city", "state", "country", "website",
                "industry", "hs_lead_status",
            ],
        }

        if filter_groups:
            payload["filterGroups"] = filter_groups

        result = self.api_queue.request(
            service="hubspot",
            method="POST",
            url=f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/search",
            headers=self._headers(api_key),
            json_data=payload,
        )

        if not result["success"]:
            return {"success": False, "data": [], "error": result.get("error", "HubSpot API error")}

        contacts = result.get("data", {}).get("results", [])
        return {"success": True, "data": contacts, "error": None}

    def search_companies(self, domain: str = "", name: str = "",
                         limit: int = 20) -> dict:
        """
        Search HubSpot CRM for companies.
        Returns: {"success": bool, "data": [company_dicts], "error": str|None}
        """
        api_key = self._get_api_key()
        if not api_key:
            return {"success": False, "data": [], "error": "HubSpot API key not configured"}

        if not self.api_queue:
            return {"success": False, "data": [], "error": "API queue not initialized"}

        filters = []
        if domain:
            filters.append({
                "propertyName": "domain",
                "operator": "CONTAINS_TOKEN",
                "value": domain,
            })
        if name:
            filters.append({
                "propertyName": "name",
                "operator": "CONTAINS_TOKEN",
                "value": name,
            })

        payload = {
            "limit": min(limit, 100),
            "properties": [
                "name", "domain", "industry", "city", "state", "country",
                "numberofemployees", "phone", "website",
            ],
        }

        if filters:
            payload["filterGroups"] = [{"filters": filters}]

        result = self.api_queue.request(
            service="hubspot",
            method="POST",
            url=f"{HUBSPOT_BASE_URL}/crm/v3/objects/companies/search",
            headers=self._headers(api_key),
            json_data=payload,
        )

        if not result["success"]:
            return {"success": False, "data": [], "error": result.get("error")}

        companies = result.get("data", {}).get("results", [])
        return {"success": True, "data": companies, "error": None}

    def enrich_contact(self, email: str) -> dict:
        """
        Look up a single contact by email in HubSpot CRM.
        Returns: {"success": bool, "data": {contact_props}, "error": str|None}
        """
        api_key = self._get_api_key()
        if not api_key:
            return {"success": False, "data": {}, "error": "HubSpot API key not configured"}

        if not self.api_queue:
            return {"success": False, "data": {}, "error": "API queue not initialized"}

        payload = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "email",
                    "operator": "EQ",
                    "value": email,
                }]
            }],
            "properties": [
                "firstname", "lastname", "email", "phone", "company",
                "jobtitle", "city", "state", "country", "website",
                "industry", "hs_lead_status",
            ],
            "limit": 1,
        }

        result = self.api_queue.request(
            service="hubspot",
            method="POST",
            url=f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/search",
            headers=self._headers(api_key),
            json_data=payload,
        )

        if not result["success"]:
            return {"success": False, "data": {}, "error": result.get("error")}

        results = result.get("data", {}).get("results", [])
        if not results:
            return {"success": True, "data": {}, "error": None}

        props = results[0].get("properties", {})
        return {"success": True, "data": props, "error": None}

    def map_to_lead(self, hubspot_record: dict) -> dict:
        """
        Convert a raw HubSpot contact record to Aura's Lead field format.
        Compatible with scraper_engine output so same qualification pipeline applies.
        """
        props = hubspot_record.get("properties", hubspot_record)
        first = props.get("firstname", "")
        last = props.get("lastname", "")
        company = props.get("company", "")

        return {
            "business_name": company or f"{first} {last}".strip(),
            "category": props.get("industry", ""),
            "address": "",
            "city": props.get("city", ""),
            "country": props.get("country", ""),
            "phone": props.get("phone", ""),
            "email": props.get("email", ""),
            "source_url": "",
            "source_platform": "hubspot",
            "has_website": bool(props.get("website")),
            "website_url": props.get("website", ""),
            "snippet": f"{first} {last} — {props.get('jobtitle', '')} at {company}".strip(),
            "hubspot_contact_id": hubspot_record.get("id", ""),
        }
