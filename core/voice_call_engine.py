"""
Aura — Voice Call Engine
Manages outbound/inbound voice calls via Twilio, with TTS/STT pipeline.
Handles call lifecycle, transcript building, and post-call analysis.
"""

import json
import base64
import asyncio
import threading
from datetime import datetime

from config import (
    VOICE_WS_PORT, VOICE_MAX_CALL_DURATION_S,
    VOICE_SAMPLE_RATE,
)
from database.schema import VoiceCall, Lead, Settings, Agent
from utils.logger import get_logger

logger = get_logger("voice_call_engine")

# Twilio
try:
    from twilio.rest import Client as TwilioClient
    from twilio.twiml.voice_response import VoiceResponse, Connect
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.debug("twilio not installed — voice calls unavailable")

# WebSocket server
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.debug("websockets not installed — WS server unavailable")


class CallSession:
    """Manages state for a single active call."""

    def __init__(self, call_id: int, lead_data: dict, tts, stt, router_engine=None):
        self.call_id = call_id
        self.lead_data = lead_data
        self.tts = tts
        self.stt = stt
        self.router_engine = router_engine
        self.transcript = []       # [{"speaker": "agent"|"lead", "text": "...", "ts": "..."}]
        self.conversation = []     # LLM message history
        self.audio_buffer = b""
        self.is_active = True
        self.started_at = datetime.utcnow()

    def add_transcript_entry(self, speaker: str, text: str):
        """Add a transcript entry."""
        self.transcript.append({
            "speaker": speaker,
            "text": text,
            "ts": datetime.utcnow().isoformat(),
        })

    def get_llm_response(self, user_text: str, system_prompt: str = "") -> str:
        """Get LLM response for the conversation."""
        self.conversation.append({"role": "user", "content": user_text})

        if not self.router_engine:
            return "I understand. Could you tell me more about that?"

        prompt = f"Lead said: {user_text}\n\nConversation so far:\n"
        for msg in self.conversation[-10:]:
            prompt += f"{msg['role']}: {msg['content']}\n"

        try:
            result = self.router_engine.route(
                "voice_conversation", prompt,
                context={"system_prompt": system_prompt}
            )
            if result.get("success"):
                response = result.get("data", "")
                self.conversation.append({"role": "assistant", "content": response})
                return response
        except Exception as e:
            logger.error(f"LLM response failed: {e}")

        return "I see, that's interesting. Let me think about how we can help with that."


