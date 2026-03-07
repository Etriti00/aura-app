"""
Tests for the 4 integration gap fixes:
1. Gateway → Hunting (orchestrator triggers scraping)
2. Research → Email (outreach injects research/case context)
3. Voice call UI wiring (signals connected)
4. Caller agent in fleet (stalled-lead detection + approval flow)
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

from tests.conftest import InMemoryDatabaseManager
from database.schema import (
    Lead, Campaign, Settings, Skill, Agent,
    FollowUpSend, FollowUpStep, FollowUpSequence,
    ConversationThread, VoiceCall, PendingApproval,
)
from config import (
    AUTONOMY_REQUIRES_APPROVAL,
    CALLER_FAILED_EMAIL_THRESHOLD, CALLER_STALLED_DAYS,
)


@pytest.fixture
def db():
    db_manager = InMemoryDatabaseManager()
    db_manager.init_db()
    return db_manager


@pytest.fixture
def db_with_settings(db):
    with db.session_scope() as session:
        session.add(Settings(id=1, voice_call_enabled=True))
    return db


@pytest.fixture
def db_with_leads(db_with_settings):
    db = db_with_settings
    with db.session_scope() as session:
        campaign = Campaign(
            name="Test Campaign", search_query="test",
            target_city="Dallas", target_niche="restaurants",
            status="active",
        )
        session.add(campaign)
        session.flush()

        lead = Lead(
            business_name="Acme Corp", campaign_id=campaign.id,
            category="tech", city="Dallas", phone="+15555550101",
            email="test@acme.com",
        )
        session.add(lead)
        session.flush()

        # Add a skill
        session.add(Skill(
            name="Test Skill", system_prompt="Be helpful.",
            tone="friendly", is_default=True,
        ))
    return db


# ─── Gap 1: Orchestrator → Hunting ───────────────────────────────

class TestOrchestratorTriggersHunting:
    """Verify _exec_start_campaign() triggers scraping via hunter_ctrl."""

    def test_start_campaign_triggers_scrape(self, db):
        from core.orchestrator_engine import OrchestratorEngine

        orch = OrchestratorEngine(db, MagicMock())
        mock_hunter = MagicMock()
        mock_hunter.is_running = False

        engines = {"hunter_ctrl": mock_hunter}
        params = {"niche": "restaurants", "city": "Dallas", "limit": 25}

        result = orch._exec_start_campaign(params, engines)

        assert result["success"] is True
        mock_hunter.start_scrape.assert_called_once()
        call_kwargs = mock_hunter.start_scrape.call_args
        assert "restaurants" in str(call_kwargs)
        assert "Dallas" in str(call_kwargs)

    def test_start_campaign_works_without_hunter_ctrl(self, db):
        from core.orchestrator_engine import OrchestratorEngine

        orch = OrchestratorEngine(db, MagicMock())
        engines = {}  # No hunter_ctrl

        params = {"niche": "plumbers", "city": "Austin", "limit": 10}
        result = orch._exec_start_campaign(params, engines)

        assert result["success"] is True
        assert result["data"]["niche"] == "plumbers"

    def test_start_campaign_handles_scrape_error(self, db):
        from core.orchestrator_engine import OrchestratorEngine

        orch = OrchestratorEngine(db, MagicMock())
        mock_hunter = MagicMock()
        mock_hunter.start_scrape.side_effect = RuntimeError("Scraper down")

        engines = {"hunter_ctrl": mock_hunter}
        params = {"niche": "bakeries", "city": "NYC", "limit": 50}

        # Should not raise — error is caught
        result = orch._exec_start_campaign(params, engines)
        assert result["success"] is True

    def test_start_campaign_respects_autonomy(self, db):
        from core.orchestrator_engine import OrchestratorEngine

        orch = OrchestratorEngine(db, MagicMock())
        mock_autonomy = MagicMock()
        mock_autonomy.check_permission.return_value = {
            "data": {"allowed": False, "needs_approval": True}
        }
        mock_autonomy.queue_for_approval.return_value = {
            "data": {"approval_id": 42}
        }

        engines = {"autonomy": mock_autonomy}
        params = {"niche": "cafes", "city": "LA", "limit": 30}

        result = orch._exec_start_campaign(params, engines)
        assert result["success"] is False
        assert result.get("approval_queued") is True


# ─── Gap 2: Research → Email Generation ──────────────────────────

class TestResearchInjectedIntoEmail:
    """Verify outreach_controller.generate_draft() injects research/case context."""

    def test_generate_email_with_research_context(self):
        from core.ai_engine import AIEngine

        engine = AIEngine()
        engine._call_llm = MagicMock(return_value='{"subject": "Hi", "body": "Hello", "tone": "friendly"}')

        result = engine.generate_email(
            lead_data={"business_name": "Acme", "category": "tech"},
            skill={"name": "Closer", "system_prompt": "Be bold."},
            research_context="Pain Points: No website, losing customers to competitors",
            case_context="Previous emails bounced 2x",
        )

        assert result["subject"] == "Hi"
        # Verify the prompt includes research context
        call_args = engine._call_llm.call_args
        prompt = call_args[0][1][0]["content"]
        assert "RESEARCH INTELLIGENCE" in prompt
        assert "Pain Points" in prompt
        assert "CASE HISTORY" in prompt
        assert "Previous emails bounced" in prompt

    def test_generate_email_without_research_context(self):
        from core.ai_engine import AIEngine

        engine = AIEngine()
        engine._call_llm = MagicMock(return_value='{"subject": "Hi", "body": "Hello", "tone": "friendly"}')

        result = engine.generate_email(
            lead_data={"business_name": "Acme"},
            skill={"name": "Closer", "system_prompt": "Be bold."},
        )

        assert result["subject"] == "Hi"
        call_args = engine._call_llm.call_args
        prompt = call_args[0][1][0]["content"]
        assert "RESEARCH INTELLIGENCE" not in prompt

    def test_generate_email_via_router_with_research(self):
        from core.ai_engine import AIEngine

        engine = AIEngine()
        engine.router = MagicMock()
        engine.router.route.return_value = {
            "success": True,
            "data": '{"subject": "Hey", "body": "Body", "tone": "warm"}',
        }

        result = engine.generate_email(
            lead_data={"business_name": "TestCo"},
            skill={"name": "Closer", "system_prompt": "Close deals."},
            research_context="Tech Stack: WordPress, no CRM",
            case_context="Lead qualified score 8/10",
        )

        assert result["subject"] == "Hey"
        call_args = engine.router.route.call_args
        prompt = call_args[0][1]
        assert "RESEARCH INTELLIGENCE" in prompt
        assert "Tech Stack" in prompt

    def test_outreach_controller_has_engine_attrs(self):
        from controllers.outreach_controller import OutreachController

        db = InMemoryDatabaseManager()
        db.init_db()
        mock_kv = MagicMock()
        ctrl = OutreachController(db, mock_kv)

        assert hasattr(ctrl, "research_engine")
        assert hasattr(ctrl, "case_engine")
        assert ctrl.research_engine is None
        assert ctrl.case_engine is None


# ─── Gap 3: Voice Call UI Wiring ─────────────────────────────────

class TestVoiceCallUIWiring:
    """Verify calls page signals are properly defined."""

    def test_calls_page_has_view_transcript_signal(self, qapp):
        from ui.pages.calls import CallsPage

        page = CallsPage()
        assert hasattr(page, "view_transcript_requested")
        assert hasattr(page, "call_requested")

    def test_on_view_transcript_emits_signal(self, qapp):
        from ui.pages.calls import CallsPage

        page = CallsPage()
        received = []
        page.view_transcript_requested.connect(lambda cid: received.append(cid))

        page._on_view_transcript(42)
        assert received == [42]


# ─── Gap 4: Caller Agent & Stalled Lead Detection ────────────────

class TestCallerAgentConfig:
    """Verify config and fleet setup for caller agent."""

    def test_make_call_in_all_autonomy_levels(self):
        """make_call must require approval at ALL levels (not just supervised)."""
        assert "make_call" in AUTONOMY_REQUIRES_APPROVAL["supervised"]
        assert "make_call" in AUTONOMY_REQUIRES_APPROVAL["autonomous"]
        assert "make_call" in AUTONOMY_REQUIRES_APPROVAL["full_trust"]
        # observer has "all" which covers everything
        assert "all" in AUTONOMY_REQUIRES_APPROVAL["observer"]

    def test_make_call_in_task_specialty_map(self):
        from core.fleet_orchestrator import TASK_SPECIALTY_MAP
        assert "make_call" in TASK_SPECIALTY_MAP
        assert TASK_SPECIALTY_MAP["make_call"] == "Caller"

    def test_caller_constants_exist(self):
        from config import (
            CALLER_CHECK_INTERVAL_MS,
            CALLER_FAILED_EMAIL_THRESHOLD,
            CALLER_STALLED_DAYS,
        )
        assert CALLER_CHECK_INTERVAL_MS > 0
        assert CALLER_FAILED_EMAIL_THRESHOLD >= 1
        assert CALLER_STALLED_DAYS >= 1


class TestStalledLeadDetection:
    """Verify _find_call_eligible_leads() finds correct leads."""

    def _make_fleet_ctrl(self, db):
        from controllers.fleet_controller import FleetController
        mock_agent_engine = MagicMock()
        mock_fleet = MagicMock()
        mock_observer = MagicMock()
        ctrl = FleetController(db, mock_agent_engine, mock_fleet, mock_observer)
        ctrl.voice_engine = MagicMock()
        ctrl.autonomy_ctrl = MagicMock()
        return ctrl

    def test_finds_leads_with_failed_emails(self, db_with_leads):
        db = db_with_leads
        ctrl = self._make_fleet_ctrl(db)

        with db.session_scope() as session:
            lead = session.query(Lead).first()
            # Create a follow-up sequence + step for FK constraints
            seq = FollowUpSequence(name="Test Seq", campaign_id=lead.campaign_id)
            session.add(seq)
            session.flush()
            step = FollowUpStep(
                sequence_id=seq.id, step_number=1,
                delay_days=1,
            )
            session.add(step)
            session.flush()

            # Add 3 failed email sends
            for _ in range(CALLER_FAILED_EMAIL_THRESHOLD):
                session.add(FollowUpSend(
                    lead_id=lead.id, step_id=step.id,
                    status="failed",
                ))
            session.flush()

        results = ctrl._find_call_eligible_leads()
        assert len(results) >= 1
        assert results[0]["lead_id"] == 1
        assert "failed emails" in results[0]["reason"]

    def test_finds_interested_stalled_leads(self, db_with_leads):
        db = db_with_leads
        ctrl = self._make_fleet_ctrl(db)

        with db.session_scope() as session:
            lead = session.query(Lead).first()
            # Create interested conversation that's stalled
            thread = ConversationThread(
                lead_id=lead.id,
                reply_intent="interested",
                last_activity=datetime.utcnow() - timedelta(days=CALLER_STALLED_DAYS + 1),
            )
            session.add(thread)
            session.flush()

        results = ctrl._find_call_eligible_leads()
        assert len(results) >= 1
        assert any("stalled" in r["reason"] for r in results)

    def test_skips_leads_without_phone(self, db_with_settings):
        db = db_with_settings
        ctrl = self._make_fleet_ctrl(db)

        with db.session_scope() as session:
            campaign = Campaign(
                name="No Phone", search_query="test",
                target_city="Dallas", target_niche="test",
                status="active",
            )
            session.add(campaign)
            session.flush()

            # Lead without phone
            lead = Lead(
                business_name="No Phone Corp", campaign_id=campaign.id,
                category="tech", city="Dallas", phone=None,
            )
            session.add(lead)
            session.flush()

            seq = FollowUpSequence(name="Seq", campaign_id=campaign.id)
            session.add(seq)
            session.flush()
            step = FollowUpStep(
                sequence_id=seq.id, step_number=1, delay_days=1,
            )
            session.add(step)
            session.flush()

            for _ in range(5):
                session.add(FollowUpSend(
                    lead_id=lead.id, step_id=step.id, status="failed",
                ))

        results = ctrl._find_call_eligible_leads()
        assert len(results) == 0

    def test_skips_leads_already_called(self, db_with_leads):
        db = db_with_leads
        ctrl = self._make_fleet_ctrl(db)

        with db.session_scope() as session:
            lead = session.query(Lead).first()
            # Already has a completed call
            session.add(VoiceCall(
                lead_id=lead.id, direction="outbound",
                status="completed", from_number="+1", to_number="+2",
            ))
            session.flush()

            seq = FollowUpSequence(name="Seq", campaign_id=lead.campaign_id)
            session.add(seq)
            session.flush()
            step = FollowUpStep(
                sequence_id=seq.id, step_number=1, delay_days=1,
            )
            session.add(step)
            session.flush()

            for _ in range(5):
                session.add(FollowUpSend(
                    lead_id=lead.id, step_id=step.id, status="failed",
                ))

        results = ctrl._find_call_eligible_leads()
        assert len(results) == 0

    def test_skips_leads_with_pending_approval(self, db_with_leads):
        db = db_with_leads
        ctrl = self._make_fleet_ctrl(db)

        with db.session_scope() as session:
            lead = session.query(Lead).first()
            # Already has a pending make_call approval
            session.add(PendingApproval(
                action_type="make_call", status="pending",
                lead_id=lead.id, action_description="Call",
            ))
            session.flush()

            seq = FollowUpSequence(name="Seq", campaign_id=lead.campaign_id)
            session.add(seq)
            session.flush()
            step = FollowUpStep(
                sequence_id=seq.id, step_number=1, delay_days=1,
            )
            session.add(step)
            session.flush()

            for _ in range(5):
                session.add(FollowUpSend(
                    lead_id=lead.id, step_id=step.id, status="failed",
                ))

        results = ctrl._find_call_eligible_leads()
        assert len(results) == 0


class TestCallerTimerRespectsToggle:
    """Verify _check_stalled_leads respects voice_call_enabled toggle."""

    def test_check_skipped_when_voice_disabled(self, db):
        from controllers.fleet_controller import FleetController

        with db.session_scope() as session:
            session.add(Settings(id=1, voice_call_enabled=False))

        ctrl = FleetController(db, MagicMock(), MagicMock(), MagicMock())
        ctrl.voice_engine = MagicMock()
        ctrl.autonomy_ctrl = MagicMock()

        ctrl._check_stalled_leads()

        # Should NOT call queue_for_approval since voice is disabled
        ctrl.autonomy_ctrl.queue_for_approval.assert_not_called()

    def test_check_skipped_when_no_voice_engine(self, db):
        from controllers.fleet_controller import FleetController

        ctrl = FleetController(db, MagicMock(), MagicMock(), MagicMock())
        ctrl.voice_engine = None
        ctrl.autonomy_ctrl = MagicMock()

        ctrl._check_stalled_leads()
        ctrl.autonomy_ctrl.queue_for_approval.assert_not_called()


class TestApprovalExecutesMakeCall:
    """Verify orchestrator executes make_call after approval."""

    def test_execute_approved_make_call(self, db):
        from core.orchestrator_engine import OrchestratorEngine

        orch = OrchestratorEngine(db, MagicMock())
        mock_voice = MagicMock()
        engines = {"voice": mock_voice}

        approval_data = {
            "action_type": "make_call",
            "payload": {"lead_id": 42},
        }

        orch._execute_approved_action(approval_data, engines)
        mock_voice.initiate_call.assert_called_once_with(42)

    def test_execute_approved_non_call_action(self, db):
        from core.orchestrator_engine import OrchestratorEngine

        orch = OrchestratorEngine(db, MagicMock())
        mock_voice = MagicMock()
        engines = {"voice": mock_voice}

        approval_data = {
            "action_type": "send_email",
            "payload": {"lead_id": 42},
        }

        orch._execute_approved_action(approval_data, engines)
        mock_voice.initiate_call.assert_not_called()

    def test_execute_approved_call_handles_error(self, db):
        from core.orchestrator_engine import OrchestratorEngine

        orch = OrchestratorEngine(db, MagicMock())
        mock_voice = MagicMock()
        mock_voice.initiate_call.side_effect = RuntimeError("Twilio down")
        engines = {"voice": mock_voice}

        approval_data = {
            "action_type": "make_call",
            "payload": {"lead_id": 99},
        }

        # Should not raise
        orch._execute_approved_action(approval_data, engines)


class TestCallerAgentInHierarchy:
    """Verify Caller agent exists in DB seeding."""

    def test_caller_in_hierarchy(self, db_with_agents):
        with db_with_agents.session_scope() as session:
            caller = session.query(Agent).filter_by(name="Caller").first()
            assert caller is not None
            assert caller.rank == 3
            assert caller.reports_to_id is not None

            commander = session.query(Agent).filter_by(name="Commander").first()
            assert caller.reports_to_id == commander.id
