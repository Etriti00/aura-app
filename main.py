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

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
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
    theme = settings.theme if settings else "light"

    # Launch main window
    from ui.main_window import MainWindow
    window = MainWindow(db_manager=db_manager, key_vault=key_vault)
    window._apply_theme(theme)
    window.show()
    logger.info("Main window launched.")

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
