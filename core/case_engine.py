"""
Aura — Case Engine
Manages per-lead case files: notes, living memory summary, timeline assembly.
Feature 4: Lead as Case — every lead is a case with notes, memory, and full history.
"""

import json
from datetime import datetime

from database.db_manager import DatabaseManager
from database.schema import (
    CaseNote, CaseMemory, Lead, EnrichmentData,
    LeadStateTransition, ConversationThread, FollowUpSend,
)
from config import (
    CASE_NOTE_MAX_RECENT,
    CASE_MEMORY_SUMMARIZE_THRESHOLD,
    CASE_CONTEXT_MAX_TOKENS,
)
from utils.logger import get_logger

logger = get_logger("case_engine")


class CaseEngine:
    """Manages per-lead case files: notes, living summary, context assembly."""

    def __init__(self, db_manager: DatabaseManager,
                 router_engine=None, token_manager=None):
        self.db_manager = db_manager
        self.router_engine = router_engine
        self.token_manager = token_manager

    # ─── Notes ────────────────────────────────────────────────────────────

    def add_note(self, lead_id: int, note_type: str, content: str,
                 agent_id: int = None, metadata: dict = None) -> dict:
        """Add a timestamped note to the lead's case file."""
        try:
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if not lead:
                    return {"success": False, "error": f"Lead {lead_id} not found"}

                note = CaseNote(
                    lead_id=lead_id,
                    agent_id=agent_id,
                    note_type=note_type,
                    content=content[:5000],
                    metadata_json=json.dumps(metadata or {}),
                )
                session.add(note)
                session.flush()
                note_id = note.id

                # Check if we should re-summarize
                note_count = (
                    session.query(CaseNote)
                    .filter_by(lead_id=lead_id)
                    .count()
                )
                memory = (
                    session.query(CaseMemory)
                    .filter_by(lead_id=lead_id)
                    .first()
                )
                last_summary_count = memory.note_count_at_summary if memory else 0

            # Trigger re-summarization outside the session if threshold crossed
            if (note_count - last_summary_count) >= CASE_MEMORY_SUMMARIZE_THRESHOLD:
                self.update_case_memory(lead_id)

            return {"success": True, "note_id": note_id}
        except Exception as e:
            logger.error(f"Failed to add case note for lead {lead_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_case_notes(self, lead_id: int, note_type: str = None,
                       limit: int = 50) -> dict:
        """Query CaseNote rows with optional type filter."""
        try:
            with self.db_manager.session_scope() as session:
                q = (
                    session.query(CaseNote)
                    .filter_by(lead_id=lead_id)
                )
                if note_type:
                    q = q.filter_by(note_type=note_type)
                notes = (
                    q.order_by(CaseNote.created_at.desc())
                    .limit(limit)
                    .all()
                )
                data = [
                    {
                        "id": n.id,
                        "lead_id": n.lead_id,
                        "agent_id": n.agent_id,
                        "note_type": n.note_type,
                        "content": n.content,
                        "metadata": json.loads(n.metadata_json or "{}"),
                        "created_at": n.created_at.isoformat() if n.created_at else None,
                    }
                    for n in notes
                ]
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"Failed to get case notes for lead {lead_id}: {e}")
            return {"success": False, "data": [], "error": str(e)}

    # ─── Case Memory (Living Summary) ─────────────────────────────────────

    def get_case_memory(self, lead_id: int) -> dict:
        """Get the CaseMemory row for a lead."""
        try:
            with self.db_manager.session_scope() as session:
                memory = (
                    session.query(CaseMemory)
                    .filter_by(lead_id=lead_id)
                    .first()
                )
                if not memory:
                    return {"success": True, "data": None}
                data = {
                    "id": memory.id,
                    "lead_id": memory.lead_id,
                    "memory_type": memory.memory_type,
                    "content": memory.content,
                    "note_count_at_summary": memory.note_count_at_summary,
                    "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
                }
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"Failed to get case memory for lead {lead_id}: {e}")
            return {"success": False, "data": None, "error": str(e)}

    def update_case_memory(self, lead_id: int) -> dict:
        """Re-summarize the case by feeding recent CaseNote content to haiku."""
        try:
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if not lead:
                    return {"success": False, "error": f"Lead {lead_id} not found"}

                notes = (
                    session.query(CaseNote)
                    .filter_by(lead_id=lead_id)
                    .order_by(CaseNote.created_at.asc())
                    .all()
                )
                note_count = len(notes)

                if not notes:
                    return {"success": True, "summary": ""}

                # Build notes text for summarization
                notes_text = "\n".join(
                    f"[{n.created_at.strftime('%Y-%m-%d %H:%M') if n.created_at else '?'}] "
                    f"[{n.note_type}] {n.content}"
                    for n in notes
                )

                biz_name = lead.business_name or "Unknown"

            # Summarize via LLM or truncate
            summary = self._summarize_case_notes(biz_name, notes_text)

            # Upsert CaseMemory
            with self.db_manager.session_scope() as session:
                memory = (
                    session.query(CaseMemory)
                    .filter_by(lead_id=lead_id)
                    .first()
                )
                if memory:
                    memory.content = summary
                    memory.note_count_at_summary = note_count
                    memory.updated_at = datetime.utcnow()
                else:
                    session.add(CaseMemory(
                        lead_id=lead_id,
                        memory_type="summary",
                        content=summary,
                        note_count_at_summary=note_count,
                    ))

            return {"success": True, "summary": summary}
        except Exception as e:
            logger.error(f"Failed to update case memory for lead {lead_id}: {e}")
            return {"success": False, "error": str(e)}

    def _summarize_case_notes(self, business_name: str, notes_text: str) -> str:
        """Summarize case notes via haiku or fall back to truncation."""
        if not self.router_engine:
            return notes_text[:2000]

        prompt = (
            f"Summarize the case history for lead '{business_name}'. "
            "Include: key interactions, qualification status, outreach results, "
            "important observations, and current state. Be concise but preserve "
            "all important facts.\n\n"
            f"CASE NOTES:\n{notes_text[:6000]}"
        )

        try:
            result = self.router_engine.route(
                "summarize_case", prompt,
                context={"max_tokens": 500, "temperature": 0.2},
            )
            if result.get("success"):
                return result["data"]
        except Exception as e:
            logger.debug(f"Case summarization LLM call failed: {e}")

        return notes_text[:2000]

    # ─── Build Case Context ───────────────────────────────────────────────

    def build_case_context(self, lead_id: int,
                           max_tokens: int = CASE_CONTEXT_MAX_TOKENS) -> str:
        """Assemble a structured case file string for injection into agent context."""
        try:
            parts = []

            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if not lead:
                    return ""

                # Section 1: Lead info
                parts.append(
                    f"CASE_FILE: {lead.business_name or 'Unknown'} (Lead #{lead.id})\n"
                    f"LEAD_INFO:\n"
                    f"  Business: {lead.business_name} | Category: {lead.category}\n"
                    f"  City: {lead.city} | Email: {lead.email} | Phone: {lead.phone}\n"
                    f"  Website: {lead.website_url}\n"
                    f"  Status: {lead.status} | Lifecycle: {lead.lifecycle_state}"
                )

                # Section 2: Enrichment
                enrichment = (
                    session.query(EnrichmentData)
                    .filter_by(lead_id=lead_id)
                    .first()
                )
                if enrichment:
                    parts.append(
                        f"ENRICHMENT:\n"
                        f"  Rating: {enrichment.google_maps_rating or 'N/A'}/5 "
                        f"({enrichment.google_maps_review_count or 0} reviews)\n"
                        f"  Social: FB={enrichment.has_facebook}, "
                        f"IG={enrichment.has_instagram}, LI={enrichment.has_linkedin}"
                    )

                # Section 3: Case memory (living summary)
                memory = (
                    session.query(CaseMemory)
                    .filter_by(lead_id=lead_id)
                    .first()
                )
                if memory and memory.content:
                    parts.append(f"CASE_SUMMARY:\n  {memory.content}")
                else:
                    parts.append("CASE_SUMMARY:\n  (No summary yet)")

                # Section 4: Recent notes
                notes = (
                    session.query(CaseNote)
                    .filter_by(lead_id=lead_id)
                    .order_by(CaseNote.created_at.desc())
                    .limit(CASE_NOTE_MAX_RECENT)
                    .all()
                )
                if notes:
                    note_lines = []
                    for n in reversed(notes):  # chronological
                        ts = n.created_at.strftime("%m/%d %H:%M") if n.created_at else "?"
                        note_lines.append(f"  [{ts}] [{n.note_type}] {n.content[:200]}")
                    parts.append(
                        f"RECENT_NOTES ({len(notes)}):\n" + "\n".join(note_lines)
                    )

                # Section 5: Conversation thread
                thread = (
                    session.query(ConversationThread)
                    .filter_by(lead_id=lead_id)
                    .order_by(ConversationThread.last_activity.desc())
                    .first()
                )
                if thread and thread.messages_json:
                    try:
                        messages = json.loads(thread.messages_json or "[]")
                        last_msgs = messages[-5:]  # last 5
                        if last_msgs:
                            msg_lines = []
                            for m in last_msgs:
                                role = m.get("role", "?")
                                content = m.get("content", "")[:200]
                                msg_lines.append(f"  [{role}]: {content}")
                            parts.append(
                                f"CONVERSATION (last {len(last_msgs)}):\n"
                                + "\n".join(msg_lines)
                            )
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Section 6: Lifecycle history
                transitions = (
                    session.query(LeadStateTransition)
                    .filter_by(lead_id=lead_id)
                    .order_by(LeadStateTransition.created_at.desc())
                    .limit(5)
                    .all()
                )
                if transitions:
                    trans_lines = []
                    for t in reversed(transitions):
                        ts = t.created_at.strftime("%m/%d %H:%M") if t.created_at else "?"
                        trans_lines.append(
                            f"  {t.from_state} -> {t.to_state} "
                            f"(by: {t.triggered_by}, {ts})"
                        )
                    parts.append(
                        f"LIFECYCLE_HISTORY:\n" + "\n".join(trans_lines)
                    )

                # Section 7: Follow-up history
                followups = (
                    session.query(FollowUpSend)
                    .filter_by(lead_id=lead_id)
                    .order_by(FollowUpSend.sent_at.desc())
                    .all()
                )
                if followups:
                    last_sent = followups[0].sent_at
                    last_str = last_sent.strftime("%Y-%m-%d") if last_sent else "N/A"
                    parts.append(
                        f"FOLLOWUP_HISTORY:\n"
                        f"  {len(followups)} follow-ups sent. Last: {last_str}"
                    )

            result = "\n\n".join(parts)

            # Token-budget the result
            if self.token_manager:
                current_tokens = self.token_manager.estimate_tokens(result)
                if current_tokens > max_tokens:
                    # Truncate to approximately max_tokens
                    ratio = max_tokens / current_tokens
                    target_chars = int(len(result) * ratio)
                    result = result[:target_chars] + "\n[...case context truncated]"

            return result
        except Exception as e:
            logger.error(f"Failed to build case context for lead {lead_id}: {e}")
            return ""

    # ─── Timeline ─────────────────────────────────────────────────────────

    def get_case_timeline(self, lead_id: int, limit: int = 50) -> dict:
        """Return chronological list of all events for a lead."""
        try:
            events = []

            with self.db_manager.session_scope() as session:
                # CaseNotes
                notes = (
                    session.query(CaseNote)
                    .filter_by(lead_id=lead_id)
                    .order_by(CaseNote.created_at.asc())
                    .all()
                )
                for n in notes:
                    events.append({
                        "type": "case_note",
                        "subtype": n.note_type,
                        "content": n.content,
                        "agent_id": n.agent_id,
                        "created_at": n.created_at.isoformat() if n.created_at else None,
                    })

                # LeadStateTransitions
                transitions = (
                    session.query(LeadStateTransition)
                    .filter_by(lead_id=lead_id)
                    .order_by(LeadStateTransition.created_at.asc())
                    .all()
                )
                for t in transitions:
                    events.append({
                        "type": "lifecycle",
                        "subtype": f"{t.from_state}->{t.to_state}",
                        "content": f"{t.from_state} -> {t.to_state} (by: {t.triggered_by})",
                        "agent_id": t.agent_id,
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                    })

                # ConversationThread messages
                thread = (
                    session.query(ConversationThread)
                    .filter_by(lead_id=lead_id)
                    .first()
                )
                if thread and thread.messages_json:
                    try:
                        messages = json.loads(thread.messages_json or "[]")
                        for m in messages:
                            events.append({
                                "type": "conversation",
                                "subtype": m.get("role", "unknown"),
                                "content": m.get("content", ""),
                                "agent_id": None,
                                "created_at": m.get("timestamp"),
                            })
                    except (json.JSONDecodeError, TypeError):
                        pass

            # Sort by created_at
            events.sort(key=lambda e: e.get("created_at") or "")

            return {"success": True, "data": events[:limit]}
        except Exception as e:
            logger.error(f"Failed to get case timeline for lead {lead_id}: {e}")
            return {"success": False, "data": [], "error": str(e)}
