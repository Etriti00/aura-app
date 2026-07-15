"""
Aura — Liquid Glass dispatch
One entry point per concern, routed to the platform module that owns it:
win_effects (Windows 11 acrylic), mac_effects (NSVisualEffectView), or
linux_effects (KDE blur hint). Every path degrades to False, in which case
the QSS gradient stands in and nothing else changes.
"""

import os
import sys


def wants_translucent_backing() -> bool:
    """Must the window use a translucent Qt backing store?

    Decided before the native window exists — the attribute cannot be
    changed afterwards. True wherever a compositor blur can be requested.
    """
    if os.environ.get("AURA_DISABLE_GLASS"):
        return False
    if sys.platform.startswith("win"):
        return True
    if sys.platform == "darwin":
        from ui import mac_effects
        return mac_effects.glass_available()
    if sys.platform.startswith("linux"):
        from ui import linux_effects
        return linux_effects.glass_available()
    return False


def apply_main_window_glass(window) -> bool:
    """Enable the native backdrop for the main window. Returns True when
    active, and the caller flips the "acrylic" QSS property."""
    try:
        if sys.platform.startswith("win"):
            from ui.win_effects import enable_acrylic_accent, enable_dark_chrome
            hwnd = int(window.winId())
            enable_dark_chrome(hwnd)  # dark titlebar even if the blur is refused
            return enable_acrylic_accent(hwnd)
        if sys.platform == "darwin":
            from ui import mac_effects
            return mac_effects.apply_window_glass(window)
        if sys.platform.startswith("linux"):
            from ui import linux_effects
            return linux_effects.apply_window_glass(window)
    except Exception:
        pass
    return False
