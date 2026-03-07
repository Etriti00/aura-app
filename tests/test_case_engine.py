"""Tests for CaseEngine — add_note, build_case_context, update_case_memory, get_case_timeline."""

import json
import pytest
from datetime import datetime
from core.case_engine import CaseEngine
from database.schema import (
    CaseNote, CaseMemory, Lead, Campaign, EnrichmentData,
    LeadStateTransition, ConversationThread, FollowUpSend, Agent,
)


# ─── Schema Model Tests ───────────────────────────────────────────────────

class TestSchemaModels:

    def test_case_note_creation(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        with db.session_scope() as session:
            note = CaseNote(
                lead_id=lead_id, note_type="observation",
                content="Test note", metadata_json="{}",
            )
            session.add(note)
            session.flush()
            assert note.id is not None

    def test_case_memory_creation(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        with db.session_scope() as session:
            mem = CaseMemory(
                lead_id=lead_id, memory_type="summary",
                content="Summary text", note_count_at_summary=5,
            )
            session.add(mem)
            session.flush()
            assert mem.id is not None

    def test_case_note_with_agent(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        with db.session_scope() as session:
            agent = Agent(name="TestAgent", role="worker", status="idle")
            session.add(agent)
            session.flush()
            note = CaseNote(
                lead_id=lead_id, agent_id=agent.id,
                note_type="qualification", content="Lead looks good",
            )
            session.add(note)
            session.flush()
            assert note.agent_id == agent.id


# ─── Add Note ──────────────────────────────────────────────────────────────

class TestAddNote:

    def test_add_note_basic(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        result = engine.add_note(lead_id, "observation", "Test observation")
        assert result["success"] is True
        assert "note_id" in result

    def test_add_note_with_metadata(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        result = engine.add_note(
            lead_id, "outreach", "Email sent",
            metadata={"task_id": 42, "cost_usd": 0.01},
        )
        assert result["success"] is True
        # Verify metadata stored
        with db.session_scope() as session:
            note = session.query(CaseNote).filter_by(id=result["note_id"]).first()
            meta = json.loads(note.metadata_json)
            assert meta["task_id"] == 42

    def test_add_note_invalid_lead(self, db):
        engine = CaseEngine(db)
        result = engine.add_note(99999, "observation", "Should fail")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_add_note_truncates_long_content(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        long_content = "x" * 10000
        result = engine.add_note(lead_id, "observation", long_content)
        assert result["success"] is True
        with db.session_scope() as session:
            note = session.query(CaseNote).filter_by(id=result["note_id"]).first()
            assert len(note.content) <= 5000


# ─── Get Case Notes ───────────────────────────────────────────────────────

class TestGetCaseNotes:

    def test_empty_notes(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        result = engine.get_case_notes(lead_id)
        assert result["success"] is True
        assert result["data"] == []

    def test_returns_added_notes(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        engine.add_note(lead_id, "observation", "Note 1")
        engine.add_note(lead_id, "outreach", "Note 2")
        result = engine.get_case_notes(lead_id)
        assert result["success"] is True
        assert len(result["data"]) == 2

    def test_filter_by_type(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        engine.add_note(lead_id, "observation", "Obs note")
        engine.add_note(lead_id, "outreach", "Outreach note")
        engine.add_note(lead_id, "observation", "Another obs")
        result = engine.get_case_notes(lead_id, note_type="observation")
        assert len(result["data"]) == 2


# ─── Case Memory ──────────────────────────────────────────────────────────

class TestCaseMemory:

    def test_get_memory_empty(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        result = engine.get_case_memory(lead_id)
        assert result["success"] is True
        assert result["data"] is None

    def test_update_case_memory_creates_row(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        # Add some notes first
        for i in range(5):
            engine.add_note(lead_id, "observation", f"Note {i}")
        result = engine.update_case_memory(lead_id)
        assert result["success"] is True
        assert "summary" in result
        # Verify DB row
        with db.session_scope() as session:
            mem = session.query(CaseMemory).filter_by(lead_id=lead_id).first()
            assert mem is not None
            assert mem.note_count_at_summary == 5

    def test_update_case_memory_no_notes(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        result = engine.update_case_memory(lead_id)
        assert result["success"] is True
        assert result["summary"] == ""

    def test_update_case_memory_updates_existing(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        for i in range(3):
            engine.add_note(lead_id, "observation", f"Note {i}")
        engine.update_case_memory(lead_id)
        # Add more notes and re-summarize
        for i in range(3, 6):
            engine.add_note(lead_id, "outreach", f"Note {i}")
        engine.update_case_memory(lead_id)
        with db.session_scope() as session:
            mem = session.query(CaseMemory).filter_by(lead_id=lead_id).first()
            assert mem.note_count_at_summary == 6


# ─── Build Case Context ───────────────────────────────────────────────────

class TestBuildCaseContext:

    def test_returns_string_for_valid_lead(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        ctx = engine.build_case_context(lead_id)
        assert isinstance(ctx, str)
        assert "Test Business" in ctx
        assert "Lead #" in ctx

    def test_includes_lead_info(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        ctx = engine.build_case_context(lead_id)
        assert "plumbing" in ctx
        assert "Austin" in ctx
        assert "test@test.com" in ctx

    def test_includes_enrichment(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        with db.session_scope() as session:
            enrichment = EnrichmentData(
                lead_id=lead_id,
                google_maps_rating=4.5,
                google_maps_review_count=123,
                has_facebook=True,
            )
            session.add(enrichment)
        engine = CaseEngine(db)
        ctx = engine.build_case_context(lead_id)
        assert "4.5" in ctx
        assert "123" in ctx

    def test_includes_case_notes(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        engine.add_note(lead_id, "observation", "Important finding")
        ctx = engine.build_case_context(lead_id)
        assert "Important finding" in ctx
        assert "RECENT_NOTES" in ctx

    def test_includes_lifecycle_history(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        with db.session_scope() as session:
            transition = LeadStateTransition(
                lead_id=lead_id,
                from_state="new", to_state="qualifying",
                triggered_by="system",
            )
            session.add(transition)
        engine = CaseEngine(db)
        ctx = engine.build_case_context(lead_id)
        assert "new" in ctx
        assert "qualifying" in ctx

    def test_invalid_lead_returns_empty(self, db):
        engine = CaseEngine(db)
        ctx = engine.build_case_context(99999)
        assert ctx == ""

    def test_includes_conversation(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        with db.session_scope() as session:
            thread = ConversationThread(
                lead_id=lead_id,
                messages_json=json.dumps([
                    {"role": "agent", "content": "Hello!"},
                    {"role": "lead", "content": "I'm interested"},
                ]),
                message_count=2,
            )
            session.add(thread)
        engine = CaseEngine(db)
        ctx = engine.build_case_context(lead_id)
        assert "Hello!" in ctx or "interested" in ctx


# ─── Timeline ─────────────────────────────────────────────────────────────

class TestGetCaseTimeline:

    def test_empty_timeline(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        result = engine.get_case_timeline(lead_id)
        assert result["success"] is True
        assert result["data"] == []

    def test_includes_case_notes(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        engine.add_note(lead_id, "observation", "Timeline note")
        result = engine.get_case_timeline(lead_id)
        assert len(result["data"]) == 1
        assert result["data"][0]["type"] == "case_note"

    def test_includes_lifecycle_transitions(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        with db.session_scope() as session:
            session.add(LeadStateTransition(
                lead_id=lead_id,
                from_state="new", to_state="qualifying",
                triggered_by="agent",
            ))
        engine = CaseEngine(db)
        result = engine.get_case_timeline(lead_id)
        lifecycle_events = [e for e in result["data"] if e["type"] == "lifecycle"]
        assert len(lifecycle_events) == 1

    def test_includes_conversation_messages(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        with db.session_scope() as session:
            session.add(ConversationThread(
                lead_id=lead_id,
                messages_json=json.dumps([
                    {"role": "agent", "content": "Hi", "timestamp": "2024-01-01T10:00:00"},
                ]),
                message_count=1,
            ))
        engine = CaseEngine(db)
        result = engine.get_case_timeline(lead_id)
        conv_events = [e for e in result["data"] if e["type"] == "conversation"]
        assert len(conv_events) == 1

    def test_respects_limit(self, db_with_lead):
        db, lead_id, _ = db_with_lead
        engine = CaseEngine(db)
        for i in range(10):
            engine.add_note(lead_id, "observation", f"Note {i}")
        result = engine.get_case_timeline(lead_id, limit=3)
        assert len(result["data"]) == 3
