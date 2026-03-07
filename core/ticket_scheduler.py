"""
Aura — Ticket Scheduler
Due-date monitoring, sprint planning, timeline queries, and overdue
notifications. Works directly with ticket due_date fields (no separate
CalendarEvent model).
"""

from datetime import datetime, timedelta

from database.db_manager import DatabaseManager
from database.schema import Agent, AgentTicket, AgentMessage
from utils.logger import get_logger

logger = get_logger("ticket_scheduler")


class TicketScheduler:
    """Due-date monitoring, sprint planning, and timeline for tickets."""

    def __init__(self, db_manager: DatabaseManager, ticket_engine,
                 agent_engine=None):
        self.db_manager = db_manager
        self.ticket_engine = ticket_engine
        self.agent_engine = agent_engine

    # ─── Due-Date Checks ──────────────────────────────────────────────

    def check_due_dates(self, warning_hours: int = 4) -> dict:
        """Check for overdue and upcoming-due tickets.

        Returns: {overdue: [...], upcoming: [...], notifications: [...]}
        """
        try:
            now = datetime.utcnow()
            warning_cutoff = now + timedelta(hours=warning_hours)
            overdue = []
            upcoming = []
            notifications = []

            with self.db_manager.session_scope() as session:
                # Overdue: due_date < now, not done
                overdue_tickets = (
                    session.query(AgentTicket)
                    .filter(
                        AgentTicket.due_date.isnot(None),
                        AgentTicket.due_date < now,
                        AgentTicket.status != "done",
                    )
                    .all()
                )
                for t in overdue_tickets:
                    assignee = None
                    if t.assignee_id:
                        assignee = session.query(Agent).filter_by(
                            id=t.assignee_id
                        ).first()
                    overdue.append({
                        "id": t.id,
                        "title": t.title,
                        "priority": t.priority,
                        "due_date": t.due_date.isoformat(),
                        "assignee_name": assignee.name if assignee else "Unassigned",
                        "assignee_id": t.assignee_id,
                        "hours_overdue": round(
                            (now - t.due_date).total_seconds() / 3600, 1
                        ),
                    })
                    notifications.append({
                        "type": "overdue",
                        "ticket_id": t.id,
                        "title": t.title,
                        "assignee_id": t.assignee_id,
                    })

                # Upcoming: now <= due_date <= warning_cutoff, not done
                upcoming_tickets = (
                    session.query(AgentTicket)
                    .filter(
                        AgentTicket.due_date.isnot(None),
                        AgentTicket.due_date >= now,
                        AgentTicket.due_date <= warning_cutoff,
                        AgentTicket.status != "done",
                    )
                    .all()
                )
                for t in upcoming_tickets:
                    assignee = None
                    if t.assignee_id:
                        assignee = session.query(Agent).filter_by(
                            id=t.assignee_id
                        ).first()
                    upcoming.append({
                        "id": t.id,
                        "title": t.title,
                        "priority": t.priority,
                        "due_date": t.due_date.isoformat(),
                        "assignee_name": assignee.name if assignee else "Unassigned",
                        "assignee_id": t.assignee_id,
                        "hours_remaining": round(
                            (t.due_date - now).total_seconds() / 3600, 1
                        ),
                    })
                    notifications.append({
                        "type": "upcoming",
                        "ticket_id": t.id,
                        "title": t.title,
                        "assignee_id": t.assignee_id,
                    })

            return {
                "success": True,
                "overdue": overdue,
                "upcoming": upcoming,
                "notifications": notifications,
                "overdue_count": len(overdue),
                "upcoming_count": len(upcoming),
            }
        except Exception as e:
            logger.error(f"Due-date check failed: {e}")
            return {"success": False, "error": str(e)}

    def send_due_date_notifications(self, notifications: list) -> dict:
        """Send AgentMessages to assignees about overdue/upcoming tickets."""
        if not self.agent_engine:
            return {"success": False, "error": "Agent engine not available"}

        sent = 0
        try:
            # Find Commander to send from
            commander_id = None
            with self.db_manager.session_scope() as session:
                commander = session.query(Agent).filter_by(rank=1).first()
                if commander:
                    commander_id = commander.id

            if not commander_id:
                return {"success": False, "error": "Commander not found"}

            for n in notifications:
                if not n.get("assignee_id"):
                    continue
                msg_type = (
                    "ticket_overdue" if n["type"] == "overdue"
                    else "ticket_due_soon"
                )
                self.agent_engine.send_message(
                    from_id=commander_id,
                    to_id=n["assignee_id"],
                    message_type=msg_type,
                    content={
                        "ticket_id": n["ticket_id"],
                        "title": n["title"],
                        "type": n["type"],
                    },
                )
                sent += 1

            return {"success": True, "sent": sent}
        except Exception as e:
            logger.error(f"Due-date notification failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Sprint Planning ──────────────────────────────────────────────

    def create_sprint(self, name: str, start_date: datetime,
                      end_date: datetime, ticket_ids: list) -> dict:
        """Assign a set of tickets to a sprint by setting due_date and label."""
        try:
            updated = 0
            sprint_label = f"sprint:{name}"

            for tid in ticket_ids:
                result = self.ticket_engine.update_ticket(
                    tid,
                    due_date=end_date,
                    labels=sprint_label,
                )
                if result.get("success"):
                    updated += 1
                    self.ticket_engine.add_comment(
                        ticket_id=tid,
                        content=f"Added to sprint '{name}' ({start_date.strftime('%m/%d')} - {end_date.strftime('%m/%d')})",
                        author_type="system",
                        comment_type="status_change",
                    )

            logger.info(f"Sprint '{name}' created with {updated} tickets")
            return {
                "success": True,
                "sprint_name": name,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "ticket_count": updated,
            }
        except Exception as e:
            logger.error(f"Sprint creation failed: {e}")
            return {"success": False, "error": str(e)}

    def get_sprint_progress(self, sprint_name: str) -> dict:
        """Get progress for a named sprint."""
        try:
            sprint_label = f"sprint:{sprint_name}"
            result = self.ticket_engine.get_all_tickets(label=sprint_label)
            if not result.get("success"):
                return result

            tickets = result["data"]
            total = len(tickets)
            done = sum(1 for t in tickets if t.get("status") == "done")
            in_progress = sum(1 for t in tickets if t.get("status") == "in_progress")
            progress_pct = int(done / total * 100) if total > 0 else 0

            return {
                "success": True,
                "sprint_name": sprint_name,
                "total": total,
                "done": done,
                "in_progress": in_progress,
                "remaining": total - done,
                "progress_pct": progress_pct,
            }
        except Exception as e:
            logger.error(f"Sprint progress query failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Timeline ─────────────────────────────────────────────────────

    def get_timeline(self, days_ahead: int = 14) -> dict:
        """Get tickets grouped by due date for the next N days."""
        try:
            now = datetime.utcnow()
            end = now + timedelta(days=days_ahead)
            dates = {}

            with self.db_manager.session_scope() as session:
                tickets = (
                    session.query(AgentTicket)
                    .filter(
                        AgentTicket.due_date.isnot(None),
                        AgentTicket.due_date >= now,
                        AgentTicket.due_date <= end,
                        AgentTicket.status != "done",
                    )
                    .order_by(AgentTicket.due_date)
                    .all()
                )

                for t in tickets:
                    date_key = t.due_date.strftime("%Y-%m-%d")
                    if date_key not in dates:
                        dates[date_key] = []
                    assignee = None
                    if t.assignee_id:
                        assignee = session.query(Agent).filter_by(
                            id=t.assignee_id
                        ).first()
                    dates[date_key].append({
                        "id": t.id,
                        "title": t.title,
                        "priority": t.priority,
                        "status": t.status,
                        "assignee_name": assignee.name if assignee else "Unassigned",
                        "due_date": t.due_date.isoformat(),
                    })

            return {"success": True, "dates": dates, "days_ahead": days_ahead}
        except Exception as e:
            logger.error(f"Timeline query failed: {e}")
            return {"success": False, "error": str(e)}
