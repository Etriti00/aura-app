"""
Aura — Native window effects (Linux)
Blur-behind on KDE Plasma via the _KDE_NET_WM_BLUR_BEHIND_REGION X11
property, which KWin honors for the whole window when the region is empty.
KDE is the one Linux compositor with a stable public blur contract; on
GNOME and others there is none, so the QSS gradient stands in unchanged.

ctypes + libX11 only — no third party dependency, mirroring win_effects.py.
"""

import ctypes
import ctypes.util
import os
import sys

from utils.logger import get_logger

logger = get_logger("linux_effects")

_XA_CARDINAL = 6
_PROP_MODE_REPLACE = 0


def glass_available() -> bool:
    """True on a KDE X11 session where KWin will blur behind the window."""
    if not sys.platform.startswith("linux") or os.environ.get("AURA_DISABLE_GLASS"):
        return False
    try:
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.platformName() != "xcb":
            return False  # Wayland has no public blur protocol to ask for
    except Exception:
        return False
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    return "KDE" in desktop


def apply_window_glass(window) -> bool:
    """Ask KWin to blur behind the window. Returns True when the hint is set;
    the caller then flips the "acrylic" QSS property, exactly like Windows."""
    if not glass_available():
        return False
    try:
        libx11 = ctypes.util.find_library("X11")
        if not libx11:
            return False
        x11 = ctypes.CDLL(libx11)
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]

        display = x11.XOpenDisplay(None)
        if not display:
            return False
        try:
            atom = x11.XInternAtom(display, b"_KDE_NET_WM_BLUR_BEHIND_REGION", 0)
            # Empty region: KWin blurs the entire window.
            x11.XChangeProperty(
                ctypes.c_void_p(display), ctypes.c_ulong(int(window.winId())),
                ctypes.c_ulong(atom), ctypes.c_ulong(_XA_CARDINAL), 32,
                _PROP_MODE_REPLACE, None, 0,
            )
            x11.XFlush(ctypes.c_void_p(display))
        finally:
            x11.XCloseDisplay(ctypes.c_void_p(display))
        logger.info("KDE blur-behind hint set")
        return True
    except Exception as e:
        logger.warning("Linux glass unavailable: %s", e)
        return False
