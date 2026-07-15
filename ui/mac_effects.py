"""
Aura — Native window effects (macOS)
Real Liquid Glass: an NSVisualEffectView with behind-window blending sits
under the Qt content, so macOS blurs the desktop behind the window and the
QSS acrylic tints layer on top — the same recipe win_effects.py uses on
Windows 11, built from the material Apple's own sidebars and toolbars use.

The window chrome goes full-bleed (transparent titlebar, content under it,
hidden title) for the seamless Tahoe look. That costs titlebar-drag, which
MainWindow restores with startSystemMove() on its top bar and sidebar logo.

Requires pyobjc-framework-Cocoa; anywhere it is missing these calls are
harmless no-ops and the QSS gradient stands in.
"""

import os
import sys

from utils.logger import get_logger

logger = get_logger("mac_effects")

# NSVisualEffectView constants (AppKit numeric values, stable since 10.14)
_MATERIAL_UNDER_WINDOW = 21   # underWindowBackground: desktop show-through
_MATERIAL_HUD = 13            # hudWindow: darker, denser glass (fallback tuning)
_BLEND_BEHIND_WINDOW = 0
_STATE_ACTIVE = 1             # keep the blur when the window loses key
_AUTORESIZE_WH = 18           # NSViewWidthSizable | NSViewHeightSizable
_MASK_FULL_SIZE_CONTENT = 1 << 15
_TITLE_HIDDEN = 1

_TOOLBAR_STYLE_UNIFIED = 3    # NSWindowToolbarStyleUnified

# Darkness of the native tint layer between the blur and the Qt content.
# Balanced so the desktop blur genuinely shows through (liquid glass, not a
# black slab) while text stays readable; the QSS layers add local depth.
_TINT_ALPHA_WINDOW = 0.52
_TINT_ALPHA_SHEET = 0.70

# Height of the app's own header row under seamless chrome — matches the
# unified-toolbar titlebar so lights, logo and search share one centreline.
HEADER_HEIGHT = 52
# Traffic lights occupy the top-left ~70px; the logo starts to their right
# with clear breathing room so the header reads sleek, not cramped.
TRAFFIC_LIGHT_INSET = 96


def glass_available() -> bool:
    """True when the process can do native macOS glass right now."""
    if sys.platform != "darwin" or os.environ.get("AURA_DISABLE_GLASS"):
        return False
    try:
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.platformName() != "cocoa":
            return False  # offscreen tests have no NSWindow to wrap
        import AppKit  # noqa: F401
        return True
    except Exception as e:
        logger.warning("macOS glass unavailable: %s", e)
        return False


_NS_WINDOW_BELOW = -1


def _wrap_in_effect_view(widget, material: int, tint_alpha: float) -> bool:
    """Slide an NSVisualEffectView + dark tint layer behind the Qt view.

    Both views join the window's frame view as siblings *below* the QNSView,
    so blur then darkness render behind everything Qt paints. Replacing the
    window's contentView instead breaks QCocoaWindow's invariants and the
    window never reaches the screen — verified by bisection on macOS 26.

    The tint is a native CALayer, not a stylesheet fill: QSS backgrounds on
    a translucent QMainWindow do not reliably reach the backing store, and
    the Windows acrylic gets its darkness from the compositor the same way.
    """
    import objc
    from AppKit import NSVisualEffectView, NSView, NSColor

    qt_view = objc.objc_object(c_void_p=int(widget.winId()))
    frame_view = qt_view.superview()
    if frame_view is None:
        return False

    effect = NSVisualEffectView.alloc().initWithFrame_(frame_view.bounds())
    effect.setAutoresizingMask_(_AUTORESIZE_WH)
    effect.setBlendingMode_(_BLEND_BEHIND_WINDOW)
    effect.setMaterial_(material)
    effect.setState_(_STATE_ACTIVE)
    effect.setWantsLayer_(True)

    # The dark tint is a CHILD of the effect view, not a sibling: sibling
    # z-order via addSubview:positioned: proved unreliable (the blur landed
    # on top and the tint did nothing). As a subview it always paints over
    # the blur, darkening it before the Qt content composites on top.
    tint = NSView.alloc().initWithFrame_(effect.bounds())
    tint.setAutoresizingMask_(_AUTORESIZE_WH)
    tint.setWantsLayer_(True)
    tint.layer().setBackgroundColor_(
        NSColor.colorWithCalibratedRed_green_blue_alpha_(
            0.03, 0.03, 0.05, tint_alpha).CGColor())
    effect.addSubview_(tint)

    frame_view.addSubview_positioned_relativeTo_(effect, _NS_WINDOW_BELOW, qt_view)
    return True


