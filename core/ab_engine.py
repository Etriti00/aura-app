"""
Aura — A/B Skill Testing Engine
Deterministic variant assignment and campaign-level A/B stats.
"""

from database.db_manager import DatabaseManager
from database.schema import Lead, Campaign, Skill
from utils.logger import get_logger

logger = get_logger("ab_engine")


class ABEngine:
    """Manages A/B skill testing: assignment and statistics."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def assign_variant(self, lead_id: int, campaign_id: int) -> str:
        """
        Deterministically assign A/B variant to a lead.
        Returns "A" or "B". Writes to DB.
        """
        try:
            with self.db_manager.session_scope() as session:
                campaign = session.query(Campaign).filter_by(id=campaign_id).first()
                if not campaign or not campaign.ab_skill_b_id:
                    # No B variant configured — always A
                    lead = session.query(Lead).filter_by(id=lead_id).first()
                    if lead:
                        lead.ab_variant = "A"
                    return "A"

                # Deterministic assignment based on lead_id
                ratio = campaign.ab_split_ratio or 0.5
                variant = "A" if (lead_id % 100) < (ratio * 100) else "B"

                lead = session.query(Lead).filter_by(id=lead_id).first()
                if lead:
                    lead.ab_variant = variant

                return variant
        except Exception as e:
            logger.error(f"Error assigning A/B variant: {e}")
            return "A"

    def get_skill_for_variant(self, campaign_id: int, variant: str) -> int:
        """Get the skill_id for a given variant in a campaign."""
        try:
            with self.db_manager.session_scope() as session:
                campaign = session.query(Campaign).filter_by(id=campaign_id).first()
                if not campaign:
                    return 0
                if variant == "B" and campaign.ab_skill_b_id:
                    return campaign.ab_skill_b_id
                return campaign.skill_id or 0
        except Exception as e:
            logger.error(f"Error getting skill for variant: {e}")
            return 0

    def get_campaign_ab_stats(self, campaign_id: int) -> dict:
        """
        Calculate A/B test statistics for a campaign.
        Returns stats per variant with winner determination.
        """
        try:
            with self.db_manager.session_scope() as session:
                leads = session.query(Lead).filter_by(campaign_id=campaign_id).all()

                stats = {
                    "A": {"sent": 0, "replied": 0, "rate": 0.0},
                    "B": {"sent": 0, "replied": 0, "rate": 0.0},
                }

                for lead in leads:
                    variant = lead.ab_variant or "A"
                    if variant not in stats:
                        continue
                    if lead.status in ("emailed", "email_sent", "replied", "converted"):
                        stats[variant]["sent"] += 1
                    if lead.status in ("replied", "converted"):
                        stats[variant]["replied"] += 1

                # Calculate rates
                for v in ("A", "B"):
                    if stats[v]["sent"] > 0:
                        stats[v]["rate"] = round(
                            stats[v]["replied"] / stats[v]["sent"], 3
                        )

                # Determine winner
                min_sends = 20
                if stats["A"]["sent"] >= min_sends and stats["B"]["sent"] >= min_sends:
                    confidence = "high"
                    if stats["A"]["rate"] > stats["B"]["rate"]:
                        winner = "A"
                    elif stats["B"]["rate"] > stats["A"]["rate"]:
                        winner = "B"
                    else:
                        winner = "tie"
                else:
                    confidence = "low"
                    winner = None

                return {
                    "A": stats["A"],
                    "B": stats["B"],
                    "winner": winner,
                    "confidence": confidence,
                }
        except Exception as e:
            logger.error(f"Error calculating A/B stats: {e}")
            return {
                "A": {"sent": 0, "replied": 0, "rate": 0.0},
                "B": {"sent": 0, "replied": 0, "rate": 0.0},
                "winner": None,
                "confidence": "low",
            }

    def get_skill_ab_performance(self, skill_id: int) -> dict:
        """
        Get aggregate A/B performance for a skill across all campaigns.
        """
        try:
            with self.db_manager.session_scope() as session:
                # Find campaigns where this skill is used as A or B
                campaigns_a = session.query(Campaign).filter_by(skill_id=skill_id).all()
                campaigns_b = session.query(Campaign).filter_by(ab_skill_b_id=skill_id).all()

                total_sent = 0
                total_replied = 0

                for campaign in campaigns_a:
                    leads = session.query(Lead).filter_by(
                        campaign_id=campaign.id, ab_variant="A"
                    ).all()
                    for lead in leads:
                        if lead.status in ("emailed", "email_sent", "replied", "converted"):
                            total_sent += 1
                        if lead.status in ("replied", "converted"):
                            total_replied += 1

                for campaign in campaigns_b:
                    leads = session.query(Lead).filter_by(
                        campaign_id=campaign.id, ab_variant="B"
                    ).all()
                    for lead in leads:
                        if lead.status in ("emailed", "email_sent", "replied", "converted"):
                            total_sent += 1
                        if lead.status in ("replied", "converted"):
                            total_replied += 1

                rate = round(total_replied / total_sent, 3) if total_sent > 0 else 0.0

                return {
                    "skill_id": skill_id,
                    "total_sent": total_sent,
                    "total_replied": total_replied,
                    "reply_rate": rate,
                }
        except Exception as e:
            logger.error(f"Error getting skill A/B performance: {e}")
            return {"skill_id": skill_id, "total_sent": 0, "total_replied": 0, "reply_rate": 0.0}
