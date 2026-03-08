"""
Aura — Navigation Service
Cross-page navigation with context passing and action registry.
Enables programmatic navigation between all 12 pages with data context.
"""

from typing import Optional, Dict, Callable, Any

try:
    from PySide6.QtCore import QObject, Signal
    _HAS_QT = True
except ImportError:
    _HAS_QT = False

    class QObject:
        """Stub for headless/CLI mode."""
        def __init__(self, parent=None):
            pass

    class Signal:
        """Minimal signal stub that works as a simple callback list."""
        def __init__(self, *args):
            self._callbacks = []

        def connect(self, cb):
            self._callbacks.append(cb)

        def emit(self, *args):
            for cb in self._callbacks:
                cb(*args)

from utils.logger import get_logger

logger = get_logger("navigation_service")

# Page indices (must match sidebar order)
PAGE_DASHBOARD = 0
PAGE_HUNTER = 1
PAGE_FORGE = 2
PAGE_OUTREACH = 3
PAGE_FLEET = 4
PAGE_KANBAN = 5
PAGE_HISTORY = 6
PAGE_TRENDS = 7
PAGE_BUDGET = 8
PAGE_INTEGRATIONS = 9
PAGE_SETTINGS = 10
PAGE_SUPPRESSION = 11
PAGE_RESEARCH = 12
PAGE_CALLS = 13

PAGE_NAMES = {
    PAGE_DASHBOARD: "Dashboard",
    PAGE_HUNTER: "Hunter",
    PAGE_FORGE: "Forge",
    PAGE_OUTREACH: "Outreach",
    PAGE_FLEET: "Fleet",
    PAGE_KANBAN: "Kanban",
    PAGE_HISTORY: "History",
    PAGE_TRENDS: "Trends",
    PAGE_BUDGET: "Budget",
    PAGE_INTEGRATIONS: "Integrations",
    PAGE_SETTINGS: "Settings",
    PAGE_SUPPRESSION: "Suppression",
    PAGE_RESEARCH: "Research",
    PAGE_CALLS: "Calls",
}

# Reverse lookup: name → index
PAGE_INDEX_BY_NAME = {v.lower(): k for k, v in PAGE_NAMES.items()}


