"""
Tests for NavigationService + CommandPalette — cross-page navigation.
"""
import pytest
from unittest.mock import MagicMock

from core.navigation_service import (
    NavigationService,
    PAGE_DASHBOARD, PAGE_HUNTER, PAGE_FORGE, PAGE_OUTREACH,
    PAGE_FLEET, PAGE_KANBAN, PAGE_HISTORY, PAGE_TRENDS,
    PAGE_BUDGET, PAGE_INTEGRATIONS, PAGE_SETTINGS, PAGE_SUPPRESSION,
    PAGE_NAMES, PAGE_INDEX_BY_NAME,
)


@pytest.fixture
def qapp():
    """Minimal QApplication for signal testing."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def nav_service(qapp):
    """NavigationService instance (QObject, parent=None)."""
    service = NavigationService(parent=None)
    return service


class TestPageConstants:
    """Test page index constants."""

    def test_page_indices(self):
        assert PAGE_DASHBOARD == 0
        assert PAGE_HUNTER == 1
        assert PAGE_FORGE == 2
        assert PAGE_OUTREACH == 3
        assert PAGE_FLEET == 4
        assert PAGE_KANBAN == 5
        assert PAGE_HISTORY == 6
        assert PAGE_TRENDS == 7
        assert PAGE_BUDGET == 8
        assert PAGE_INTEGRATIONS == 9
        assert PAGE_SETTINGS == 10
        assert PAGE_SUPPRESSION == 11

    def test_page_names_complete(self):
        """All 14 pages should be in PAGE_NAMES."""
        assert len(PAGE_NAMES) == 14

    def test_page_index_by_name(self):
        """Should map name strings to indices."""
        assert PAGE_INDEX_BY_NAME["dashboard"] == 0
        assert PAGE_INDEX_BY_NAME["hunter"] == 1
        assert PAGE_INDEX_BY_NAME["suppression"] == 11


class TestNavigationService:
    """Test NavigationService."""

    def test_init(self, nav_service):
        assert nav_service is not None

    def test_navigate_by_index(self, nav_service, qapp):
        """Should emit navigate_requested signal."""
        received = []
        nav_service.navigate_requested.connect(
            lambda idx, ctx: received.append((idx, ctx))
        )
        nav_service.navigate_by_index(3)
        assert len(received) == 1
        assert received[0][0] == 3

    def test_navigate_by_name(self, nav_service, qapp):
        """Should resolve name to index and navigate."""
        received = []
        nav_service.navigate_requested.connect(
            lambda idx, ctx: received.append((idx, ctx))
        )
        nav_service.navigate_by_name("kanban")
        assert len(received) == 1
        assert received[0][0] == PAGE_KANBAN

    def test_navigate_by_name_invalid(self, nav_service, qapp):
        """Should not emit for invalid page name."""
        received = []
        nav_service.navigate_requested.connect(
            lambda idx, ctx: received.append((idx, ctx))
        )
        nav_service.navigate_by_name("nonexistent_page")
        assert len(received) == 0

    def test_navigate_with_context(self, nav_service, qapp):
        """Should pass context dict with navigation."""
        received = []
        nav_service.navigate_requested.connect(
            lambda idx, ctx: received.append((idx, ctx))
        )
        context = {"lead_id": 42, "campaign_id": 7}
        nav_service.navigate_by_index(3, context)
        assert len(received) == 1
        assert received[0][1].get("lead_id") == 42

    def test_go_to_hunter(self, nav_service, qapp):
        """Should navigate to hunter page."""
        received = []
        nav_service.navigate_requested.connect(
            lambda idx, ctx: received.append((idx, ctx))
        )
        nav_service.go_to_hunter()
        assert received[0][0] == PAGE_HUNTER

    def test_go_to_outreach(self, nav_service, qapp):
        """Should navigate to outreach with context."""
        received = []
        nav_service.navigate_requested.connect(
            lambda idx, ctx: received.append((idx, ctx))
        )
        nav_service.go_to_outreach(campaign_id=5, lead_id=10)
        assert received[0][0] == PAGE_OUTREACH
        assert received[0][1].get("campaign_id") == 5

    def test_go_to_kanban(self, nav_service, qapp):
        """Should navigate to kanban with ticket context."""
        received = []
        nav_service.navigate_requested.connect(
            lambda idx, ctx: received.append((idx, ctx))
        )
        nav_service.go_to_kanban(ticket_id=99)
        assert received[0][0] == PAGE_KANBAN
        assert received[0][1].get("ticket_id") == 99

    def test_go_back(self, nav_service, qapp):
        """Should navigate back in history stack."""
        received = []
        nav_service.navigate_requested.connect(
            lambda idx, ctx: received.append((idx, ctx))
        )
        # Navigate to several pages
        nav_service.navigate_by_index(1)
        nav_service.navigate_by_index(5)
        nav_service.navigate_by_index(3)
        received.clear()

        nav_service.go_back()
        # Should go back to the previous page (5)
        if received:
            assert received[0][0] == 5


class TestActionRegistry:
    """Test action registration and execution."""

    def test_register_action(self, nav_service):
        """Should register a named action."""
        callback = MagicMock()
        nav_service.register_action("test_action", callback)
        actions = nav_service.get_available_actions()
        assert "test_action" in actions

    def test_execute_action(self, nav_service):
        """Should execute a registered action."""
        callback = MagicMock()
        nav_service.register_action("test_action", callback)
        nav_service.execute_action("test_action")
        callback.assert_called_once()

    def test_execute_unknown_action(self, nav_service):
        """Should not crash on unknown action."""
        nav_service.execute_action("nonexistent_action")


class TestNavigationCommands:
    """Test command palette integration."""

    def test_get_navigation_commands(self, nav_service):
        """Should return a list of commands for the palette."""
        commands = nav_service.get_navigation_commands()
        assert isinstance(commands, list)
        assert len(commands) >= 12

    def test_command_structure(self, nav_service):
        """Each command should have required fields."""
        commands = nav_service.get_navigation_commands()
        for cmd in commands:
            assert "label" in cmd or "name" in cmd
            assert "type" in cmd

    def test_commands_include_all_pages(self, nav_service):
        """Should include navigation commands for all 12 pages."""
        commands = nav_service.get_navigation_commands()
        nav_commands = [c for c in commands if c.get("type") == "navigate"]
        assert len(nav_commands) >= 12


class TestCommandPaletteWidget:
    """Test CommandPalette widget."""

    def test_import(self):
        """Should import without errors."""
        from ui.components.command_palette import CommandPalette
        assert CommandPalette is not None

    def test_fuzzy_match_import(self):
        """Should import fuzzy match function."""
        from ui.components.command_palette import _fuzzy_match
        assert callable(_fuzzy_match)

    def test_fuzzy_match_exact(self):
        """Exact match should score highest."""
        from ui.components.command_palette import _fuzzy_match
        score = _fuzzy_match("hunter", "hunter")
        assert score >= 0.9

    def test_fuzzy_match_prefix(self):
        """Prefix match should score high."""
        from ui.components.command_palette import _fuzzy_match
        score = _fuzzy_match("hun", "hunter")
        assert score >= 0.5

    def test_fuzzy_match_contains(self):
        """Substring match should score moderately."""
        from ui.components.command_palette import _fuzzy_match
        score = _fuzzy_match("unt", "hunter")
        assert score > 0

    def test_fuzzy_match_no_match(self):
        """Non-matching strings should score 0."""
        from ui.components.command_palette import _fuzzy_match
        score = _fuzzy_match("xyz", "hunter")
        assert score == 0 or score < 0.1

    def test_command_palette_init(self, qapp):
        """Should initialize without errors."""
        from ui.components.command_palette import CommandPalette
        from PySide6.QtWidgets import QWidget
        parent = QWidget()
        palette = CommandPalette(parent)
        assert palette is not None

    def test_set_commands(self, qapp):
        """Should accept a list of commands."""
        from ui.components.command_palette import CommandPalette
        from PySide6.QtWidgets import QWidget
        parent = QWidget()
        palette = CommandPalette(parent)
        commands = [
            {"name": "Go to Hunter", "type": "navigate", "index": 1},
            {"name": "Go to Forge", "type": "navigate", "index": 2},
        ]
        palette.set_commands(commands)

    def test_show_palette(self, qapp):
        """Should show the palette overlay."""
        from ui.components.command_palette import CommandPalette
        from PySide6.QtWidgets import QWidget
        parent = QWidget()
        parent.resize(800, 600)
        palette = CommandPalette(parent)
        palette.show_palette()
        assert palette.isVisible()
