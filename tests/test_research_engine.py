"""
Tests for ResearchEngine — lead research orchestration.
"""

import json
import pytest
from datetime import datetime

from database.schema import ResearchReport, Lead, Campaign, Settings


# ─── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def research_db(db):
    """Database with a campaign, lead, and settings."""
    with db.session_scope() as session:
        session.add(Settings(id=1, research_auto_enabled=True, research_deep_threshold=7))
        camp = Campaign(name="Test Campaign", search_query="plumbing")
        session.add(camp)
        session.flush()
        lead = Lead(
            campaign_id=camp.id,
            business_name="Acme Plumbing",
            city="Austin",
            category="plumbing",
            email="acme@test.com",
            phone="555-1234",
            website_url="https://acmeplumbing.com",
            status="qualified",
            lifecycle_state="qualified",
            website_score=5,
        )
        session.add(lead)
        session.flush()
        lead_id = lead.id
        camp_id = camp.id
    return db, lead_id, camp_id


@pytest.fixture
def engine(research_db):
    from core.research_engine import ResearchEngine
    db, lead_id, camp_id = research_db
    eng = ResearchEngine(db)
    return eng, db, lead_id, camp_id


# ─── Mock Providers ──────────────────────────────────────


class MockTavilyProvider:
    is_available = True

    def search(self, query, max_results=5):
        return {
            "success": True,
            "data": {
                "answer": f"Acme Plumbing is a well-known plumbing company.",
                "results": [{"title": "Acme", "url": "https://acme.com", "content": "Plumbing services", "score": 0.9}],
                "query": query,
            },
        }


class MockFirecrawlProvider:
    is_available = True

    def crawl_url(self, url):
        return {
            "success": True,
            "data": {
                "url": url,
                "markdown": "# Acme Plumbing\nWe provide top plumbing services.",
                "title": "Acme Plumbing",
            },
        }


class MockApifyProvider:
    is_available = True

    def scrape_google_reviews(self, business_name, city, max_reviews=10):
        return {
            "success": True,
            "data": {
                "business": business_name,
                "city": city,
                "reviews": [{"author": "John", "rating": 5, "text": "Great service!", "date": "2025-01-01"}],
                "total_found": 1,
            },
        }

    def search_company_info(self, company_name):
        return {
            "success": True,
            "data": {
                "company": company_name,
                "results": [{"title": "Acme Info", "url": "https://acme.com", "description": "Plumbing company"}],
            },
        }


class FailingProvider:
    is_available = True

    def search(self, *a, **kw):
        return {"success": False, "error": "API error"}

    def crawl_url(self, *a, **kw):
        return {"success": False, "error": "API error"}


# ─── Constructor ─────────────────────────────────────────


class TestResearchEngineInit:
    def test_init_defaults(self, engine):
        eng, _, _, _ = engine
        assert eng.tavily is None
        assert eng.firecrawl is None
        assert eng.apify is None
        assert eng.case_engine is None

    def test_provider_status_empty(self, engine):
        eng, _, _, _ = engine
        status = eng.get_provider_status()
        assert status["tavily"] is False
        assert status["firecrawl"] is False
        assert status["apify"] is False


# ─── Depth Determination ─────────────────────────────────


class TestDetermineDepth:
    def test_low_score_returns_quick(self, engine):
        eng, _, lead_id, _ = engine
        depth = eng._determine_depth(lead_id)
        assert depth == "quick"

    def test_high_score_returns_deep(self, engine):
        eng, db, lead_id, _ = engine
        with db.session_scope() as session:
            lead = session.query(Lead).get(lead_id)
            lead.website_score = 9
        depth = eng._determine_depth(lead_id)
        assert depth == "deep"


# ─── Research Lead — No Providers ─────────────────────────


class TestResearchNoProviders:
    def test_lead_not_found(self, engine):
        eng, _, _, _ = engine
        result = eng.research_lead(99999)
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_no_providers_fails(self, engine):
        eng, _, lead_id, _ = engine
        result = eng.research_lead(lead_id)
        assert result["success"] is False
        assert "no research providers" in result["error"].lower()

    def test_report_marked_failed(self, engine):
        eng, db, lead_id, _ = engine
        eng.research_lead(lead_id)
        with db.session_scope() as session:
            report = session.query(ResearchReport).filter_by(lead_id=lead_id).first()
            assert report is not None
            assert report.status == "failed"


# ─── Research Lead — With Mock Providers ─────────────────


