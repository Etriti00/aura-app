"""
Aura — Conversation Engine
Multi-turn email thread management with reply classification,
objection handling, and re-engagement scheduling.
"""

import json
from datetime import datetime, timedelta

from database.db_manager import DatabaseManager
from database.schema import ConversationThread, Lead
from config import (
    CONVERSATION_RE_ENGAGE_DEFAULT_DAYS,
    CONVERSATION_MAX_THREAD_MESSAGES,
    REPLY_INTENT_TYPES, OBJECTION_TYPES,
)
from utils.logger import get_logger

logger = get_logger("conversation_engine")


class ConversationEngine:
    """Manages multi-turn conversation threads per lead."""

    def __init__(self, db_manager: DatabaseManager, router_engine=None,
                 rag_engine=None, knowledge_graph=None):
        self.db_manager = db_manager
        self.router_engine = router_engine
        self.rag_engine = rag_engine
        self.knowledge_graph = knowledge_graph

    # ─── Thread Management ─────────────────────────────────────

    def get_thread(self, lead_id: int) -> dict:
        """Get or create a conversation thread for a lead."""
        try:
            with self.db_manager.session_scope() as session:
                thread = session.query(ConversationThread).filter_by(
                    lead_id=lead_id
                ).first()

                if not thread:
                    thread = ConversationThread(lead_id=lead_id)
                    session.add(thread)
                    session.flush()

                data = {
                    "id": thread.id,
                    "lead_id": thread.lead_id,
                    "thread_status": thread.thread_status,
                    "messages": json.loads(thread.messages_json or "[]"),
                    "reply_intent": thread.reply_intent,
                    "objection_type": thread.objection_type,
                    "message_count": thread.message_count,
                    "re_engage_at": thread.re_engage_at.isoformat() if thread.re_engage_at else None,
                    "last_activity": thread.last_activity.isoformat() if thread.last_activity else None,
                }

            return {"success": True, "data": data}

        except Exception as e:
            logger.error(f"get_thread failed: {e}")
            return {"success": False, "error": str(e)}

    def append_message(self, lead_id: int, role: str, content: str,
                       intent: str = None) -> dict:
        """Add a message to the conversation thread."""
        try:
            with self.db_manager.session_scope() as session:
                thread = session.query(ConversationThread).filter_by(
                    lead_id=lead_id
                ).first()

                if not thread:
                    thread = ConversationThread(lead_id=lead_id)
                    session.add(thread)
                    session.flush()

                messages = json.loads(thread.messages_json or "[]")

                msg = {
                    "role": role,
                    "content": content,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                if intent:
                    msg["intent"] = intent

                messages.append(msg)

                # Trim to max messages
                if len(messages) > CONVERSATION_MAX_THREAD_MESSAGES:
                    messages = messages[-CONVERSATION_MAX_THREAD_MESSAGES:]

                thread.messages_json = json.dumps(messages)
                thread.message_count = len(messages)
                thread.last_activity = datetime.utcnow()

                if intent:
                    thread.reply_intent = intent

            return {"success": True, "data": {"message_count": len(messages)}}

        except Exception as e:
            logger.error(f"append_message failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Reply Classification ──────────────────────────────────

    def classify_reply_intent(self, reply_text: str,
                              thread_context: str = "") -> dict:
        """
        Classify the intent of a lead reply.
        Uses router LLM if available, otherwise keyword-based heuristic.
        """
        if self.router_engine:
            try:
                prompt = (
                    f"Classify this lead reply into one of: {', '.join(REPLY_INTENT_TYPES)}.\n\n"
                    f"Reply: \"{reply_text}\"\n\n"
                    f"Respond with JSON only: {{\"intent\": \"<type>\", \"confidence\": <0-1>}}"
                )
                result = self.router_engine.route("qualify_lead_basic", prompt)
                if result.get("success"):
                    raw = result.get("data", "")
                    parsed = json.loads(raw)
                    intent = parsed.get("intent", "question")
                    if intent in REPLY_INTENT_TYPES:
                        return {"success": True, "data": {"intent": intent, "confidence": parsed.get("confidence", 0.8)}}
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}")

        # Heuristic fallback
        intent = self._heuristic_classify(reply_text)
        return {"success": True, "data": {"intent": intent, "confidence": 0.5}}

    def _heuristic_classify(self, text: str) -> str:
        """Simple keyword-based reply classification."""
        lower = text.lower()

        unsubscribe_kw = ["unsubscribe", "remove me", "stop emailing", "opt out", "don't contact"]
        if any(kw in lower for kw in unsubscribe_kw):
            return "unsubscribe"

        objection_kw = ["too expensive", "not interested", "no budget", "bad timing",
                        "already have", "using another", "competitor", "not now", "maybe later"]
        if any(kw in lower for kw in objection_kw):
            return "objection"

        interested_kw = ["interested", "tell me more", "sounds good", "let's talk",
                         "schedule a call", "send more info", "love to", "set up a meeting"]
        if any(kw in lower for kw in interested_kw):
            return "interested"

        question_kw = ["how", "what", "when", "where", "?", "can you", "do you"]
        if any(kw in lower for kw in question_kw):
            return "question"

        return "not_now"

    # ─── Objection Handling ────────────────────────────────────

    def handle_objection(self, lead_id: int, objection_type: str) -> dict:
        """Record objection and generate suggested response."""
        if objection_type not in OBJECTION_TYPES:
            return {"success": False, "error": f"Unknown objection type: {objection_type}"}

        try:
            with self.db_manager.session_scope() as session:
                thread = session.query(ConversationThread).filter_by(
                    lead_id=lead_id
                ).first()
                if thread:
                    thread.objection_type = objection_type
                    thread.reply_intent = "objection"

            # Generate response suggestion based on objection type
            responses = {
                "price": "I understand budget is important. Let me share how our ROI typically covers the investment within the first month.",
                "timing": "No problem! When would be a better time to revisit this? I can follow up then.",
                "need": "I appreciate your honesty. Could you tell me more about what you're currently using? There might be gaps we can help fill.",
                "authority": "Understood. Would it help if I prepared a brief summary you could share with the decision maker?",
                "competitor": "That's great you already have a solution. What's working well? We often help businesses in your space improve specific areas.",
                "other": "I appreciate you taking the time to respond. Is there anything specific I could address to help your decision?",
            }

            return {
                "success": True,
                "data": {
                    "objection_type": objection_type,
                    "suggested_response": responses.get(objection_type, responses["other"]),
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Re-engagement ─────────────────────────────────────────

    def schedule_re_engagement(self, lead_id: int,
                               delay_days: int = CONVERSATION_RE_ENGAGE_DEFAULT_DAYS) -> dict:
        """Schedule a lead for re-engagement after a delay."""
        try:
            re_engage_at = datetime.utcnow() + timedelta(days=delay_days)

            with self.db_manager.session_scope() as session:
                thread = session.query(ConversationThread).filter_by(
                    lead_id=lead_id
                ).first()

                if not thread:
                    thread = ConversationThread(lead_id=lead_id)
                    session.add(thread)

                thread.thread_status = "re_engage"
                thread.re_engage_at = re_engage_at

            return {
                "success": True,
                "data": {
                    "lead_id": lead_id,
                    "re_engage_at": re_engage_at.isoformat(),
                    "delay_days": delay_days,
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_pending_re_engagements(self) -> dict:
        """Get all threads due for re-engagement."""
        try:
            now = datetime.utcnow()
            with self.db_manager.session_scope() as session:
                threads = (
                    session.query(ConversationThread)
                    .filter(
                        ConversationThread.thread_status == "re_engage",
                        ConversationThread.re_engage_at <= now,
                    )
                    .all()
                )

                items = [
                    {
                        "id": t.id,
                        "lead_id": t.lead_id,
                        "re_engage_at": t.re_engage_at.isoformat() if t.re_engage_at else None,
                        "message_count": t.message_count,
                    }
                    for t in threads
                ]

            return {"success": True, "data": items}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Stats ─────────────────────────────────────────────────

    def get_thread_stats(self, campaign_id: int = None) -> dict:
        """Get conversation thread statistics."""
        try:
            from sqlalchemy import func

            with self.db_manager.session_scope() as session:
                query = session.query(
                    ConversationThread.thread_status,
                    func.count(ConversationThread.id),
                ).group_by(ConversationThread.thread_status)

                if campaign_id is not None:
                    query = query.filter(ConversationThread.campaign_id == campaign_id)

                rows = query.all()
                stats = {status: count for status, count in rows}

                total = sum(stats.values())
                stats["total"] = total

            return {"success": True, "data": stats}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Response Generation ───────────────────────────────────

    def generate_response(self, lead_id: int, reply_text: str) -> dict:
        """
        Generate a response to a lead reply using intent classification.
        Full pipeline: classify → handle objection/generate → append.
        """
        classification = self.classify_reply_intent(reply_text)
        if not classification["success"]:
            return classification

        intent = classification["data"]["intent"]

        # Record the incoming reply
        self.append_message(lead_id, "lead", reply_text, intent=intent)

        if intent == "unsubscribe":
            return {
                "success": True,
                "data": {
                    "intent": intent,
                    "action": "remove_from_outreach",
                    "response": None,
                },
            }

        if intent == "objection":
            objection_result = self.handle_objection(lead_id, "other")
            response = objection_result.get("data", {}).get("suggested_response", "")
        elif intent == "interested":
            response = "Great to hear! I'd love to set up a quick 15-minute call to discuss how we can help. What time works best for you?"
        elif intent == "question":
            response = "Great question! Let me get you the details on that."
        else:
            response = "Thanks for your reply. I'll follow up with more information soon."

        # Record the agent response
        self.append_message(lead_id, "agent", response)

        return {
            "success": True,
            "data": {
                "intent": intent,
                "response": response,
                "confidence": classification["data"].get("confidence", 0.5),
            },
        }
