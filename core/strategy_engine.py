"""
Aura — Strategy Engine
Goal-oriented planning: user sets a target (e.g., "Get me 10 plumbing clients in Austin"),
Aura calculates backward from target → contacts needed → cost estimate → phased milestones.
"""

import math
from datetime import datetime

from database.db_manager import DatabaseManager
from database.schema import StrategicGoal, GoalMilestone, Campaign
from config import (
    DEFAULT_SCRAPE_TO_QUALIFY_RATE,
    DEFAULT_QUALIFY_TO_EMAIL_RATE,
    DEFAULT_EMAIL_TO_REPLY_RATE,
    DEFAULT_REPLY_TO_MEETING_RATE,
    DEFAULT_MEETING_TO_CONVERSION_RATE,
    TIER_COST_PER_1K_TOKENS,
)
from utils.logger import get_logger

logger = get_logger("strategy_engine")


class StrategyEngine:
    """Plans and executes goal-oriented sales strategies."""

    def __init__(self, db_manager: DatabaseManager, fleet_orchestrator=None,
                 knowledge_graph=None):
        self.db_manager = db_manager
        self.fleet_orchestrator = fleet_orchestrator
        self.knowledge_graph = knowledge_graph

    # ─── Goal Management ───────────────────────────────────────

    def create_goal(self, goal_text: str, target_metric: str = "conversions",
                    target_value: int = 10, budget: float = None,
                    niche: str = "", city: str = "") -> dict:
        """Create a new strategic goal and calculate the plan."""
        try:
            plan = self.calculate_plan(target_value, target_metric, niche, city)
            if not plan["success"]:
                return plan

            plan_data = plan["data"]

            with self.db_manager.session_scope() as session:
                goal = StrategicGoal(
                    goal_text=goal_text,
                    target_metric=target_metric,
                    target_value=target_value,
                    budget_usd=budget,
                    niche=niche,
                    city=city,
                    status="planning",
                    estimated_contacts_needed=plan_data["contacts_needed"],
                    estimated_cost=plan_data["estimated_cost"],
                )
                session.add(goal)
                session.flush()
                goal_id = goal.id

            # Generate milestones
            self.generate_milestones(goal_id)

            return {"success": True, "data": {"goal_id": goal_id, "plan": plan_data}}

        except Exception as e:
            logger.error(f"create_goal failed: {e}")
            return {"success": False, "error": str(e)}

    def calculate_plan(self, target_value: int, target_metric: str = "conversions",
                       niche: str = "", city: str = "") -> dict:
        """
        Backward calculation from target to contacts needed.
        conversions → meetings → replies → emails → qualified → scraped
        """
        try:
            # Use default rates (can be overridden with niche-specific data later)
            if target_metric == "conversions":
                meetings_needed = math.ceil(target_value / DEFAULT_MEETING_TO_CONVERSION_RATE)
                replies_needed = math.ceil(meetings_needed / DEFAULT_REPLY_TO_MEETING_RATE)
                emails_needed = math.ceil(replies_needed / DEFAULT_EMAIL_TO_REPLY_RATE)
                qualified_needed = math.ceil(emails_needed / DEFAULT_QUALIFY_TO_EMAIL_RATE)
                contacts_needed = math.ceil(qualified_needed / DEFAULT_SCRAPE_TO_QUALIFY_RATE)
            elif target_metric == "meetings":
                replies_needed = math.ceil(target_value / DEFAULT_REPLY_TO_MEETING_RATE)
                emails_needed = math.ceil(replies_needed / DEFAULT_EMAIL_TO_REPLY_RATE)
                qualified_needed = math.ceil(emails_needed / DEFAULT_QUALIFY_TO_EMAIL_RATE)
                contacts_needed = math.ceil(qualified_needed / DEFAULT_SCRAPE_TO_QUALIFY_RATE)
                meetings_needed = target_value
            elif target_metric == "replies":
                emails_needed = math.ceil(target_value / DEFAULT_EMAIL_TO_REPLY_RATE)
                qualified_needed = math.ceil(emails_needed / DEFAULT_QUALIFY_TO_EMAIL_RATE)
                contacts_needed = math.ceil(qualified_needed / DEFAULT_SCRAPE_TO_QUALIFY_RATE)
                meetings_needed = 0
                replies_needed = target_value
            else:
                return {"success": False, "error": f"Unknown metric: {target_metric}"}

            # Cost estimate (rough: ~500 tokens per email at sonnet tier)
            estimated_tokens = emails_needed * 500
            cost_per_token = TIER_COST_PER_1K_TOKENS.get("sonnet", 0.006)
            estimated_cost = round((estimated_tokens / 1000) * cost_per_token, 2)

            return {
                "success": True,
                "data": {
                    "target_metric": target_metric,
                    "target_value": target_value,
                    "contacts_needed": contacts_needed,
                    "qualified_needed": qualified_needed,
                    "emails_needed": emails_needed,
                    "replies_needed": replies_needed,
                    "meetings_needed": meetings_needed,
                    "estimated_cost": estimated_cost,
                    "funnel_rates": {
                        "scrape_to_qualify": DEFAULT_SCRAPE_TO_QUALIFY_RATE,
                        "qualify_to_email": DEFAULT_QUALIFY_TO_EMAIL_RATE,
                        "email_to_reply": DEFAULT_EMAIL_TO_REPLY_RATE,
                        "reply_to_meeting": DEFAULT_REPLY_TO_MEETING_RATE,
                        "meeting_to_conversion": DEFAULT_MEETING_TO_CONVERSION_RATE,
                    },
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_milestones(self, goal_id: int) -> dict:
        """Generate phased milestones for a goal."""
        try:
            with self.db_manager.session_scope() as session:
                goal = session.query(StrategicGoal).get(goal_id)
                if not goal:
                    return {"success": False, "error": "Goal not found"}

                # Clear existing milestones
                session.query(GoalMilestone).filter_by(goal_id=goal_id).delete()

                contacts = goal.estimated_contacts_needed
                milestones_data = [
                    (1, f"Scrape {contacts} leads in {goal.niche or 'target niche'}", contacts),
                    (2, f"Qualify leads (target: {int(contacts * DEFAULT_SCRAPE_TO_QUALIFY_RATE)})", int(contacts * DEFAULT_SCRAPE_TO_QUALIFY_RATE)),
                    (3, f"Generate and send {int(contacts * DEFAULT_SCRAPE_TO_QUALIFY_RATE * DEFAULT_QUALIFY_TO_EMAIL_RATE)} emails", int(contacts * DEFAULT_SCRAPE_TO_QUALIFY_RATE * DEFAULT_QUALIFY_TO_EMAIL_RATE)),
                    (4, f"Process replies and nurture conversations", goal.target_value * 2),
                    (5, f"Achieve {goal.target_value} {goal.target_metric}", goal.target_value),
                ]

                for phase, desc, target in milestones_data:
                    session.add(GoalMilestone(
                        goal_id=goal_id, phase=phase,
                        description=desc, target_value=target,
                    ))

            return {"success": True, "data": {"goal_id": goal_id, "milestones": len(milestones_data)}}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Goal Lifecycle ────────────────────────────────────────

    def get_goal(self, goal_id: int) -> dict:
        """Get a goal with its milestones."""
        try:
            with self.db_manager.session_scope() as session:
                goal = session.query(StrategicGoal).get(goal_id)
                if not goal:
                    return {"success": False, "error": "Goal not found"}

                milestones = (
                    session.query(GoalMilestone)
                    .filter_by(goal_id=goal_id)
                    .order_by(GoalMilestone.phase)
                    .all()
                )

                return {
                    "success": True,
                    "data": {
                        "id": goal.id,
                        "goal_text": goal.goal_text,
                        "target_metric": goal.target_metric,
                        "target_value": goal.target_value,
                        "status": goal.status,
                        "progress_pct": goal.progress_pct,
                        "niche": goal.niche,
                        "city": goal.city,
                        "estimated_cost": goal.estimated_cost,
                        "actual_cost": goal.actual_cost,
                        "milestones": [
                            {
                                "phase": m.phase,
                                "description": m.description,
                                "target_value": m.target_value,
                                "actual_value": m.actual_value,
                                "status": m.status,
                            }
                            for m in milestones
                        ],
                    },
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_all_goals(self, status: str = None) -> dict:
        """Get all goals, optionally filtered by status."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(StrategicGoal)
                if status:
                    query = query.filter_by(status=status)

                goals = query.order_by(StrategicGoal.created_at.desc()).all()
                items = [
                    {
                        "id": g.id,
                        "goal_text": g.goal_text,
                        "target_metric": g.target_metric,
                        "target_value": g.target_value,
                        "status": g.status,
                        "progress_pct": g.progress_pct,
                        "niche": g.niche,
                        "city": g.city,
                    }
                    for g in goals
                ]

            return {"success": True, "data": items}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def activate_goal(self, goal_id: int) -> dict:
        """Activate a goal and its first milestone."""
        try:
            with self.db_manager.session_scope() as session:
                goal = session.query(StrategicGoal).get(goal_id)
                if not goal:
                    return {"success": False, "error": "Goal not found"}

                goal.status = "active"

                first_milestone = (
                    session.query(GoalMilestone)
                    .filter_by(goal_id=goal_id)
                    .order_by(GoalMilestone.phase)
                    .first()
                )
                if first_milestone:
                    first_milestone.status = "active"

            return {"success": True, "data": {"goal_id": goal_id, "status": "active"}}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_progress(self, goal_id: int) -> dict:
        """Recalculate goal progress based on milestone completion."""
        try:
            with self.db_manager.session_scope() as session:
                goal = session.query(StrategicGoal).get(goal_id)
                if not goal:
                    return {"success": False, "error": "Goal not found"}

                milestones = (
                    session.query(GoalMilestone)
                    .filter_by(goal_id=goal_id)
                    .all()
                )

                if not milestones:
                    return {"success": True, "data": {"progress_pct": 0.0}}

                completed = sum(1 for m in milestones if m.status == "completed")
                progress = round((completed / len(milestones)) * 100, 1)
                goal.progress_pct = progress

                if progress >= 100:
                    goal.status = "completed"
                    goal.completed_at = datetime.utcnow()

            return {"success": True, "data": {"goal_id": goal_id, "progress_pct": progress}}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_goal_cost_summary(self, goal_id: int) -> dict:
        """Get cost summary for a goal."""
        try:
            with self.db_manager.session_scope() as session:
                goal = session.query(StrategicGoal).get(goal_id)
                if not goal:
                    return {"success": False, "error": "Goal not found"}

                milestones = session.query(GoalMilestone).filter_by(goal_id=goal_id).all()
                actual_cost = sum(m.actual_cost for m in milestones)
                estimated_cost = goal.estimated_cost
                budget_usd = goal.budget_usd

            return {
                "success": True,
                "data": {
                    "goal_id": goal_id,
                    "estimated_cost": estimated_cost,
                    "actual_cost": actual_cost,
                    "budget_usd": budget_usd,
                    "under_budget": (budget_usd is None) or (actual_cost <= budget_usd),
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_next_milestone(self, goal_id: int) -> dict:
        """Find and activate the next pending milestone."""
        try:
            with self.db_manager.session_scope() as session:
                next_ms = (
                    session.query(GoalMilestone)
                    .filter_by(goal_id=goal_id, status="pending")
                    .order_by(GoalMilestone.phase)
                    .first()
                )

                if not next_ms:
                    return {"success": True, "data": {"message": "All milestones complete or active"}}

                next_ms.status = "active"
                phase = next_ms.phase
                desc = next_ms.description

            logger.info(f"Activated milestone phase {phase} for goal {goal_id}: {desc}")
            return {
                "success": True,
                "data": {"goal_id": goal_id, "phase": phase, "description": desc},
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