class VoiceCallEngine:
    """Orchestrates voice calls: Twilio + TTS + STT + LLM conversation."""

    def __init__(self, db_manager, router_engine=None, key_vault=None):
        self.db_manager = db_manager
        self.router_engine = router_engine
        self.key_vault = key_vault
        self.tts = None              # Active TTS provider
        self.stt = None              # Active STT provider
        self.twilio_client = None
        self.twilio_phone = ""
        self._ws_server = None
        self._ws_thread = None
        self._active_calls = {}      # call_sid → CallSession
        self.case_engine = None
        self.research_engine = None
        self.lead_lifecycle_engine = None

    def configure(self, key_vault) -> None:
        """Initialize providers from encrypted settings."""
        self.key_vault = key_vault
        with self.db_manager.session_scope() as session:
            settings = session.query(Settings).first()
            if not settings:
                return

            # Twilio
            account_sid = key_vault.decrypt(settings.twilio_account_sid_enc) if settings.twilio_account_sid_enc else ""
            auth_token = key_vault.decrypt(settings.twilio_auth_token_enc) if settings.twilio_auth_token_enc else ""
            self.twilio_phone = settings.twilio_phone_number or ""

            if account_sid and auth_token and TWILIO_AVAILABLE:
                try:
                    self.twilio_client = TwilioClient(account_sid, auth_token)
                    logger.info("Twilio client configured")
                except Exception as e:
                    logger.warning(f"Twilio init failed: {e}")

            # TTS
            tts_provider = settings.voice_tts_provider or "elevenlabs"
            elevenlabs_key = key_vault.decrypt(settings.elevenlabs_key_enc) if settings.elevenlabs_key_enc else ""
            voice_id = settings.elevenlabs_voice_id or ""

            if tts_provider == "elevenlabs" and elevenlabs_key:
                try:
                    from core.voice.tts_elevenlabs import ElevenLabsTTS
                    self.tts = ElevenLabsTTS(api_key=elevenlabs_key, voice_id=voice_id)
                    if self.tts.is_available:
                        logger.info("ElevenLabs TTS configured")
                    else:
                        self.tts = None
                except Exception as e:
                    logger.warning(f"ElevenLabs init failed: {e}")

            if not self.tts and tts_provider in ("openai", "elevenlabs"):
                # Fallback to OpenAI TTS
                openai_key = key_vault.decrypt(settings.openai_key_enc) if settings.openai_key_enc else ""
                if openai_key:
                    try:
                        from core.voice.tts_openai import OpenAITTS
                        self.tts = OpenAITTS(api_key=openai_key)
                        if self.tts.is_available:
                            logger.info("OpenAI TTS configured (fallback)")
                        else:
                            self.tts = None
                    except Exception as e:
                        logger.warning(f"OpenAI TTS init failed: {e}")

            if not self.tts:
                # Fallback to Piper (local)
                piper_path = settings.piper_model_path or ""
                if piper_path:
                    try:
                        from core.voice.tts_piper import PiperTTS
                        self.tts = PiperTTS(model_path=piper_path)
                        if self.tts.is_available:
                            logger.info("Piper TTS configured (local fallback)")
                        else:
                            self.tts = None
                    except Exception as e:
                        logger.warning(f"Piper TTS init failed: {e}")

            # STT
            stt_provider = settings.voice_stt_provider or "whisper_local"
            openai_key = key_vault.decrypt(settings.openai_key_enc) if settings.openai_key_enc else ""

            try:
                from core.voice.stt_whisper import WhisperSTT
                if stt_provider == "whisper_api" and openai_key:
                    self.stt = WhisperSTT(mode="api", api_key=openai_key)
                else:
                    self.stt = WhisperSTT(mode="local")
                if self.stt.is_available:
                    logger.info(f"Whisper STT configured ({stt_provider})")
                else:
                    self.stt = None
            except Exception as e:
                logger.warning(f"Whisper STT init failed: {e}")

    def start_server(self, port: int = None) -> dict:
        """Start WebSocket server for Twilio Media Streams."""
        if not WEBSOCKETS_AVAILABLE:
            return {"success": False, "error": "websockets not installed"}

        port = port or VOICE_WS_PORT

        async def _ws_handler(websocket, path):
            """Handle a Twilio Media Stream WebSocket connection."""
            call_sid = None
            try:
                async for message in websocket:
                    data = json.loads(message)
                    event = data.get("event")

                    if event == "start":
                        call_sid = data.get("start", {}).get("callSid")
                        logger.info(f"WS stream started for call {call_sid}")

                    elif event == "media" and call_sid in self._active_calls:
                        session = self._active_calls[call_sid]
                        payload = data.get("media", {}).get("payload", "")
                        audio_bytes = base64.b64decode(payload)
                        session.audio_buffer += audio_bytes

                        # Process when buffer reaches ~1 second of audio
                        if len(session.audio_buffer) >= VOICE_SAMPLE_RATE:
                            text = ""
                            if self.stt:
                                text = self.stt.transcribe(session.audio_buffer)
                            session.audio_buffer = b""

                            if text:
                                session.add_transcript_entry("lead", text)
                                # Get LLM response
                                response = session.get_llm_response(text)
                                session.add_transcript_entry("agent", response)

                                # TTS → send back
                                if self.tts and hasattr(self.tts, "synthesize_pcm"):
                                    audio = self.tts.synthesize_pcm(response)
                                    if audio:
                                        encoded = base64.b64encode(audio).decode()
                                        await websocket.send(json.dumps({
                                            "event": "media",
                                            "streamSid": data.get("streamSid"),
                                            "media": {"payload": encoded},
                                        }))

                    elif event == "stop":
                        logger.info(f"WS stream stopped for call {call_sid}")
                        break

            except Exception as e:
                logger.error(f"WS handler error: {e}")

        def _run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            start = websockets.serve(_ws_handler, "0.0.0.0", port)
            self._ws_server = loop.run_until_complete(start)
            logger.info(f"Voice WS server started on port {port}")
            loop.run_forever()

        self._ws_thread = threading.Thread(target=_run_server, daemon=True)
        self._ws_thread.start()
        return {"success": True, "data": {"port": port}}

    def stop_server(self) -> None:
        """Stop the WebSocket server."""
        if self._ws_server:
            self._ws_server.close()
            self._ws_server = None
            logger.info("Voice WS server stopped")

    def initiate_call(self, lead_id: int, agent_id: int = None) -> dict:
        """Start an outbound call to a lead."""
        if not self.twilio_client:
            return {"success": False, "error": "Twilio not configured"}
        if not self.tts:
            return {"success": False, "error": "No TTS provider available"}

        # Load lead data
        with self.db_manager.session_scope() as session:
            lead = session.query(Lead).get(lead_id)
            if not lead:
                return {"success": False, "error": "Lead not found"}
            if not lead.phone:
                return {"success": False, "error": "Lead has no phone number"}
            lead_data = {
                "id": lead.id,
                "business_name": lead.business_name,
                "phone": lead.phone,
                "city": lead.city,
                "email": lead.email,
                "campaign_id": lead.campaign_id,
            }

        # Build opening context from case + research
        context_parts = [f"Calling {lead_data['business_name']}"]
        if self.case_engine:
            try:
                case_ctx = self.case_engine.build_case_context(lead_id)
                if case_ctx.get("success"):
                    context_parts.append(case_ctx.get("data", {}).get("summary", ""))
            except Exception:
                pass
        if self.research_engine:
            try:
                report = self.research_engine.get_report(lead_id)
                if report.get("success"):
                    context_parts.append(report.get("data", {}).get("llm_summary", ""))
            except Exception:
                pass

        # Create VoiceCall record
        with self.db_manager.session_scope() as session:
            call = VoiceCall(
                lead_id=lead_id,
                agent_id=agent_id,
                campaign_id=lead_data.get("campaign_id"),
                direction="outbound",
                status="queued",
                from_number=self.twilio_phone,
                to_number=lead_data["phone"],
                tts_provider=type(self.tts).__name__ if self.tts else None,
                stt_provider=type(self.stt).__name__ if self.stt else None,
            )
            session.add(call)
            session.flush()
            call_id = call.id

        try:
            # Generate TwiML that connects to our WS server
            twiml = VoiceResponse()
            connect = Connect()
            connect.stream(url=f"wss://localhost:{VOICE_WS_PORT}/")
            twiml.append(connect)

            # Make the call
            twilio_call = self.twilio_client.calls.create(
                to=lead_data["phone"],
                from_=self.twilio_phone,
                twiml=str(twiml),
                timeout=VOICE_MAX_CALL_DURATION_S,
            )

            call_sid = twilio_call.sid

            # Create call session
            call_session = CallSession(
                call_id=call_id,
                lead_data=lead_data,
                tts=self.tts,
                stt=self.stt,
                router_engine=self.router_engine,
            )
            # Set system prompt with lead context
            call_session.conversation.append({
                "role": "system",
                "content": "\n".join(context_parts),
            })
            self._active_calls[call_sid] = call_session

            # Update record
            with self.db_manager.session_scope() as session:
                call = session.query(VoiceCall).get(call_id)
                if call:
                    call.twilio_call_sid = call_sid
                    call.status = "ringing"
                    call.started_at = datetime.utcnow()

            return {
                "success": True,
                "data": {
                    "call_id": call_id,
                    "call_sid": call_sid,
                    "lead_name": lead_data["business_name"],
                    "phone": lead_data["phone"],
                },
            }

        except Exception as e:
            logger.error(f"Failed to initiate call to lead {lead_id}: {e}")
            with self.db_manager.session_scope() as session:
                call = session.query(VoiceCall).get(call_id)
                if call:
                    call.status = "failed"
            return {"success": False, "error": str(e)}

    def end_call(self, call_id: int) -> dict:
        """End an active call and finalize transcript."""
        with self.db_manager.session_scope() as session:
            call = session.query(VoiceCall).get(call_id)
            if not call:
                return {"success": False, "error": "Call not found"}
            call_sid = call.twilio_call_sid

        # Find and close session
        call_session = self._active_calls.pop(call_sid, None)

        # Hang up via Twilio
        if self.twilio_client and call_sid:
            try:
                self.twilio_client.calls(call_sid).update(status="completed")
            except Exception as e:
                logger.warning(f"Twilio hangup failed: {e}")

        # Finalize transcript and generate notes
        transcript = call_session.transcript if call_session else []
        notes = ""
        outcome = None
        sentiment = None

        if transcript and self.router_engine:
            try:
                transcript_text = "\n".join(
                    f"{t['speaker']}: {t['text']}" for t in transcript
                )
                prompt = f"""Analyze this call transcript and return JSON:
{{
  "notes": "2-3 sentence summary of the call",
  "outcome": "interested|not_interested|callback|meeting_booked|voicemail|no_answer",
  "sentiment": "positive|neutral|negative"
}}

TRANSCRIPT:
{transcript_text}"""

                result = self.router_engine.route("voice_call_notes", prompt)
                if result.get("success"):
                    text = result.get("data", "")
                    if isinstance(text, str):
                        text = text.strip()
                        if text.startswith("```"):
                            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                        parsed = json.loads(text)
                        notes = parsed.get("notes", "")
                        outcome = parsed.get("outcome")
                        sentiment = parsed.get("sentiment")
            except Exception as e:
                logger.warning(f"Call analysis failed: {e}")

        # Update call record
        duration = 0
        lead_id = None
        with self.db_manager.session_scope() as session:
            call = session.query(VoiceCall).get(call_id)
            if call:
                call.status = "completed"
                call.ended_at = datetime.utcnow()
                call.transcript = json.dumps(transcript)
                call.call_notes = notes
                call.call_outcome = outcome
                call.sentiment = sentiment
                if call.started_at:
                    duration = int(
                        (datetime.utcnow() - call.started_at).total_seconds()
                    )
                    call.duration_seconds = duration
                lead_id = call.lead_id

        # Log to case file
        if self.case_engine and notes and lead_id:
            try:
                self.case_engine.add_note(
                    lead_id=lead_id,
                    note_type="voice_call",
                    content=f"Call completed: {notes}",
                )
            except Exception as e:
                logger.debug(f"Case note logging failed: {e}")

        return {
            "success": True,
            "data": {
                "call_id": call_id,
                "notes": notes,
                "outcome": outcome,
                "sentiment": sentiment,
                "duration": duration,
            },
        }

    def handle_incoming_call(self, from_number: str, call_sid: str) -> dict:
        """Handle an incoming call — match to lead, accept."""
        with self.db_manager.session_scope() as session:
            lead = session.query(Lead).filter(
                Lead.phone.contains(from_number[-10:])
            ).first()

            if not lead:
                return {"success": False, "error": "Unknown caller"}

            lead_data = {
                "id": lead.id,
                "business_name": lead.business_name,
                "phone": lead.phone,
                "city": lead.city,
                "campaign_id": lead.campaign_id,
            }

            call = VoiceCall(
                lead_id=lead.id,
                campaign_id=lead.campaign_id,
                direction="inbound",
                status="in_progress",
                twilio_call_sid=call_sid,
                from_number=from_number,
                to_number=self.twilio_phone,
                started_at=datetime.utcnow(),
                tts_provider=type(self.tts).__name__ if self.tts else None,
                stt_provider=type(self.stt).__name__ if self.stt else None,
            )
            session.add(call)
            session.flush()
            call_id = call.id

        call_session = CallSession(
            call_id=call_id,
            lead_data=lead_data,
            tts=self.tts,
            stt=self.stt,
            router_engine=self.router_engine,
        )
        self._active_calls[call_sid] = call_session

        return {
            "success": True,
            "data": {
                "call_id": call_id,
                "lead_name": lead_data["business_name"],
                "direction": "inbound",
            },
        }

    def get_call_history(self, lead_id: int = None, limit: int = 50) -> dict:
        """Get call history, optionally filtered by lead."""
        with self.db_manager.session_scope() as session:
            query = session.query(VoiceCall)
            if lead_id:
                query = query.filter_by(lead_id=lead_id)
            calls = query.order_by(VoiceCall.created_at.desc()).limit(limit).all()

            items = []
            for c in calls:
                lead = session.query(Lead).get(c.lead_id)
                items.append({
                    "id": c.id,
                    "lead_id": c.lead_id,
                    "lead_name": lead.business_name if lead else "Unknown",
                    "direction": c.direction,
                    "status": c.status,
                    "duration": c.duration_seconds,
                    "outcome": c.call_outcome,
                    "sentiment": c.sentiment,
                    "notes": (c.call_notes or "")[:200],
                    "started_at": str(c.started_at) if c.started_at else "",
                    "created_at": str(c.created_at) if c.created_at else "",
                })

            return {"success": True, "data": items}

    def get_active_calls(self) -> dict:
        """Get currently active calls."""
        active = []
        for sid, session in self._active_calls.items():
            active.append({
                "call_sid": sid,
                "call_id": session.call_id,
                "lead_name": session.lead_data.get("business_name", ""),
                "transcript_count": len(session.transcript),
                "started_at": session.started_at.isoformat(),
            })
        return {"success": True, "data": active}

    def get_call_transcript(self, call_id: int) -> dict:
        """Get full transcript for a call."""
        with self.db_manager.session_scope() as session:
            call = session.query(VoiceCall).get(call_id)
            if not call:
                return {"success": False, "error": "Call not found"}
            return {
                "success": True,
                "data": {
                    "call_id": call_id,
                    "transcript": json.loads(call.transcript or "[]"),
                    "notes": call.call_notes,
                    "outcome": call.call_outcome,
                    "sentiment": call.sentiment,
                },
            }

    def get_provider_status(self) -> dict:
        """Get status of voice providers."""
        return {
            "twilio": self.twilio_client is not None,
            "tts": self.tts is not None and self.tts.is_available,
            "tts_provider": type(self.tts).__name__ if self.tts else None,
            "stt": self.stt is not None and self.stt.is_available,
            "stt_provider": type(self.stt).__name__ if self.stt else None,
            "ws_server": self._ws_server is not None,
        }
