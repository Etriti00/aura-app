"""
Aura — Hunter.io Engine
Email finder, domain search, and email verification via Hunter's API.
All requests route through APIQueue for rate limiting with header-based pause.
"""

from typing import Optional, List, Dict
from database.db_manager import DatabaseManager
from core.key_vault import KeyVault
from utils.logger import get_logger

logger = get_logger("hunter_engine")

HUNTER_BASE_URL = "https://api.hunter.io"


class HunterEngine:
    """Hunter.io API integration for email finding and verification."""

    def __init__(self, db_manager: DatabaseManager, key_vault: KeyVault, api_queue=None):
        self.db_manager = db_manager
        self.key_vault = key_vault
        self.api_queue = api_queue

    def _get_api_key(self) -> Optional[str]:
        """Decrypt Hunter API key at moment of use."""
        try:
            from database.schema import Settings
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings and settings.hunter_key_enc:
                    return self.key_vault.decrypt(settings.hunter_key_enc)
        except Exception as e:
            logger.error(f"Failed to decrypt Hunter key: {e}")
        return None

    def find_email(self, domain: str, first_name: str = None,
                   last_name: str = None) -> dict:
        """
        Find email for a person at a domain.
        Returns: {"success": bool, "data": {"email": str, "score": int, "sources": list}, "error": str|None}
        """
        api_key = self._get_api_key()
        if not api_key:
            return {"success": False, "data": {}, "error": "Hunter API key not configured"}

        if not self.api_queue:
            return {"success": False, "data": {}, "error": "API queue not initialized"}

        params = {"domain": domain, "api_key": api_key}
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name

        result = self.api_queue.request(
            service="hunter",
            method="GET",
            url=f"{HUNTER_BASE_URL}/v2/email-finder",
            params=params,
        )

        if not result["success"]:
            return {"success": False, "data": {}, "error": result.get("error")}

        data = result.get("data", {}).get("data", {})
        return {
            "success": True,
            "data": {
                "email": data.get("email", ""),
                "score": data.get("score", 0),
                "sources": data.get("sources", []),
                "position": data.get("position", ""),
                "first_name": data.get("first_name", ""),
                "last_name": data.get("last_name", ""),
            },
            "error": None,
        }

    def domain_search(self, domain: str, limit: int = 10) -> dict:
        """
        Search all emails at a domain.
        Returns: {"success": bool, "data": [{"email": str, "type": str, "confidence": int}], "error": str|None}
        """
        api_key = self._get_api_key()
        if not api_key:
            return {"success": False, "data": [], "error": "Hunter API key not configured"}

        if not self.api_queue:
            return {"success": False, "data": [], "error": "API queue not initialized"}

        params = {
            "domain": domain,
            "api_key": api_key,
            "limit": min(limit, 100),
        }

        result = self.api_queue.request(
            service="hunter",
            method="GET",
            url=f"{HUNTER_BASE_URL}/v2/domain-search",
            params=params,
        )

        if not result["success"]:
            return {"success": False, "data": [], "error": result.get("error")}

        emails_data = result.get("data", {}).get("data", {}).get("emails", [])
        parsed = []
        for entry in emails_data:
            parsed.append({
                "email": entry.get("value", ""),
                "type": entry.get("type", ""),
                "confidence": entry.get("confidence", 0),
                "first_name": entry.get("first_name", ""),
                "last_name": entry.get("last_name", ""),
                "position": entry.get("position", ""),
            })

        return {"success": True, "data": parsed, "error": None}

    def verify_email(self, email: str) -> dict:
        """
        Verify an email address.
        Returns: {"success": bool, "data": {"valid": bool, "score": int, "disposable": bool, "webmail": bool}, "error": str|None}
        """
        api_key = self._get_api_key()
        if not api_key:
            return {"success": False, "data": {}, "error": "Hunter API key not configured"}

        if not self.api_queue:
            return {"success": False, "data": {}, "error": "API queue not initialized"}

        params = {"email": email, "api_key": api_key}

        result = self.api_queue.request(
            service="hunter",
            method="GET",
            url=f"{HUNTER_BASE_URL}/v2/email-verifier",
            params=params,
        )

        if not result["success"]:
            return {"success": False, "data": {}, "error": result.get("error")}

        data = result.get("data", {}).get("data", {})
        score = data.get("score", 0)
        status = data.get("status", "unknown")

        return {
            "success": True,
            "data": {
                "valid": status in ("valid", "accept_all") and score >= 50,
                "score": score,
                "status": status,
                "disposable": data.get("disposable", False),
                "webmail": data.get("webmail", False),
            },
            "error": None,
        }

    def map_hunter_results_to_leads(self, hunter_records: list,
                                     campaign_id: int = None) -> list:
        """Convert Hunter domain search results to Aura lead dicts."""
        leads = []
        for record in hunter_records:
            if not record.get("email"):
                continue
            leads.append({
                "business_name": "",
                "category": "",
                "address": "",
                "city": "",
                "country": "",
                "phone": "",
                "email": record["email"],
                "source_url": "",
                "source_platform": "hunter",
                "has_website": True,
                "website_url": "",
                "snippet": f"{record.get('first_name', '')} {record.get('last_name', '')} — {record.get('position', '')}",
                "hunter_email_confidence": record.get("confidence", 0),
            })
        return leads
