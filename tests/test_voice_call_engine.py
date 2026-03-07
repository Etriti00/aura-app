"""
Tests for VoiceCallEngine — voice call management and lifecycle.
"""

import json
import pytest
from datetime import datetime

from database.schema import VoiceCall, Lead, Campaign, Settings, Agent


# ─── Mock Providers ──────────────────────────────────────


class MockTTS:
    is_available = True

    def synthesize(self, text):
        return b"fake_audio"

    def synthesize_pcm(self, text, sample_rate=8000):
        return b"fake_pcm"


class MockSTT:
    is_available = True

    def transcribe(self, audio_bytes):
        return "Test transcription"


class MockCaseEngine:
    def __init__(self):
        self.notes = []

    def add_note(self, lead_id, note_type, content):
        self.notes.append({"lead_id": lead_id, "type": note_type, "content": content})

    def build_case_context(self, lead_id):
        return {"success": True, "data": {"summary": "Test case summary"}}


# ─── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def voice_db(db):
    """Database with campaign, lead (with phone), agents, and settings."""
    with db.session_scope() as session:
        session.add(Settings(
            id=1,
            voice_call_enabled=True,
            voice_tts_provider="elevenlabs",
            voice_stt_provider="whisper_local",
            voice_max_call_duration_s=300,
        ))
        camp = Campaign(name="Voice Campaign", search_query="test")
        session.add(camp)
        session.flush()
        lead = Lead(
            campaign_id=camp.id,
            business_name="Test Business",
            city="Austin",
            category="plumbing",
            email="test@test.com",
            phone="+15551234567",
            website_url="https://test.com",
            status="qualified",
            lifecycle_state="qualified",
        )
        session.add(lead)
        lead_no_phone = Lead(
            campaign_id=camp.id,
            business_name="No Phone Biz",
            city="Austin",
            category="plumbing",
            email="nophone@test.com",
            status="new",
            lifecycle_state="new",
        )
        session.add(lead_no_phone)
        agent = Agent(
            name="Voice Agent", role="worker", rank=3,
            identity_emoji="phone", model_tier="sonnet", status="idle",
        )
        session.add(agent)
        session.flush()
        lead_id = lead.id
        lead_no_phone_id = lead_no_phone.id
        camp_id = camp.id
        agent_id = agent.id
    return db, lead_id, lead_no_phone_id, camp_id, agent_id


@pytest.fixture
def engine(voice_db):
    from core.voice_call_engine import VoiceCallEngine
    db, lead_id, lead_no_phone_id, camp_id, agent_id = voice_db
    eng = VoiceCallEngine(db)
    return eng, db, lead_id, lead_no_phone_id, camp_id, agent_id


# ─── Constructor ─────────────────────────────────────────


class TestVoiceCallEngineInit:
    def test_init_defaults(self, engine):
        eng, _, _, _, _, _ = engine
        assert eng.tts is None
        assert eng.stt is None
        assert eng.twilio_client is None
        assert eng._active_calls == {}
        assert eng.case_engine is None
        assert eng.research_engine is None

    def test_provider_status_empty(self, engine):
        eng, _, _, _, _, _ = engine
        status = eng.get_provider_status()
        assert status["twilio"] is False
        assert status["tts"] is False
        assert status["stt"] is False
        assert status["ws_server"] is False


# ─── Initiate Call — Validation ──────────────────────────


class TestInitiateCallValidation:
    def test_no_twilio(self, engine):
        eng, _, lead_id, _, _, _ = engine
        result = eng.initiate_call(lead_id)
        assert result["success"] is False
        assert "twilio" in result["error"].lower()

    def test_no_tts(self, engine):
        eng, _, lead_id, _, _, _ = engine
        eng.twilio_client = object()
        result = eng.initiate_call(lead_id)
        assert result["success"] is False
        assert "tts" in result["error"].lower()

    def test_lead_not_found(self, engine):
        eng, _, _, _, _, _ = engine
        eng.twilio_client = object()
        eng.tts = MockTTS()
        result = eng.initiate_call(99999)
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_lead_no_phone(self, engine):
        eng, _, _, lead_no_phone_id, _, _ = engine
        eng.twilio_client = object()
        eng.tts = MockTTS()
        result = eng.initiate_call(lead_no_phone_id)
        assert result["success"] is False
        assert "no phone" in result["error"].lower()


# ─── Call Session ────────────────────────────────────────


