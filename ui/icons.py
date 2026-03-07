"""
Aura -- Icon Registry
Central mapping of all icons using qtawesome (Material Design Icons 6.x).
Theme-aware icon creation with dark/light color support.
"""

import qtawesome as qta
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap


# -- Theme Color Tokens -------------------------------------------------------

ICON_COLORS = {
    "dark": {
        "default": "#FFFFFF",
        "muted": "rgba(255,255,255,0.45)",
        "accent": "#4E5BF2",
        "success": "#22C55E",
        "warning": "#F59E0B",
        "danger": "#EF4444",
        "info": "#818CF8",
    },
    "light": {
        "default": "#1D1D1F",
        "muted": "#6E6E73",
        "accent": "#4E5BF2",
        "success": "#34C759",
        "warning": "#FF9500",
        "danger": "#FF3B30",
        "info": "#6366F1",
    },
}


# -- Master Icon Name Registry ------------------------------------------------

ICONS = {
    # Sidebar navigation (12 pages)
    "sidebar_dashboard":     "mdi6.view-dashboard-outline",
    "sidebar_hunter":        "mdi6.magnify",
    "sidebar_forge":         "mdi6.hammer-wrench",
    "sidebar_outreach":      "mdi6.email-arrow-right-outline",
    "sidebar_fleet":         "mdi6.robot-outline",
    "sidebar_kanban":        "mdi6.view-column-outline",
    "sidebar_history":       "mdi6.history",
    "sidebar_trends":        "mdi6.trending-up",
    "sidebar_budget":        "mdi6.currency-usd",
    "sidebar_integrations":  "mdi6.link-variant",
    "sidebar_settings":      "mdi6.cog-outline",
    "sidebar_suppression":   "mdi6.cancel",
    "sidebar_research":      "mdi6.flask-outline",
    "sidebar_calls":         "mdi6.phone-outline",

    # Logo / brand
    "logo_mark":             "mdi6.star-four-points",

    # Chat panel
    "chat_toggle":           "mdi6.chat-outline",
    "chat_action":           "mdi6.flash-outline",
    "chat_title":            "mdi6.star-four-points",
    "chat_close":            "mdi6.close",
    "chat_send":             "mdi6.arrow-up",
    "chat_confirm":          "mdi6.check",
    "chat_cancel":           "mdi6.close",

    # Masked input
    "eye_visible":           "mdi6.eye-outline",
    "eye_hidden":            "mdi6.lock-outline",

    # Empty states
    "empty_default":         "mdi6.inbox-outline",
    "empty_dashboard":       "mdi6.chart-bar",
    "empty_hunter":          "mdi6.target",
    "empty_fleet":           "mdi6.robot-outline",
    "empty_kanban":          "mdi6.clipboard-text-outline",
    "empty_history":         "mdi6.history",
    "empty_outreach":        "mdi6.email-outline",

    # Toast notifications
    "toast_success":         "mdi6.check-circle-outline",
    "toast_error":           "mdi6.close-circle-outline",
    "toast_warning":         "mdi6.alert-outline",
    "toast_info":            "mdi6.information-outline",
    "toast_close":           "mdi6.close",

    # Dashboard
    "export_pdf":            "mdi6.file-pdf-box",
    "export_csv":            "mdi6.file-delimited-outline",
    "ab_test":               "mdi6.flash-outline",
    "variant_marker":        "mdi6.circle-small",

    # Forge
    "warning":               "mdi6.alert-outline",
    "skill_builtin":         "mdi6.lock-outline",
    "skill_custom":          "mdi6.pencil-outline",

    # Hunter
    "batch_import":          "mdi6.folder-upload-outline",
    "apollo_search":         "mdi6.rocket-launch-outline",

    # Outreach
    "generate":              "mdi6.star-four-points",
    "send_email":            "mdi6.email-fast-outline",
    "tab_compose":           "mdi6.email-edit-outline",
    "tab_sequences":         "mdi6.repeat",
    "tab_replies":           "mdi6.email-arrow-left-outline",
    "tab_scheduled":         "mdi6.clock-outline",
    "tab_channels":          "mdi6.bullhorn-outline",

    # Fleet
    "current_task":          "mdi6.flash-outline",

    # Settings sections
    "section_keys":          "mdi6.key-outline",
    "section_auth":          "mdi6.shield-lock-outline",
    "section_subscription":  "mdi6.link-variant",
    "section_models":        "mdi6.brain",
    "section_sender":        "mdi6.email-outline",
    "section_smtp":          "mdi6.server-network",
    "section_appearance":    "mdi6.palette-outline",
    "section_imap":          "mdi6.email-arrow-left-outline",
    "section_toggles":       "mdi6.toggle-switch-outline",
    "section_autonomy":      "mdi6.robot-outline",
    "section_ai":            "mdi6.brain",

    # Suppression
    "refresh":               "mdi6.refresh",
    "delete":                "mdi6.trash-can-outline",
    "import_csv":            "mdi6.file-import-outline",

    # Navigation / expand-collapse
    "chevron_right":         "mdi6.chevron-right",
    "chevron_down":          "mdi6.chevron-down",
    "chevron_left":          "mdi6.chevron-left",

    # Integrations
    "telegram":              "mdi6.send",
    "discord":               "mdi6.controller-classic",

    # Main window
    "error_chat":            "mdi6.alert-outline",

    # Setup wizard
    "wizard_welcome":        "mdi6.star-four-points",
    "wizard_done":           "mdi6.check-decagram",
    "wizard_success":        "mdi6.check-circle-outline",
    "wizard_failure":        "mdi6.alert-circle-outline",
}

# Fallback icon for unknown keys
_FALLBACK = "mdi6.help-circle-outline"


def get_icon(name: str, theme: str = "dark",
             color_key: str = "default") -> QIcon:
    """Return a QIcon for the given registry key."""
    icon_name = ICONS.get(name, _FALLBACK)
    color = ICON_COLORS.get(theme, ICON_COLORS["dark"]).get(
        color_key, "#FFFFFF"
    )
    return qta.icon(icon_name, color=color)


def get_pixmap(name: str, theme: str = "dark",
               color_key: str = "default", size: int = 24) -> QPixmap:
    """Return a QPixmap for use with QLabel.setPixmap()."""
    icon = get_icon(name, theme, color_key)
    return icon.pixmap(QSize(size, size))


# -- Sidebar convenience ------------------------------------------------------

SIDEBAR_ICON_KEYS = [
    "sidebar_dashboard", "sidebar_hunter", "sidebar_forge",
    "sidebar_outreach", "sidebar_fleet", "sidebar_kanban",
    "sidebar_history", "sidebar_trends", "sidebar_budget",
    "sidebar_integrations", "sidebar_settings", "sidebar_suppression",
    "sidebar_research", "sidebar_calls",
]
