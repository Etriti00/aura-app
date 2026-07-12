"""
Aura — Main Entry Point
Initializes the application, database, and launches either the setup wizard
or the main window depending on first_run_complete status.
"""

import sys
import os

# Ensure the app directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtCore import Qt

from config import APP_NAME, FONTS_DIR
from database.db_manager import DatabaseManager
from core.key_vault import KeyVault
from utils.logger import get_logger

logger = get_logger("main")


def load_fonts():
    """Load custom fonts from the assets directory."""
    if FONTS_DIR.exists():
        for font_file in FONTS_DIR.glob("*.ttf"):
            font_id = QFontDatabase.addApplicationFont(str(font_file))
            if font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(font_id)
                logger.debug(f"Loaded font: {families}")
            else:
                logger.warning(f"Failed to load font: {font_file}")


def main():
    """Application entry point."""
    # Enable high-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Windows: register an explicit AppUserModelID before any window is
    # created so the taskbar shows the Aura icon and groups under Aura
    # instead of inheriting the host python.exe icon.
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Etriti.Aura.SalesAgent"
            )
        except Exception:
            pass

    app = QApplication(sys.argv)

    # Application icon (taskbar, dock, window chrome, alt-tab). Prefer the
    # platform-native icon so every OS taskbar renders the real logo.
    from PySide6.QtGui import QIcon
    _icons_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "assets", "icons"
    )
    if sys.platform == "darwin":
        _icon_file = "aura_icon.icns"
    elif sys.platform.startswith("win"):
        _icon_file = "aura_icon.ico"
    else:
        _icon_file = "aura_icon.png"
    _icon_path = os.path.join(_icons_dir, _icon_file)
    if not os.path.exists(_icon_path):
        _icon_path = os.path.join(_icons_dir, "aura_icon.png")
    if os.path.exists(_icon_path):
        app.setWindowIcon(QIcon(_icon_path))
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName("aura")
    app.setStyle("Fusion")  # Consistent cross-platform base style

    # Load custom fonts
    load_fonts()

    # Set default font
    default_font = QFont("Inter", 10)
    default_font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(default_font)

    # Initialize database
    logger.info(f"Starting {APP_NAME}...")
    db_manager = DatabaseManager()
    db_manager.init_db()
    db_manager.migrate_schema()
    db_manager.seed_defaults()
    db_manager.seed_default_agents()
    logger.info("Database initialized.")

    # Initialize key vault
    key_vault = KeyVault()

    # Migrate any keys still encrypted with the legacy salt
    _settings_for_migration = db_manager.get_settings()
    if _settings_for_migration:
        _enc_fields = [f for f in dir(_settings_for_migration) if f.endswith("_enc") and getattr(_settings_for_migration, f, None)]
        _migrated = False
        for _field in _enc_fields:
            _old_ct = getattr(_settings_for_migration, _field)
            _new_ct = key_vault.migrate_ciphertext(_old_ct)
            if _new_ct:
                from database.schema import Settings
                with db_manager.session_scope() as session:
                    s = session.query(Settings).first()
                    setattr(s, _field, _new_ct)
                _migrated = True
        if _migrated:
            logger.info("Migrated encrypted keys to new per-install salt")

    # Detect hardware change (all encrypted keys fail to decrypt)
    _hardware_change = False
    _settings_check = db_manager.get_settings()
    if _settings_check:
        _enc_fields_check = [f for f in dir(_settings_check) if f.endswith("_enc") and getattr(_settings_check, f, None)]
        if _enc_fields_check:
            _all_failed = all(
                not key_vault.decrypt(getattr(_settings_check, f))
                for f in _enc_fields_check
            )
            if _all_failed:
                logger.warning("All encrypted keys failed to decrypt — possible hardware change")
                _hardware_change = True

    # Check first-run status
    settings = db_manager.get_settings()

    if settings and not settings.first_run_complete:
        # Show setup wizard
        logger.info("First run detected — launching setup wizard.")
        from ui.setup_wizard import SetupWizard
        wizard = SetupWizard(db_manager, key_vault)
        result = wizard.exec()
        if result != SetupWizard.DialogCode.Accepted:
            # User closed wizard without finishing — exit app
            logger.info("Setup wizard cancelled. Exiting.")
            sys.exit(0)

    # Determine theme
    settings = db_manager.get_settings()
    # Aura ships a single dark interface; the light theme was removed.
    theme = "dark"

    # Launch main window
    from ui.main_window import MainWindow
    window = MainWindow(db_manager=db_manager, key_vault=key_vault)

    # Real Liquid Glass on Windows 11: blur the desktop behind the window and
    # tint it. Qt's backing store must be transparent for the blur to show.
    # The "acrylic" property lets the stylesheet swap the opaque gradient for
    # a see-through tint.
    try:
        from ui.win_effects import enable_acrylic_accent, enable_dark_chrome

        hwnd = int(window.winId())
        enable_dark_chrome(hwnd)  # dark title bar + rounded corners
        if enable_acrylic_accent(hwnd):
            window.setProperty("acrylic", "true")
    except Exception:
        pass

    window._apply_theme(theme)
    window.show()
    logger.info("Main window launched.")

    # Dev aid: live theme reload when AURA_THEME_WATCH=1 saves a QSS file and
    # re-applies the theme in the running window.
    if os.environ.get("AURA_THEME_WATCH"):
        from PySide6.QtCore import QFileSystemWatcher
        from config import THEMES_DIR
        _theme_files = [
            str(THEMES_DIR / "neon_dark.qss"),
        ]
        _watcher = QFileSystemWatcher(_theme_files)

        def _reload_theme(_path):
            try:
                window._apply_theme(theme)
            except Exception as _e:
                logger.warning("Theme reload failed: %s", _e)
            for _f in _theme_files:
                if _f not in _watcher.files():
                    _watcher.addPath(_f)

        _watcher.fileChanged.connect(_reload_theme)
        window._theme_watcher = _watcher
        logger.info("Theme hot-reload enabled.")

    if _hardware_change:
        from ui.components.toast_notification import show_toast
        show_toast(
            window,
            "Hardware change detected. Your API keys could not be decrypted. "
            "Please re-enter them in Settings → API Keys.",
            toast_type="warning",
            duration=8000,
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    # Handle browser installation subprocess for frozen app
    if "--install-browser" in sys.argv:
        try:
            from playwright.__main__ import main as pw_main
            sys.argv = [sys.argv[0], "install", "chromium"]
            pw_main()
        except SystemExit:
            pass
        except Exception as e:
            print(f"Failed to install browser: {e}")
        sys.exit(0)

    main()
