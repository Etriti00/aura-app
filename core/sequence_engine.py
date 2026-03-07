"""
Aura — Follow-Up Sequence Engine
Manages multi-step follow-up email sequences for campaigns.
"""

from datetime import datetime, timedelta

from database.db_manager import DatabaseManager
from database.schema import (
    Lead, Campaign, FollowUpSequence, FollowUpStep, FollowUpSend, Settings
)
from utils.logger import get_logger

logger = get_logger("sequence_engine")


class SequenceEngine:
    """Manages follow-up sequences: scheduling, tracking, and prompt building."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def get_leads_due_for_followup(self, campaign_id: int) -> list:
        """
        Find leads with scheduled follow-ups that are due now.
        Returns list of dicts with lead info + step details.
        """
        try:
            with self.db_manager.session_scope() as session:
                now = datetime.utcnow()
                due_sends = (
                    session.query(FollowUpSend)
                    .join(FollowUpStep)
                    .join(FollowUpSequence)
                    .join(Lead, FollowUpSend.lead_id == Lead.id)
                    .filter(
                        FollowUpSequence.campaign_id == campaign_id,
                        FollowUpSend.status == "scheduled",
                        FollowUpSend.scheduled_for <= now,
                    )
                    .all()
                )

                results = []
                for send in due_sends:
                    lead = session.query(Lead).filter_by(id=send.lead_id).first()
                    step = session.query(FollowUpStep).filter_by(id=send.step_id).first()
                    if not lead or not step:
                        continue
                    results.append({
                        "lead_id": lead.id,
                        "lead_email": lead.email,
                        "business_name": lead.business_name,
                        "category": lead.category,
                        "city": lead.city,
                        "website_url": lead.website_url,
                        "original_subject": lead.email_subject,
                        "original_body": lead.email_body,
                        "send_id": send.id,
                        "step_id": step.id,
                        "step_number": step.step_number,
                        "sequence_id": step.sequence_id,
                        "skill_id": step.skill_id,
                        "subject_prefix": step.subject_prefix or "Re: ",
                    })
                return results
        except Exception as e:
            logger.error(f"Error getting due follow-ups: {e}")
            return []

    def schedule_next_step(self, lead_id: int, sequence_id: int) -> dict:
        """
        Schedule the next follow-up step for a lead.
        Returns {"done": True} if all steps completed, or step details.
        """
        try:
            with self.db_manager.session_scope() as session:
                # Count completed sends for this lead in this sequence
                completed = (
                    session.query(FollowUpSend)
                    .join(FollowUpStep)
                    .filter(
                        FollowUpSend.lead_id == lead_id,
                        FollowUpStep.sequence_id == sequence_id,
                        FollowUpSend.status == "sent",
                    )
                    .count()
                )

                # Get all steps in order
                steps = (
                    session.query(FollowUpStep)
                    .filter_by(sequence_id=sequence_id)
                    .order_by(FollowUpStep.step_number)
                    .all()
                )

                if completed >= len(steps):
                    return {"success": True, "done": True}

                next_step = steps[completed]

                # Calculate scheduled time
                last_send = (
                    session.query(FollowUpSend)
                    .join(FollowUpStep)
                    .filter(
                        FollowUpSend.lead_id == lead_id,
                        FollowUpStep.sequence_id == sequence_id,
                        FollowUpSend.status == "sent",
                    )
                    .order_by(FollowUpSend.sent_at.desc())
                    .first()
                )

                if last_send and last_send.sent_at:
                    base_time = last_send.sent_at
                else:
                    # First follow-up — base from original email sent time
                    lead = session.query(Lead).filter_by(id=lead_id).first()
                    base_time = lead.email_sent_at if lead and lead.email_sent_at else datetime.utcnow()

                scheduled_for = base_time + timedelta(days=next_step.delay_days)

                # Create the send record
                new_send = FollowUpSend(
                    lead_id=lead_id,
                    step_id=next_step.id,
                    scheduled_for=scheduled_for,
                    status="scheduled",
                )
                session.add(new_send)

                return {
                    "success": True,
                    "done": False,
                    "step_number": next_step.step_number,
                    "scheduled_for": scheduled_for.isoformat(),
                    "delay_days": next_step.delay_days,
                    "skill_id": next_step.skill_id,
                }
        except Exception as e:
            logger.error(f"Error scheduling next step: {e}")
            return {"success": False, "error": str(e)}

    def build_followup_prompt(self, lead: dict, step: dict, prior_sends: list) -> str:
        """
        Build a context-aware follow-up prompt for AI email generation.
        Includes original email, prior follow-ups, and instructions.
        """
        parts = [
            f"You are writing a follow-up email to {lead.get('business_name', 'a business')}.",
            f"Industry: {lead.get('category', 'unknown')}",
            f"Location: {lead.get('city', 'unknown')}",
            "",
            "--- ORIGINAL EMAIL SENT ---",
            f"Subject: {lead.get('original_subject', '')}",
            f"Body: {lead.get('original_body', '')}",
            "",
        ]

        if prior_sends:
            parts.append("--- PRIOR FOLLOW-UP EMAILS SENT ---")
            for i, ps in enumerate(prior_sends, 1):
                parts.append(f"Follow-up #{i} (sent {ps.get('sent_at', 'unknown')}):")
                parts.append(f"  Subject: {ps.get('subject', '')}")
                parts.append(f"  Body: {ps.get('body', '')}")
                parts.append("")

        parts.extend([
            "--- INSTRUCTIONS ---",
            f"This is follow-up #{step.get('step_number', 1)}.",
            f"Use the subject prefix: \"{step.get('subject_prefix', 'Re: ')}\"",
            "Write a follow-up email. Do not repeat the same angle as previous emails.",
            "Be briefer each time. Reference that you emailed before without sounding desperate.",
            "Return JSON with keys: subject, body",
        ])

        return "\n".join(parts)

    def get_sequences_for_campaign(self, campaign_id: int = None) -> list:
        """Get all sequences, optionally filtered by campaign."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(FollowUpSequence)
                if campaign_id:
                    query = query.filter_by(campaign_id=campaign_id)
                sequences = query.all()
                results = []
                for seq in sequences:
                    steps_data = []
                    for step in seq.steps:
                        steps_data.append({
                            "id": step.id,
                            "step_number": step.step_number,
                            "delay_days": step.delay_days,
                            "skill_id": step.skill_id,
                            "subject_prefix": step.subject_prefix,
                        })
                    results.append({
                        "id": seq.id,
                        "name": seq.name,
                        "campaign_id": seq.campaign_id,
                        "is_active": seq.is_active,
                        "steps": steps_data,
                    })
                return results
        except Exception as e:
            logger.error(f"Error getting sequences: {e}")
            return []

    def create_sequence(self, name: str, campaign_id: int, steps: list) -> dict:
        """
        Create a new follow-up sequence with steps.
        steps: [{"delay_days": int, "skill_id": int, "subject_prefix": str}, ...]
        """
        try:
            with self.db_manager.session_scope() as session:
                seq = FollowUpSequence(
                    name=name,
                    campaign_id=campaign_id,
                    is_active=True,
                )
                session.add(seq)
                session.flush()

                for i, step_data in enumerate(steps, 1):
                    step = FollowUpStep(
                        sequence_id=seq.id,
                        step_number=i,
                        delay_days=step_data.get("delay_days", 3),
                        skill_id=step_data.get("skill_id"),
                        subject_prefix=step_data.get("subject_prefix", "Re: "),
                    )
                    session.add(step)

                # Assign to campaign
                campaign = session.query(Campaign).filter_by(id=campaign_id).first()
                if campaign:
                    campaign.sequence_id = seq.id

                return {"success": True, "data": {"id": seq.id, "name": name}}
        except Exception as e:
            logger.error(f"Error creating sequence: {e}")
            return {"success": False, "error": str(e)}
