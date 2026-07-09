"""
Aura — Sequence Controller
Runs a 30-min QTimer loop to process due follow-up emails.
"""

from datetime import datetime

from PySide6.QtCore import QObject, Signal, QTimer

from database.db_manager import DatabaseManager
from core.sequence_engine import SequenceEngine
from core.ai_engine import AIEngine
from core.delivery_engine import DeliveryEngine
from config import FOLLOWUP_CHECK_INTERVAL_MS
from utils.logger import get_logger
from utils.thread_worker import ThreadWorker

logger = get_logger("sequence_controller")


class SequenceController(QObject):
    """Background controller for processing follow-up sequences."""

    followup_sent = Signal(int, str)       # lead_id, step_number
    followup_error = Signal(int, str)      # lead_id, error
    batch_complete = Signal(int, int)      # sent_count, failed_count

    def __init__(
        self,
        db_manager: DatabaseManager,
        sequence_engine: SequenceEngine,
        ai_engine: AIEngine,
        delivery_engine: DeliveryEngine,
        parent=None,
    ):
        super().__init__(parent)
        self.db_manager = db_manager
        self.sequence = sequence_engine
        self.ai = ai_engine
        self.delivery = delivery_engine
        self._worker = None

        # 30-minute timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.process_due_followups)
        self._timer.setInterval(FOLLOWUP_CHECK_INTERVAL_MS)

    def start(self):
        """Start the background follow-up timer."""
        logger.info("Follow-up sequence controller started (30-min interval)")
        self._timer.start()

    def stop(self):
        """Stop the background timer."""
        self._timer.stop()

    def process_due_followups(self):
        """Check and process all due follow-ups across campaigns."""
        logger.info("Checking for due follow-ups…")

        def _work():
            sent = 0
            failed = 0

            try:
                from database.schema import Campaign
                with self.db_manager.session_scope() as session:
                    campaigns = (
                        session.query(Campaign)
                        .filter(
                            Campaign.status == "active",
                            Campaign.sequence_id.isnot(None),
                        )
                        .all()
                    )
                    campaign_ids = [c.id for c in campaigns]

                for campaign_id in campaign_ids:
                    due_leads = self.sequence.get_leads_due_for_followup(campaign_id)

                    for lead_data in due_leads:
                        try:
                            # Get skill for this step (extract values inside session)
                            skill_id = lead_data.get("skill_id")
                            skill_system_prompt = ""
                            skill_preferred_model = None
                            if skill_id:
                                from database.schema import Skill
                                with self.db_manager.session_scope() as session:
                                    skill = session.query(Skill).filter_by(id=skill_id).first()
                                    if skill:
                                        skill_system_prompt = skill.system_prompt or ""
                                        skill_preferred_model = skill.preferred_model

                            # Build prompt and generate follow-up
                            prompt = self.sequence.build_followup_prompt(
                                lead_data, lead_data, []
                            )

                            ai_result = self.ai.generate(
                                prompt=prompt,
                                system_prompt=skill_system_prompt,
                                model=skill_preferred_model,
                            )

                            if not ai_result.get("success"):
                                failed += 1
                                self.followup_error.emit(
                                    lead_data["lead_id"],
                                    ai_result.get("error", "AI generation failed"),
                                )
                                continue

                            # Parse the generated email
                            import json
                            try:
                                email_data = json.loads(ai_result.get("response", "{}"))
                                subject = email_data.get("subject", "Follow-up")
                                body = email_data.get("body", "")
                            except (json.JSONDecodeError, AttributeError):
                                subject = f"{lead_data['subject_prefix']}{lead_data['original_subject']}"
                                body = ai_result.get("response", "")

                            # Get sender info
                            settings = self.db_manager.get_settings()
                            from_email = settings.sender_email if settings else ""
                            from_name = settings.sender_name if settings else ""

                            if not from_email:
                                failed += 1
                                continue

                            # Send the follow-up
                            send_result = self.delivery.send_email(
                                to_email=lead_data["lead_email"],
                                from_email=from_email,
                                subject=subject,
                                body=body,
                                from_name=from_name,
                            )

                            if send_result.get("success"):
                                # Mark the send as completed
                                from database.schema import FollowUpSend
                                with self.db_manager.session_scope() as session:
                                    send = session.query(FollowUpSend).filter_by(
                                        id=lead_data["send_id"]
                                    ).first()
                                    if send:
                                        send.status = "sent"
                                        send.sent_at = datetime.utcnow()

                                sent += 1
                                self.followup_sent.emit(
                                    lead_data.get("lead_id", 0),
                                    str(lead_data.get("step_number", "?")),
                                )

                                # Schedule next step
                                self.sequence.schedule_next_step(
                                    lead_data["lead_id"],
                                    lead_data.get("sequence_id", 0),
                                )
                            else:
                                failed += 1
                                # Mark as failed
                                from database.schema import FollowUpSend
                                with self.db_manager.session_scope() as session:
                                    send = session.query(FollowUpSend).filter_by(
                                        id=lead_data["send_id"]
                                    ).first()
                                    if send:
                                        send.status = "failed"

                                self.followup_error.emit(
                                    lead_data["lead_id"],
                                    send_result.get("error", "Send failed"),
                                )
                        except Exception as e:
                            failed += 1
                            logger.error(f"Follow-up error for lead {lead_data.get('lead_id')}: {e}")

            except Exception as e:
                logger.error(f"Follow-up batch processing error: {e}")

            return sent, failed

        def _on_done(result):
            if result:
                sent, failed = result
                logger.info(f"Follow-up batch: {sent} sent, {failed} failed")
                self.batch_complete.emit(sent, failed)

        self._worker = ThreadWorker(_work)
        self._worker.signals.result.connect(_on_done)
        self._worker.start()
