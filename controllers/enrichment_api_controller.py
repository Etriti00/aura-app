"""
Aura — Enrichment API Controller
Owns QThread for Apollo/Hunter API operations. Bridges core engines to UI.
"""

from PySide6.QtCore import QObject, Signal

from database.db_manager import DatabaseManager
from database.schema import Lead, Settings
from core.apollo_engine import ApolloEngine
from core.hunter_engine import HunterEngine
from core.suppression_engine import SuppressionEngine
from utils.thread_worker import ThreadWorker
from utils.logger import get_logger

logger = get_logger("enrichment_api_controller")


class EnrichmentApiController(QObject):
    """Controller for Apollo/Hunter API enrichment operations."""

    # Signals
    lead_enriched = Signal(int, dict)       # lead_id, enrichment_data
    search_progress = Signal(int)           # 0-100
    search_finished = Signal(int)           # total leads found
    error = Signal(str)                     # error message
    rate_limited = Signal(str, int)         # service, wait_seconds
    status_message = Signal(str)            # human-readable status

    def __init__(self, db_manager: DatabaseManager,
                 apollo_engine: ApolloEngine,
                 hunter_engine: HunterEngine,
                 suppression_engine: SuppressionEngine = None):
        super().__init__()
        self.db_manager = db_manager
        self.apollo = apollo_engine
        self.hunter = hunter_engine
        self.suppression = suppression_engine
        self._worker = None

    def enrich_lead_with_apis(self, lead_id: int):
        """Enrich a single lead via Hunter verification + Apollo fallback. Runs in ThreadWorker."""
        def _work(_progress_callback=None, _cancel_checker=None):
            return self._do_enrich_lead(lead_id)

        self._worker = ThreadWorker(_work)
        self._worker.signals.result.connect(self._on_enrich_result)
        self._worker.signals.error.connect(lambda msg: self.error.emit(msg))
        self._worker.start()

    def _do_enrich_lead(self, lead_id: int) -> dict:
        """Core enrichment logic — runs in background thread."""
        with self.db_manager.session_scope() as session:
            lead = session.query(Lead).get(lead_id)
            if not lead:
                return {"success": False, "error": "Lead not found"}

            # Check suppression list first
            if self.suppression and self.suppression.is_suppressed(
                email=lead.email or "", domain=""
            ):
                return {"success": False, "error": "Lead is suppressed"}

            email = lead.email or ""
            domain = ""
            if lead.website_url:
                from urllib.parse import urlparse
                parsed = urlparse(lead.website_url if "://" in lead.website_url
                                  else f"https://{lead.website_url}")
                domain = parsed.netloc or parsed.path.split("/")[0]

            enriched = {}

            # Step 1: Verify existing email via Hunter
            if email and self.hunter:
                verify = self.hunter.verify_email(email)
                if verify["success"] and verify["data"]:
                    if not verify["data"]["valid"]:
                        enriched["email_invalid"] = True
                        email = ""  # Clear bad email, try to find a new one
                    else:
                        enriched["hunter_email_confidence"] = verify["data"]["score"]

            # Step 2: Find email via Hunter domain search if missing
            if not email and domain and self.hunter:
                search = self.hunter.domain_search(domain, limit=5)
                if search["success"] and search["data"]:
                    # Pick the highest confidence email
                    best = max(search["data"], key=lambda x: x.get("confidence", 0))
                    if best.get("confidence", 0) >= 50:
                        email = best["email"]
                        enriched["email"] = email
                        enriched["hunter_email_confidence"] = best["confidence"]

            # Step 3: Apollo fallback if still no email
            if not email and self.apollo:
                apollo_result = None
                if lead.website_url:
                    apollo_result = self.apollo.enrich_person(
                        linkedin_url=lead.source_url if "linkedin" in (lead.source_url or "") else None
                    )
                if apollo_result and apollo_result["success"] and apollo_result["data"]:
                    person = apollo_result["data"]
                    if person.get("email"):
                        email = person["email"]
                        enriched["email"] = email
                        enriched["apollo_person_id"] = person.get("id", "")

            # Update lead (session_scope auto-commits on exit)
            if enriched:
                if "email" in enriched and enriched["email"]:
                    lead.email = enriched["email"]

            return {"success": True, "data": enriched, "lead_id": lead_id, "error": None}

    def _on_enrich_result(self, result):
        if result.get("success"):
            self.lead_enriched.emit(result.get("lead_id", 0), result.get("data", {}))
        else:
            self.error.emit(result.get("error", "Enrichment failed"))

    def search_apollo_for_campaign(self, campaign_id: int, niche: str,
                                    city: str, title_keywords: list = None,
                                    employee_max: int = 50, limit: int = 50):
        """Search Apollo for leads and save to campaign. Runs in ThreadWorker."""
        def _work(_progress_callback=None, _cancel_checker=None):
            return self._do_apollo_search(
                campaign_id, niche, city, title_keywords, employee_max, limit,
                _progress_callback, _cancel_checker,
            )

        self._worker = ThreadWorker(_work)
        self._worker.signals.result.connect(self._on_search_result)
        self._worker.signals.error.connect(lambda msg: self.error.emit(msg))
        self._worker.signals.progress.connect(self.search_progress.emit)
        self._worker.start()

    def _do_apollo_search(self, campaign_id, niche, city, title_keywords,
                           employee_max, limit, progress_cb, cancel_checker):
        """Apollo search + save — runs in background thread."""
        self.status_message.emit("Searching Apollo.io...")

        result = self.apollo.search_people(
            niche=niche,
            city=city,
            company_size_max=employee_max,
            title_keywords=title_keywords,
            limit=limit,
        )

        if result.get("rate_limited"):
            wait = result.get("retry_after", 60)
            self.rate_limited.emit("apollo", int(wait))
            return {"success": False, "error": f"Apollo rate limited — retry in {int(wait)}s"}

        if not result["success"]:
            return {"success": False, "error": result.get("error", "Apollo search failed")}

        people = result["data"]
        if not people:
            return {"success": True, "data": [], "total": 0, "error": None}

        saved = 0
        total = len(people)

        for i, person in enumerate(people):
            if cancel_checker and cancel_checker():
                break

            lead_dict = self.apollo.map_to_lead(person)

            # Check suppression
            if self.suppression and self.suppression.is_suppressed(
                email=lead_dict.get("email", ""), domain=""
            ):
                continue

            # Save to DB
            with self.db_manager.session_scope() as session:
                lead = Lead(
                    campaign_id=campaign_id,
                    business_name=lead_dict.get("business_name", ""),
                    category=lead_dict.get("category", ""),
                    city=lead_dict.get("city", ""),
                    country=lead_dict.get("country", ""),
                    phone=lead_dict.get("phone", ""),
                    email=lead_dict.get("email", ""),
                    source_url=lead_dict.get("source_url", ""),
                    source_platform="apollo",
                    has_website=lead_dict.get("has_website", False),
                    website_url=lead_dict.get("website_url", ""),
                    status="new",
                )
                session.add(lead)

            saved += 1
            self.lead_enriched.emit(0, lead_dict)

            if progress_cb:
                progress_cb(int((i + 1) / total * 100))

        return {"success": True, "data": [], "total": saved, "error": None}

    def _on_search_result(self, result):
        total = result.get("total", 0)
        self.search_finished.emit(total)
        if result.get("error"):
            self.error.emit(result["error"])
        else:
            self.status_message.emit(f"Apollo search complete — {total} leads found")
