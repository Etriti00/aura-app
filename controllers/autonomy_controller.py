"""
Aura — Autonomy Controller
Manages permission levels that gate outbound actions.
Observer → Supervised → Autonomous → Full Trust.
"""

import json
from datetime import datetime

from database.db_manager import DatabaseManager
from database.schema import PendingApproval, Settings
from config import AUTONOMY_REQUIRES_APPROVAL, AutonomyLevel
from utils.logger import get_logger

logger = get_logger("autonomy_controller")


class AutonomyController:
    """Gates actions based on configured autonomy level."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._cached_level = None
        self.command_history = None  # Injected from main_window

    # ─── Permission Checking ───────────────────────────────────

    def check_permission(self, action_type: str, autonomy_level: str = None) -> dict:
        """
        Check if an action is allowed at the current (or given) autonomy level.
        Returns {"allowed": bool, "needs_approval": bool}.
        """
        try:
            level = autonomy_level or self._get_cached_level()
            requires = AUTONOMY_REQUIRES_APPROVAL.get(level, ["all"])

            if "all" in requires:
                return {"success": True, "data": {"allowed": False, "needs_approval": True, "level": level}}

            if action_type in requires:
                return {"success": True, "data": {"allowed": False, "needs_approval": True, "level": level}}

            return {"success": True, "data": {"allowed": True, "needs_approval": False, "level": level}}

        except Exception as e:
            logger.error(f"check_permission failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Level Management ──────────────────────────────────────

    def get_autonomy_level(self) -> dict:
        """Get the current autonomy level from settings."""
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                level = settings.autonomy_level if settings else "supervised"
            self._cached_level = level
            return {"success": True, "data": {"level": level}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_autonomy_level(self, level: str) -> dict:
        """Set the autonomy level."""
        valid_levels = [e.value for e in AutonomyLevel]
        if level not in valid_levels:
            return {"success": False, "error": f"Invalid level: {level}. Valid: {valid_levels}"}

        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if not settings:
                    settings = Settings(id=1)
                    session.add(settings)
                settings.autonomy_level = level

            self._cached_level = level
            logger.info(f"Autonomy level set to: {level}")
            return {"success": True, "data": {"level": level}}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Approval Queue ────────────────────────────────────────

    def queue_for_approval(self, action_type: str, description: str = "",
                           payload: dict = None, agent_id: int = None,
                           lead_id: int = None) -> dict:
        """Queue an action for user approval."""
        try:
            with self.db_manager.session_scope() as session:
                approval = PendingApproval(
                    action_type=action_type,
                    action_description=description,
                    action_payload=json.dumps(payload or {}),
                    agent_id=agent_id,
                    lead_id=lead_id,
                    status="pending",
                )
                session.add(approval)
                session.flush()
                approval_id = approval.id

            return {"success": True, "data": {"approval_id": approval_id}}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_pending_approvals(self) -> dict:
        """Get all pending approval requests."""
        try:
            with self.db_manager.session_scope() as session:
                approvals = (
                    session.query(PendingApproval)
                    .filter_by(status="pending")
                    .order_by(PendingApproval.created_at.desc())
                    .all()
                )

                items = [
                    {
                        "id": a.id,
                        "action_type": a.action_type,
                        "action_description": a.action_description,
                        "payload": json.loads(a.action_payload) if a.action_payload else {},
                        "agent_id": a.agent_id,
                        "lead_id": a.lead_id,
                        "created_at": a.created_at.isoformat() if a.created_at else None,
                    }
                    for a in approvals
                ]

            return {"success": True, "data": items}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def approve_action(self, approval_id: int) -> dict:
        """Approve a pending action."""
        return self._resolve_action(approval_id, "approved")

    def deny_action(self, approval_id: int) -> dict:
        """Deny a pending action."""
        return self._resolve_action(approval_id, "denied")

    # ─── Private ───────────────────────────────────────────────

    def _resolve_action(self, approval_id: int, status: str) -> dict:
        """Resolve a pending approval (approve or deny)."""
        try:
            with self.db_manager.session_scope() as session:
                approval = session.query(PendingApproval).get(approval_id)
                if not approval:
                    return {"success": False, "error": f"Approval {approval_id} not found"}
                if approval.status != "pending":
                    return {"success": False, "error": f"Approval already {approval.status}"}

                approval.status = status
                approval.resolved_at = datetime.utcnow()

                data = {
                    "approval_id": approval_id,
                    "action_type": approval.action_type,
                    "status": status,
                }

            logger.info(f"Approval {approval_id} {status}")

            if self.command_history:
                try:
                    self.command_history.log_command(
                        source="system",
                        command_type=f"approval_{status}",
                        command_text=f"Action '{data.get('action_type', '')}' {status}",
                        actor_type="user",
                        status="completed",
                        parameters=data,
                    )
                except Exception:
                    pass

            return {"success": True, "data": data}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_cached_level(self) -> str:
        """Get cached level or fetch from DB."""
        if self._cached_level is None:
            result = self.get_autonomy_level()
            return result.get("data", {}).get("level", "supervised")
        return self._cached_level
