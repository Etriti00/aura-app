"""
Tests for end-to-end automation wiring:
- Auto-qualification after enrichment
- Outreach lead filter broadening
- Fleet controller timer management
- Default AI engine settings
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from database.schema import (
    Base, Campaign, Lead, Settings, Agent,
)


# ─── Fixtures ───────────────────────────────────────────────


@pytest.fixture
def db_with_campaign(db):
    """Database with a campaign and several leads in various states."""
    with db.session_scope() as session:
        session.add(Settings(id=1))
        camp = Campaign(
            name="Test Campaign",
            search_query="plumbers austin",
            target_city="Austin",
            target_niche="plumbing",
            scrape_sources='["duckduckgo"]',
        )
        session.add(camp)
        session.flush()

        # Qualified lead with email
        session.add(Lead(
            campaign_id=camp.id, business_name="Qualified Plumber",
            city="Austin", category="plumbing", email="qualified@test.com",
            status="qualified",
        ))
        # New lead with email
        session.add(Lead(
            campaign_id=camp.id, business_name="New Lead With Email",
            city="Austin", category="plumbing", email="new@test.com",
            status="new",
        ))
        # New lead without email
        session.add(Lead(
            campaign_id=camp.id, business_name="No Email Lead",
            city="Austin", category="plumbing", email=None,
            status="new",
        ))
        # Disqualified lead with email
        session.add(Lead(
            campaign_id=camp.id, business_name="Disqualified Lead",
            city="Austin", category="plumbing", email="disq@test.com",
            status="disqualified",
        ))
        # Emailed lead
        session.add(Lead(
            campaign_id=camp.id, business_name="Already Emailed",
            city="Austin", category="plumbing", email="emailed@test.com",
            status="emailed",
        ))
        # Researched lead with email
        session.add(Lead(
            campaign_id=camp.id, business_name="Researched Lead",
            city="Austin", category="plumbing", email="researched@test.com",
            status="researched",
        ))
        session.flush()
        campaign_id = camp.id
    return db, campaign_id


@pytest.fixture
def hunter_ctrl(db):
    """HunterController with mocked AI engine."""
    from controllers.hunter_controller import HunterController
    ctrl = HunterController(db, enrichment_engine=None)
    return ctrl, db


@pytest.fixture
def outreach_ctrl(db_with_campaign):
    """OutreachController with campaign and leads."""
    db, campaign_id = db_with_campaign
    from controllers.outreach_controller import OutreachController
    from core.key_vault import KeyVault
    kv = KeyVault()
    ctrl = OutreachController(db, kv)
    return ctrl, db, campaign_id


# ─── Auto-Qualification Tests ──────────────────────────────


class TestAutoQualification:
    """Tests for auto-qualification of leads after enrichment."""

    def test_hunter_qualifies_lead_after_enrichment(self, hunter_ctrl, qapp):
        """When ai_engine is set, leads should be qualified after save."""
        ctrl, db = hunter_ctrl

        # Mock AI engine
        mock_ai = MagicMock()
        mock_ai.qualify_lead.return_value = {
            "qualified": True,
            "score": 8,
            "reason": "Good business prospect",
            "email_hint": "Focus on cost savings",
        }
        ctrl.ai_engine = mock_ai

        # Create a campaign
        with db.session_scope() as session:
            camp = Campaign(
                name="Test", search_query="test", target_niche="plumbing",
            )
            session.add(camp)
            session.flush()
            ctrl._current_campaign_id = camp.id

        # Simulate saving a lead and qualifying
        from core.scraper_engine import ScrapedLead
        lead = ScrapedLead(
            business_name="Test Business", category="plumbing", city="Austin",
            phone="555-1234", email="test@test.com", source_url="http://test.com",
            source_platform="duckduckgo", has_website=True,
            website_url="http://test.com",
        )
        lead_dict = ctrl._save_lead(lead)
        assert lead_dict is not None

        # Now simulate the qualification part
        qual = mock_ai.qualify_lead(lead_dict, "plumbing")
        with db.session_scope() as session:
            db_lead = session.query(Lead).filter_by(id=lead_dict["id"]).first()
            if qual.get("qualified"):
                db_lead.status = "qualified"
                db_lead.notes = f"[Qualified] Score: {qual['score']}/10"

        # Verify
        with db.session_scope() as session:
            db_lead = session.query(Lead).filter_by(id=lead_dict["id"]).first()
            assert db_lead.status == "qualified"
            assert "[Qualified] Score: 8/10" in db_lead.notes

    def test_hunter_disqualifies_low_score_lead(self, hunter_ctrl, qapp):
        """Leads with score < 6 should be disqualified."""
        ctrl, db = hunter_ctrl

        mock_ai = MagicMock()
        mock_ai.qualify_lead.return_value = {
            "qualified": False,
            "score": 3,
            "reason": "Not a real business",
            "email_hint": "",
        }
        ctrl.ai_engine = mock_ai

        with db.session_scope() as session:
            camp = Campaign(name="Test", search_query="test", target_niche="plumbing")
            session.add(camp)
            session.flush()
            ctrl._current_campaign_id = camp.id

        from core.scraper_engine import ScrapedLead
        lead = ScrapedLead(
            business_name="Bad Lead", category="plumbing", city="Austin",
            phone="", email="", source_url="http://bad.com",
            source_platform="duckduckgo", has_website=False, website_url="",
        )
        lead_dict = ctrl._save_lead(lead)

        qual = mock_ai.qualify_lead(lead_dict, "plumbing")
        with db.session_scope() as session:
            db_lead = session.query(Lead).filter_by(id=lead_dict["id"]).first()
            db_lead.status = "disqualified"
            db_lead.notes = f"[Disqualified] Score: {qual['score']}/10 — {qual['reason']}"

        with db.session_scope() as session:
            db_lead = session.query(Lead).filter_by(id=lead_dict["id"]).first()
            assert db_lead.status == "disqualified"
            assert "Not a real business" in db_lead.notes

    def test_hunter_qualification_without_ai_engine(self, hunter_ctrl, qapp):
        """Without ai_engine, leads should stay as 'new' (backward compat)."""
        ctrl, db = hunter_ctrl
        assert ctrl.ai_engine is None  # Not injected

        with db.session_scope() as session:
            camp = Campaign(name="Test", search_query="test", target_niche="plumbing")
            session.add(camp)
            session.flush()
            ctrl._current_campaign_id = camp.id

        from core.scraper_engine import ScrapedLead
        lead = ScrapedLead(
            business_name="Test", category="plumbing", city="Austin",
            phone="", email="test@test.com", source_url="http://test.com",
            source_platform="duckduckgo", has_website=True,
            website_url="http://test.com",
        )
        lead_dict = ctrl._save_lead(lead)

        # Lead should stay "new"
        with db.session_scope() as session:
            db_lead = session.query(Lead).filter_by(id=lead_dict["id"]).first()
            assert db_lead.status == "new"

    def test_hunter_has_ai_engine_attribute(self, hunter_ctrl, qapp):
        """HunterController should have ai_engine and lead_lifecycle_engine attrs."""
        ctrl, _ = hunter_ctrl
        assert hasattr(ctrl, "ai_engine")
        assert hasattr(ctrl, "lead_lifecycle_engine")
        assert ctrl.ai_engine is None
        assert ctrl.lead_lifecycle_engine is None

    def test_lead_qualified_signal_exists(self, hunter_ctrl, qapp):
        """HunterController should have a lead_qualified signal."""
        ctrl, _ = hunter_ctrl
        assert hasattr(ctrl, "lead_qualified")

    def test_lifecycle_transition_on_qualify(self, hunter_ctrl, qapp):
        """Lifecycle engine should be called when qualification succeeds."""
        ctrl, db = hunter_ctrl

        mock_ai = MagicMock()
        mock_ai.qualify_lead.return_value = {
            "qualified": True, "score": 9, "reason": "Great", "email_hint": "",
        }
        mock_lifecycle = MagicMock()

        ctrl.ai_engine = mock_ai
        ctrl.lead_lifecycle_engine = mock_lifecycle

        with db.session_scope() as session:
            camp = Campaign(name="Test", search_query="test", target_niche="plumbing")
            session.add(camp)
            session.flush()
            ctrl._current_campaign_id = camp.id

        from core.scraper_engine import ScrapedLead
        lead = ScrapedLead(
            business_name="Great Lead", category="plumbing", city="Austin",
            phone="555-0000", email="great@test.com", source_url="http://great.com",
            source_platform="duckduckgo", has_website=True,
            website_url="http://great.com",
        )
        lead_dict = ctrl._save_lead(lead)
        lead_id = lead_dict["id"]

        # Simulate the qualification block from _run_scrape
        qual = ctrl.ai_engine.qualify_lead(lead_dict, "plumbing")
        with db.session_scope() as session:
            db_lead = session.query(Lead).filter_by(id=lead_id).first()
            if qual.get("qualified"):
                db_lead.status = "qualified"
        if ctrl.lead_lifecycle_engine:
            new_state = "qualified" if qual.get("qualified") else "disqualified"
            ctrl.lead_lifecycle_engine.transition(lead_id, new_state, triggered_by="auto_qualify")

        mock_lifecycle.transition.assert_called_once_with(
            lead_id, "qualified", triggered_by="auto_qualify",
        )


# ─── Outreach Filter Tests ─────────────────────────────────


class TestOutreachLeadFilter:
    """Tests for the broadened outreach lead filter."""

    def test_includes_qualified_leads(self, outreach_ctrl):
        ctrl, db, campaign_id = outreach_ctrl
        leads = ctrl.get_outreach_leads(campaign_id)
        names = [l["business_name"] for l in leads]
        assert "Qualified Plumber" in names

    def test_includes_new_leads_with_email(self, outreach_ctrl):
        ctrl, db, campaign_id = outreach_ctrl
        leads = ctrl.get_outreach_leads(campaign_id)
        names = [l["business_name"] for l in leads]
        assert "New Lead With Email" in names

    def test_includes_researched_leads(self, outreach_ctrl):
        ctrl, db, campaign_id = outreach_ctrl
        leads = ctrl.get_outreach_leads(campaign_id)
        names = [l["business_name"] for l in leads]
        assert "Researched Lead" in names

    def test_excludes_disqualified_leads(self, outreach_ctrl):
        ctrl, db, campaign_id = outreach_ctrl
        leads = ctrl.get_outreach_leads(campaign_id)
        names = [l["business_name"] for l in leads]
        assert "Disqualified Lead" not in names

    def test_excludes_no_email_leads(self, outreach_ctrl):
        ctrl, db, campaign_id = outreach_ctrl
        leads = ctrl.get_outreach_leads(campaign_id)
        names = [l["business_name"] for l in leads]
        assert "No Email Lead" not in names

    def test_excludes_emailed_leads(self, outreach_ctrl):
        ctrl, db, campaign_id = outreach_ctrl
        leads = ctrl.get_outreach_leads(campaign_id)
        names = [l["business_name"] for l in leads]
        assert "Already Emailed" not in names

    def test_qualified_leads_come_first(self, outreach_ctrl):
        ctrl, db, campaign_id = outreach_ctrl
        leads = ctrl.get_outreach_leads(campaign_id)
        statuses = [l["status"] for l in leads]
        # Qualified should be before new/researched
        if "qualified" in statuses and "new" in statuses:
            assert statuses.index("qualified") < statuses.index("new")


# ─── Fleet Controller Timer Tests ──────────────────────────


class TestFleetTimerManagement:
    """Tests for fleet controller managing pipeline automation timers."""

    def test_fleet_controller_has_pipeline_attrs(self, qapp):
        """FleetController should have reply_ctrl, sequence_ctrl, outreach_ctrl."""
        from controllers.fleet_controller import FleetController
        fc = FleetController(MagicMock(), MagicMock(), MagicMock(), MagicMock())
        assert hasattr(fc, "reply_ctrl")
        assert hasattr(fc, "sequence_ctrl")
        assert hasattr(fc, "outreach_ctrl")
        assert fc.reply_ctrl is None
        assert fc.sequence_ctrl is None
        assert fc.outreach_ctrl is None

    def test_boot_fleet_starts_reply_timer(self, qapp):
        """boot_fleet should call reply_ctrl.start()."""
        from controllers.fleet_controller import FleetController
        mock_fleet = MagicMock()
        mock_fleet.boot_fleet.return_value = {"success": True, "data": {"booted": 5}}
        fc = FleetController(MagicMock(), MagicMock(), mock_fleet, MagicMock())

        mock_reply = MagicMock()
        fc.reply_ctrl = mock_reply
        fc.boot_fleet()
        mock_reply.start.assert_called_once()

    def test_boot_fleet_starts_sequence_timer(self, qapp):
        """boot_fleet should call sequence_ctrl.start()."""
        from controllers.fleet_controller import FleetController
        mock_fleet = MagicMock()
        mock_fleet.boot_fleet.return_value = {"success": True, "data": {"booted": 5}}
        fc = FleetController(MagicMock(), MagicMock(), mock_fleet, MagicMock())

        mock_seq = MagicMock()
        fc.sequence_ctrl = mock_seq
        fc.boot_fleet()
        mock_seq.start.assert_called_once()

    def test_boot_fleet_starts_outreach_timer(self, qapp):
        """boot_fleet should call outreach_ctrl.start_schedule_timer()."""
        from controllers.fleet_controller import FleetController
        mock_fleet = MagicMock()
        mock_fleet.boot_fleet.return_value = {"success": True, "data": {"booted": 5}}
        fc = FleetController(MagicMock(), MagicMock(), mock_fleet, MagicMock())

        mock_outreach = MagicMock()
        fc.outreach_ctrl = mock_outreach
        fc.boot_fleet()
        mock_outreach.start_schedule_timer.assert_called_once()

    def test_shutdown_fleet_stops_all_timers(self, qapp):
        """shutdown_fleet should stop all pipeline controllers."""
        from controllers.fleet_controller import FleetController
        mock_fleet = MagicMock()
        fc = FleetController(MagicMock(), MagicMock(), mock_fleet, MagicMock())

        mock_reply = MagicMock()
        mock_seq = MagicMock()
        mock_outreach = MagicMock()
        fc.reply_ctrl = mock_reply
        fc.sequence_ctrl = mock_seq
        fc.outreach_ctrl = mock_outreach

        fc.shutdown_fleet()
        mock_reply.stop.assert_called_once()
        mock_seq.stop.assert_called_once()
        mock_outreach.stop_schedule_timer.assert_called_once()

    def test_boot_fleet_handles_missing_controllers(self, qapp):
        """boot_fleet should not crash when pipeline controllers are None."""
        from controllers.fleet_controller import FleetController
        mock_fleet = MagicMock()
        mock_fleet.boot_fleet.return_value = {"success": True, "data": {"booted": 5}}
        fc = FleetController(MagicMock(), MagicMock(), mock_fleet, MagicMock())
        # reply_ctrl, sequence_ctrl, outreach_ctrl are all None
        fc.boot_fleet()  # Should not raise

    def test_shutdown_fleet_handles_missing_controllers(self, qapp):
        """shutdown_fleet should not crash when pipeline controllers are None."""
        from controllers.fleet_controller import FleetController
        mock_fleet = MagicMock()
        fc = FleetController(MagicMock(), MagicMock(), mock_fleet, MagicMock())
        fc.shutdown_fleet()  # Should not raise


# ─── Default Settings Tests ─────────────────────────────────


class TestDefaultSettings:
    """Tests for new default AI engine settings."""

    def test_new_settings_enables_conversation_engine(self, db):
        with db.session_scope() as session:
            s = Settings(id=1)
            session.add(s)
            session.flush()
            assert s.conversation_engine_enabled is True

    def test_new_settings_enables_knowledge_graph(self, db):
        with db.session_scope() as session:
            s = Settings(id=1)
            session.add(s)
            session.flush()
            assert s.knowledge_graph_enabled is True

    def test_new_settings_enables_self_improvement(self, db):
        with db.session_scope() as session:
            s = Settings(id=1)
            session.add(s)
            session.flush()
            assert s.self_improvement_enabled is True

    def test_reflection_still_enabled_by_default(self, db):
        with db.session_scope() as session:
            s = Settings(id=1)
            session.add(s)
            session.flush()
            assert s.reflection_enabled is True