def apply_window_glass(window) -> bool:
    """Full Liquid Glass treatment for the main window.

    The widget must already have WA_TranslucentBackground (set before the
    native window exists) or Qt paints an opaque backing store over the blur.
    Returns True when active; the caller then sets the "acrylic" property so
    QSS swaps the opaque gradient for a translucent tint.
    """
    if not glass_available():
        return False
    try:
        import objc
        from AppKit import NSApplication, NSAppearance, NSColor

        # Dark glass regardless of the system setting: Aura ships one theme.
        # App-level, not just window-level — NSVisualEffectView resolves its
        # material against the effective appearance, and on a light-mode Mac
        # a window-only override still leaves the material milky-bright.
        NSApplication.sharedApplication().setAppearance_(
            NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua"))

        qt_view = objc.objc_object(c_void_p=int(window.winId()))
        ns_window = qt_view.window()
        if ns_window is None:
            return False

        ns_window.setAppearance_(
            NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua"))
        ns_window.setOpaque_(False)
        ns_window.setBackgroundColor_(NSColor.clearColor())

        # Seamless chrome: Qt's ExpandedClientAreaHint (set in MainWindow)
        # extends the client area under the titlebar; here we only hide the
        # title text and keep the titlebar transparent. No manual styleMask
        # edits — Qt owns the mask and reverts them on show().
        ns_window.setTitlebarAppearsTransparent_(True)
        ns_window.setTitleVisibility_(_TITLE_HIDDEN)

        if not _wrap_in_effect_view(window, _MATERIAL_UNDER_WINDOW, _TINT_ALPHA_WINDOW):
            return False
        logger.info("macOS Liquid Glass enabled")
        return True
    except Exception as e:
        logger.warning("macOS glass failed: %s", e)
        return False


def reassert_chrome(window) -> bool:
    """Finish the seamless chrome AFTER QWidget.show().

    Qt (ExpandedClientAreaHint) already extends the client area under the
    titlebar. The empty unified toolbar added here makes macOS size that
    titlebar to ~52px with the traffic lights vertically centred, so the
    lights sit on the same centreline as the app's 52px header row.
    """
    if not glass_available():
        return False
    try:
        import objc
        from AppKit import NSToolbar

        qt_view = objc.objc_object(c_void_p=int(window.winId()))
        ns_window = qt_view.window()
        if ns_window is None:
            return False
        if ns_window.toolbar() is None:
            toolbar = NSToolbar.alloc().initWithIdentifier_("aura.unified")
            toolbar.setShowsBaselineSeparator_(False)
            ns_window.setToolbar_(toolbar)
            ns_window.setToolbarStyle_(_TOOLBAR_STYLE_UNIFIED)
        ns_window.setTitlebarAppearsTransparent_(True)
        ns_window.setTitleVisibility_(_TITLE_HIDDEN)
        return True
    except Exception as e:
        logger.warning("chrome reassert failed: %s", e)
        return False


def apply_sheet_glass(widget) -> bool:
    """Glass backdrop for dialogs — same material, standard dialog chrome."""
    if not glass_available():
        return False
    try:
        from PySide6.QtCore import Qt
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        import objc
        from AppKit import NSAppearance, NSColor

        qt_view = objc.objc_object(c_void_p=int(widget.winId()))
        ns_window = qt_view.window()
        if ns_window is None:
            return False
        ns_window.setAppearance_(
            NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua"))
        ns_window.setOpaque_(False)
        ns_window.setBackgroundColor_(NSColor.clearColor())

        if not _wrap_in_effect_view(widget, _MATERIAL_HUD, _TINT_ALPHA_SHEET):
            return False
        widget.setProperty("acrylic", "mac")  # mac-specific QSS tint
        return True
    except Exception as e:
        logger.warning("macOS sheet glass failed: %s", e)
        return False
