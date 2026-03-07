"""
Aura — Escalation Engine
Blocked-ticket detection, hierarchy-based escalation chain, and agent ticket
request approval flow (Commander as gatekeeper).
"""

import json
from datetime import datetime

from database.db_manager import DatabaseManager
from database.schema import Agent, AgentTicket, AgentMessage
from utils.logger import get_logger

logger = get_logger("escalation_engine")


class EscalationEngine:
    """Handles ticket escalation, agent ticket requests, and approval flow."""

    def __init__(self, db_manager: DatabaseManager, ticket_engine, agent_engine=None):
        self.db_manager = db_manager
        self.ticket_engine = ticket_engine
        self.agent_engine = agent_engine

    # ─── Escalation ────────────────────────────────────────────────────

    def check_and_escalate(self) -> dict:
        """Scan for blocked tickets and escalate them up the hierarchy."""
        try:
            escalated = []
            with self.db_manager.session_scope() as session:
                blocked = (
                    session.query(AgentTicket)
                    .filter(
                        AgentTicket.blocked_reason.isnot(None),
                        AgentTicket.blocked_reason != "",
                        AgentTicket.status == "in_progress",
                        AgentTicket.escalated_to_id.is_(None),
                    )
                    .all()
                )

                for ticket in blocked:
                    if not ticket.assignee_id:
                        continue

                    assignee = session.query(Agent).filter_by(
                        id=ticket.assignee_id
                    ).first()
                    if not assignee or not assignee.reports_to_id:
                        continue

                    supervisor = session.query(Agent).filter_by(
                        id=assignee.reports_to_id
                    ).first()
                    if not supervisor:
                        continue

                    # Perform escalation
                    ticket.escalated_to_id = supervisor.id
                    ticket.assignee_id = supervisor.id

                    # Add escalation comment
                    self.ticket_engine.add_comment(
                        ticket_id=ticket.id,
                        content=(
                            f"Escalated from {assignee.name} (rank {assignee.rank}) "
                            f"to {supervisor.name} (rank {supervisor.rank}). "
                            f"Reason: {ticket.blocked_reason}"
                        ),
                        author_type="system",
                        comment_type="escalation",
                    )

                    # Send agent message
                    if self.agent_engine:
                        self.agent_engine.send_message(
                            from_id=assignee.id,
                            to_id=supervisor.id,
                            message_type="escalation",
                            content={
                                "ticket_id": ticket.id,
                                "title": ticket.title,
                                "reason": ticket.blocked_reason,
                                "from_agent": assignee.name,
                            },
                        )

                    escalated.append({
                        "ticket_id": ticket.id,
                        "title": ticket.title,
                        "from_agent": assignee.name,
                        "to_agent": supervisor.name,
                        "reason": ticket.blocked_reason,
                    })

                    logger.info(
                        f"Escalated ticket #{ticket.id} '{ticket.title}' "
                        f"from {assignee.name} → {supervisor.name}"
                    )

            return {"success": True, "escalated": escalated, "count": len(escalated)}
        except Exception as e:
            logger.error(f"Escalation check failed: {e}")
            return {"success": False, "error": str(e)}

    def escalate_ticket(self, ticket_id: int, from_agent_id: int,
                        to_agent_id: int, reason: str) -> dict:
        """Manually escalate a specific ticket."""
        try:
            with self.db_manager.session_scope() as session:
                ticket = session.query(AgentTicket).filter_by(id=ticket_id).first()
                if not ticket:
                    return {"success": False, "error": "Ticket not found"}

                from_agent = session.query(Agent).filter_by(id=from_agent_id).first()
                to_agent = session.query(Agent).filter_by(id=to_agent_id).first()

                ticket.escalated_to_id = to_agent_id
                ticket.assignee_id = to_agent_id
                ticket.blocked_reason = reason

                from_name = from_agent.name if from_agent else "Unknown"
                to_name = to_agent.name if to_agent else "Unknown"

            self.ticket_engine.add_comment(
                ticket_id=ticket_id,
                content=f"Manually escalated from {from_name} to {to_name}. Reason: {reason}",
                author_type="system",
                comment_type="escalation",
            )

            if self.agent_engine:
                self.agent_engine.send_message(
                    from_id=from_agent_id,
                    to_id=to_agent_id,
                    message_type="escalation",
                    content={
                        "ticket_id": ticket_id,
                        "reason": reason,
                        "from_agent": from_name,
                    },
                )

            return {"success": True, "ticket_id": ticket_id}
        except Exception as e:
            logger.error(f"Manual escalation failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Ticket Request Flow ───────────────────────────────────────────

    def process_ticket_request(self, requesting_agent_id: int,
                               ticket_data: dict) -> dict:
        """Agent requests to create a ticket. Auto-approve or send to Commander."""
        try:
            eval_result = self.auto_evaluate_ticket_request(
                requesting_agent_id, ticket_data
            )
            auto_approved = eval_result.get("auto_approved", False)

            if auto_approved:
                # Create ticket directly
                result = self.ticket_engine.create_ticket(
                    title=ticket_data.get("title", "Agent-created ticket"),
                    description=ticket_data.get("description", ""),
                    priority=ticket_data.get("priority", "medium"),
                    assignee_id=ticket_data.get("assignee_id"),
                    reporter_id=requesting_agent_id,
                    reporter_type="agent",
                    labels=ticket_data.get("labels", ""),
                    parent_ticket_id=ticket_data.get("parent_ticket_id"),
                    approval_status="approved",
                )
                if result.get("success"):
                    self.ticket_engine.add_comment(
                        ticket_id=result["data"]["id"],
                        content=f"Auto-approved: {eval_result.get('reason', 'meets criteria')}",
                        author_type="system",
                        comment_type="approval",
                    )
                return result
            else:
                # Create with pending approval
                result = self.ticket_engine.create_ticket(
                    title=ticket_data.get("title", "Agent-created ticket"),
                    description=ticket_data.get("description", ""),
                    priority=ticket_data.get("priority", "medium"),
                    assignee_id=ticket_data.get("assignee_id"),
                    reporter_id=requesting_agent_id,
                    reporter_type="agent",
                    labels=ticket_data.get("labels", ""),
                    parent_ticket_id=ticket_data.get("parent_ticket_id"),
                    approval_status="pending",
                )
                if result.get("success"):
                    # Notify Commander
                    commander_id = self._get_commander_id()
                    if commander_id and self.agent_engine:
                        with self.db_manager.session_scope() as session:
                            requester = session.query(Agent).filter_by(
                                id=requesting_agent_id
                            ).first()
                            requester_name = requester.name if requester else "Unknown"

                        self.agent_engine.send_message(
                            from_id=requesting_agent_id,
                            to_id=commander_id,
                            message_type="ticket_request",
                            content={
                                "ticket_id": result["data"]["id"],
                                "title": ticket_data.get("title"),
                                "requesting_agent": requester_name,
                                "reason": ticket_data.get("reason", "No reason provided"),
                            },
                        )
                        self.ticket_engine.add_comment(
                            ticket_id=result["data"]["id"],
                            content=(
                                f"Pending approval from Commander. "
                                f"Requested by {requester_name}: "
                                f"{ticket_data.get('reason', 'No reason provided')}"
                            ),
                            author_type="system",
                            comment_type="approval",
                        )
                return result
        except Exception as e:
            logger.error(f"Ticket request processing failed: {e}")
            return {"success": False, "error": str(e)}

    def approve_ticket_request(self, ticket_id: int, approver_id: int) -> dict:
        """Approve a pending agent ticket request."""
        try:
            with self.db_manager.session_scope() as session:
                ticket = session.query(AgentTicket).filter_by(id=ticket_id).first()
                if not ticket:
                    return {"success": False, "error": "Ticket not found"}
                if ticket.approval_status != "pending":
                    return {"success": False, "error": "Ticket not pending approval"}

                ticket.approval_status = "approved"
                ticket.approved_by_id = approver_id
                ticket.status = "backlog"

                approver = session.query(Agent).filter_by(id=approver_id).first()
                approver_name = approver.name if approver else "User"
                reporter_id = ticket.reporter_id

            self.ticket_engine.add_comment(
                ticket_id=ticket_id,
                content=f"Approved by {approver_name}",
                author_type="system",
                comment_type="approval",
            )

            # Notify requesting agent
            if reporter_id and self.agent_engine:
                self.agent_engine.send_message(
                    from_id=approver_id,
                    to_id=reporter_id,
                    message_type="ticket_approval",
                    content={
                        "ticket_id": ticket_id,
                        "status": "approved",
                        "approved_by": approver_name,
                    },
                )

            logger.info(f"Ticket #{ticket_id} approved by {approver_name}")
            return {"success": True, "ticket_id": ticket_id}
        except Exception as e:
            logger.error(f"Ticket approval failed: {e}")
            return {"success": False, "error": str(e)}

    def deny_ticket_request(self, ticket_id: int, approver_id: int,
                            reason: str = "") -> dict:
        """Deny a pending agent ticket request."""
        try:
            with self.db_manager.session_scope() as session:
                ticket = session.query(AgentTicket).filter_by(id=ticket_id).first()
                if not ticket:
                    return {"success": False, "error": "Ticket not found"}
                if ticket.approval_status != "pending":
                    return {"success": False, "error": "Ticket not pending approval"}

                ticket.approval_status = "denied"
                ticket.approved_by_id = approver_id
                ticket.status = "done"
                ticket.completed_at = datetime.utcnow()

                approver = session.query(Agent).filter_by(id=approver_id).first()
                approver_name = approver.name if approver else "User"
                reporter_id = ticket.reporter_id

            self.ticket_engine.add_comment(
                ticket_id=ticket_id,
                content=f"Denied by {approver_name}. Reason: {reason or 'No reason given'}",
                author_type="system",
                comment_type="approval",
            )

            if reporter_id and self.agent_engine:
                self.agent_engine.send_message(
                    from_id=approver_id,
                    to_id=reporter_id,
                    message_type="ticket_approval",
                    content={
                        "ticket_id": ticket_id,
                        "status": "denied",
                        "denied_by": approver_name,
                        "reason": reason,
                    },
                )

            logger.info(f"Ticket #{ticket_id} denied by {approver_name}")
            return {"success": True, "ticket_id": ticket_id}
        except Exception as e:
            logger.error(f"Ticket denial failed: {e}")
            return {"success": False, "error": str(e)}

    def auto_evaluate_ticket_request(self, requesting_agent_id: int,
                                     ticket_data: dict) -> dict:
        """Decide whether to auto-approve an agent's ticket request.

        Auto-approve if:
        - Sub-ticket under the agent's own ticket
        - Self-assignment (agent assigning to itself)
        - Low priority ticket

        Require Commander approval if:
        - New top-level ticket
        - Cross-subtree assignment (assigning to agent outside own reports)
        - Critical priority
        """
        try:
            parent_id = ticket_data.get("parent_ticket_id")
            assignee_id = ticket_data.get("assignee_id")
            priority = ticket_data.get("priority", "medium")

            # Critical priority always needs approval
            if priority == "critical":
                return {
                    "auto_approved": False,
                    "reason": "Critical priority requires Commander approval",
                }

            # Sub-ticket under own ticket → auto-approve
            if parent_id:
                with self.db_manager.session_scope() as session:
                    parent = session.query(AgentTicket).filter_by(
                        id=parent_id
                    ).first()
                    if parent and parent.assignee_id == requesting_agent_id:
                        return {
                            "auto_approved": True,
                            "reason": "Sub-ticket under own assignment",
                        }

            # Self-assignment → auto-approve
            if assignee_id == requesting_agent_id:
                return {
                    "auto_approved": True,
                    "reason": "Self-assignment",
                }

            # Low priority self-created → auto-approve
            if priority == "low" and not assignee_id:
                return {
                    "auto_approved": True,
                    "reason": "Low priority unassigned ticket",
                }

            # Everything else needs approval
            return {
                "auto_approved": False,
                "reason": "Requires Commander approval",
            }
        except Exception as e:
            logger.error(f"Auto-evaluate failed: {e}")
            return {"auto_approved": False, "reason": f"Evaluation error: {e}"}

    # ─── Supervisor Chain ──────────────────────────────────────────────

    def get_supervisor_chain(self, agent_id: int) -> list:
        """Walk the reports_to chain up to rank 1. Returns list of agent dicts."""
        chain = []
        visited = set()
        try:
            with self.db_manager.session_scope() as session:
                current_id = agent_id
                while current_id and current_id not in visited:
                    visited.add(current_id)
                    agent = session.query(Agent).filter_by(id=current_id).first()
                    if not agent:
                        break
                    chain.append({
                        "id": agent.id,
                        "name": agent.name,
                        "rank": agent.rank or 3,
                        "role": agent.role,
                    })
                    current_id = agent.reports_to_id
        except Exception as e:
            logger.error(f"Supervisor chain lookup failed: {e}")
        return chain

    def get_pending_requests(self) -> dict:
        """Get all tickets pending Commander approval."""
        try:
            with self.db_manager.session_scope() as session:
                pending = (
                    session.query(AgentTicket)
                    .filter_by(approval_status="pending")
                    .order_by(AgentTicket.created_at.desc())
                    .all()
                )
                result = []
                for t in pending:
                    reporter = None
                    if t.reporter_id:
                        reporter = session.query(Agent).filter_by(
                            id=t.reporter_id
                        ).first()
                    result.append({
                        "id": t.id,
                        "title": t.title,
                        "description": t.description,
                        "priority": t.priority,
                        "reporter_name": reporter.name if reporter else "Unknown",
                        "reporter_emoji": reporter.identity_emoji if reporter else "",
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                    })
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Helpers ───────────────────────────────────────────────────────

    def _get_commander_id(self) -> int | None:
        """Find the Commander (rank-1) agent ID."""
        try:
            with self.db_manager.session_scope() as session:
                commander = (
                    session.query(Agent)
                    .filter_by(rank=1)
                    .first()
                )
                return commander.id if commander else None
        except Exception:
            return None
