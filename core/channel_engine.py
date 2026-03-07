"""
Aura — Channel Engine
Multi-channel outreach: email + LinkedIn + Twitter draft generation.
Stores drafts in ChannelDraft table for approval before sending.
"""

from datetime import datetime
from typing import Dict, Optional

from database.db_manager import DatabaseManager
from database.schema import ChannelDraft, Lead, Settings
from config import SUPPORTED_CHANNELS
from utils.logger import get_logger

logger = get_logger("channel_engine")


class ChannelEngine:
    """
    Generate and manage multi-channel outreach drafts.
    Email drafts go through DeliveryEngine; LinkedIn/Twitter are
    staged for manual copy-to-clipboard.
    """

    def __init__(self, db_manager: DatabaseManager, ai_engine=None):
        self.db_manager = db_manager
        self.ai_engine = ai_engine  # AIEngine (uses router if attached)

    def generate_all_channels(self, lead_data: dict, skill: dict,
                               sender_name: str = "", sender_company: str = "") -> dict:
        """
        Generate drafts for all enabled channels (email, linkedin, twitter).

        Returns:
            {
                "email": {"subject": str, "body": str},
                "linkedin": {"body": str},
                "twitter": {"body": str},
                "total_cost_usd": float,
            }
        """
        results = {}
        total_cost = 0.0

        # Email — standard generation via ai_engine
        if self.ai_engine:
            email_draft = self.ai_engine.generate_email(
                lead_data=lead_data,
                skill=skill,
                sender_name=sender_name,
                sender_company=sender_company,
            )
            results["email"] = {
                "subject": email_draft.get("subject", ""),
                "body": email_draft.get("body", ""),
            }

            # LinkedIn — connection request (max 300 chars)
            linkedin_draft = self._generate_channel_draft(
                lead_data, skill, sender_name, sender_company,
                channel="linkedin",
                instruction="Write a LinkedIn connection request. Max 300 characters. Be professional but warm. Do not use subject line.",
                max_tokens=128,
            )
            results["linkedin"] = {"body": linkedin_draft.get("body", "")}
            total_cost += linkedin_draft.get("cost_usd", 0.0)

            # Twitter — casual DM (max 140 chars)
            twitter_draft = self._generate_channel_draft(
                lead_data, skill, sender_name, sender_company,
                channel="twitter",
                instruction="Write a Twitter/X DM. Max 140 characters. Casual, direct, intriguing.",
                max_tokens=64,
            )
            results["twitter"] = {"body": twitter_draft.get("body", "")}
            total_cost += twitter_draft.get("cost_usd", 0.0)

        results["total_cost_usd"] = total_cost
        return results

    def _generate_channel_draft(self, lead_data, skill, sender_name, sender_company,
                                 channel, instruction, max_tokens) -> dict:
        """Generate a single channel draft using the router/LLM."""
        if not self.ai_engine:
            return {"body": "", "cost_usd": 0.0}

        skill_name = skill.get("name", "Professional")
        skill_prompt = skill.get("system_prompt", "")

        prompt = f"""You are writing a {channel} outreach message.

PERSONA: {skill_name}
{skill_prompt}

LEAD:
- Business: {lead_data.get('business_name', '')}
- Category: {lead_data.get('category', '')}
- City: {lead_data.get('city', '')}

SENDER: {sender_name} from {sender_company}

{instruction}

Return ONLY the message text, no JSON, no quotes:"""

        # Use router if available, otherwise direct LLM call
        if self.ai_engine.router:
            result = self.ai_engine.router.route(
                "generate_email", prompt,
                {"temperature": 0.7, "max_tokens": max_tokens}
            )
            body = result.get("data", "") if result.get("success") else ""
            cost = result.get("cost_usd", 0.0)
        else:
            body = self.ai_engine._call_llm(
                self.ai_engine._models["tier3"],
                [{"role": "user", "content": prompt}],
                temperature=0.7, max_tokens=max_tokens,
            ) or ""
            cost = 0.0

        return {"body": body.strip(), "cost_usd": cost}

    def save_channel_drafts(self, lead_id: int, drafts: dict) -> dict:
        """Save generated drafts to the ChannelDraft table."""
        saved = 0
        try:
            with self.db_manager.session_scope() as session:
                for channel in SUPPORTED_CHANNELS:
                    if channel not in drafts:
                        continue
                    draft_data = drafts[channel]
                    draft = ChannelDraft(
                        lead_id=lead_id,
                        channel=channel,
                        subject=draft_data.get("subject", ""),
                        body=draft_data.get("body", ""),
                        status="draft",
                        created_at=datetime.utcnow(),
                    )
                    session.add(draft)
                    saved += 1
            return {"success": True, "saved": saved}
        except Exception as e:
            logger.error(f"Failed to save channel drafts: {e}")
            return {"success": False, "error": str(e)}

    def get_channel_drafts(self, lead_id: int) -> dict:
        """Get all channel drafts for a lead, grouped by channel."""
        try:
            with self.db_manager.session_scope() as session:
                drafts = (
                    session.query(ChannelDraft)
                    .filter_by(lead_id=lead_id)
                    .order_by(ChannelDraft.created_at.desc())
                    .all()
                )
                result = {}
                for d in drafts:
                    if d.channel not in result:
                        result[d.channel] = {
                            "id": d.id,
                            "subject": d.subject or "",
                            "body": d.body or "",
                            "status": d.status,
                            "created_at": str(d.created_at) if d.created_at else "",
                        }
                return result
        except Exception as e:
            logger.error(f"Failed to get channel drafts: {e}")
            return {}

    def approve_draft(self, draft_id: int) -> dict:
        """Mark a channel draft as approved."""
        try:
            with self.db_manager.session_scope() as session:
                draft = session.query(ChannelDraft).filter_by(id=draft_id).first()
                if not draft:
                    return {"success": False, "error": "Draft not found"}
                draft.status = "approved"
                return {"success": True, "channel": draft.channel, "body": draft.body}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mark_sent(self, draft_id: int) -> dict:
        """Mark a channel draft as sent."""
        try:
            with self.db_manager.session_scope() as session:
                draft = session.query(ChannelDraft).filter_by(id=draft_id).first()
                if not draft:
                    return {"success": False, "error": "Draft not found"}
                draft.status = "sent"
                draft.sent_at = datetime.utcnow()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
