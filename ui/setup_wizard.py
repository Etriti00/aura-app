"""
Aura — First-Run Setup Wizard
Modal dialog that guides the user through initial setup:
1. Welcome
2. Browser Installation (Playwright)
3. API Key Entry
4. Model Selection
5. Done
"""

import os
import sys

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QStackedWidget, QWidget,
    QLabel, QProgressBar, QComboBox, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QProcess

from ui.components.modern_button import ModernButton
from ui.components.masked_input import MaskedInput
from ui.icons import get_pixmap
from config import DEFAULT_TIER2_MODEL, DEFAULT_TIER3_MODEL, APP_NAME


class SetupWizard(QDialog):
    """
    First-run wizard that installs Playwright browsers and collects
    initial API key configuration.
    """

    def __init__(self, db_manager, key_vault, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.key_vault = key_vault
        self._process = None
        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        self.setWindowTitle(f"{APP_NAME} — Setup")
        self.setFixedSize(600, 520)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint
        )
        self.setModal(True)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()

        # Build all wizard steps
        self.stack.addWidget(self._build_welcome_page())
        self.stack.addWidget(self._build_browser_page())
        self.stack.addWidget(self._build_api_key_page())
        self.stack.addWidget(self._build_model_page())
        self.stack.addWidget(self._build_done_page())

        layout.addWidget(self.stack)

    # ─── Page 1: Welcome ───────────────────────────────────────────────

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("wizardPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)

        layout.addStretch()

        icon = QLabel()
        icon.setPixmap(get_pixmap("wizard_welcome", "dark", "accent", 48))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setObjectName("wizardIcon")
        layout.addWidget(icon)

        title = QLabel(f"Welcome to {APP_NAME}")
        title.setObjectName("wizardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(
            "Your local AI sales agent.\n"
            "Let's get you set up in just a few steps."
        )
        subtitle.setObjectName("wizardSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addStretch()

        btn = ModernButton("Get Started", "primary")
        btn.setFixedHeight(44)
        btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        layout.addWidget(btn)

        # Skip Setup Link
        skip_link = ModernButton("Skip Setup", "secondary")
        skip_link.setObjectName("wizardSkipLink")
        skip_link.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_link.clicked.connect(self._skip_setup)
        layout.addWidget(skip_link, alignment=Qt.AlignmentFlag.AlignCenter)

        return page

    # ─── Page 2: Browser Installation ──────────────────────────────────

    def _build_browser_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("wizardPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)

        title = QLabel("Browser Engine")
        title.setObjectName("wizardTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Aura needs to install a browser engine to power its web research.\n"
            "This is a one-time download (~150MB)."
        )
        subtitle.setObjectName("wizardSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addStretch()

        self.browser_progress = QProgressBar()
        self.browser_progress.setRange(0, 0)  # Indeterminate initially
        self.browser_progress.setVisible(False)
        layout.addWidget(self.browser_progress)

        self.browser_status = QLabel("")
        self.browser_status.setObjectName("sectionSubheader")
        self.browser_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.browser_status)

        layout.addStretch()

        btn_layout = QHBoxLayout()

        self.skip_browser_btn = ModernButton("Skip", "secondary")
        self.skip_browser_btn.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        btn_layout.addWidget(self.skip_browser_btn)

        self.install_browser_btn = ModernButton("Install Browser", "primary")
        self.install_browser_btn.setFixedHeight(44)
        self.install_browser_btn.clicked.connect(self._install_browser)
        btn_layout.addWidget(self.install_browser_btn)

        layout.addLayout(btn_layout)

        # Skip Setup Link
        skip_link = ModernButton("Skip Setup Entirely", "secondary")
        skip_link.setObjectName("wizardSkipLink")
        skip_link.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_link.clicked.connect(self._skip_setup)
        layout.addWidget(skip_link, alignment=Qt.AlignmentFlag.AlignCenter)

        return page

    def _install_browser(self):
        """Run playwright install chromium as a subprocess."""
        self.install_browser_btn.setEnabled(False)
        self.skip_browser_btn.setEnabled(False)
        self.browser_progress.setVisible(True)
        self.browser_status.setText("Installing Chromium browser... This may take a minute.")

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.finished.connect(self._on_browser_install_finished)
        self._process.readyReadStandardOutput.connect(self._on_browser_output)

        # Run: Aura.exe --install-browser (frozen) or python main.py --install-browser (dev)
        if getattr(sys, 'frozen', False):
            self._process.start(sys.executable, ["--install-browser"])
        else:
            self._process.start(sys.executable, [os.path.abspath(sys.argv[0]), "--install-browser"])

    def _on_browser_output(self):
        if self._process:
            output = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
            # Show last line of output
            lines = output.strip().split("\n")
            if lines:
                self.browser_status.setText(lines[-1][:80])

    def _on_browser_install_finished(self, exit_code, exit_status):
        self.browser_progress.setVisible(False)
        if exit_code == 0:
            self.browser_status.setText("Browser installed successfully!")
            self.browser_status.setObjectName("statusTextSuccess")
            self.browser_status.style().unpolish(self.browser_status)
            self.browser_status.style().polish(self.browser_status)
        else:
            self.browser_status.setText("Installation failed. You can install later from Settings.")
            self.browser_status.setObjectName("warningText")
            self.browser_status.style().unpolish(self.browser_status)
            self.browser_status.style().polish(self.browser_status)

        # Auto-advance after a short delay
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.stack.setCurrentIndex(2))

    # ─── Page 3: API Key Entry ─────────────────────────────────────────

    def _build_api_key_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("wizardPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)

        title = QLabel("API Keys")
        title.setObjectName("wizardTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Enter at least one AI provider key to enable intelligence.\n"
            "Your keys are encrypted and stored locally — never sent anywhere."
        )
        subtitle.setObjectName("wizardSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Gemini
        gemini_label = QLabel("Google Gemini API Key")
        gemini_label.setObjectName("formLabel")
        layout.addWidget(gemini_label)
        self.gemini_input = MaskedInput("Enter Gemini API key...")
        layout.addWidget(self.gemini_input)

        layout.addSpacing(4)

        # Anthropic
        anthropic_label = QLabel("Anthropic API Key (optional)")
        anthropic_label.setObjectName("formLabel")
        layout.addWidget(anthropic_label)
        self.anthropic_input = MaskedInput("Enter Anthropic API key...")
        layout.addWidget(self.anthropic_input)

        layout.addSpacing(4)

        # OpenAI
        openai_label = QLabel("OpenAI API Key (optional)")
        openai_label.setObjectName("formLabel")
        layout.addWidget(openai_label)
        self.openai_input = MaskedInput("Enter OpenAI API key...")
        layout.addWidget(self.openai_input)

        layout.addSpacing(4)

        # OpenRouter
        openrouter_label = QLabel("OpenRouter API Key (optional — one key for all models)")
        openrouter_label.setObjectName("formLabel")
        layout.addWidget(openrouter_label)
        self.openrouter_input = MaskedInput("Enter OpenRouter API key...")
        layout.addWidget(self.openrouter_input)

        layout.addStretch()

        btn = ModernButton("Continue", "primary")
        btn.setFixedHeight(44)
        btn.clicked.connect(self._save_api_keys)
        layout.addWidget(btn)

        # Skip Setup Link
        skip_link = ModernButton("Skip Setup", "secondary")
        skip_link.setObjectName("wizardSkipLink")
        skip_link.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_link.clicked.connect(self._skip_setup)
        layout.addWidget(skip_link, alignment=Qt.AlignmentFlag.AlignCenter)

        return page

    def _save_api_keys(self):
        """Encrypt and save API keys to the database."""
        gemini_key = self.gemini_input.get_value()
        anthropic_key = self.anthropic_input.get_value()
        openai_key = self.openai_input.get_value()
        openrouter_key = self.openrouter_input.get_value()

        if not any([gemini_key, anthropic_key, openai_key, openrouter_key]):
            from ui.components.toast_notification import show_toast
            show_toast(self, "Please enter at least one API key, or click 'Skip Setup'.",
                       toast_type="warning", duration=4000)
            return

        with self.db_manager.session_scope() as session:
            from database.schema import Settings
            settings = session.query(Settings).first()
            if settings:
                if gemini_key:
                    settings.gemini_key_enc = self.key_vault.encrypt(gemini_key)
                if anthropic_key:
                    settings.anthropic_key_enc = self.key_vault.encrypt(anthropic_key)
                if openai_key:
                    settings.openai_key_enc = self.key_vault.encrypt(openai_key)
                if openrouter_key:
                    settings.openrouter_key_enc = self.key_vault.encrypt(openrouter_key)

        self.stack.setCurrentIndex(3)

    # ─── Page 4: Model Selection ───────────────────────────────────────

    def _build_model_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("wizardPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)

        title = QLabel("AI Model Selection")
        title.setObjectName("wizardTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Choose which AI models to use for each tier.\n"
            "Tier 2 (cheap) qualifies leads. Tier 3 (premium) writes emails."
        )
        subtitle.setObjectName("wizardSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        # Tier 2
        t2_label = QLabel("Tier 2 — Lead Qualification (Low Cost)")
        t2_label.setObjectName("formLabel")
        layout.addWidget(t2_label)

        self.tier2_combo = QComboBox()
        self.tier2_combo.addItems([
            "gemini/gemini-2.0-flash",
            "gemini/gemini-2.5-flash-preview-09-2025",
            "openai/gpt-4.1-mini",
            "openai/gpt-4.1-nano",
            "openai/gpt-4o-mini",
            "anthropic/claude-haiku-4-5",
            "openrouter/google/gemini-2.0-flash",
            "openrouter/openai/gpt-4.1-mini",
            "ollama/llama3",
            "ollama/mistral",
        ])
        self.tier2_combo.setCurrentText(DEFAULT_TIER2_MODEL)
        layout.addWidget(self.tier2_combo)

        layout.addSpacing(12)

        # Tier 3
        t3_label = QLabel("Tier 3 — Email Generation (Premium)")
        t3_label.setObjectName("formLabel")
        layout.addWidget(t3_label)

        self.tier3_combo = QComboBox()
        self.tier3_combo.addItems([
            "anthropic/claude-sonnet-4-6",
            "openai/gpt-4.1",
            "openai/gpt-4o",
            "gemini/gemini-2.5-pro-preview",
            "gemini/gemini-1.5-pro-latest",
            "openrouter/openai/gpt-4.1",
            "openrouter/auto",
            "ollama/llama3:70b",
        ])
        self.tier3_combo.setCurrentText(DEFAULT_TIER3_MODEL)
        layout.addWidget(self.tier3_combo)

        layout.addStretch()

        btn = ModernButton("Continue", "primary")
        btn.setFixedHeight(44)
        btn.clicked.connect(self._save_models)
        layout.addWidget(btn)

        # Skip Setup Link
        skip_link = ModernButton("Skip Setup", "secondary")
        skip_link.setObjectName("wizardSkipLink")
        skip_link.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_link.clicked.connect(self._skip_setup)
        layout.addWidget(skip_link, alignment=Qt.AlignmentFlag.AlignCenter)

        return page

    def _save_models(self):
        """Save model selections to database."""
        with self.db_manager.session_scope() as session:
            from database.schema import Settings
            settings = session.query(Settings).first()
            if settings:
                settings.tier2_model = self.tier2_combo.currentText()
                settings.tier3_model = self.tier3_combo.currentText()

        self.stack.setCurrentIndex(4)

    # ─── Page 5: Done ──────────────────────────────────────────────────

    def _build_done_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("wizardPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)

        layout.addStretch()

        icon = QLabel()
        icon.setPixmap(get_pixmap("wizard_done", "dark", "success", 48))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setObjectName("wizardIcon")
        layout.addWidget(icon)

        title = QLabel("You're all set!")
        title.setObjectName("wizardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(
            "Aura is configured and ready to go.\n"
            "You can always change these settings later."
        )
        subtitle.setObjectName("wizardSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addStretch()

        btn = ModernButton("Open Aura", "primary")
        btn.setFixedHeight(44)
        btn.clicked.connect(self._finish_setup)
        layout.addWidget(btn)

        return page

    def _finish_setup(self):
        """Mark first run complete and close wizard."""
        with self.db_manager.session_scope() as session:
            from database.schema import Settings
            settings = session.query(Settings).first()
            if settings:
                settings.first_run_complete = True

        self.accept()

    def _skip_setup(self):
        """Skip the rest of the wizard and enter the app."""
        self._finish_setup()