class NavigationService(QObject):
    """
    Cross-page navigation service.
    Emits navigate_requested(page_index, context_dict) which MainWindow
    connects to switch pages and pass context.
    """

    navigate_requested = Signal(int, dict)  # page_index, context

    def __init__(self, parent=None):
        super().__init__(parent)
        self._action_registry: Dict[str, Callable] = {}
        self._history: list = []  # navigation history stack for back navigation

    # ─── Named navigation methods ────────────────────────────────────────

    def go_to_dashboard(self, context: Optional[dict] = None):
        """Navigate to Dashboard."""
        self._navigate(PAGE_DASHBOARD, context)

    def go_to_hunter(self, context: Optional[dict] = None):
        """Navigate to Hunter page. Context: prefill_niche, prefill_city, prefill_query."""
        self._navigate(PAGE_HUNTER, context)

    def go_to_forge(self, context: Optional[dict] = None):
        """Navigate to Forge. Context: agent_id (open editor), skill_id (open skill)."""
        self._navigate(PAGE_FORGE, context)

    def go_to_outreach(self, campaign_id: int = None, lead_id: int = None,
                        context: Optional[dict] = None):
        """Navigate to Outreach. Auto-select campaign and/or lead."""
        ctx = context or {}
        if campaign_id is not None:
            ctx["campaign_id"] = campaign_id
        if lead_id is not None:
            ctx["lead_id"] = lead_id
        self._navigate(PAGE_OUTREACH, ctx)

    def go_to_fleet(self, agent_id: int = None, context: Optional[dict] = None):
        """Navigate to Fleet. Context: agent_id (open detail)."""
        ctx = context or {}
        if agent_id is not None:
            ctx["agent_id"] = agent_id
        self._navigate(PAGE_FLEET, ctx)

    def go_to_kanban(self, ticket_id: int = None, context: Optional[dict] = None):
        """Navigate to Kanban. Context: ticket_id (open detail)."""
        ctx = context or {}
        if ticket_id is not None:
            ctx["ticket_id"] = ticket_id
        self._navigate(PAGE_KANBAN, ctx)

    def go_to_history(self, context: Optional[dict] = None):
        """Navigate to History. Context: filter dict, agent_id, source."""
        self._navigate(PAGE_HISTORY, context)

    def go_to_trends(self, keyword: str = None, context: Optional[dict] = None):
        """Navigate to Trends. Context: keyword (start search)."""
        ctx = context or {}
        if keyword:
            ctx["keyword"] = keyword
        self._navigate(PAGE_TRENDS, ctx)

    def go_to_budget(self, context: Optional[dict] = None):
        """Navigate to Budget."""
        self._navigate(PAGE_BUDGET, context)

    def go_to_integrations(self, context: Optional[dict] = None):
        """Navigate to Integrations."""
        self._navigate(PAGE_INTEGRATIONS, context)

    def go_to_settings(self, section: str = None, context: Optional[dict] = None):
        """Navigate to Settings. Context: section (scroll to specific area)."""
        ctx = context or {}
        if section:
            ctx["section"] = section
        self._navigate(PAGE_SETTINGS, ctx)

    def go_to_suppression(self, context: Optional[dict] = None):
        """Navigate to Suppression. Context: add_email (prefill entry)."""
        self._navigate(PAGE_SUPPRESSION, context)

    def go_to_research(self, lead_id: int = None, context: Optional[dict] = None):
        """Navigate to Research. Context: lead_id (view report)."""
        ctx = context or {}
        if lead_id is not None:
            ctx["lead_id"] = lead_id
        self._navigate(PAGE_RESEARCH, ctx)

    def go_to_calls(self, lead_id: int = None, context: Optional[dict] = None):
        """Navigate to Calls. Context: lead_id (initiate call)."""
        ctx = context or {}
        if lead_id is not None:
            ctx["lead_id"] = lead_id
        self._navigate(PAGE_CALLS, ctx)

    # ─── Generic navigation ──────────────────────────────────────────────

    def navigate_by_name(self, page_name: str, context: Optional[dict] = None):
        """Navigate to a page by name (case-insensitive)."""
        index = PAGE_INDEX_BY_NAME.get(page_name.lower())
        if index is not None:
            self._navigate(index, context)
        else:
            logger.warning(f"Unknown page name: {page_name}")

    def navigate_by_index(self, index: int, context: Optional[dict] = None):
        """Navigate to a page by index."""
        if 0 <= index <= PAGE_CALLS:
            self._navigate(index, context)
        else:
            logger.warning(f"Invalid page index: {index}")

    def go_back(self):
        """Navigate to the previous page."""
        if len(self._history) >= 2:
            self._history.pop()  # Remove current
            prev = self._history[-1]
            self.navigate_requested.emit(prev["index"], prev.get("context", {}))

    # ─── Action registry ─────────────────────────────────────────────────

    def register_action(self, action_name: str, handler: Callable):
        """Register a named cross-page action."""
        self._action_registry[action_name] = handler
        logger.debug(f"Registered action: {action_name}")

    def execute_action(self, action_name: str, **kwargs) -> Any:
        """Execute a registered cross-page action."""
        handler = self._action_registry.get(action_name)
        if handler:
            try:
                return handler(**kwargs)
            except Exception as e:
                logger.error(f"Action '{action_name}' failed: {e}")
                return None
        else:
            logger.warning(f"Unknown action: {action_name}")
            return None

    def get_available_actions(self) -> list:
        """Return list of registered action names."""
        return list(self._action_registry.keys())

    # ─── Command palette support ─────────────────────────────────────────

    def get_navigation_commands(self) -> list:
        """Return list of navigation commands for the command palette."""
        commands = []
        for index, name in PAGE_NAMES.items():
            commands.append({
                "type": "navigate",
                "label": f"Go to {name}",
                "page_index": index,
                "page_name": name,
            })

        for action_name in self._action_registry:
            commands.append({
                "type": "action",
                "label": action_name.replace("_", " ").title(),
                "action_name": action_name,
            })

        return commands

    # ─── Internal ────────────────────────────────────────────────────────

    def _navigate(self, index: int, context: Optional[dict] = None):
        ctx = context or {}
        self._history.append({"index": index, "context": ctx})
        # Keep history bounded
        if len(self._history) > 50:
            self._history = self._history[-50:]
        logger.debug(f"Navigate to {PAGE_NAMES.get(index, index)} with context={list(ctx.keys())}")
        self.navigate_requested.emit(index, ctx)
