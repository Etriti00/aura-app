"""
Tests for the Conversation Engine — threads, messages, intent classification,
objection handling, re-engagement, stats.
"""

import pytest
import json
from datetime import datetime, timedelta

from database.schema import ConversationThread, Campaign, Lead


def _create_lead_with_campaign(db, name="Test Biz"):
    """Helper to create a campaign + lead."""
    with db.session_scope() as s:
        c = Campaign(name="Conv Test", target_city="Austin", target_niche="plumbing")
        s.add(c)
        s.flush()
        lead = Lead(campaign_id=c.id, business_name=name, lifecycle_state="contacted")
        s.add(lead)
        s.flush()
        return lead.id, c.id


# ─── Thread Management ────────────────────────────────────────


class TestThreadManagement:
    """Test thread creation and retrieval."""

    def test_get_thread_creates_if_missing(self, conversation_engine):
        engine, db = conversation_engine
        lead_id, _ = _create_lead_with_campaign(db)

        result = engine.get_thread(lead_id)
        assert result["success"] is True
        assert result["data"]["lead_id"] == lead_id
        assert result["data"]["thread_status"] == "active"

    def test_get_thread_returns_existing(self, conversation_engine):
        engine, db = conversation_engine
        lead_id, _ = _create_lead_with_campaign(db)

        engine.get_thread(lead_id)
        result = engine.get_thread(lead_id)
        assert result["success"] is True

    def test_append_message(self, conversation_engine):
        engine, db = conversation_engine
        lead_id, _ = _create_lead_with_campaign(db)

        result = engine.append_message(lead_id, "agent", "Hello, interested in our services?")
        assert result["success"] is True
        assert result["data"]["message_count"] == 1

    def test_append_multiple_messages(self, conversation_engine):
        engine, db = conversation_engine
        lead_id, _ = _create_lead_with_campaign(db)

        engine.append_message(lead_id, "agent", "Hello!")
        engine.append_message(lead_id, "lead", "Tell me more")
        engine.append_message(lead_id, "agent", "Sure, here are the details...")

        result = engine.get_thread(lead_id)
        assert result["data"]["message_count"] == 3
        assert len(result["data"]["messages"]) == 3


# ─── Reply Classification ─────────────────────────────────────


class TestReplyClassification:
    """Test heuristic and LLM-based reply intent classification."""

    def test_classify_interested(self, conversation_engine):
        engine, _ = conversation_engine
        result = engine.classify_reply_intent("Sounds good, let's talk about this more!")
        assert result["success"] is True
        assert result["data"]["intent"] == "interested"

    def test_classify_objection(self, conversation_engine):
        engine, _ = conversation_engine
        result = engine.classify_reply_intent("Not interested right now, maybe later")
        assert result["data"]["intent"] == "objection"

    def test_classify_unsubscribe(self, conversation_engine):
        engine, _ = conversation_engine
        result = engine.classify_reply_intent("Please unsubscribe me from your list")
        assert result["data"]["intent"] == "unsubscribe"

    def test_classify_question(self, conversation_engine):
        engine, _ = conversation_engine
        result = engine.classify_reply_intent("How much does your service cost?")
        assert result["data"]["intent"] == "question"

    def test_classify_fallback(self, conversation_engine):
        engine, _ = conversation_engine
        result = engine.classify_reply_intent("ok thanks")
        assert result["data"]["intent"] == "not_now"


# ─── Objection Handling ───────────────────────────────────────


class TestObjectionHandling:

    def test_handle_price_objection(self, conversation_engine):
        engine, db = conversation_engine
        lead_id, _ = _create_lead_with_campaign(db)
        engine.get_thread(lead_id)

        result = engine.handle_objection(lead_id, "price")
        assert result["success"] is True
        assert "ROI" in result["data"]["suggested_response"]

    def test_handle_invalid_objection_type(self, conversation_engine):
        engine, db = conversation_engine
        lead_id, _ = _create_lead_with_campaign(db)

        result = engine.handle_objection(lead_id, "invalid_type")
        assert result["success"] is False


# ─── Re-engagement ─────────────────────────────────────────────


class TestReEngagement:

    def test_schedule_re_engagement(self, conversation_engine):
        engine, db = conversation_engine
        lead_id, _ = _create_lead_with_campaign(db)

        result = engine.schedule_re_engagement(lead_id, delay_days=7)
        assert result["success"] is True
        assert result["data"]["delay_days"] == 7

    def test_get_pending_re_engagements(self, conversation_engine):
        engine, db = conversation_engine
        lead_id, _ = _create_lead_with_campaign(db)

        # Schedule for the past (so it's due now)
        with db.session_scope() as s:
            thread = ConversationThread(
                lead_id=lead_id, thread_status="re_engage",
                re_engage_at=datetime.utcnow() - timedelta(hours=1),
            )
            s.add(thread)

        result = engine.get_pending_re_engagements()
        assert result["success"] is True
        assert len(result["data"]) >= 1


# ─── Response Generation ──────────────────────────────────────


class TestResponseGeneration:

    def test_generate_response_interested(self, conversation_engine):
        engine, db = conversation_engine
        lead_id, _ = _create_lead_with_campaign(db)

        result = engine.generate_response(lead_id, "Sounds good, tell me more!")
        assert result["success"] is True
        assert result["data"]["intent"] == "interested"
        assert result["data"]["response"] is not None

    def test_generate_response_unsubscribe(self, conversation_engine):
        engine, db = conversation_engine
        lead_id, _ = _create_lead_with_campaign(db)

        result = engine.generate_response(lead_id, "Please unsubscribe me")
        assert result["data"]["intent"] == "unsubscribe"
        assert result["data"]["action"] == "remove_from_outreach"


# ─── Stats ─────────────────────────────────────────────────────


class TestStats:

    def test_thread_stats(self, conversation_engine):
        engine, db = conversation_engine
        lead_id, _ = _create_lead_with_campaign(db)
        engine.get_thread(lead_id)  # creates an active thread

        result = engine.get_thread_stats()
        assert result["success"] is True
        assert "total" in result["data"]
        assert result["data"]["total"] >= 1
