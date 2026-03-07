"""
Aura -- Ticket Engine
CRUD operations for tickets, status transitions, priority management,
hierarchy enforcement, and due-date monitoring.
"""

from datetime import datetime, timedelta
from typing import Optional

from database.db_manager import DatabaseManager
from database.schema import Agent, AgentTicket, TicketComment, TicketDependency
from config import TICKET_STATUSES, TICKET_PRIORITIES
from utils.logger import get_logger

logger = get_logger("ticket_engine")


class TicketEngine:
    """Manages ticket lifecycle, hierarchy rules, and scheduling."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    # ─── CRUD ──────────────────────────────────────────────────

    def create_ticket(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        assignee_id: Optional[int] = None,
        reporter_id: Optional[int] = None,
        reporter_type: str = "user",
        parent_ticket_id: Optional[int] = None,
        due_date: Optional[datetime] = None,
        labels: str = "",
        approval_status: Optional[str] = None,
    ) -> dict:
        try:
            with self.db_manager.session_scope() as session:
                ticket = AgentTicket(
                    title=title,
                    description=description,
                    priority=priority if priority in TICKET_PRIORITIES else "medium",
                    assignee_id=assignee_id,
                    reporter_id=reporter_id,
                    reporter_type=reporter_type,
                    parent_ticket_id=parent_ticket_id,
                    due_date=due_date,
                    labels=labels,
                    approval_status=approval_status,
                )
                session.add(ticket)
                session.flush()
                result = self._ticket_to_dict(ticket, session)
            logger.info(f"Created ticket #{result['id']}: {title}")
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            return {"success": False, "error": str(e)}

    def update_ticket(self, ticket_id: int, **fields) -> dict:
        try:
            with self.db_manager.session_scope() as session:
                ticket = session.query(AgentTicket).filter_by(id=ticket_id).first()
                if not ticket:
                    return {"success": False, "error": "Ticket not found"}
                for key, value in fields.items():
                    if hasattr(ticket, key) and key not in ("id", "created_at"):
                        setattr(ticket, key, value)
                ticket.updated_at = datetime.utcnow()
                session.flush()
                result = self._ticket_to_dict(ticket, session)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Failed to update ticket #{ticket_id}: {e}")
            return {"success": False, "error": str(e)}

    def move_ticket(self, ticket_id: int, new_status: str) -> dict:
        if new_status not in TICKET_STATUSES:
            return {"success": False, "error": f"Invalid status: {new_status}"}
        try:
            with self.db_manager.session_scope() as session:
                ticket = session.query(AgentTicket).filter_by(id=ticket_id).first()
                if not ticket:
                    return {"success": False, "error": "Ticket not found"}
                old_status = ticket.status
                ticket.status = new_status
                ticket.updated_at = datetime.utcnow()
                if new_status == "done" and not ticket.completed_at:
                    ticket.completed_at = datetime.utcnow()
                elif new_status != "done":
                    ticket.completed_at = None
                # Clear blocked reason when moving out of blocked state
                if new_status != "in_progress" and ticket.blocked_reason:
                    ticket.blocked_reason = None
                session.flush()
                # Add status change comment
                comment = TicketComment(
                    ticket_id=ticket_id,
                    content=f"Status changed: {old_status} → {new_status}",
                    author_type="system",
                    comment_type="status_change",
                )
                session.add(comment)
            logger.info(f"Ticket #{ticket_id} moved: {old_status} → {new_status}")
            return {"success": True, "ticket_id": ticket_id, "new_status": new_status}
        except Exception as e:
            logger.error(f"Failed to move ticket #{ticket_id}: {e}")
            return {"success": False, "error": str(e)}

    def delete_ticket(self, ticket_id: int) -> dict:
        try:
            with self.db_manager.session_scope() as session:
                ticket = session.query(AgentTicket).filter_by(id=ticket_id).first()
                if not ticket:
                    return {"success": False, "error": "Ticket not found"}
                session.delete(ticket)
            logger.info(f"Deleted ticket #{ticket_id}")
            return {"success": True, "ticket_id": ticket_id}
        except Exception as e:
            logger.error(f"Failed to delete ticket #{ticket_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_ticket(self, ticket_id: int) -> dict:
        try:
            with self.db_manager.session_scope() as session:
                ticket = session.query(AgentTicket).filter_by(id=ticket_id).first()
                if not ticket:
                    return {"success": False, "error": "Ticket not found"}
                result = self._ticket_to_dict(ticket, session)
                result["comments"] = [
                    self._comment_to_dict(c, session) for c in ticket.comments
                ]
                result["sub_tickets"] = [
                    self._ticket_to_dict(st, session) for st in ticket.sub_tickets
                ]
                result["dependencies"] = []
                for dep in ticket.dependencies:
                    dep_ticket = session.query(AgentTicket).filter_by(
                        id=dep.depends_on_id
                    ).first()
                    if dep_ticket:
                        result["dependencies"].append({
                            "id": dep.id,
                            "depends_on_id": dep.depends_on_id,
                            "depends_on_title": dep_ticket.title,
                            "depends_on_status": dep_ticket.status,
                        })
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Failed to get ticket #{ticket_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_all_tickets(
        self,
        status: Optional[str] = None,
        assignee_id: Optional[int] = None,
        priority: Optional[str] = None,
        label: Optional[str] = None,
    ) -> dict:
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(AgentTicket)
                if status:
                    query = query.filter(AgentTicket.status == status)
                if assignee_id:
                    query = query.filter(AgentTicket.assignee_id == assignee_id)
                if priority:
                    query = query.filter(AgentTicket.priority == priority)
                if label:
                    query = query.filter(AgentTicket.labels.contains(label))
                tickets = query.order_by(AgentTicket.created_at.desc()).all()
                result = [self._ticket_to_dict(t, session) for t in tickets]
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Failed to get tickets: {e}")
            return {"success": False, "error": str(e)}

    def get_tickets_by_status(
        self,
        assignee_id: Optional[int] = None,
        priority: Optional[str] = None,
        label: Optional[str] = None,
    ) -> dict:
        """Returns dict of {status: [ticket_dicts]} for Kanban columns."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(AgentTicket)
                if assignee_id:
                    query = query.filter(AgentTicket.assignee_id == assignee_id)
                if priority:
                    query = query.filter(AgentTicket.priority == priority)
                if label:
                    query = query.filter(AgentTicket.labels.contains(label))
                tickets = query.order_by(AgentTicket.created_at).all()
                grouped = {s: [] for s in TICKET_STATUSES}
                for t in tickets:
                    status_key = t.status if t.status in TICKET_STATUSES else "backlog"
                    grouped[status_key].append(self._ticket_to_dict(t, session))
            return {"success": True, "data": grouped}
        except Exception as e:
            logger.error(f"Failed to get tickets by status: {e}")
            return {"success": False, "error": str(e)}

    # ─── Comments ──────────────────────────────────────────────

    def add_comment(
        self,
        ticket_id: int,
        content: str,
        author_id: Optional[int] = None,
        author_type: str = "user",
        comment_type: str = "comment",
    ) -> dict:
        try:
            with self.db_manager.session_scope() as session:
                ticket = session.query(AgentTicket).filter_by(id=ticket_id).first()
                if not ticket:
                    return {"success": False, "error": "Ticket not found"}
                comment = TicketComment(
                    ticket_id=ticket_id,
                    author_id=author_id,
                    author_type=author_type,
                    content=content,
                    comment_type=comment_type,
                )
                session.add(comment)
                session.flush()
                result = self._comment_to_dict(comment, session)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Failed to add comment to ticket #{ticket_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_comments(self, ticket_id: int) -> dict:
        try:
            with self.db_manager.session_scope() as session:
                comments = (
                    session.query(TicketComment)
                    .filter_by(ticket_id=ticket_id)
                    .order_by(TicketComment.created_at)
                    .all()
                )
                result = [self._comment_to_dict(c, session) for c in comments]
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Dependencies ──────────────────────────────────────────

    def add_dependency(self, ticket_id: int, depends_on_id: int) -> dict:
        if ticket_id == depends_on_id:
            return {"success": False, "error": "Ticket cannot depend on itself"}
        try:
            with self.db_manager.session_scope() as session:
                existing = (
                    session.query(TicketDependency)
                    .filter_by(ticket_id=ticket_id, depends_on_id=depends_on_id)
                    .first()
                )
                if existing:
                    return {"success": False, "error": "Dependency already exists"}
                dep = TicketDependency(ticket_id=ticket_id, depends_on_id=depends_on_id)
                session.add(dep)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_dependency(self, ticket_id: int, depends_on_id: int) -> dict:
        try:
            with self.db_manager.session_scope() as session:
                dep = (
                    session.query(TicketDependency)
                    .filter_by(ticket_id=ticket_id, depends_on_id=depends_on_id)
                    .first()
                )
                if dep:
                    session.delete(dep)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_blocked(self, ticket_id: int) -> dict:
        """Check if a ticket is blocked by unfinished dependencies."""
        try:
            with self.db_manager.session_scope() as session:
                deps = (
                    session.query(TicketDependency)
                    .filter_by(ticket_id=ticket_id)
                    .all()
                )
                blocking = []
                for dep in deps:
                    blocker = session.query(AgentTicket).filter_by(
                        id=dep.depends_on_id
                    ).first()
                    if blocker and blocker.status != "done":
                        blocking.append({
                            "id": blocker.id,
                            "title": blocker.title,
                            "status": blocker.status,
                        })
            return {"success": True, "is_blocked": len(blocking) > 0, "blockers": blocking}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Sub-tickets ───────────────────────────────────────────

    def get_sub_tickets(self, parent_id: int) -> dict:
        try:
            with self.db_manager.session_scope() as session:
                subs = (
                    session.query(AgentTicket)
                    .filter_by(parent_ticket_id=parent_id)
                    .order_by(AgentTicket.created_at)
                    .all()
                )
                result = [self._ticket_to_dict(t, session) for t in subs]
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Hierarchy Enforcement ─────────────────────────────────

    def can_agent_create_ticket(
        self, agent_id: int, target_agent_id: Optional[int] = None
    ) -> dict:
        """Check if an agent has permission to create/assign a ticket based on rank."""
        try:
            with self.db_manager.session_scope() as session:
                agent = session.query(Agent).filter_by(id=agent_id).first()
                if not agent:
                    return {"success": False, "error": "Agent not found"}
                rank = agent.rank or 3
                # Rank 1: can do anything
                if rank == 1:
                    return {"success": True, "allowed": True, "needs_approval": False}
                # Rank 2: can assign to rank 3+ in their subtree
                if rank == 2:
                    if target_agent_id:
                        target = session.query(Agent).filter_by(id=target_agent_id).first()
                        if target and (target.rank or 3) > rank:
                            return {"success": True, "allowed": True, "needs_approval": False}
                    return {"success": True, "allowed": True, "needs_approval": True}
                # Rank 3: always needs approval
                return {"success": True, "allowed": True, "needs_approval": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def can_agent_move_ticket(self, agent_id: int, ticket_id: int) -> dict:
        """Check if an agent has permission to change ticket status."""
        try:
            with self.db_manager.session_scope() as session:
                agent = session.query(Agent).filter_by(id=agent_id).first()
                ticket = session.query(AgentTicket).filter_by(id=ticket_id).first()
                if not agent or not ticket:
                    return {"success": False, "error": "Agent or ticket not found"}
                rank = agent.rank or 3
                # Rank 1: can move any ticket
                if rank == 1:
                    return {"success": True, "allowed": True}
                # Assigned agent can move their own ticket
                if ticket.assignee_id == agent_id:
                    return {"success": True, "allowed": True}
                # Rank 2: can move tickets of agents they supervise
                if rank == 2 and ticket.assignee_id:
                    assignee = session.query(Agent).filter_by(id=ticket.assignee_id).first()
                    if assignee and assignee.reports_to_id == agent_id:
                        return {"success": True, "allowed": True}
                return {"success": True, "allowed": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Due Date Monitoring ───────────────────────────────────

    def get_overdue_tickets(self) -> dict:
        """Return tickets past their due date that are not done."""
        try:
            now = datetime.utcnow()
            with self.db_manager.session_scope() as session:
                tickets = (
                    session.query(AgentTicket)
                    .filter(
                        AgentTicket.due_date.isnot(None),
                        AgentTicket.due_date < now,
                        AgentTicket.status != "done",
                    )
                    .all()
                )
                result = [self._ticket_to_dict(t, session) for t in tickets]
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_upcoming_due(self, hours: int = 4) -> dict:
        """Return tickets due within N hours."""
        try:
            now = datetime.utcnow()
            deadline = now + timedelta(hours=hours)
            with self.db_manager.session_scope() as session:
                tickets = (
                    session.query(AgentTicket)
                    .filter(
                        AgentTicket.due_date.isnot(None),
                        AgentTicket.due_date >= now,
                        AgentTicket.due_date <= deadline,
                        AgentTicket.status != "done",
                    )
                    .all()
                )
                result = [self._ticket_to_dict(t, session) for t in tickets]
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Statistics ────────────────────────────────────────────

    def get_ticket_stats(self) -> dict:
        """Return counts per status, per priority, per assignee for dashboard widgets."""
        try:
            with self.db_manager.session_scope() as session:
                tickets = session.query(AgentTicket).all()
                by_status = {s: 0 for s in TICKET_STATUSES}
                by_priority = {p: 0 for p in TICKET_PRIORITIES}
                total = len(tickets)
                overdue = 0
                now = datetime.utcnow()
                for t in tickets:
                    if t.status in by_status:
                        by_status[t.status] += 1
                    if t.priority in by_priority:
                        by_priority[t.priority] += 1
                    if t.due_date and t.due_date < now and t.status != "done":
                        overdue += 1
            return {
                "success": True,
                "data": {
                    "total": total,
                    "by_status": by_status,
                    "by_priority": by_priority,
                    "overdue": overdue,
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Helpers ───────────────────────────────────────────────

    def _ticket_to_dict(self, ticket: AgentTicket, session) -> dict:
        """Convert ticket ORM object to a plain dict inside session scope."""
        assignee_name = ""
        assignee_emoji = ""
        if ticket.assignee_id:
            assignee = session.query(Agent).filter_by(id=ticket.assignee_id).first()
            if assignee:
                assignee_name = assignee.name
                assignee_emoji = assignee.identity_emoji or ""

        reporter_name = ""
        if ticket.reporter_id:
            reporter = session.query(Agent).filter_by(id=ticket.reporter_id).first()
            if reporter:
                reporter_name = reporter.name

        due_date_display = ""
        if ticket.due_date:
            due_date_display = ticket.due_date.strftime("%b %d, %H:%M")

        sub_count = (
            session.query(AgentTicket)
            .filter_by(parent_ticket_id=ticket.id)
            .count()
        )

        return {
            "id": ticket.id,
            "title": ticket.title,
            "description": ticket.description,
            "priority": ticket.priority,
            "status": ticket.status,
            "assignee_id": ticket.assignee_id,
            "assignee_name": assignee_name,
            "assignee_emoji": assignee_emoji,
            "reporter_id": ticket.reporter_id,
            "reporter_name": reporter_name,
            "reporter_type": ticket.reporter_type,
            "parent_ticket_id": ticket.parent_ticket_id,
            "due_date": ticket.due_date.isoformat() if ticket.due_date else None,
            "due_date_display": due_date_display,
            "labels": ticket.labels or "",
            "blocked_reason": ticket.blocked_reason,
            "escalated_to_id": ticket.escalated_to_id,
            "approval_status": ticket.approval_status,
            "approved_by_id": ticket.approved_by_id,
            "linked_task_id": ticket.linked_task_id,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
            "completed_at": ticket.completed_at.isoformat() if ticket.completed_at else None,
            "sub_ticket_count": sub_count,
        }

    def _comment_to_dict(self, comment: TicketComment, session) -> dict:
        author_name = ""
        author_emoji = ""
        if comment.author_id:
            author = session.query(Agent).filter_by(id=comment.author_id).first()
            if author:
                author_name = author.name
                author_emoji = author.identity_emoji or ""

        return {
            "id": comment.id,
            "ticket_id": comment.ticket_id,
            "author_id": comment.author_id,
            "author_name": author_name,
            "author_emoji": author_emoji,
            "author_type": comment.author_type,
            "content": comment.content,
            "comment_type": comment.comment_type,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
        }
