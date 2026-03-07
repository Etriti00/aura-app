"""
Aura — CRM Engine
Sync leads to HubSpot and Pipedrive CRMs via their REST APIs.
"""

from datetime import datetime
from typing import Optional, Dict

from database.db_manager import DatabaseManager
from database.schema import Lead, Campaign, Settings, CrmSyncLog
from core.key_vault import KeyVault
from utils.logger import get_logger

logger = get_logger("crm_engine")

HUBSPOT_BASE = "https://api.hubapi.com"
PIPEDRIVE_BASE = "https://api.pipedrive.com"


class CRMEngine:
    """Sync Aura leads to HubSpot or Pipedrive CRM platforms."""

    def __init__(self, db_manager: DatabaseManager, key_vault: KeyVault):
        self.db_manager = db_manager
        self.key_vault = key_vault

    def _get_crm_config(self) -> Dict:
        """Load CRM platform and API key from Settings."""
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if not settings:
                    return {}
                platform = settings.crm_platform or ""
                key_enc = ""
                if platform == "hubspot":
                    key_enc = settings.hubspot_key_enc or ""
                elif platform == "pipedrive":
                    key_enc = settings.pipedrive_key_enc or ""

                api_key = ""
                if key_enc:
                    api_key = self.key_vault.decrypt(key_enc)

                return {"platform": platform, "api_key": api_key}
        except Exception as e:
            logger.error(f"CRM config load error: {e}")
            return {}

    # ─── HubSpot ───────────────────────────────────────────────────

    def sync_lead_to_hubspot(self, lead_id: int) -> dict:
        """Sync a single lead to HubSpot as a contact."""
        config = self._get_crm_config()
        if config.get("platform") != "hubspot" or not config.get("api_key"):
            return {"success": False, "error": "HubSpot not configured"}

        try:
            import httpx

            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if not lead:
                    return {"success": False, "error": "Lead not found"}

                payload = {
                    "properties": {
                        "email": lead.email or "",
                        "company": lead.business_name or "",
                        "phone": lead.phone or "",
                        "city": lead.city or "",
                        "website": lead.website_url or "",
                        "hs_lead_status": self._map_status_to_hubspot(lead.status),
                    }
                }

            resp = httpx.post(
                f"{HUBSPOT_BASE}/crm/v3/objects/contacts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )

            if resp.status_code in (200, 201):
                crm_id = resp.json().get("id", "")
                self._log_sync(lead_id, "hubspot", crm_id, "synced")
                return {"success": True, "crm_record_id": crm_id}
            elif resp.status_code == 409:
                # Contact already exists — update instead
                return self._update_hubspot_contact(lead_id, config["api_key"])
            else:
                error = resp.text[:200]
                self._log_sync(lead_id, "hubspot", "", "failed", error)
                return {"success": False, "error": f"HubSpot {resp.status_code}: {error}"}

        except Exception as e:
            self._log_sync(lead_id, "hubspot", "", "failed", str(e))
            return {"success": False, "error": str(e)}

    def _update_hubspot_contact(self, lead_id: int, api_key: str) -> dict:
        """Update an existing HubSpot contact by email search."""
        try:
            import httpx

            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if not lead or not lead.email:
                    return {"success": False, "error": "No email for update"}

            # Search for existing contact
            search_resp = httpx.post(
                f"{HUBSPOT_BASE}/crm/v3/objects/contacts/search",
                json={"filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": lead.email}]}]},
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=15,
            )

            if search_resp.status_code == 200:
                results = search_resp.json().get("results", [])
                if results:
                    crm_id = results[0].get("id", "")
                    self._log_sync(lead_id, "hubspot", crm_id, "synced")
                    return {"success": True, "crm_record_id": crm_id}

            return {"success": False, "error": "Contact exists but could not be updated"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _map_status_to_hubspot(status: str) -> str:
        mapping = {
            "new": "NEW", "qualified": "OPEN", "emailed": "IN_PROGRESS",
            "replied": "OPEN_DEAL", "disqualified": "UNQUALIFIED",
        }
        return mapping.get(status, "NEW")

    # ─── Pipedrive ─────────────────────────────────────────────────

    def sync_lead_to_pipedrive(self, lead_id: int) -> dict:
        """Sync a single lead to Pipedrive as a person + deal."""
        config = self._get_crm_config()
        if config.get("platform") != "pipedrive" or not config.get("api_key"):
            return {"success": False, "error": "Pipedrive not configured"}

        try:
            import httpx

            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if not lead:
                    return {"success": False, "error": "Lead not found"}

                person_payload = {
                    "name": lead.business_name or "Unknown",
                    "email": [{"value": lead.email or "", "primary": True}],
                    "phone": [{"value": lead.phone or "", "primary": True}],
                }

            # Create person
            resp = httpx.post(
                f"{PIPEDRIVE_BASE}/v1/persons",
                params={"api_token": config["api_key"]},
                json=person_payload,
                timeout=15,
            )

            if resp.status_code not in (200, 201):
                error = resp.text[:200]
                self._log_sync(lead_id, "pipedrive", "", "failed", error)
                return {"success": False, "error": f"Pipedrive {resp.status_code}: {error}"}

            person_data = resp.json().get("data", {})
            person_id = person_data.get("id", "")

            # Create deal linked to person
            deal_payload = {
                "title": f"Aura Lead: {lead.business_name or 'Unknown'}",
                "person_id": person_id,
                "status": "open",
            }
            deal_resp = httpx.post(
                f"{PIPEDRIVE_BASE}/v1/deals",
                params={"api_token": config["api_key"]},
                json=deal_payload,
                timeout=15,
            )

            crm_id = str(person_id)
            if deal_resp.status_code in (200, 201):
                deal_id = deal_resp.json().get("data", {}).get("id", "")
                crm_id = f"person:{person_id},deal:{deal_id}"

            self._log_sync(lead_id, "pipedrive", crm_id, "synced")
            return {"success": True, "crm_record_id": crm_id}

        except Exception as e:
            self._log_sync(lead_id, "pipedrive", "", "failed", str(e))
            return {"success": False, "error": str(e)}

    # ─── Batch sync ────────────────────────────────────────────────

    def sync_campaign_to_crm(self, campaign_id: int, status_filter: str = None) -> dict:
        """Sync all leads in a campaign to the configured CRM."""
        config = self._get_crm_config()
        platform = config.get("platform", "")
        if not platform or not config.get("api_key"):
            return {"success": False, "error": "CRM not configured", "synced": 0, "failed": 0}

        try:
            with self.db_manager.session_scope() as session:
                query = session.query(Lead).filter_by(campaign_id=campaign_id)
                if status_filter:
                    query = query.filter_by(status=status_filter)
                lead_ids = [l.id for l in query.all()]

            synced = 0
            failed = 0
            errors = []

            for lid in lead_ids:
                if platform == "hubspot":
                    result = self.sync_lead_to_hubspot(lid)
                elif platform == "pipedrive":
                    result = self.sync_lead_to_pipedrive(lid)
                else:
                    result = {"success": False, "error": f"Unknown platform: {platform}"}

                if result.get("success"):
                    synced += 1
                else:
                    failed += 1
                    errors.append(f"Lead {lid}: {result.get('error', 'Unknown')}")

            return {"success": True, "synced": synced, "failed": failed, "errors": errors}
        except Exception as e:
            return {"success": False, "error": str(e), "synced": 0, "failed": 0}

    def get_sync_status(self, lead_id: int) -> dict:
        """Get the latest CRM sync status for a lead."""
        try:
            with self.db_manager.session_scope() as session:
                log = (
                    session.query(CrmSyncLog)
                    .filter_by(lead_id=lead_id)
                    .order_by(CrmSyncLog.created_at.desc())
                    .first()
                )
                if not log:
                    return {"synced": False}
                return {
                    "synced": log.sync_status == "synced",
                    "platform": log.crm_platform,
                    "crm_record_id": log.crm_record_id,
                    "status": log.sync_status,
                    "synced_at": str(log.synced_at) if log.synced_at else "",
                    "error": log.error_message or "",
                }
        except Exception:
            return {"synced": False}

    def test_connection(self) -> dict:
        """Test CRM API connection."""
        config = self._get_crm_config()
        if not config.get("platform") or not config.get("api_key"):
            return {"success": False, "error": "CRM not configured"}

        try:
            import httpx
            if config["platform"] == "hubspot":
                resp = httpx.get(
                    f"{HUBSPOT_BASE}/crm/v3/objects/contacts",
                    headers={"Authorization": f"Bearer {config['api_key']}"},
                    params={"limit": 1},
                    timeout=10,
                )
                return {"success": resp.status_code == 200, "error": "" if resp.status_code == 200 else resp.text[:200]}
            elif config["platform"] == "pipedrive":
                resp = httpx.get(
                    f"{PIPEDRIVE_BASE}/v1/persons",
                    params={"api_token": config["api_key"], "limit": 1},
                    timeout=10,
                )
                return {"success": resp.status_code == 200, "error": "" if resp.status_code == 200 else resp.text[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)}

        return {"success": False, "error": "Unknown platform"}

    # ─── Logging ───────────────────────────────────────────────────

    def _log_sync(self, lead_id: int, platform: str, crm_id: str,
                  status: str, error: str = None):
        """Log a CRM sync attempt."""
        try:
            with self.db_manager.session_scope() as session:
                log = CrmSyncLog(
                    lead_id=lead_id,
                    crm_platform=platform,
                    crm_record_id=crm_id,
                    sync_status=status,
                    synced_at=datetime.utcnow() if status == "synced" else None,
                    error_message=error,
                    created_at=datetime.utcnow(),
                )
                session.add(log)
        except Exception as e:
            logger.warning(f"Failed to log CRM sync: {e}")