class TestCallSession:
    def test_init(self):
        from core.voice_call_engine import CallSession
        session = CallSession(
            call_id=1,
            lead_data={"business_name": "Test"},
            tts=None,
            stt=None,
        )
        assert session.call_id == 1
        assert session.is_active is True
        assert session.transcript == []
        assert session.conversation == []

    def test_add_transcript_entry(self):
        from core.voice_call_engine import CallSession
        session = CallSession(1, {}, None, None)
        session.add_transcript_entry("lead", "Hello!")
        assert len(session.transcript) == 1
        assert session.transcript[0]["speaker"] == "lead"
        assert session.transcript[0]["text"] == "Hello!"
        assert "ts" in session.transcript[0]

    def test_get_llm_response_no_router(self):
        from core.voice_call_engine import CallSession
        session = CallSession(1, {}, None, None, router_engine=None)
        response = session.get_llm_response("Hi there")
        assert isinstance(response, str)
        assert len(response) > 0
        assert len(session.conversation) == 1

    def test_conversation_tracking(self):
        from core.voice_call_engine import CallSession
        session = CallSession(1, {}, None, None)
        session.get_llm_response("Hello")
        session.get_llm_response("How are you?")
        assert len(session.conversation) == 2
        assert session.conversation[0]["content"] == "Hello"
        assert session.conversation[1]["content"] == "How are you?"


# ─── Call History / Transcript ────────────────────────────


class TestCallHistory:
    def test_empty_history(self, engine):
        eng, _, _, _, _, _ = engine
        result = eng.get_call_history()
        assert result["success"] is True
        assert result["data"] == []

    def test_history_with_records(self, engine):
        eng, db, lead_id, _, camp_id, _ = engine
        with db.session_scope() as session:
            session.add(VoiceCall(
                lead_id=lead_id,
                campaign_id=camp_id,
                direction="outbound",
                status="completed",
                from_number="+15550001111",
                to_number="+15551234567",
                duration_seconds=120,
                call_outcome="interested",
                sentiment="positive",
                call_notes="Great call",
            ))
        result = eng.get_call_history()
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["lead_name"] == "Test Business"
        assert result["data"][0]["outcome"] == "interested"

    def test_history_filter_by_lead(self, engine):
        eng, db, lead_id, lead_no_phone_id, camp_id, _ = engine
        with db.session_scope() as session:
            session.add(VoiceCall(
                lead_id=lead_id, campaign_id=camp_id,
                direction="outbound", status="completed",
            ))
            session.add(VoiceCall(
                lead_id=lead_no_phone_id, campaign_id=camp_id,
                direction="inbound", status="completed",
            ))
        result = eng.get_call_history(lead_id=lead_id)
        assert len(result["data"]) == 1

    def test_transcript_not_found(self, engine):
        eng, _, _, _, _, _ = engine
        result = eng.get_call_transcript(99999)
        assert result["success"] is False

    def test_transcript_retrieval(self, engine):
        eng, db, lead_id, _, camp_id, _ = engine
        transcript_data = [
            {"speaker": "agent", "text": "Hello!", "ts": "2025-01-01T12:00:00"},
            {"speaker": "lead", "text": "Hi there", "ts": "2025-01-01T12:00:05"},
        ]
        with db.session_scope() as session:
            call = VoiceCall(
                lead_id=lead_id,
                campaign_id=camp_id,
                direction="outbound",
                status="completed",
                transcript=json.dumps(transcript_data),
                call_notes="Good conversation",
                call_outcome="interested",
                sentiment="positive",
            )
            session.add(call)
            session.flush()
            call_id = call.id
        result = eng.get_call_transcript(call_id)
        assert result["success"] is True
        assert len(result["data"]["transcript"]) == 2
        assert result["data"]["notes"] == "Good conversation"
        assert result["data"]["outcome"] == "interested"


# ─── Active Calls ────────────────────────────────────────


class TestActiveCalls:
    def test_no_active_calls(self, engine):
        eng, _, _, _, _, _ = engine
        result = eng.get_active_calls()
        assert result["success"] is True
        assert result["data"] == []

    def test_active_call_tracking(self, engine):
        from core.voice_call_engine import CallSession
        eng, _, _, _, _, _ = engine
        cs = CallSession(
            call_id=42,
            lead_data={"business_name": "Test Business"},
            tts=None,
            stt=None,
        )
        eng._active_calls["CA_fake_sid"] = cs
        result = eng.get_active_calls()
        assert len(result["data"]) == 1
        assert result["data"][0]["call_id"] == 42
        assert result["data"][0]["lead_name"] == "Test Business"
        assert result["data"][0]["call_sid"] == "CA_fake_sid"


# ─── End Call ────────────────────────────────────────────


