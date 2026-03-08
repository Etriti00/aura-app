"""
Aura — Hunter Controller
MVC bridge: connects Hunter UI events to the scraper engine via background threads.
Creates campaigns, saves leads to DB individually, applies Tier 1 filtering.
Orchestrates multi-source hunting: scrapers + API sources + CSV imports.
"""

import json
from dataclasses import asdict

from PySide6.QtCore import QObject, Signal

from core.scraper_engine import ScraperEngine, ScrapedLead
from config import LEAD_SOURCES
from database.db_manager import DatabaseManager
from database.schema import Campaign, Lead
from utils.thread_worker import ThreadWorker
from utils.logger import get_logger

logger = get_logger("hunter_controller")


class HunterController(QObject):
    """
    Controls the multi-source lead hunting pipeline:
    1. Creates a campaign when scraping starts
    2. Runs scrapers + API sources in background thread
    3. Saves each lead to DB immediately (crash-safe)
    4. Handles LinkedIn CSV import and HubSpot search
    5. Emits signals for UI updates
    """

    # Signals for UI updates
    lead_found = Signal(dict)           # Emitted for each new lead
    lead_enriched = Signal(int, dict)   # lead_id, enrichment_data
    lead_qualified = Signal(int, dict)  # lead_id, qualification_result
    scrape_progress = Signal(int)       # 0-100 progress
    scrape_finished = Signal(int)       # Total leads found
    scrape_error = Signal(str)          # Error message
    kill_switch_activated = Signal(int)  # Cooldown seconds remaining
    status_message = Signal(str)        # Human-readable status
    linkedin_import_finished = Signal(int, int)  # total, skipped
    hubspot_search_finished = Signal(int)         # total found

    def __init__(self, db_manager: DatabaseManager, enrichment_engine=None):
        super().__init__()
        self.db_manager = db_manager
        self.scraper = ScraperEngine()
        self.enrichment_engine = enrichment_engine
        self._worker = None
        self._current_campaign_id = None

        # API engines — injected by MainWindow
        self.apollo_engine = None
        self.hunter_engine = None
        self.hubspot_engine = None
        self.linkedin_engine = None

        # AI engines — injected by MainWindow for auto-qualification
        self.ai_engine = None
        self.lead_lifecycle_engine = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start_scrape(
        self,
        query: str,
        city: str,
        niche: str,
        campaign_name: str = "",
        limit: int = 50,
        sources: list = None,
    ):
        """Start a new scraping session in a background thread."""
        if self.is_running:
            self.scrape_error.emit("A scrape is already running.")
            return

        if self.scraper.safety.is_killed:
            remaining = self.scraper.safety.cooldown_remaining_seconds
            self.kill_switch_activated.emit(remaining)
            return

        # Create a new campaign
        if not campaign_name:
            campaign_name = f"{niche} in {city}"

        self._current_campaign_id = self._create_campaign(
            name=campaign_name,
            query=query,
            city=city,
            niche=niche,
            sources=sources or ["duckduckgo", "google_maps", "yelp"],
        )

        self.status_message.emit(f"Starting scrape: {campaign_name}")

        # Launch scraper in background thread
        self.scraper = ScraperEngine()  # Fresh instance with new fingerprint
        self._worker = ThreadWorker(
            fn=self._run_scrape,
            kwargs={
                "query": query,
                "city": city,
                "niche": niche,
                "limit": limit,
                "sources": sources,
            }
        )
        self._worker.signals.result.connect(self._on_scrape_complete)
        self._worker.signals.error.connect(self._on_scrape_error)
        self._worker.signals.progress.connect(self.scrape_progress.emit)
        self._worker.signals.finished.connect(self._on_worker_finished)
        self._worker.start()

    def stop_scrape(self):
        """Request cancellation of the running scrape."""
        if self._worker and self._worker.isRunning():
            self.scraper.safety.cancel()
            self._worker.cancel()
            self.status_message.emit("Stopping scrape...")
            logger.info("Scrape cancellation requested.")

    def _run_scrape(
        self,
        query: str,
        city: str,
        niche: str,
        limit: int,
        sources: list,
        _progress_callback=None,
        _cancel_checker=None,
    ) -> list:
        """Execute multi-source scrape (runs in background thread)."""
        # Split sources into scraper vs API
        scraper_sources = [s for s in (sources or []) if s in LEAD_SOURCES.get("scraper", [])]
        api_sources = [s for s in (sources or []) if s in LEAD_SOURCES.get("api", [])]

        all_leads = []
        seen_names = set()  # For cross-source deduplication

        # Phase 1: Run web scrapers
        if scraper_sources:
            self.status_message.emit(f"Scraping web sources: {', '.join(scraper_sources)}...")
            scraped = self.scraper.run(
                query=query,
                city=city,
                niche=niche,
                limit=limit,
                sources=scraper_sources,
                _progress_callback=_progress_callback,
                _cancel_checker=_cancel_checker,
            )
            all_leads.extend(scraped)
            for lead in scraped:
                seen_names.add(lead.business_name.lower().strip())

        # Phase 2: Query API sources
        remaining = max(0, limit - len(all_leads))
        if api_sources and remaining > 0:
            api_leads = self._query_api_sources(
                api_sources, niche, city, remaining, _cancel_checker
            )
            for lead_dict in api_leads:
                name_key = lead_dict.get("business_name", "").lower().strip()
                if name_key and name_key not in seen_names:
                    seen_names.add(name_key)
                    all_leads.append(lead_dict)

        # Start batch browser for enrichment (avoids launching Chromium per-lead)
        if self.enrichment_engine:
            try:
                self.enrichment_engine.start_batch()
            except Exception as e:
                logger.warning(f"Failed to start batch browser: {e}")

        # Phase 3: Save all leads to DB
        saved_count = 0
        try:
            for lead in all_leads:
                if _cancel_checker and _cancel_checker():
                    break

                lead_dict = self._save_lead(lead)
                if lead_dict:
                    saved_count += 1
                    self.lead_found.emit(lead_dict)

                    # Run enrichment if enabled
                    if self.enrichment_engine:
                        try:
                            enrichment_data = self.enrichment_engine.enrich_lead(lead_dict)
                            if enrichment_data:
                                self.lead_enriched.emit(lead_dict["id"], enrichment_data)
                        except Exception as e:
                            logger.warning(f"Enrichment failed for lead #{lead_dict['id']}: {e}")

                    # Auto-qualify via AI after enrichment
                    if self.ai_engine:
                        try:
                            qual = self.ai_engine.qualify_lead(lead_dict, niche)
                            with self.db_manager.session_scope() as session:
                                db_lead = session.query(Lead).filter_by(id=lead_dict["id"]).first()
                                if db_lead:
                                    if qual.get("qualified"):
                                        db_lead.status = "qualified"
                                        db_lead.notes = (db_lead.notes or "") + f"\n[Qualified] Score: {qual.get('score', 0)}/10 — {qual.get('reason', '')}"
                                    else:
                                        db_lead.status = "disqualified"
                                        db_lead.notes = (db_lead.notes or "") + f"\n[Disqualified] Score: {qual.get('score', 0)}/10 — {qual.get('reason', '')}"
                            self.lead_qualified.emit(lead_dict["id"], qual)
                            if self.lead_lifecycle_engine:
                                new_state = "qualified" if qual.get("qualified") else "disqualified"
                                self.lead_lifecycle_engine.transition(
                                    lead_dict["id"], new_state, triggered_by="auto_qualify",
                                )
                            # Auto-research qualified leads
                            if qual.get("qualified") and getattr(self, "research_engine", None):
                                try:
                                    from database.schema import Settings
                                    with self.db_manager.session_scope() as session:
                                        settings = session.query(Settings).first()
                                        auto_enabled = settings.research_auto_enabled if settings else True
                                    if auto_enabled:
                                        self.research_engine.research_lead(lead_dict["id"])
                                except Exception as re:
                                    logger.debug(f"Auto-research failed for lead #{lead_dict['id']}: {re}")
                        except Exception as e:
                            logger.warning(f"Qualification failed for lead #{lead_dict['id']}: {e}")
        finally:
            if self.enrichment_engine:
                try:
                    self.enrichment_engine.end_batch()
                except Exception:
                    pass

        # Update campaign counters
        self._update_campaign_stats()

        # Check if kill switch was triggered during scrape
        if self.scraper.safety.is_killed:
            remaining = self.scraper.safety.cooldown_remaining_seconds
            self.kill_switch_activated.emit(remaining)

        return saved_count

    def _query_api_sources(self, sources: list, niche: str, city: str,
                            limit: int, _cancel_checker=None) -> list:
        """Query API sources (Apollo, Hunter.io, HubSpot) and return lead dicts."""
        results = []

        for source in sources:
            if _cancel_checker and _cancel_checker():
                break

            try:
                if source == "apollo" and self.apollo_engine:
                    self.status_message.emit("Searching Apollo.io...")
                    resp = self.apollo_engine.search_people(
                        niche=niche, city=city, limit=min(limit, 100)
                    )
                    if resp.get("success"):
                        for person in resp.get("data", []):
                            results.append(self.apollo_engine.map_to_lead(person))

                elif source == "hunter_io" and self.hunter_engine:
                    self.status_message.emit("Searching Hunter.io...")
                    # Hunter.io is primarily domain-based; do a domain search if we have context
                    # For general hunting, this is less effective — skip unless domain available
                    pass

                elif source == "hubspot" and self.hubspot_engine:
                    self.status_message.emit("Searching HubSpot CRM...")
                    resp = self.hubspot_engine.search_contacts(
                        niche=niche, city=city, limit=min(limit, 100)
                    )
                    if resp.get("success"):
                        for contact in resp.get("data", []):
                            results.append(self.hubspot_engine.map_to_lead(contact))

            except Exception as e:
                logger.warning(f"API source '{source}' failed: {e}")

        return results[:limit]

    def _create_campaign(self, name: str, query: str, city: str, niche: str, sources: list) -> int:
        """Create a new campaign in the database."""
        with self.db_manager.session_scope() as session:
            campaign = Campaign(
                name=name,
                search_query=query,
                target_city=city,
                target_niche=niche,
                scrape_sources=json.dumps(sources),
                status="active",
            )
            session.add(campaign)
            session.flush()
            campaign_id = campaign.id
            logger.info(f"Created campaign #{campaign_id}: {name}")
            return campaign_id

    def _save_lead(self, lead: ScrapedLead) -> dict:
        """Save a single lead to the database. Returns dict for UI or None on failure."""
        try:
            with self.db_manager.session_scope() as session:
                db_lead = Lead(
                    campaign_id=self._current_campaign_id,
                    business_name=lead.business_name,
                    category=lead.category,
                    city=lead.city,
                    phone=lead.phone,
                    email=lead.email,
                    source_url=lead.source_url,
                    source_platform=lead.source_platform,
                    has_website=lead.has_website,
                    website_url=lead.website_url,
                    status="new",
                )
                session.add(db_lead)
                session.flush()

                return {
                    "id": db_lead.id,
                    "business_name": lead.business_name,
                    "category": lead.category,
                    "city": lead.city,
                    "phone": lead.phone,
                    "email": lead.email,
                    "source_platform": lead.source_platform,
                    "has_website": lead.has_website,
                    "website_url": lead.website_url,
                    "status": "new",
                }
        except Exception as e:
            logger.error(f"Failed to save lead '{lead.business_name}': {e}")
            return None

    def _update_campaign_stats(self):
        """Update denormalized campaign counters."""
        if not self._current_campaign_id:
            return

        try:
            with self.db_manager.session_scope() as session:
                campaign = session.query(Campaign).filter_by(id=self._current_campaign_id).first()
                if campaign:
                    total = session.query(Lead).filter_by(campaign_id=campaign.id).count()
                    qualified = session.query(Lead).filter_by(
                        campaign_id=campaign.id, status="qualified"
                    ).count()
                    campaign.total_leads = total
                    campaign.qualified_leads = qualified
                    logger.info(f"Campaign #{campaign.id} stats: {total} leads, {qualified} qualified")
        except Exception as e:
            logger.error(f"Failed to update campaign stats: {e}")

    def _on_scrape_complete(self, result):
        """Handle successful scrape completion."""
        count = result if isinstance(result, int) else 0
        self.status_message.emit(f"Scraping complete! Found {count} leads.")
        self.scrape_finished.emit(count)
        logger.info(f"Scrape finished: {count} leads saved.")

    def _on_scrape_error(self, error_msg: str):
        """Handle scrape error."""
        self.scrape_error.emit(error_msg)
        logger.error(f"Scrape error: {error_msg}")

    def _on_worker_finished(self):
        """Clean up after worker completes."""
        self._worker = None

    def get_campaign_leads(self, campaign_id: int = None) -> list:
        """Retrieve all leads for a campaign."""
        cid = campaign_id or self._current_campaign_id
        if not cid:
            return []

        with self.db_manager.session_scope() as session:
            leads = session.query(Lead).filter_by(campaign_id=cid).all()
            return [
                {
                    "id": l.id,
                    "business_name": l.business_name,
                    "category": l.category,
                    "city": l.city,
                    "phone": l.phone,
                    "email": l.email,
                    "source_platform": l.source_platform,
                    "has_website": l.has_website,
                    "website_url": l.website_url,
                    "status": l.status,
                }
                for l in leads
            ]

    # ─── LinkedIn CSV Import ─────────────────────────────────────────

    def import_linkedin_csv(self, file_path: str):
        """Import leads from a LinkedIn Sales Navigator CSV export."""
        if not self.linkedin_engine:
            self.scrape_error.emit("LinkedIn engine not configured.")
            return

        def _do_import():
            result = self.linkedin_engine.import_from_csv(file_path)
            if not result.get("success"):
                self.scrape_error.emit(result.get("error", "LinkedIn import failed"))
                return 0, 0

            leads = result.get("leads", [])
            skipped = result.get("skipped", 0)

            # Create a campaign for the import
            campaign_id = self._create_campaign(
                name=f"LinkedIn Import",
                query="linkedin_csv",
                city="",
                niche="",
                sources=["linkedin_csv"],
            )
            self._current_campaign_id = campaign_id

            saved = 0
            for lead_dict in leads:
                saved_lead = self._save_lead_from_dict(lead_dict)
                if saved_lead:
                    saved += 1
                    self.lead_found.emit(saved_lead)

            self._update_campaign_stats()
            return saved, skipped

        worker = ThreadWorker(fn=lambda **kw: _do_import())
        worker.signals.result.connect(
            lambda result: self.linkedin_import_finished.emit(
                result[0] if isinstance(result, tuple) else 0,
                result[1] if isinstance(result, tuple) else 0,
            )
        )
        worker.signals.error.connect(lambda msg: self.scrape_error.emit(msg))
        worker.start()

    # ─── HubSpot Search ──────────────────────────────────────────────

    def search_hubspot(self, niche: str, city: str, company_name: str = "",
                       limit: int = 50):
        """Search HubSpot CRM for contacts."""
        if not self.hubspot_engine:
            self.scrape_error.emit("HubSpot engine not configured.")
            return

        def _do_search(**kwargs):
            resp = self.hubspot_engine.search_contacts(
                niche=niche, city=city, company_name=company_name, limit=limit,
            )
            if not resp.get("success"):
                self.scrape_error.emit(resp.get("error", "HubSpot search failed"))
                return 0

            contacts = resp.get("data", [])
            campaign_id = self._create_campaign(
                name=f"HubSpot: {niche} in {city}",
                query="hubspot_search",
                city=city,
                niche=niche,
                sources=["hubspot"],
            )
            self._current_campaign_id = campaign_id

            saved = 0
            for contact in contacts:
                lead_dict = self.hubspot_engine.map_to_lead(contact)
                saved_lead = self._save_lead_from_dict(lead_dict)
                if saved_lead:
                    saved += 1
                    self.lead_found.emit(saved_lead)

            self._update_campaign_stats()
            return saved

        worker = ThreadWorker(fn=_do_search)
        worker.signals.result.connect(
            lambda result: self.hubspot_search_finished.emit(
                result if isinstance(result, int) else 0
            )
        )
        worker.signals.error.connect(lambda msg: self.scrape_error.emit(msg))
        worker.start()

    def _save_lead_from_dict(self, lead_dict: dict) -> dict:
        """Save a lead from a dict (API/import sources). Returns dict for UI or None."""
        try:
            with self.db_manager.session_scope() as session:
                db_lead = Lead(
                    campaign_id=self._current_campaign_id,
                    business_name=lead_dict.get("business_name", ""),
                    category=lead_dict.get("category", ""),
                    city=lead_dict.get("city", ""),
                    phone=lead_dict.get("phone", ""),
                    email=lead_dict.get("email", ""),
                    source_url=lead_dict.get("source_url", ""),
                    source_platform=lead_dict.get("source_platform", ""),
                    has_website=lead_dict.get("has_website", False),
                    website_url=lead_dict.get("website_url", ""),
                    status="new",
                )
                session.add(db_lead)
                session.flush()

                return {
                    "id": db_lead.id,
                    "business_name": db_lead.business_name,
                    "category": db_lead.category,
                    "city": db_lead.city,
                    "phone": db_lead.phone,
                    "email": db_lead.email,
                    "source_platform": db_lead.source_platform,
                    "has_website": db_lead.has_website,
                    "website_url": db_lead.website_url,
                    "status": "new",
                }
        except Exception as e:
            logger.error(f"Failed to save lead '{lead_dict.get('business_name')}': {e}")
            return None
