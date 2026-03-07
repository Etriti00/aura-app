"""
Aura — Lead Research Engine
Pre-outreach intelligence: gathers company info, pain points, competitors,
and opportunities using Tavily, Firecrawl, and Apify providers.
Synthesizes raw data via LLM into structured research reports.
"""

import json
from datetime import datetime

from config import RESEARCH_QUICK_TIMEOUT_S, RESEARCH_DEEP_TIMEOUT_S
from database.schema import ResearchReport, Lead, Settings
from utils.logger import get_logger

logger = get_logger("research_engine")


class ResearchEngine:
    """Orchestrates multi-source lead research before outreach."""

    def __init__(self, db_manager, router_engine=None, key_vault=None):
        self.db_manager = db_manager
        self.router_engine = router_engine
        self.key_vault = key_vault
        self.tavily = None
        self.firecrawl = None
        self.apify = None
        self.case_engine = None  # injected by main_window

    def configure(self, key_vault) -> None:
        """Initialize providers from encrypted settings."""
        self.key_vault = key_vault
        with self.db_manager.session_scope() as session:
            settings = session.query(Settings).first()
            if not settings:
                return

            tavily_key = key_vault.decrypt(settings.tavily_key_enc) if settings.tavily_key_enc else ""
            firecrawl_key = key_vault.decrypt(settings.firecrawl_key_enc) if settings.firecrawl_key_enc else ""
            apify_key = key_vault.decrypt(settings.apify_key_enc) if settings.apify_key_enc else ""

        if tavily_key:
            try:
                from core.research_providers.tavily_provider import TavilyProvider
                self.tavily = TavilyProvider(api_key=tavily_key)
                if self.tavily.is_available:
                    logger.info("Tavily provider configured")
                else:
                    self.tavily = None
            except Exception as e:
                logger.warning(f"Tavily init failed: {e}")

        if firecrawl_key:
            try:
                from core.research_providers.firecrawl_provider import FirecrawlProvider
                self.firecrawl = FirecrawlProvider(api_key=firecrawl_key)
                if self.firecrawl.is_available:
                    logger.info("Firecrawl provider configured")
                else:
                    self.firecrawl = None
            except Exception as e:
                logger.warning(f"Firecrawl init failed: {e}")

        if apify_key:
            try:
                from core.research_providers.apify_provider import ApifyProvider
                self.apify = ApifyProvider(api_key=apify_key)
                if self.apify.is_available:
                    logger.info("Apify provider configured")
                else:
                    self.apify = None
            except Exception as e:
                logger.warning(f"Apify init failed: {e}")

    def _determine_depth(self, lead_id: int) -> str:
        """Determine research depth based on lead's qualification score."""
        with self.db_manager.session_scope() as session:
            settings = session.query(Settings).first()
            threshold = settings.research_deep_threshold if settings else 7
            lead = session.query(Lead).get(lead_id)
            if lead and lead.website_score >= threshold:
                return "deep"
        return "quick"

    def research_lead(self, lead_id: int, depth: str = "auto") -> dict:
        """
        Research a lead using available providers.
        depth: "auto" (based on qual score), "quick", or "deep"
        """
        # Load lead data
        with self.db_manager.session_scope() as session:
            lead = session.query(Lead).get(lead_id)
            if not lead:
                return {"success": False, "error": "Lead not found"}
            lead_data = {
                "id": lead.id,
                "business_name": lead.business_name,
                "website_url": lead.website_url,
                "city": lead.city,
                "email": lead.email,
                "category": lead.category,
                "campaign_id": lead.campaign_id,
            }

        if depth == "auto":
            depth = self._determine_depth(lead_id)

        # Check for existing running report
        with self.db_manager.session_scope() as session:
            existing = session.query(ResearchReport).filter_by(
                lead_id=lead_id, status="running"
            ).first()
            if existing:
                return {"success": False, "error": "Research already in progress"}

        # Create report record
        with self.db_manager.session_scope() as session:
            report = ResearchReport(
                lead_id=lead_id,
                campaign_id=lead_data.get("campaign_id"),
                depth=depth,
                status="running",
            )
            session.add(report)
            session.flush()
            report_id = report.id

        try:
            raw_data = {}
            sources_used = []

            # Quick research: Tavily search + Firecrawl website crawl
            if self.tavily:
                query = f"{lead_data['business_name']} {lead_data.get('city', '')} services reviews"
                tavily_result = self.tavily.search(query)
                if tavily_result.get("success"):
                    raw_data["tavily"] = tavily_result["data"]
                    sources_used.append("tavily")

            if self.firecrawl and lead_data.get("website_url"):
                fc_result = self.firecrawl.crawl_url(lead_data["website_url"])
                if fc_result.get("success"):
                    raw_data["firecrawl"] = fc_result["data"]
                    sources_used.append("firecrawl")

            # Deep research: + Apify reviews + company search
            if depth == "deep" and self.apify:
                reviews_result = self.apify.scrape_google_reviews(
                    lead_data["business_name"], lead_data.get("city", "")
                )
                if reviews_result.get("success"):
                    raw_data["apify_reviews"] = reviews_result["data"]
                    sources_used.append("apify")

                company_result = self.apify.search_company_info(lead_data["business_name"])
                if company_result.get("success"):
                    raw_data["apify_company"] = company_result["data"]

            if not sources_used:
                with self.db_manager.session_scope() as session:
                    report = session.query(ResearchReport).get(report_id)
                    if report:
                        report.status = "failed"
                        report.error_message = "No research providers available"
                return {"success": False, "error": "No research providers available"}

            # Synthesize via LLM
            synthesis = self._synthesize(lead_data, raw_data, depth)

            # Save report
            with self.db_manager.session_scope() as session:
                report = session.query(ResearchReport).get(report_id)
                if report:
                    report.status = "completed"
                    report.sources_used = json.dumps(sources_used)
                    report.raw_data = json.dumps(raw_data, default=str)[:100000]
                    report.company_overview = synthesis.get("company_overview", "")
                    report.services_offered = synthesis.get("services_offered", "")
                    report.pain_points = synthesis.get("pain_points", "")
                    report.competitors = synthesis.get("competitors", "")
                    report.tech_stack = synthesis.get("tech_stack", "")
                    report.recent_news = synthesis.get("recent_news", "")
                    report.gaps_opportunities = synthesis.get("gaps_opportunities", "")
                    report.llm_summary = synthesis.get("summary", "")
                    report.updated_at = datetime.utcnow()

            # Log to case file
            if self.case_engine:
                try:
                    self.case_engine.add_note(
                        lead_id=lead_id,
                        note_type="research",
                        content=f"Research completed ({depth}): {synthesis.get('summary', '')[:500]}",
                    )
                except Exception as e:
                    logger.debug(f"Case note logging failed: {e}")

            return {
                "success": True,
                "data": {
                    "report_id": report_id,
                    "depth": depth,
                    "sources": sources_used,
                    "summary": synthesis.get("summary", ""),
                },
            }

        except Exception as e:
            logger.error(f"Research failed for lead {lead_id}: {e}")
            with self.db_manager.session_scope() as session:
                report = session.query(ResearchReport).get(report_id)
                if report:
                    report.status = "failed"
                    report.error_message = str(e)[:500]
            return {"success": False, "error": str(e)}

    def _synthesize(self, lead_data: dict, raw_data: dict, depth: str) -> dict:
        """Use LLM to synthesize raw research data into structured sections."""
        default = {
            "company_overview": "",
            "services_offered": "",
            "pain_points": "",
            "competitors": "",
            "tech_stack": "",
            "recent_news": "",
            "gaps_opportunities": "",
            "summary": "",
        }

        if not self.router_engine:
            # No LLM available — just summarize what we have
            parts = []
            if "tavily" in raw_data:
                answer = raw_data["tavily"].get("answer", "")
                if answer:
                    parts.append(answer)
            if "firecrawl" in raw_data:
                md = raw_data["firecrawl"].get("markdown", "")
                if md:
                    parts.append(md[:2000])
            default["summary"] = "\n".join(parts)[:3000]
            return default

        # Build synthesis prompt
        raw_text = json.dumps(raw_data, default=str)[:8000]
        prompt = f"""Analyze this research data about "{lead_data['business_name']}" in {lead_data.get('city', 'unknown city')}.

RESEARCH DATA:
{raw_text}

Return a JSON object with these exact keys:
- "company_overview": Brief company description (2-3 sentences)
- "services_offered": List of services/products they offer
- "pain_points": Potential pain points or weaknesses you can identify
- "competitors": Known competitors or market position
- "tech_stack": Any technology/tools they use (from website analysis)
- "recent_news": Any recent news or developments
- "gaps_opportunities": Gaps in their business where we could offer value
- "summary": A concise 2-paragraph executive summary for a sales agent

Return ONLY valid JSON, no markdown or other formatting."""

        try:
            result = self.router_engine.route("synthesize_research", prompt)
            if result.get("success"):
                text = result.get("data", "")
                # Parse JSON from response
                if isinstance(text, str):
                    text = text.strip()
                    if text.startswith("```"):
                        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                    parsed = json.loads(text)
                    return {k: parsed.get(k, "") for k in default}
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Research synthesis parse failed: {e}")

        return default

    def get_report(self, lead_id: int) -> dict:
        """Get the latest research report for a lead."""
        with self.db_manager.session_scope() as session:
            report = session.query(ResearchReport).filter_by(
                lead_id=lead_id
            ).order_by(ResearchReport.created_at.desc()).first()

            if not report:
                return {"success": False, "error": "No report found"}

            return {
                "success": True,
                "data": {
                    "id": report.id,
                    "lead_id": report.lead_id,
                    "depth": report.depth,
                    "status": report.status,
                    "sources_used": json.loads(report.sources_used or "[]"),
                    "company_overview": report.company_overview,
                    "services_offered": report.services_offered,
                    "pain_points": report.pain_points,
                    "competitors": report.competitors,
                    "tech_stack": report.tech_stack,
                    "recent_news": report.recent_news,
                    "gaps_opportunities": report.gaps_opportunities,
                    "llm_summary": report.llm_summary,
                    "error_message": report.error_message,
                    "created_at": str(report.created_at) if report.created_at else "",
                    "updated_at": str(report.updated_at) if report.updated_at else "",
                },
            }

    def get_research_queue(self, campaign_id: int = None) -> dict:
        """Get pending/running research tasks."""
        with self.db_manager.session_scope() as session:
            query = session.query(ResearchReport).filter(
                ResearchReport.status.in_(["pending", "running"])
            )
            if campaign_id:
                query = query.filter_by(campaign_id=campaign_id)

            reports = query.order_by(ResearchReport.created_at.desc()).all()
            items = []
            for r in reports:
                lead = session.query(Lead).get(r.lead_id)
                items.append({
                    "id": r.id,
                    "lead_id": r.lead_id,
                    "lead_name": lead.business_name if lead else "Unknown",
                    "depth": r.depth,
                    "status": r.status,
                    "created_at": str(r.created_at) if r.created_at else "",
                })

            return {"success": True, "data": items}

    def get_all_reports(self, campaign_id: int = None, limit: int = 50) -> dict:
        """Get all research reports, newest first."""
        with self.db_manager.session_scope() as session:
            query = session.query(ResearchReport)
            if campaign_id:
                query = query.filter_by(campaign_id=campaign_id)

            reports = query.order_by(ResearchReport.created_at.desc()).limit(limit).all()
            items = []
            for r in reports:
                lead = session.query(Lead).get(r.lead_id)
                items.append({
                    "id": r.id,
                    "lead_id": r.lead_id,
                    "lead_name": lead.business_name if lead else "Unknown",
                    "depth": r.depth,
                    "status": r.status,
                    "sources_used": json.loads(r.sources_used or "[]"),
                    "llm_summary": (r.llm_summary or "")[:200],
                    "created_at": str(r.created_at) if r.created_at else "",
                })

            return {"success": True, "data": items}

    def has_report(self, lead_id: int) -> bool:
        """Check if a lead has a completed research report."""
        with self.db_manager.session_scope() as session:
            return session.query(ResearchReport).filter_by(
                lead_id=lead_id, status="completed"
            ).first() is not None

    def get_provider_status(self) -> dict:
        """Get status of each research provider."""
        return {
            "tavily": self.tavily is not None and self.tavily.is_available,
            "firecrawl": self.firecrawl is not None and self.firecrawl.is_available,
            "apify": self.apify is not None and self.apify.is_available,
        }
