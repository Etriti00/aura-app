"""
Tests for the Lead Lifecycle Engine — state machine, transitions, callbacks, audit trail.
"""

import pytest
import json

from database.schema import Lead, LeadStateTransition, Campaign
from config import LEAD_STATE_TRANSITIONS, LEAD_TERMINAL_STATES
from tests.conftest import get_agent_id_by_name


def _create_campaign(db):
    """Helper to create a campaign for lead testing."""
    with db.session_scope() as s:
        c = Campaign(name="Test Campaign", target_city="Austin", target_niche="plumbing")
        s.add(c)
        s.flush()
        return c.id


def _create_lead(db, campaign_id, state="new", name="Test Biz"):
    """Helper to create a lead with a given lifecycle state."""
    with db.session_scope() as s:
        lead = Lead(
            campaign_id=campaign_id, business_name=name,
            lifecycle_state=state, status=state,
        )
        s.add(lead)
        s.flush()
        return lead.id


# ─── Schema Tests ──────────────────────────────────────────────


class TestLeadStateTransitionSchema:
    """Verify LeadStateTransition model creates and persists."""

    def test_transition_record_creation(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id)
        agent_id = get_agent_id_by_name(db, "Scout")

        with db.session_scope() as s:
            t = LeadStateTransition(
                lead_id=lead_id, from_state="new", to_state="researched",
                triggered_by="Scout", agent_id=agent_id,
                metadata_json=json.dumps({"reason": "auto-research"}),
            )
            s.add(t)
            s.flush()
            assert t.id is not None
            assert t.from_state == "new"
            assert t.to_state == "researched"

    def test_lead_lifecycle_state_column(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="qualifying")

        with db.session_scope() as s:
            lead = s.query(Lead).get(lead_id)
            assert lead.lifecycle_state == "qualifying"


# ─── Transition Tests ──────────────────────────────────────────


class TestTransition:
    """Test core state transition logic."""

    def test_valid_transition(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="new")

        result = engine.transition(lead_id, "researched", triggered_by="Scout")
        assert result["success"] is True
        assert result["data"]["from_state"] == "new"
        assert result["data"]["to_state"] == "researched"

    def test_invalid_transition_rejected(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="new")

        result = engine.transition(lead_id, "closed_won")
        assert result["success"] is False
        assert "Invalid transition" in result["error"]

    def test_terminal_state_blocks_transition(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="closed_won")

        result = engine.transition(lead_id, "negotiating")
        assert result["success"] is False
        assert "terminal state" in result["error"]

    def test_disqualified_is_terminal(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="disqualified")

        result = engine.transition(lead_id, "new")
        assert result["success"] is False
        assert "terminal state" in result["error"]

    def test_transition_updates_lead_state(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="new")

        engine.transition(lead_id, "qualifying")

        with db.session_scope() as s:
            lead = s.query(Lead).get(lead_id)
            assert lead.lifecycle_state == "qualifying"
            assert lead.status == "qualifying"  # backward compat

    def test_transition_creates_audit_record(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="qualified")

        engine.transition(lead_id, "email_drafted", triggered_by="Closer",
                          metadata={"skill": "The Closer"})

        with db.session_scope() as s:
            t = s.query(LeadStateTransition).filter_by(lead_id=lead_id).first()
            assert t is not None
            assert t.from_state == "qualified"
            assert t.to_state == "email_drafted"
            assert t.triggered_by == "Closer"
            meta = json.loads(t.metadata_json)
            assert meta["skill"] == "The Closer"

    def test_nonexistent_lead_returns_error(self, lifecycle_engine):
        engine, db = lifecycle_engine
        result = engine.transition(99999, "researched")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_multi_step_progression(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="new")

        path = ["researched", "qualifying", "qualified", "email_drafted", "contacted"]
        for state in path:
            result = engine.transition(lead_id, state)
            assert result["success"] is True

        with db.session_scope() as s:
            lead = s.query(Lead).get(lead_id)
            assert lead.lifecycle_state == "contacted"

    def test_re_engage_from_closed_lost(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="closed_lost")

        result = engine.transition(lead_id, "re_engage_scheduled")
        assert result["success"] is True
        assert result["data"]["to_state"] == "re_engage_scheduled"


# ─── Callback Tests ────────────────────────────────────────────


class TestCallbacks:
    """Test on_enter, on_exit, and on_transition callbacks."""

    def test_on_enter_callback_fires(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="new")

        fired = []
        engine.register_on_enter("researched", lambda lid, f, t: fired.append((lid, f, t)))

        engine.transition(lead_id, "researched")
        assert len(fired) == 1
        assert fired[0] == (lead_id, "new", "researched")

    def test_on_exit_callback_fires(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="qualifying")

        fired = []
        engine.register_on_exit("qualifying", lambda lid, f, t: fired.append((lid, f, t)))

        engine.transition(lead_id, "qualified")
        assert len(fired) == 1
        assert fired[0] == (lead_id, "qualifying", "qualified")

    def test_on_transition_callback_fires(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="contacted")

        fired = []
        engine.register_on_transition(
            "contacted", "interested",
            lambda lid, f, t: fired.append("interested!")
        )

        engine.transition(lead_id, "interested")
        assert "interested!" in fired


# ─── Query Tests ───────────────────────────────────────────────


class TestQueries:
    """Test query methods: valid transitions, history, leads in state, stats."""

    def test_get_valid_transitions(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="contacted")

        result = engine.get_valid_transitions(lead_id)
        assert result["success"] is True
        assert "interested" in result["data"]["valid_transitions"]
        assert "objection_raised" in result["data"]["valid_transitions"]

    def test_get_valid_transitions_terminal(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="closed_won")

        result = engine.get_valid_transitions(lead_id)
        assert result["success"] is True
        assert result["data"]["valid_transitions"] == []

    def test_get_transition_history(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        lead_id = _create_lead(db, campaign_id, state="new")

        engine.transition(lead_id, "researched")
        engine.transition(lead_id, "qualifying")

        result = engine.get_transition_history(lead_id)
        assert result["success"] is True
        assert len(result["data"]) == 2

    def test_get_leads_in_state(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        _create_lead(db, campaign_id, state="interested", name="Biz A")
        _create_lead(db, campaign_id, state="interested", name="Biz B")
        _create_lead(db, campaign_id, state="contacted", name="Biz C")

        result = engine.get_leads_in_state("interested")
        assert result["success"] is True
        names = [l["business_name"] for l in result["data"]]
        assert "Biz A" in names
        assert "Biz B" in names
        assert "Biz C" not in names

    def test_get_lifecycle_stats(self, lifecycle_engine):
        engine, db = lifecycle_engine
        campaign_id = _create_campaign(db)
        _create_lead(db, campaign_id, state="new")
        _create_lead(db, campaign_id, state="new")
        _create_lead(db, campaign_id, state="qualified")

        result = engine.get_lifecycle_stats(campaign_id=campaign_id)
        assert result["success"] is True
        assert result["data"].get("new", 0) >= 2
        assert result["data"].get("qualified", 0) >= 1