class TestResearchWithProviders:
    def test_quick_research_tavily_only(self, engine):
        eng, db, lead_id, _ = engine
        eng.tavily = MockTavilyProvider()
        result = eng.research_lead(lead_id, depth="quick")
        assert result["success"] is True
        assert "tavily" in result["data"]["sources"]
        assert result["data"]["depth"] == "quick"

    def test_quick_research_firecrawl_only(self, engine):
        eng, db, lead_id, _ = engine
        eng.firecrawl = MockFirecrawlProvider()
        result = eng.research_lead(lead_id, depth="quick")
        assert result["success"] is True
        assert "firecrawl" in result["data"]["sources"]

    def test_quick_research_both(self, engine):
        eng, db, lead_id, _ = engine
        eng.tavily = MockTavilyProvider()
        eng.firecrawl = MockFirecrawlProvider()
        result = eng.research_lead(lead_id, depth="quick")
        assert result["success"] is True
        assert "tavily" in result["data"]["sources"]
        assert "firecrawl" in result["data"]["sources"]

    def test_deep_research_all_providers(self, engine):
        eng, db, lead_id, _ = engine
        eng.tavily = MockTavilyProvider()
        eng.firecrawl = MockFirecrawlProvider()
        eng.apify = MockApifyProvider()
        result = eng.research_lead(lead_id, depth="deep")
        assert result["success"] is True
        assert "tavily" in result["data"]["sources"]
        assert "firecrawl" in result["data"]["sources"]
        assert "apify" in result["data"]["sources"]

    def test_report_saved_completed(self, engine):
        eng, db, lead_id, _ = engine
        eng.tavily = MockTavilyProvider()
        eng.research_lead(lead_id, depth="quick")
        with db.session_scope() as session:
            report = session.query(ResearchReport).filter_by(lead_id=lead_id).first()
            assert report.status == "completed"
            assert report.sources_used is not None
            sources = json.loads(report.sources_used)
            assert "tavily" in sources

    def test_auto_depth_picks_quick(self, engine):
        eng, _, lead_id, _ = engine
        eng.tavily = MockTavilyProvider()
        result = eng.research_lead(lead_id, depth="auto")
        assert result["success"] is True
        assert result["data"]["depth"] == "quick"

    def test_auto_depth_picks_deep(self, engine):
        eng, db, lead_id, _ = engine
        with db.session_scope() as session:
            lead = session.query(Lead).get(lead_id)
            lead.website_score = 9
        eng.tavily = MockTavilyProvider()
        eng.apify = MockApifyProvider()
        result = eng.research_lead(lead_id, depth="auto")
        assert result["success"] is True
        assert result["data"]["depth"] == "deep"


# ─── Duplicate / Conflict ────────────────────────────────


class TestResearchConflict:
    def test_blocks_duplicate_running(self, engine):
        eng, db, lead_id, camp_id = engine
        with db.session_scope() as session:
            session.add(ResearchReport(
                lead_id=lead_id, campaign_id=camp_id,
                depth="quick", status="running",
            ))
        eng.tavily = MockTavilyProvider()
        result = eng.research_lead(lead_id)
        assert result["success"] is False
        assert "already in progress" in result["error"].lower()


# ─── Synthesis ───────────────────────────────────────────


class TestSynthesis:
    def test_no_router_returns_raw_summary(self, engine):
        eng, _, _, _ = engine
        lead_data = {"business_name": "Acme", "city": "Austin"}
        raw_data = {"tavily": {"answer": "Acme is great"}}
        result = eng._synthesize(lead_data, raw_data, "quick")
        assert "Acme is great" in result["summary"]

    def test_no_router_firecrawl_data(self, engine):
        eng, _, _, _ = engine
        lead_data = {"business_name": "Acme", "city": "Austin"}
        raw_data = {"firecrawl": {"markdown": "# Acme\nPlumbing services"}}
        result = eng._synthesize(lead_data, raw_data, "quick")
        assert "Acme" in result["summary"]

    def test_all_default_keys_present(self, engine):
        eng, _, _, _ = engine
        result = eng._synthesize({}, {}, "quick")
        for key in ["company_overview", "services_offered", "pain_points",
                     "competitors", "tech_stack", "recent_news",
                     "gaps_opportunities", "summary"]:
            assert key in result


# ─── Report Retrieval ────────────────────────────────────


class TestReportRetrieval:
    def test_get_report_none(self, engine):
        eng, _, lead_id, _ = engine
        result = eng.get_report(lead_id)
        assert result["success"] is False

    def test_get_report_after_research(self, engine):
        eng, _, lead_id, _ = engine
        eng.tavily = MockTavilyProvider()
        eng.research_lead(lead_id)
        result = eng.get_report(lead_id)
        assert result["success"] is True
        assert result["data"]["lead_id"] == lead_id
        assert result["data"]["status"] == "completed"

    def test_has_report_false(self, engine):
        eng, _, lead_id, _ = engine
        assert eng.has_report(lead_id) is False

    def test_has_report_true(self, engine):
        eng, _, lead_id, _ = engine
        eng.tavily = MockTavilyProvider()
        eng.research_lead(lead_id)
        assert eng.has_report(lead_id) is True

    def test_get_all_reports_empty(self, engine):
        eng, _, _, _ = engine
        result = eng.get_all_reports()
        assert result["success"] is True
        assert result["data"] == []

    def test_get_all_reports_after_research(self, engine):
        eng, _, lead_id, _ = engine
        eng.tavily = MockTavilyProvider()
        eng.research_lead(lead_id)
        result = eng.get_all_reports()
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["lead_name"] == "Acme Plumbing"


# ─── Research Queue ──────────────────────────────────────


class TestResearchQueue:
    def test_empty_queue(self, engine):
        eng, _, _, _ = engine
        result = eng.get_research_queue()
        assert result["success"] is True
        assert result["data"] == []

    def test_queue_with_running_report(self, engine):
        eng, db, lead_id, camp_id = engine
        with db.session_scope() as session:
            session.add(ResearchReport(
                lead_id=lead_id, campaign_id=camp_id,
                depth="quick", status="running",
            ))
        result = eng.get_research_queue()
        assert len(result["data"]) == 1
        assert result["data"][0]["status"] == "running"


# ─── Case Engine Integration ─────────────────────────────


class MockCaseEngine:
    def __init__(self):
        self.notes = []

    def add_note(self, lead_id, note_type, content):
        self.notes.append({"lead_id": lead_id, "type": note_type, "content": content})


class TestCaseIntegration:
    def test_case_note_logged_on_success(self, engine):
        eng, _, lead_id, _ = engine
        eng.tavily = MockTavilyProvider()
        mock_case = MockCaseEngine()
        eng.case_engine = mock_case
        eng.research_lead(lead_id)
        assert len(mock_case.notes) == 1
        assert mock_case.notes[0]["type"] == "research"
        assert mock_case.notes[0]["lead_id"] == lead_id
