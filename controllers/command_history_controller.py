"""
Aura -- Command History Controller
UI-facing controller for the command history page: query, filter, detail, prune.
"""

from PySide6.QtCore import QObject, Signal

from database.db_manager import DatabaseManager
from core.command_history import CommandHistoryEngine
from utils.logger import get_logger

logger = get_logger("command_history_controller")


class CommandHistoryController(QObject):
    """Bridges the CommandHistoryEngine to the History UI page."""

    # ─── Signals ──────────────────────────────────────────────────────────
    history_ready = Signal(dict)
    command_tree_ready = Signal(dict)
    command_detail_ready = Signal(dict)
    stats_ready = Signal(dict)
    prune_complete = Signal(int)
    error = Signal(str)

    def __init__(
        self,
        db_manager: DatabaseManager,
        command_history_engine: CommandHistoryEngine,
    ):
        super().__init__()
        self.db_manager = db_manager
        self.engine = command_history_engine

    def refresh_history(
        self,
        source=None,
        agent_id=None,
        command_type=None,
        status=None,
        search_text=None,
        root_only=True,
        page=1,
        page_size=50,
    ):
        """Load paginated history with filters."""
        result = self.engine.get_history(
            source=source,
            agent_id=agent_id,
            command_type=command_type,
            status=status,
            search_text=search_text,
            root_only=root_only,
            page=page,
            page_size=page_size,
        )
        if result.get("success"):
            self.history_ready.emit(result["data"])
        else:
            self.error.emit(result.get("error", "Failed to load history"))

    def get_command_tree(self, command_id: int):
        """Load full command tree for expandable detail view."""
        result = self.engine.get_command_tree(command_id)
        if result.get("success"):
            self.command_tree_ready.emit(result["data"])
        else:
            self.error.emit(result.get("error", "Failed to load command tree"))

    def get_command_detail(self, command_id: int):
        """Load a single command's details."""
        result = self.engine.get_command(command_id)
        if result.get("success"):
            self.command_detail_ready.emit(result["data"])
        else:
            self.error.emit(result.get("error", "Failed to load command"))

    def refresh_stats(self):
        """Load aggregate statistics."""
        result = self.engine.get_stats()
        if result.get("success"):
            self.stats_ready.emit(result["data"])

    def prune_history(self, days: int = 90):
        """Prune old entries."""
        result = self.engine.prune_old_entries(days)
        if result.get("success"):
            self.prune_complete.emit(result.get("deleted", 0))
        else:
            self.error.emit(result.get("error", "Prune failed"))

    def get_agents_list(self) -> list:
        """Return list of agents for the filter combo."""
        try:
            from database.schema import Agent

            with self.db_manager.session_scope() as session:
                agents = session.query(Agent).order_by(Agent.rank, Agent.name).all()
                return [
                    {
                        "id": a.id,
                        "name": a.name,
                        "emoji": a.identity_emoji or "",
                        "role": a.role,
                    }
                    for a in agents
                ]
        except Exception:
            return []
