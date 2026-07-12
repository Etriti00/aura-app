"""
Aura — Native window effects (Windows 11)
Real acrylic blur-behind plus dark title bar and rounded corners, via
ctypes — no third party dependency.

The blur comes from SetWindowCompositionAttribute with an acrylic accent
policy; the window keeps a translucent Qt backing store so the compositor
blurs the desktop behind it and the QSS layers tint on top. Note that the
newer DWM system backdrop (attribute 38) must NOT be combined with the
accent policy — the two fight and the window renders opaque.

Anywhere else these calls are harmless no-ops and the QSS gradient stands in.
"""

import sys

from utils.logger import get_logger

logger = get_logger("win_effects")

# DWM window attributes
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_WINDOW_CORNER_PREFERENCE = 33


def apply_sheet_glass(widget) -> bool:
    """Give a dialog the same acrylic treatment as the main window.

    Call early in __init__, before the native window exists. Returns True
    when the acrylic accent is active; the widget then carries the
    "acrylic" stylesheet property so QSS can swap to a translucent fill.
    """
    import os
    if not sys.platform.startswith("win") or os.environ.get("AURA_DISABLE_GLASS"):
        return False
    try:
        from PySide6.QtCore import Qt

        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        hwnd = int(widget.winId())
        enable_dark_chrome(hwnd)
        if enable_acrylic_accent(hwnd):
            widget.setProperty("acrylic", "true")
            return True
    except Exception as e:
        logger.warning("Sheet glass unavailable: %s", e)
    return False


def enable_acrylic_accent(hwnd: int, tint_abgr: int = 0xB3120E0E) -> bool:
    """
    Blur-behind via SetWindowCompositionAttribute (ACCENT_ENABLE_ACRYLICBLURBEHIND).
    This is the reliable recipe for Qt windows with WA_TranslucentBackground:
    the compositor blurs the desktop and blends the given ABGR tint over it.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_uint),
                ("AccentFlags", ctypes.c_uint),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_uint),
            ]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t),
            ]

        accent = ACCENT_POLICY()
        accent.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 2  # draw all borders
        accent.GradientColor = tint_abgr

        data = WINCOMPATTRDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(accent)

        set_wca = ctypes.windll.user32.SetWindowCompositionAttribute
        ok = bool(set_wca(ctypes.c_void_p(hwnd), ctypes.byref(data)))
        if ok:
            logger.info("Acrylic accent enabled")
        else:
            logger.info("Acrylic accent rejected")
        return ok
    except Exception as e:
        logger.warning("Acrylic accent unavailable: %s", e)
        return False
def set_titlebar_dark(hwnd: int, dark: bool = True) -> None:
    """Switch the native title bar between dark and light chrome so it
    matches the active theme."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        from ctypes import wintypes
        dwm = ctypes.windll.dwmapi
        val = ctypes.c_int(1 if dark else 0)
        dwm.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), _DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(val), ctypes.sizeof(val),
        )
    except Exception as e:
        logger.warning("Title bar theme unavailable: %s", e)


def enable_dark_chrome(hwnd: int) -> None:
    """Dark title bar and rounded corners only, with no system backdrop.

    The DWM system backdrop (attr 38) and DwmExtendFrameIntoClientArea both
    fight the SetWindowCompositionAttribute acrylic blur, so the blur path
    uses this lighter helper for the window chrome instead.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        from ctypes import wintypes

        dwm = ctypes.windll.dwmapi
        h = wintypes.HWND(hwnd)

        def _set(attr: int, value: int) -> None:
            data = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(h, attr, ctypes.byref(data), ctypes.sizeof(data))

        _set(_DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
        _set(_DWMWA_WINDOW_CORNER_PREFERENCE, 2)  # DWMWCP_ROUND
    except Exception as e:
        logger.warning("Dark chrome unavailable: %s", e)

