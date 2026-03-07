"""
Tests for the icon registry and qtawesome integration.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestIconRegistryData:
    """Tests for icon registry data (no QApplication needed)."""

    def test_all_icon_keys_resolve_to_valid_mdi6_names(self):
        """Every key in ICONS should map to an mdi6.xxx string."""
        from ui.icons import ICONS
        for key, icon_name in ICONS.items():
            assert icon_name.startswith("mdi6."), (
                f"Icon key '{key}' maps to '{icon_name}' which is not an mdi6 icon"
            )

    def test_icon_colors_have_both_themes(self):
        """ICON_COLORS should have both dark and light themes."""
        from ui.icons import ICON_COLORS
        assert "dark" in ICON_COLORS
        assert "light" in ICON_COLORS

    def test_icon_colors_have_required_keys(self):
        """Each theme should have default, muted, accent, success, warning, danger, info."""
        from ui.icons import ICON_COLORS
        required = {"default", "muted", "accent", "success", "warning", "danger", "info"}
        for theme in ("dark", "light"):
            missing = required - set(ICON_COLORS[theme].keys())
            assert not missing, f"Theme '{theme}' missing color keys: {missing}"

    def test_sidebar_icon_keys_count(self):
        """There should be exactly 14 sidebar icon keys (one per page)."""
        from ui.icons import SIDEBAR_ICON_KEYS
        assert len(SIDEBAR_ICON_KEYS) == 14

    def test_sidebar_icon_keys_exist_in_registry(self):
        """All sidebar icon keys should exist in the ICONS dict."""
        from ui.icons import SIDEBAR_ICON_KEYS, ICONS
        for key in SIDEBAR_ICON_KEYS:
            assert key in ICONS, f"Sidebar icon key '{key}' not in ICONS registry"

    def test_fallback_icon_is_valid(self):
        """The fallback icon should be a valid mdi6 name."""
        from ui.icons import _FALLBACK
        assert _FALLBACK.startswith("mdi6.")

    def test_no_emojis_in_icon_values(self):
        """No ICONS values should contain emoji characters."""
        from ui.icons import ICONS
        import re
        emoji_pattern = re.compile(
            "[\U0001F300-\U0001F9FF\U00002600-\U000026FF\U00002700-\U000027BF]"
        )
        for key, val in ICONS.items():
            assert not emoji_pattern.search(val), (
                f"Icon '{key}' value '{val}' contains emoji characters"
            )

    def test_all_sidebar_keys_have_sidebar_prefix(self):
        """All sidebar icon keys should start with 'sidebar_'."""
        from ui.icons import SIDEBAR_ICON_KEYS
        for key in SIDEBAR_ICON_KEYS:
            assert key.startswith("sidebar_"), f"Key '{key}' missing 'sidebar_' prefix"

    def test_toast_icons_exist(self):
        """Toast notification icons should all be in the registry."""
        from ui.icons import ICONS
        for variant in ("success", "error", "warning", "info", "close"):
            key = f"toast_{variant}"
            assert key in ICONS, f"Toast icon '{key}' not in ICONS"

    def test_chat_icons_exist(self):
        """Chat panel icons should all be in the registry."""
        from ui.icons import ICONS
        for suffix in ("action", "title", "close", "send", "confirm", "cancel"):
            key = f"chat_{suffix}"
            assert key in ICONS, f"Chat icon '{key}' not in ICONS"

    def test_empty_state_icons_exist(self):
        """Empty state icons should all be in the registry."""
        from ui.icons import ICONS
        for suffix in ("default", "dashboard", "hunter", "fleet", "kanban", "history", "outreach"):
            key = f"empty_{suffix}"
            assert key in ICONS, f"Empty state icon '{key}' not in ICONS"

    def test_icon_count_minimum(self):
        """Registry should have at least 50 icons."""
        from ui.icons import ICONS
        assert len(ICONS) >= 50, f"Only {len(ICONS)} icons, expected at least 50"
