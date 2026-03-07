"""
Aura -- Kanban Controller
UI-facing controller for the ticket/Kanban board: CRUD, move, filter, comments.
"""

from PySide6.QtCore import QObject, Signal

from database.db_manager import DatabaseManager
from core.ticket_engine import TicketEngine
from utils.logger import get_logger

logger = get_logger("kanban_controller")


class KanbanController(QObject):
    """Bridges the ticket engine to the Kanban UI layer."""

    # ─── Signals ──────────────────────────────────────────────
    board_ready = Signal(dict)              # {status: [ticket_dicts]}
    ticket_created = Signal(dict)           # ticket dict
    ticket_updated = Signal(dict)           # ticket dict
    ticket_moved = Signal(int, str)         # ticket_id, new_status
    ticket_deleted = Signal(int)            # ticket_id
    ticket_detail_ready = Signal(dict)      # full ticket dict with comments
    comments_ready = Signal(dict)           # {ticket_id, comments: [...]}
    stats_ready = Signal(dict)              # ticket stats
    due_date_alerts = Signal(dict)          # {overdue: [...], upcoming: [...]}
    sprint_created = Signal(dict)           # sprint info
    timeline_ready = Signal(dict)           # {dates: {...}}
    error = Signal(str)

    def __init__(self, db_manager: DatabaseManager, ticket_engine: TicketEngine,
                 ticket_scheduler=None):
        super().__init__()
        self.db_manager = db_manager
        self.ticket_engine = ticket_engine
        self.ticket_scheduler = ticket_scheduler

    def refresh_board(self, assignee_id: int = None, priority: str = None,
                      label: str = None):
        """Load all tickets grouped by status for Kanban display."""
        result = self.ticket_engine.get_tickets_by_status(
            assignee_id=assignee_id, priority=priority, label=label,
        )
        if result.get("success"):
            self.board_ready.emit(result["data"])
        else:
            self.error.emit(result.get("error", "Failed to load board"))

    def create_ticket(self, title: str, description: str = "",
                      priority: str = "medium", assignee_id: int = None,
                      due_date=None, labels: str = "",
                      parent_ticket_id: int = None):
        """Create a new ticket and emit signals."""
        result = self.ticket_engine.create_ticket(
            title=title,
            description=description,
            priority=priority,
            assignee_id=assignee_id,
            due_date=due_date,
            labels=labels,
            parent_ticket_id=parent_ticket_id,
        )
        if result.get("success"):
            self.ticket_created.emit(result["data"])
        else:
            self.error.emit(result.get("error", "Failed to create ticket"))

    def move_ticket(self, ticket_id: int, new_status: str):
        """Move a ticket between Kanban columns."""
        result = self.ticket_engine.move_ticket(ticket_id, new_status)
        if result.get("success"):
            self.ticket_moved.emit(ticket_id, new_status)
        else:
            self.error.emit(result.get("error", "Failed to move ticket"))

    def update_ticket(self, ticket_id: int, **fields):
        """Update ticket fields."""
        result = self.ticket_engine.update_ticket(ticket_id, **fields)
        if result.get("success"):
            self.ticket_updated.emit(result["data"])
        else:
            self.error.emit(result.get("error", "Failed to update ticket"))

    def delete_ticket(self, ticket_id: int):
        """Delete a ticket."""
        result = self.ticket_engine.delete_ticket(ticket_id)
        if result.get("success"):
            self.ticket_deleted.emit(ticket_id)
        else:
            self.error.emit(result.get("error", "Failed to delete ticket"))

    def get_ticket_detail(self, ticket_id: int):
        """Get full ticket info with comments for detail panel."""
        result = self.ticket_engine.get_ticket(ticket_id)
        if result.get("success"):
            self.ticket_detail_ready.emit(result["data"])
        else:
            self.error.emit(result.get("error", "Failed to load ticket"))

    def add_comment(self, ticket_id: int, content: str,
                    author_type: str = "user"):
        """Add a comment to a ticket."""
        result = self.ticket_engine.add_comment(
            ticket_id=ticket_id, content=content, author_type=author_type,
        )
        if result.get("success"):
            # Reload full ticket detail to refresh comments
            self.get_ticket_detail(ticket_id)
        else:
            self.error.emit(result.get("error", "Failed to add comment"))

    def refresh_stats(self):
        """Get ticket statistics for dashboard widget."""
        result = self.ticket_engine.get_ticket_stats()
        if result.get("success"):
            self.stats_ready.emit(result["data"])

    def check_due_dates(self):
        """Check for overdue and upcoming-due tickets."""
        if not self.ticket_scheduler:
            return
        result = self.ticket_scheduler.check_due_dates()
        if result.get("success"):
            if result.get("overdue_count", 0) > 0 or result.get("upcoming_count", 0) > 0:
                self.due_date_alerts.emit(result)
                # Send notifications to agents
                self.ticket_scheduler.send_due_date_notifications(
                    result.get("notifications", [])
                )

    def create_sprint(self, name: str, start_date, end_date, ticket_ids: list):
        """Create a sprint with the given tickets."""
        if not self.ticket_scheduler:
            self.error.emit("Ticket scheduler not available")
            return
        result = self.ticket_scheduler.create_sprint(name, start_date, end_date, ticket_ids)
        if result.get("success"):
            self.sprint_created.emit(result)
            self.refresh_board()
        else:
            self.error.emit(result.get("error", "Failed to create sprint"))

    def get_timeline(self, days_ahead: int = 14):
        """Get ticket timeline for the next N days."""
        if not self.ticket_scheduler:
            return
        result = self.ticket_scheduler.get_timeline(days_ahead)
        if result.get("success"):
            self.timeline_ready.emit(result)

    def get_agents_list(self) -> list:
        """Return list of agents for assignee combo."""
        try:
            from database.schema import Agent
            with self.db_manager.session_scope() as session:
                agents = session.query(Agent).order_by(Agent.rank, Agent.name).all()
                return [
                    {
                        "id": a.id,
                        "name": a.name,
                        "emoji": a.identity_emoji or "",
                        "rank": a.rank or 3,
                        "role": a.role,
                    }
                    for a in agents
                ]
        except Exception:
            return []
