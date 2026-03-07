"""
Aura — Outreach Controller
Orchestrates email generation (Tier 3 AI) and delivery.
Manages draft → review → send workflow.
Supports A/B variant assignment, timezone scheduling, and screenshot attachment.
"""

from datetime import datetime
from PySide6.QtCore import QObject, Signal, QTimer

from core.ai_engine import AIEngine
from core.delivery_engine import DeliveryEngine
from core.key_vault import KeyVault
from core.ab_engine import ABEngine
from core.scheduler_engine import SchedulerEngine
from database.db_manager import DatabaseManager
from sqlalchemy import case as sa_case
from database.schema import Lead, Campaign, Settings, Skill
from config import LeadStatus, SCHEDULE_CHECK_INTERVAL_MS
from utils.thread_worker import ThreadWorker
from utils.logger import get_logger

logger = get_logger("outreach_controller")


class OutreachController(QObject):
    """
    Controls the email outreach pipeline:
    1. Select leads + skill
    2. Generate personalized emails via Tier 3
    3. Review drafts
    4. Send and track delivery status
    """

    email_generated = Signal(dict)     # {lead_id, subject, body, tone}
    email_sent = Signal(int, dict)     # lead_id, delivery_result
    scheduled_queued = Signal(int)     # lead_id (scheduled for later)
    batch_progress = Signal(int)       # 0-100
    batch_finished = Signal(int)       # count sent
    all_channels_drafted = Signal(int, dict)  # lead_id, {email, linkedin, twitter}
    error = Signal(str)
    status_message = Signal(str)

    def __init__(self, db_manager: DatabaseManager, key_vault: KeyVault):
        super().__init__()
        self.db_manager = db_manager
        self.key_vault = key_vault
        self.ai_engine = AIEngine()
        self.delivery = DeliveryEngine()
        self.ab_engine = ABEngine(db_manager)
        self.scheduler_engine = SchedulerEngine(db_manager)
        self._worker = None
        self._drafts = {}  # lead_id -> {subject, body, tone}
        self.channel_engine = None  # Set from main_window if cross-channel enabled
        self.research_engine = None  # Injected by main_window
        self.case_engine = None      # Injected by main_window

        # Scheduled send drain timer (5 minutes)
        self._schedule_timer = QTimer(self)
        self._schedule_timer.timeout.connect(self._drain_schedule_queue)
        self._schedule_enabled = False

    def configure_from_settings(self):
        """Load API keys and model config from DB settings."""
        settings = self.db_manager.get_settings()
        if not settings:
            return

        api_keys = {}
        if settings.gemini_key_enc:
            try:
                api_keys["gemini"] = self.key_vault.decrypt(settings.gemini_key_enc)
            except Exception:
                pass
        if settings.anthropic_key_enc:
            try:
                api_keys["anthropic"] = self.key_vault.decrypt(settings.anthropic_key_enc)
            except Exception:
                pass
        if settings.openai_key_enc:
            try:
                api_keys["openai"] = self.key_vault.decrypt(settings.openai_key_enc)
            except Exception:
                pass

        models = {}
        if settings.tier2_model:
            models["tier2"] = settings.tier2_model
        if settings.tier3_model:
            models["tier3"] = settings.tier3_model

        # Subscription tokens as fallback
        sub_tokens = {}
        for name, field in [("anthropic_sub", "anthropic_sub_token_enc"),
                            ("openai_sub", "openai_sub_token_enc")]:
            enc = getattr(settings, field, "")
            if enc:
                try:
                    sub_tokens[name] = self.key_vault.decrypt(enc)
                except Exception:
                    pass

        self.ai_engine.configure(api_keys, models, sub_tokens=sub_tokens)

        # Configure delivery
        if settings.resend_key_enc:
            try:
                resend_key = self.key_vault.decrypt(settings.resend_key_enc)
                self.delivery.configure_resend(resend_key)
            except Exception:
                pass

        if settings.smtp_host:
            smtp_pass = ""
            if settings.smtp_password_enc:
                try:
                    smtp_pass = self.key_vault.decrypt(settings.smtp_password_enc)
                except Exception:
                    pass
            self.delivery.configure_smtp(
                host=settings.smtp_host,
                port=settings.smtp_port or 587,
                username=settings.smtp_user or "",
                password=smtp_pass,
                use_tls=True,
            )

    def generate_draft(self, lead_id: int, skill_id: int) -> dict:
        """Generate a single email draft for a lead using a skill."""
        self.configure_from_settings()

        with self.db_manager.session_scope() as session:
            lead = session.query(Lead).filter_by(id=lead_id).first()
            campaign = session.query(Campaign).filter_by(id=lead.campaign_id).first() if lead else None
            skill = session.query(Skill).filter_by(id=skill_id).first()
            settings = session.query(Settings).first()

            if not lead or not skill:
                self.error.emit("Lead or skill not found.")
                return {}

            # A/B variant assignment
            actual_skill_id = skill_id
            if campaign and settings and getattr(settings, 'ab_test_enabled', False):
                if campaign.ab_skill_b_id:
                    variant = self.ab_engine.assign_variant(
                        lead_id=lead_id,
                        campaign=campaign,
                    )
                    actual_skill_id = self.ab_engine.get_skill_for_variant(
                        campaign=campaign, variant=variant
                    )
                    # Update lead with variant
                    lead.ab_variant = variant
                    # Re-fetch skill if different
                    if actual_skill_id != skill_id:
                        skill = session.query(Skill).filter_by(id=actual_skill_id).first()
                        if not skill:
                            self.error.emit(f"A/B variant skill #{actual_skill_id} not found.")
                            return {}

            lead_data = {
                "business_name": lead.business_name,
                "category": lead.category,
                "city": lead.city,
                "website_url": lead.website_url,
                "source_platform": lead.source_platform,
            }
            skill_data = {
                "name": skill.name,
                "system_prompt": skill.system_prompt,
                "tone": skill.tone,
            }
            sender_name = settings.sender_name if settings else "Alex"
            sender_company = settings.sender_company if settings else "Aura"
            ab_variant = getattr(lead, 'ab_variant', None)

        # Fetch research + case context for personalization
        research_context = ""
        case_context = ""
        if self.research_engine:
            try:
                report = self.research_engine.get_report(lead_id)
                if report.get("success") and report.get("data"):
                    rd = report["data"]
                    parts = []
                    for key in ["company_overview", "pain_points", "gaps_opportunities",
                                "services_offered", "tech_stack"]:
                        if rd.get(key):
                            parts.append(f"{key.replace('_', ' ').title()}: {rd[key]}")
                    research_context = "\n".join(parts)
            except Exception as e:
                logger.warning(f"Research context fetch failed: {e}")
        if self.case_engine:
            try:
                case_context = self.case_engine.build_case_context(lead_id)
            except Exception as e:
                logger.warning(f"Case context fetch failed: {e}")

        email = self.ai_engine.generate_email(
            lead_data=lead_data,
            skill=skill_data,
            sender_name=sender_name,
            sender_company=sender_company,
            research_context=research_context,
            case_context=case_context,
        )

        draft = {
            "lead_id": lead_id,
            "subject": email.get("subject", ""),
            "body": email.get("body", ""),
            "tone": email.get("tone", ""),
            "variant": ab_variant,
        }

        self._drafts[lead_id] = draft
        self.email_generated.emit(draft)
        return draft

    def send_email(self, lead_id: int, to_email: str, subject: str = None, body: str = None):
        """Send an email for a specific lead. May schedule for later if timezone scheduling is on."""
        self.configure_from_settings()

        draft = self._drafts.get(lead_id, {})
        subject = subject or draft.get("subject", "")
        body = body or draft.get("body", "")

        if not subject or not body:
            self.error.emit("Subject and body are required.")
            return

        if not to_email:
            self.error.emit("Recipient email is required.")
            return

        settings = self.db_manager.get_settings()
        from_email = settings.sender_email if settings else "noreply@example.com"
        from_name = settings.sender_name if settings else ""

        # Check timezone scheduling
        if settings and getattr(settings, 'send_schedule_enabled', False):
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if lead and lead.city:
                    tz_offset = self.scheduler_engine.detect_timezone_offset(lead.city)
                    send_time = self.scheduler_engine.calculate_optimal_send_time(tz_offset)
                    if send_time:
                        now_utc = datetime.utcnow()
                        if send_time > now_utc:
                            # Schedule for later
                            lead.scheduled_send_at = send_time
                            lead.email_subject = subject
                            lead.status = LeadStatus.SCHEDULED
                            self.scheduled_queued.emit(lead_id)
                            logger.info(f"Lead #{lead_id} scheduled for {send_time}")
                            if not self._schedule_timer.isActive():
                                self._schedule_timer.start(SCHEDULE_CHECK_INTERVAL_MS)
                            return

        result = self.delivery.send_email(
            to_email=to_email,
            from_email=from_email,
            subject=subject,
            body=body,
            from_name=from_name,
        )

        # Update lead status
        if result["success"]:
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if lead:
                    lead.status = "emailed"
                    lead.email_subject = subject
                    lead.email_body = body
                    lead.email_sent_at = datetime.utcnow()

        self.email_sent.emit(lead_id, result)

    def get_outreach_leads(self, campaign_id: int) -> list:
        """Get all leads eligible for outreach (qualified, researched, or new with email)."""
        with self.db_manager.session_scope() as session:
            leads = (
                session.query(Lead)
                .filter(
                    Lead.campaign_id == campaign_id,
                    Lead.email.isnot(None),
                    Lead.email != "",
                    Lead.status.in_(["qualified", "researched", "new"]),
                )
                .order_by(
                    sa_case(
                        (Lead.status == "qualified", 0),
                        (Lead.status == "researched", 1),
                        else_=2,
                    )
                )
                .all()
            )
            return [
                {
                    "id": l.id,
                    "business_name": l.business_name,
                    "category": l.category,
                    "city": l.city,
                    "email": l.email,
                    "phone": l.phone,
                    "website_url": l.website_url,
                    "status": l.status,
                }
                for l in leads
            ]

    def get_campaigns(self) -> list:
        """Get all campaigns for the outreach selector."""
        with self.db_manager.session_scope() as session:
            campaigns = session.query(Campaign).order_by(Campaign.created_at.desc()).all()
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "total_leads": c.total_leads,
                    "qualified_leads": c.qualified_leads,
                    "status": c.status,
                }
                for c in campaigns
            ]

    @property
    def drafts(self):
        return self._drafts

    def _drain_schedule_queue(self):
        """Check for leads whose scheduled send time has passed and send them."""
        ready_ids = self.scheduler_engine.get_leads_ready_to_send()
        if not ready_ids:
            return

        self.configure_from_settings()
        settings = self.db_manager.get_settings()
        from_email = settings.sender_email if settings else "noreply@example.com"
        from_name = settings.sender_name if settings else ""

        for lead_id in ready_ids:
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if not lead or not lead.email:
                    continue

                to_email = lead.email
                subject = lead.email_subject or ""
                body = self._drafts.get(lead_id, {}).get("body", "")

                if not to_email or not subject:
                    continue

                result = self.delivery.send_email(
                    to_email=to_email,
                    from_email=from_email,
                    subject=subject,
                    body=body,
                    from_name=from_name,
                )

                if result["success"]:
                    lead.status = "emailed"
                    lead.scheduled_send_at = None

                self.email_sent.emit(lead_id, result)

    def start_schedule_timer(self):
        """Start the scheduled send drain timer."""
        if not self._schedule_timer.isActive():
            self._schedule_timer.start(SCHEDULE_CHECK_INTERVAL_MS)
            self._schedule_enabled = True
            logger.info("Schedule drain timer started")

    def stop_schedule_timer(self):
        """Stop the scheduled send drain timer."""
        self._schedule_timer.stop()
        self._schedule_enabled = False

    def generate_all_channel_drafts(self, lead_id: int, skill_id: int):
        """Generate drafts for all channels (email + linkedin + twitter)."""
        if not self.channel_engine:
            # Fall back to email-only
            self.generate_draft(lead_id, skill_id)
            return

        self.configure_from_settings()

        with self.db_manager.session_scope() as session:
            lead = session.query(Lead).filter_by(id=lead_id).first()
            skill = session.query(Skill).filter_by(id=skill_id).first()
            settings = session.query(Settings).first()

            if not lead or not skill:
                self.error.emit("Lead or skill not found.")
                return

            lead_data = {
                "business_name": lead.business_name,
                "category": lead.category,
                "city": lead.city,
                "website_url": lead.website_url,
                "source_platform": lead.source_platform,
            }
            skill_data = {
                "name": skill.name,
                "system_prompt": skill.system_prompt,
                "tone": skill.tone,
            }
            sender_name = settings.sender_name if settings else "Alex"
            sender_company = settings.sender_company if settings else "Aura"

        drafts = self.channel_engine.generate_all_channels(
            lead_data, skill_data, sender_name, sender_company
        )

        # Save to DB
        self.channel_engine.save_channel_drafts(lead_id, drafts)

        # Also keep email draft in local cache
        if "email" in drafts:
            self._drafts[lead_id] = {
                "lead_id": lead_id,
                "subject": drafts["email"].get("subject", ""),
                "body": drafts["email"].get("body", ""),
                "tone": "",
            }

        self.all_channels_drafted.emit(lead_id, drafts)
