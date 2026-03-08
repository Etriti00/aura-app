"""
Aura — Triage Engine
Automated inbox triage: fetch overnight emails, categorize, summarize,
auto-draft replies, process unsubscribes.
"""

import imaplib
import email as email_lib
from email.header import decode_header
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from database.db_manager import DatabaseManager
from database.schema import Lead, Settings, ChannelDraft
from core.key_vault import KeyVault
from utils.logger import get_logger

logger = get_logger("triage_engine")


class TriageEngine:
    """
    Morning inbox triage: fetches emails, categorizes them,
    generates a summary, and auto-drafts warm replies.
    """

    def __init__(self, db_manager: DatabaseManager, key_vault: KeyVault,
                 ai_engine=None, suppression_engine=None):
        self.db_manager = db_manager
        self.key_vault = key_vault
        self.ai_engine = ai_engine
        self.suppression = suppression_engine

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
                    return None

            return {
                "host": settings.imap_host,
                "port": settings.imap_port or 993,
                "username": settings.imap_username or "",
                "password": password,
                "use_ssl": settings.imap_use_ssl if settings.imap_use_ssl is not None else True,
            }
        except Exception as e:
            logger.error(f"IMAP config error: {e}")
            return None

    # ─── Fetch & Categorize ────────────────────────────────────────

    def fetch_overnight_emails(self, hours_back: int = 12) -> List[dict]:
        """
        Fetch emails from the last N hours and categorize them.
        Returns list of {from, subject, body, category, lead_id}.
        Categories: reply, bounce, unsubscribe, other.
        """
        config = self._get_imap_config()
        if not config:
            return []

        mail = None
        try:
            since = datetime.utcnow() - timedelta(hours=hours_back)
            date_str = since.strftime("%d-%b-%Y")

            if config["use_ssl"]:
                mail = imaplib.IMAP4_SSL(config["host"], config["port"])
            else:
                mail = imaplib.IMAP4(config["host"], config["port"])

            mail.login(config["username"], config["password"])
            mail.select("INBOX")

            _, msg_ids = mail.search(None, f'(SINCE "{date_str}")')
            if not msg_ids[0]:
                return []

            emails = []
            for msg_id in msg_ids[0].split()[:100]:  # Cap at 100
                try:
                    _, msg_data = mail.fetch(msg_id, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email_lib.message_from_bytes(raw)

                    from_addr = self._decode_header(msg.get("From", ""))
                    subject = self._decode_header(msg.get("Subject", ""))
                    body = self._extract_body(msg)[:2000]

                    category = self._categorize_email(from_addr, subject, body)

                    emails.append({
                        "from": from_addr,
                        "subject": subject,
                        "body": body,
                        "category": category,
                        "lead_id": self._match_to_lead(from_addr),
                    })
                except Exception as e:
                    logger.warning(f"Error parsing email {msg_id}: {e}")

            return emails

        except Exception as e:
            logger.error(f"Triage IMAP fetch failed: {e}")
            return []
        finally:
            if mail:
                try:
                    mail.logout()
                except Exception:
                    pass

    def _categorize_email(self, from_addr: str, subject: str, body: str) -> str:
        """Categorize an email based on heuristics."""
        subject_lower = subject.lower()
        body_lower = body.lower()

        # Bounce detection
        bounce_keywords = ["delivery failed", "undeliverable", "returned mail",
                          "mail delivery", "postmaster", "mailer-daemon"]
        if any(kw in subject_lower or kw in from_addr.lower() for kw in bounce_keywords):
            return "bounce"

        # Unsubscribe detection
        unsub_keywords = ["unsubscribe", "opt out", "opt-out", "remove me",
                         "stop emailing", "do not contact"]
        if any(kw in subject_lower or kw in body_lower for kw in unsub_keywords):
            return "unsubscribe"

        # Reply detection (subject starts with Re:)
        import re
        if re.match(r'^re\s*:', subject_lower):
            return "reply"

        return "other"

    def _match_to_lead(self, from_addr: str) -> Optional[int]:
        """Try to match an email sender to an existing lead."""
        # Extract email from "Name <email@example.com>" format
        import re
        match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', from_addr)
        if not match:
            return None

        email_addr = match.group().lower()
        try:
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter(
                    Lead.email.ilike(email_addr)
                ).first()
                return lead.id if lead else None
        except Exception:
            return None

    # ─── Summary Generation ────────────────────────────────────────

    def generate_triage_summary(self, categorized_emails: List[dict]) -> str:
        """Generate an executive summary of overnight emails."""
        if not categorized_emails:
            return "No new emails to triage."

        # Count by category
        counts = {}
        for em in categorized_emails:
            cat = em.get("category", "other")
            counts[cat] = counts.get(cat, 0) + 1

        # Build summary without AI if no engine available
        if not self.ai_engine:
            lines = ["Inbox Triage Summary", "=" * 30]
            for cat, count in sorted(counts.items()):
                lines.append(f"  {cat.title()}: {count}")
            lines.append(f"\nTotal: {len(categorized_emails)} emails")
            return "\n".join(lines)

        # Use AI for a richer summary
        email_descriptions = []
        for em in categorized_emails[:20]:  # Limit for prompt size
            email_descriptions.append(
                f"- [{em['category'].upper()}] From: {em['from'][:50]} | Subject: {em['subject'][:80]}"
            )

        prompt = f"""Summarize these overnight inbox results concisely for a sales team morning briefing.

Counts: {counts}

Emails:
{chr(10).join(email_descriptions)}

Write a brief 3-5 sentence executive summary highlighting:
1. Key replies that need attention
2. Any bounces that indicate bad data
3. Unsubscribe requests to process
4. Actionable next steps"""

        if self.ai_engine.router:
            result = self.ai_engine.router.route("analyze_performance", prompt, {"max_tokens": 256})
            return result.get("data", "Summary generation failed") if result.get("success") else "Summary generation failed"
        else:
            return self.ai_engine._call_llm(
                self.ai_engine._models["tier3"],
                [{"role": "user", "content": prompt}],
                max_tokens=256,
            ) or "Summary generation failed"

    # ─── Auto-Draft Replies ────────────────────────────────────────

    def auto_draft_reply_responses(self, reply_emails: List[dict]) -> List[dict]:
        """Draft warm reply responses for detected replies."""
        drafts = []
        if not self.ai_engine:
            return drafts

        for em in reply_emails:
            if not em.get("lead_id"):
                continue

            prompt = f"""Write a brief, warm follow-up reply to this email. Keep it under 50 words.
Be conversational and acknowledge what they said.

Their message:
Subject: {em.get('subject', '')}
Body: {em.get('body', '')[:500]}

Reply (just the body text, no subject):"""

            if self.ai_engine.router:
                result = self.ai_engine.router.route("generate_email", prompt, {"max_tokens": 128, "temperature": 0.7})
                body = result.get("data", "") if result.get("success") else ""
            else:
                body = self.ai_engine._call_llm(
                    self.ai_engine._models["tier3"],
                    [{"role": "user", "content": prompt}],
                    max_tokens=128,
                ) or ""

            if body:
                # Save as channel draft
                try:
                    with self.db_manager.session_scope() as session:
                        draft = ChannelDraft(
                            lead_id=em["lead_id"],
                            channel="email",
                            subject=f"Re: {em.get('subject', '')}",
                            body=body.strip(),
                            status="draft",
                            created_at=datetime.utcnow(),
                        )
                        session.add(draft)
                    drafts.append({
                        "lead_id": em["lead_id"],
                        "subject": f"Re: {em.get('subject', '')}",
                        "body": body.strip(),
                    })
                except Exception as e:
                    logger.warning(f"Failed to save triage draft: {e}")

        return drafts

    # ─── Unsubscribe Processing ────────────────────────────────────

    def process_unsubscribes(self, unsub_emails: List[dict]):
        """Add unsubscribe requests to suppression list and disqualify leads."""
        for em in unsub_emails:
            # Extract email from sender
            import re
            match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', em.get("from", ""))
            if not match:
                continue

            email_addr = match.group().lower()

            # Add to suppression
            if self.suppression:
                self.suppression.add_email(email_addr, reason="triage_unsubscribe")

            # Disqualify lead if matched
            if em.get("lead_id"):
                try:
                    with self.db_manager.session_scope() as session:
                        lead = session.query(Lead).filter_by(id=em["lead_id"]).first()
                        if lead:
                            lead.status = "disqualified"
                except Exception as e:
                    logger.warning(f"Failed to disqualify lead {em['lead_id']}: {e}")

    # ─── Full Morning Triage ───────────────────────────────────────

    def run_morning_triage(self) -> dict:
        """Orchestrate the full morning triage workflow."""
        logger.info("Starting morning triage...")

        # Step 1: Fetch
        emails = self.fetch_overnight_emails()
        if not emails:
            return {"summary": "No new emails overnight.", "replies": [], "unsubscribes": 0, "bounces": 0}

        # Step 2: Group by category
        replies = [e for e in emails if e["category"] == "reply"]
        bounces = [e for e in emails if e["category"] == "bounce"]
        unsubs = [e for e in emails if e["category"] == "unsubscribe"]

        # Step 3: Process unsubscribes
        if unsubs:
            self.process_unsubscribes(unsubs)

        # Step 4: Auto-draft replies
        drafts = self.auto_draft_reply_responses(replies)

        # Step 5: Generate summary
        summary = self.generate_triage_summary(emails)

        result = {
            "summary": summary,
            "total_emails": len(emails),
            "replies": len(replies),
            "bounces": len(bounces),
            "unsubscribes": len(unsubs),
            "drafts_created": len(drafts),
            "draft_details": drafts,
        }

        logger.info(f"Triage complete: {result['total_emails']} emails, "
                    f"{result['replies']} replies, {result['bounces']} bounces, "
                    f"{result['unsubscribes']} unsubs")
        return result

    # ─── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _decode_header(value: str) -> str:
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
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        return ""
