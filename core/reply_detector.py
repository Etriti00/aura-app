"""
Aura — Reply Detector
Detects replies to sent emails via IMAP inbox scanning.
Matches replies using Message-ID headers and subject line similarity.
"""

import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from typing import Optional

from database.db_manager import DatabaseManager
from database.schema import Lead, Campaign, Settings, FollowUpSend
from utils.logger import get_logger

logger = get_logger("reply_detector")


class ReplyDetector:
    """Scans IMAP inbox for replies to sent outreach emails."""

    def __init__(self, db_manager: DatabaseManager, key_vault):
        self.db_manager = db_manager
        self.key_vault = key_vault
        self.rag_engine = None  # Optional RAGEngine for storing replied emails
        self.conversation_engine = None  # injected by main_window
        self.lead_lifecycle_engine = None  # injected by main_window
        self.knowledge_graph_engine = None  # injected by main_window
        self.strategy_engine = None  # injected by main_window
        self._suggested_response = None  # last generated response data

    def _get_imap_config(self) -> Optional[dict]:
        """Load IMAP credentials from settings."""
        try:
            settings = self.db_manager.get_settings()
            if not settings or not settings.imap_host:
                return None

            password = ""
            if settings.imap_password_enc:
                try:
                    password = self.key_vault.decrypt(settings.imap_password_enc)
                except Exception:
                    logger.error("Failed to decrypt IMAP password")
                    return None

            return {
                "host": settings.imap_host,
                "port": settings.imap_port or 993,
                "username": settings.imap_username or "",
                "password": password,
                "use_ssl": settings.imap_use_ssl if settings.imap_use_ssl is not None else True,
            }
        except Exception as e:
            logger.error(f"Error loading IMAP config: {e}")
            return None

    def check_inbox(self) -> list:
        """
        Connect to IMAP and search for replies to sent outreach emails.
        Returns list of {"lead_id": int, "reply_body": str, "received_at": datetime}
        """
        config = self._get_imap_config()
        if not config:
            return []

        try:
            # Find the oldest email_sent_at to limit IMAP search window
            with self.db_manager.session_scope() as session:
                oldest_sent = (
                    session.query(Lead.email_sent_at)
                    .filter(Lead.email_sent_at.isnot(None))
                    .order_by(Lead.email_sent_at.asc())
                    .first()
                )
                if not oldest_sent or not oldest_sent[0]:
                    logger.info("No sent emails found — skipping inbox check")
                    return []

                since_date = oldest_sent[0] - timedelta(days=1)

                # Get all sent leads for matching
                sent_leads = (
                    session.query(Lead)
                    .filter(Lead.status.in_(["emailed", "email_sent"]))
                    .filter(Lead.email_sent_at.isnot(None))
                    .all()
                )
                lead_subjects = {}
                for lead in sent_leads:
                    # Normalize subject for matching
                    subj = (lead.email_subject or "").strip()
                    subj_clean = self._strip_reply_prefix(subj).lower()
                    if subj_clean:
                        lead_subjects[subj_clean] = lead.id

            # Connect to IMAP
            if config["use_ssl"]:
                mail = imaplib.IMAP4_SSL(config["host"], config["port"])
            else:
                mail = imaplib.IMAP4(config["host"], config["port"])

            mail.login(config["username"], config["password"])
            mail.select("INBOX")

            # Search for emails since the oldest send date
            date_str = since_date.strftime("%d-%b-%Y")
            _, msg_ids = mail.search(None, f'(SINCE "{date_str}")')

            if not msg_ids[0]:
                mail.logout()
                return []

            replies = []
            for msg_id in msg_ids[0].split():
                try:
                    _, msg_data = mail.fetch(msg_id, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    # Try Message-ID / In-Reply-To match first
                    # (would require storing message IDs — for now use subject match)

                    # Subject match
                    subject = self._decode_header_value(msg.get("Subject", ""))
                    subject_clean = self._strip_reply_prefix(subject).lower()

                    matched_lead_id = lead_subjects.get(subject_clean)
                    if not matched_lead_id:
                        continue

                    # Extract body
                    body = self._extract_body(msg)
                    received_at = self._parse_date(msg.get("Date", ""))

                    replies.append({
                        "lead_id": matched_lead_id,
                        "reply_body": body[:2000],  # Limit stored body
                        "received_at": received_at or datetime.utcnow(),
                    })
                except Exception as e:
                    logger.warning(f"Error parsing email {msg_id}: {e}")
                    continue

            mail.logout()
            logger.info(f"Found {len(replies)} replies from inbox scan")
            return replies

        except Exception as e:
            logger.error(f"IMAP check failed: {e}")
            return []

    def mark_lead_replied(self, lead_id: int, reply_body: str, received_at: datetime) -> dict:
        """
        Update a lead's status to replied and cancel pending follow-ups.
        """
        try:
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if not lead:
                    return {"success": False, "error": "Lead not found"}

                # Don't re-mark already replied leads
                if lead.status == "replied":
                    return {"success": True, "data": {"already_replied": True}}

                lead.status = "replied"

                # Append reply to notes
                timestamp = received_at.strftime("%Y-%m-%d %H:%M")
                separator = "\n\n" if lead.notes else ""
                lead.notes = (lead.notes or "") + f"{separator}--- REPLY ({timestamp}) ---\n{reply_body}"

                # Increment campaign reply counter
                campaign = session.query(Campaign).filter_by(id=lead.campaign_id).first()
                if campaign:
                    campaign.replies = (campaign.replies or 0) + 1

                # Cancel pending follow-ups
                pending = (
                    session.query(FollowUpSend)
                    .filter_by(lead_id=lead_id, status="scheduled")
                    .all()
                )
                for send in pending:
                    send.status = "skipped"

                # Store in RAG memory as a replied email
                if self.rag_engine and lead.email_subject:
                    try:
                        self.rag_engine.store_successful_email(
                            lead_id=lead_id,
                            subject=lead.email_subject or "",
                            body=lead.notes or "",
                            reply_received=True,
                        )
                    except Exception as rag_err:
                        logger.warning(f"Failed to store reply in RAG: {rag_err}")

            # ─── Post-reply hooks (outside session scope) ───
            # Read feature toggles
            toggles = self._get_feature_toggles()

            # Lifecycle transition: contacted → replied (always on — core flow)
            if self.lead_lifecycle_engine:
                try:
                    self.lead_lifecycle_engine.transition(
                        lead_id=lead_id,
                        to_state="replied",
                        triggered_by="reply_detector",
                        metadata={"reply_preview": reply_body[:200]},
                    )
                except Exception as e:
                    logger.debug(f"Lifecycle transition failed: {e}")

            # Conversation engine: classify intent, append message, generate response
            if self.conversation_engine and toggles.get("conversation", False):
                try:
                    response_result = self.conversation_engine.generate_response(
                        lead_id=lead_id, reply_text=reply_body[:2000],
                    )
                    if response_result.get("success"):
                        self._suggested_response = response_result.get("data", {})
                except Exception as e:
                    logger.debug(f"Conversation hook failed: {e}")

            # Knowledge graph: record reply interaction
            if self.knowledge_graph_engine and toggles.get("knowledge_graph", False) and lead_id:
                try:
                    self.knowledge_graph_engine.add_node(
                        node_type="lead", node_key=str(lead_id),
                        properties={"last_reply_outcome": "replied"},
                    )
                except Exception as e:
                    logger.debug(f"Knowledge graph hook failed: {e}")

            # Strategy: update active goal progress on replies
            if self.strategy_engine:
                try:
                    goals = self.strategy_engine.get_all_goals(status="active")
                    for goal in goals.get("data", []):
                        if goal.get("target_metric") == "replies":
                            self.strategy_engine.update_progress(goal["id"])
                except Exception as e:
                    logger.debug(f"Strategy progress update failed: {e}")

            return {"success": True, "data": {"lead_id": lead_id, "status": "replied"}}
        except Exception as e:
            logger.error(f"Error marking lead replied: {e}")
            return {"success": False, "error": str(e)}

    def test_connection(self) -> dict:
        """Test IMAP connection with current settings."""
        config = self._get_imap_config()
        if not config:
            return {"success": False, "error": "IMAP not configured"}

        try:
            if config["use_ssl"]:
                mail = imaplib.IMAP4_SSL(config["host"], config["port"])
            else:
                mail = imaplib.IMAP4(config["host"], config["port"])

            mail.login(config["username"], config["password"])
            mail.select("INBOX")
            _, msgs = mail.search(None, "ALL")
            count = len(msgs[0].split()) if msgs[0] else 0
            mail.logout()

            return {"success": True, "data": {"message_count": count}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_feature_toggles(self) -> dict:
        """Read feature toggles from Settings."""
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    return {
                        "conversation": getattr(settings, "conversation_engine_enabled", False),
                        "knowledge_graph": getattr(settings, "knowledge_graph_enabled", False),
                    }
        except Exception:
            pass
        return {"conversation": False, "knowledge_graph": False}

    # ─── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _strip_reply_prefix(subject: str) -> str:
        """Remove Re:, Fwd:, etc. prefixes from subject."""
        import re
        return re.sub(r'^(re|fwd|fw)\s*:\s*', '', subject, flags=re.IGNORECASE).strip()

    @staticmethod
    def _decode_header_value(value: str) -> str:
        """Decode MIME-encoded header value."""
        try:
            parts = decode_header(value)
            decoded = []
            for part, charset in parts:
                if isinstance(part, bytes):
                    decoded.append(part.decode(charset or "utf-8", errors="replace"))
                else:
                    decoded.append(part)
            return " ".join(decoded)
        except Exception:
            return str(value)

    @staticmethod
    def _extract_body(msg) -> str:
        """Extract plain text body from email message."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """Parse email Date header into datetime."""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str).replace(tzinfo=None)
        except Exception:
            return None