class TestEndCall:
    def test_end_call_not_found(self, engine):
        eng, _, _, _, _, _ = engine
        result = eng.end_call(99999)
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_end_call_updates_record(self, engine):
        eng, db, lead_id, _, camp_id, _ = engine
        with db.session_scope() as session:
            call = VoiceCall(
                lead_id=lead_id,
                campaign_id=camp_id,
                direction="outbound",
                status="in_progress",
                twilio_call_sid="CA_test_123",
                started_at=datetime.utcnow(),
            )
            session.add(call)
            session.flush()
            call_id = call.id

        from core.voice_call_engine import CallSession
        cs = CallSession(call_id, {"business_name": "Test"}, None, None)
        cs.add_transcript_entry("agent", "Hello!")
        cs.add_transcript_entry("lead", "Not interested")
        eng._active_calls["CA_test_123"] = cs

        result = eng.end_call(call_id)
        assert result["success"] is True
        assert result["data"]["call_id"] == call_id

        with db.session_scope() as session:
            call = session.query(VoiceCall).get(call_id)
            assert call.status == "completed"
            assert call.ended_at is not None
            assert call.transcript is not None
            transcript = json.loads(call.transcript)
            assert len(transcript) == 2


# ─── Handle Incoming Call ────────────────────────────────


class TestIncomingCall:
    def test_unknown_caller(self, engine):
        eng, _, _, _, _, _ = engine
        result = eng.handle_incoming_call("+19995550000", "CA_incoming")
        assert result["success"] is False
        assert "unknown" in result["error"].lower()

    def test_known_caller(self, engine):
        eng, _, lead_id, _, _, _ = engine
        result = eng.handle_incoming_call("+15551234567", "CA_incoming")
        assert result["success"] is True
        assert result["data"]["lead_name"] == "Test Business"
        assert result["data"]["direction"] == "inbound"
        assert "CA_incoming" in eng._active_calls


# ─── Server ──────────────────────────────────────────────


class TestServer:
    def test_start_without_websockets(self, engine):
        from core.voice_call_engine import WEBSOCKETS_AVAILABLE
        eng, _, _, _, _, _ = engine
        if not WEBSOCKETS_AVAILABLE:
            result = eng.start_server()
            assert result["success"] is False
            assert "websockets" in result["error"].lower()

    def test_stop_server_noop(self, engine):
        eng, _, _, _, _, _ = engine
        eng.stop_server()


# ─── Provider Status ─────────────────────────────────────


class TestProviderStatus:
    def test_all_unconfigured(self, engine):
        eng, _, _, _, _, _ = engine
        status = eng.get_provider_status()
        assert status["twilio"] is False
        assert status["tts"] is False
        assert status["stt"] is False
        assert status["tts_provider"] is None
        assert status["stt_provider"] is None
        assert status["ws_server"] is False

    def test_with_mock_providers(self, engine):
        eng, _, _, _, _, _ = engine
        eng.twilio_client = object()
        eng.tts = MockTTS()
        eng.stt = MockSTT()
        status = eng.get_provider_status()
        assert status["twilio"] is True
        assert status["tts"] is True
        assert status["stt"] is True
        assert status["tts_provider"] == "MockTTS"
        assert status["stt_provider"] == "MockSTT"


# ─── Case Engine Integration ────────────────────────────


class TestCaseIntegration:
    def test_case_note_on_end_call(self, engine):
        eng, db, lead_id, _, camp_id, _ = engine
        mock_case = MockCaseEngine()
        eng.case_engine = mock_case

        with db.session_scope() as session:
            call = VoiceCall(
                lead_id=lead_id,
                campaign_id=camp_id,
                direction="outbound",
                status="in_progress",
                twilio_call_sid="CA_case_test",
                started_at=datetime.utcnow(),
            )
            session.add(call)
            session.flush()
            call_id = call.id

        from core.voice_call_engine import CallSession
        cs = CallSession(call_id, {"business_name": "Test"}, None, None)
        cs.add_transcript_entry("agent", "Hello, this is Aura calling.")
        cs.add_transcript_entry("lead", "Yes, tell me more.")
        eng._active_calls["CA_case_test"] = cs

        class MockRouter:
            def route(self, task_type, prompt, **kwargs):
                return {
                    "success": True,
                    "data": json.dumps({
                        "notes": "Productive call about plumbing services",
                        "outcome": "interested",
                        "sentiment": "positive",
                    }),
                }
        eng.router_engine = MockRouter()

        result = eng.end_call(call_id)
        assert result["success"] is True
        assert result["data"]["outcome"] == "interested"
        assert len(mock_case.notes) == 1
        assert mock_case.notes[0]["type"] == "voice_call"
