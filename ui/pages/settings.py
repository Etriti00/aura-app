"""
Aura — Settings Page (Tabbed Layout)
Seven sub-tabs: API Keys, AI Config, Email & Delivery, Features,
Business & Invoicing, Knowledge Base, Appearance.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QSpinBox, QScrollArea, QFrame, QCheckBox,
    QRadioButton, QButtonGroup, QSizePolicy, QTabWidget,
    QTextEdit, QFileDialog,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon

from ui.components.glass_card import GlassCard
from ui.components.modern_button import ModernButton
from ui.components.masked_input import MaskedInput
from ui.components.toast_notification import show_toast
from ui.icons import get_icon, get_pixmap


class SettingsPage(QWidget):
    """Settings page — tabbed layout with 6 sub-pages."""

    # Signals to controller (preserved from original)
    save_key_requested = Signal(str, str)
    save_models_requested = Signal(str, str)
    save_chat_model_requested = Signal(str)
    save_sender_requested = Signal(str, str, str)
    save_smtp_requested = Signal(str, int, str, str)
    save_imap_requested = Signal(str, int, str, str, bool)
    save_toggles_requested = Signal(dict)
    save_anthropic_sub_requested = Signal(str)
    auth_mode_changed = Signal(str, str)
    autonomy_level_changed = Signal(str)
    save_business_requested = Signal(dict)
    save_kb_entry_requested = Signal(str, str, str)   # category, key, value
    delete_kb_entry_requested = Signal(str, str)       # category, key

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    # ─── Main Layout ──────────────────────────────────────────────────

    def _setup_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(16)

        # Header
        title = QLabel("Settings")
        title.setObjectName("sectionHeader")
        main_layout.addWidget(title)
        subtitle = QLabel("Configure API keys, models, delivery, and business details")
        subtitle.setObjectName("sectionSubheader")
        main_layout.addWidget(subtitle)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        main_layout.addWidget(self.tabs)

        # Build tabs
        self.tabs.addTab(self._build_api_keys_tab(), get_icon("tab_api_keys", "dark"), "API Keys")
        self.tabs.addTab(self._build_ai_config_tab(), get_icon("tab_ai_config", "dark"), "AI Config")
        self.tabs.addTab(self._build_email_tab(), get_icon("tab_email_delivery", "dark"), "Email && Delivery")
        self.tabs.addTab(self._build_features_tab(), get_icon("tab_features", "dark"), "Features")
        self.tabs.addTab(self._build_business_tab(), get_icon("tab_business", "dark"), "Business && Invoicing")
        self.tabs.addTab(self._build_knowledge_base_tab(), get_icon("tab_knowledge_base", "dark"), "Knowledge Base")

    # ─── Tab Builders ─────────────────────────────────────────────────

    @staticmethod
    def _make_scroll_tab(content_widget: QWidget) -> QScrollArea:
        """Wrap a content widget in a QScrollArea for a tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content_widget)
        return scroll

    # ── Tab 1: API Keys ───────────────────────────────────────────────

    def _build_api_keys_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(20)

        # ── API Keys Card ──
        key_card = GlassCard()
        key_layout = key_card.get_layout()
        self._icon_header("section_keys", "API Keys", key_layout)
        key_info = QLabel("Keys are encrypted with hardware-bound encryption and stored locally.")
        key_info.setObjectName("mutedText")
        key_layout.addWidget(key_info)

        self.gemini_input = self._add_key_row(key_layout, "Google Gemini", "gemini")
        self.anthropic_input = self._add_key_row(key_layout, "Anthropic", "anthropic")
        self.openai_input = self._add_key_row(key_layout, "OpenAI", "openai")
        self.resend_input = self._add_key_row(key_layout, "Resend (Email)", "resend")
        self.apollo_input = self._add_key_row(key_layout, "Apollo.io", "apollo")
        self.hunter_input = self._add_key_row(key_layout, "Hunter.io", "hunter")
        self.hubspot_input = self._add_key_row(key_layout, "HubSpot CRM", "hubspot")
        self.pipedrive_input = self._add_key_row(key_layout, "Pipedrive CRM", "pipedrive")
        self.openrouter_input = self._add_key_row(key_layout, "OpenRouter", "openrouter")
        self.tavily_input = self._add_key_row(key_layout, "Tavily (AI Search)", "tavily")
        self.firecrawl_input = self._add_key_row(key_layout, "Firecrawl (Web Crawl)", "firecrawl")
        self.apify_input = self._add_key_row(key_layout, "Apify (Scraping)", "apify")
        self.twilio_sid_input = self._add_key_row(key_layout, "Twilio Account SID", "twilio_sid")
        self.twilio_token_input = self._add_key_row(key_layout, "Twilio Auth Token", "twilio_token")
        self.elevenlabs_input = self._add_key_row(key_layout, "ElevenLabs (TTS)", "elevenlabs")
        self.meta_input = self._add_key_row(key_layout, "Meta (Muse Spark)", "meta")
        self.xai_input = self._add_key_row(key_layout, "xAI (Grok)", "xai")
        self.zai_input = self._add_key_row(key_layout, "Z.ai (GLM)", "zai")
        self.moonshot_input = self._add_key_row(key_layout, "Moonshot (Kimi)", "moonshot")
        self.dashscope_input = self._add_key_row(key_layout, "Alibaba (Qwen)", "dashscope")
        self.minimax_input = self._add_key_row(key_layout, "MiniMax", "minimax")
        self.nvidia_nim_input = self._add_key_row(key_layout, "NVIDIA NIM (Nemotron)", "nvidia_nim")
        or_info = QLabel(
            "Don't have individual API keys? Use OpenRouter for one-key access "
            "to the whole fleet (Grok, GLM, Kimi, Qwen, MiniMax, Nemotron and "
            "more) at openrouter.ai"
        )
        or_info.setObjectName("mutedText")
        or_info.setWordWrap(True)
        key_layout.addWidget(or_info)
        layout.addWidget(key_card)

        # ── Authentication Mode Card ──
        auth_card = GlassCard()
        auth_layout = auth_card.get_layout()
        self._icon_header("section_auth", "Authentication Mode", auth_layout)
        auth_info = QLabel(
            "Select how each provider authenticates. API Key and Subscription "
            "are mutually exclusive — only the selected mode will be used."
        )
        auth_info.setObjectName("mutedText")
        auth_info.setWordWrap(True)
        auth_layout.addWidget(auth_info)

        # Anthropic auth mode
        anthropic_mode_label = QLabel("Anthropic / Claude")
        anthropic_mode_label.setObjectName("formLabel")
        auth_layout.addWidget(anthropic_mode_label)

        anthropic_mode_row = QHBoxLayout()
        self.anthropic_mode_group = QButtonGroup(self)
        self.anthropic_mode_none = QRadioButton("Not Configured")
        self.anthropic_mode_api = QRadioButton("API Key")
        self.anthropic_mode_sub = QRadioButton("Subscription")
        self.anthropic_mode_none.setChecked(True)
        self.anthropic_mode_group.addButton(self.anthropic_mode_none, 0)
        self.anthropic_mode_group.addButton(self.anthropic_mode_api, 1)
        self.anthropic_mode_group.addButton(self.anthropic_mode_sub, 2)
        anthropic_mode_row.addWidget(self.anthropic_mode_none)
        anthropic_mode_row.addWidget(self.anthropic_mode_api)
        anthropic_mode_row.addWidget(self.anthropic_mode_sub)
        anthropic_mode_row.addStretch()
        auth_layout.addLayout(anthropic_mode_row)
        self.anthropic_mode_group.idToggled.connect(
            lambda id, checked: self._on_auth_mode_changed("anthropic", id) if checked else None
        )

        # OpenAI auth mode
        openai_mode_label = QLabel("OpenAI / ChatGPT")
        openai_mode_label.setObjectName("formLabel")
        auth_layout.addWidget(openai_mode_label)

        openai_mode_row = QHBoxLayout()
        self.openai_mode_group = QButtonGroup(self)
        self.openai_mode_none = QRadioButton("Not Configured")
        self.openai_mode_api = QRadioButton("API Key")
        self.openai_mode_sub = QRadioButton("Subscription")
        self.openai_mode_none.setChecked(True)
        self.openai_mode_group.addButton(self.openai_mode_none, 0)
        self.openai_mode_group.addButton(self.openai_mode_api, 1)
        self.openai_mode_group.addButton(self.openai_mode_sub, 2)
        openai_mode_row.addWidget(self.openai_mode_none)
        openai_mode_row.addWidget(self.openai_mode_api)
        openai_mode_row.addWidget(self.openai_mode_sub)
        openai_mode_row.addStretch()
        auth_layout.addLayout(openai_mode_row)
        self.openai_mode_group.idToggled.connect(
            lambda id, checked: self._on_auth_mode_changed("openai", id) if checked else None
        )
        layout.addWidget(auth_card)

        # ── Subscription Auth Card ──
        sub_card = GlassCard()
        sub_layout = sub_card.get_layout()
        self._icon_header("section_subscription", "Subscription Auth", sub_layout)
        sub_info = QLabel(
            "Use your existing Claude Pro/Max, ChatGPT Plus, or Google account "
            "instead of separate API keys."
        )
        sub_info.setObjectName("mutedText")
        sub_info.setWordWrap(True)
        sub_layout.addWidget(sub_info)

        # Anthropic subscription (Claude Code CLI)
        anthropic_sub_label = QLabel("Anthropic — Claude Subscription")
        anthropic_sub_label.setObjectName("formLabel")
        sub_layout.addWidget(anthropic_sub_label)
        anthropic_sub_info = QLabel(
            "Uses your Claude Pro/Max subscription via the Claude Code CLI. "
            "Requires: 1) Install Claude Code (npm install -g @anthropic-ai/claude-code), "
            "2) Run 'claude login' in your terminal."
        )
        anthropic_sub_info.setObjectName("mutedText")
        anthropic_sub_info.setWordWrap(True)
        sub_layout.addWidget(anthropic_sub_info)

        anthropic_sub_row = QHBoxLayout()
        self.save_anthropic_sub_btn = ModernButton("Verify Claude CLI", "secondary")
        self.save_anthropic_sub_btn.setFixedHeight(40)
        self.save_anthropic_sub_btn.setMinimumWidth(150)
        self.save_anthropic_sub_btn.clicked.connect(self._on_verify_claude_cli)
        anthropic_sub_row.addWidget(self.save_anthropic_sub_btn)
        self.enable_claude_sub_btn = ModernButton("Enable Subscription", "primary")
        self.enable_claude_sub_btn.setFixedHeight(40)
        self.enable_claude_sub_btn.setMinimumWidth(150)
        self.enable_claude_sub_btn.clicked.connect(self._on_enable_claude_sub)
        anthropic_sub_row.addWidget(self.enable_claude_sub_btn)
        anthropic_sub_row.addStretch()
        sub_layout.addLayout(anthropic_sub_row)

        self.anthropic_sub_status = QLabel("")
        self.anthropic_sub_status.setObjectName("mutedText")
        sub_layout.addWidget(self.anthropic_sub_status)

        # OpenAI subscription (Codex CLI)
        openai_sub_label = QLabel("OpenAI — ChatGPT Subscription")
        openai_sub_label.setObjectName("formLabel")
        sub_layout.addWidget(openai_sub_label)
        openai_sub_info = QLabel(
            "Uses your ChatGPT Plus/Pro subscription via the OpenAI Codex CLI. "
            "Requires: 1) Install the Codex CLI (npm install -g @openai/codex), "
            "2) Run 'codex login' and sign in with your ChatGPT account."
        )
        openai_sub_info.setObjectName("mutedText")
        openai_sub_info.setWordWrap(True)
        sub_layout.addWidget(openai_sub_info)

        openai_sub_row = QHBoxLayout()
        self.verify_codex_cli_btn = ModernButton("Verify Codex CLI", "secondary")
        self.verify_codex_cli_btn.setFixedHeight(40)
        self.verify_codex_cli_btn.setMinimumWidth(150)
        self.verify_codex_cli_btn.clicked.connect(self._on_verify_codex_cli)
        openai_sub_row.addWidget(self.verify_codex_cli_btn)
        self.enable_openai_sub_btn = ModernButton("Enable Subscription", "primary")
        self.enable_openai_sub_btn.setFixedHeight(40)
        self.enable_openai_sub_btn.setMinimumWidth(150)
        self.enable_openai_sub_btn.clicked.connect(self._on_enable_openai_sub)
        openai_sub_row.addWidget(self.enable_openai_sub_btn)
        self.disable_openai_sub_btn = ModernButton("Disable", "danger")
        self.disable_openai_sub_btn.setFixedHeight(40)
        self.disable_openai_sub_btn.clicked.connect(self._on_disable_openai_sub)
        self.disable_openai_sub_btn.hide()
        openai_sub_row.addWidget(self.disable_openai_sub_btn)
        openai_sub_row.addStretch()
        sub_layout.addLayout(openai_sub_row)

        self.openai_sub_status = QLabel("")
        self.openai_sub_status.setObjectName("mutedText")
        sub_layout.addWidget(self.openai_sub_status)

        # Gemini subscription (via gemini CLI)
        gemini_sub_label = QLabel("Google — Gemini Subscription")
        gemini_sub_label.setObjectName("formLabel")
        sub_layout.addWidget(gemini_sub_label)
        gemini_sub_info = QLabel(
            "Use the gemini CLI with your Google account - no API key required. "
            "Run 'gemini auth login' once in a terminal to authenticate, then enable below."
        )
        gemini_sub_info.setObjectName("mutedText")
        gemini_sub_info.setWordWrap(True)
        sub_layout.addWidget(gemini_sub_info)

        gemini_sub_row = QHBoxLayout()
        self.gemini_enable_sub_btn = ModernButton("Use gemini CLI", "primary")
        self.gemini_enable_sub_btn.setFixedHeight(40)
        self.gemini_enable_sub_btn.clicked.connect(self._on_gemini_enable_sub)
        gemini_sub_row.addWidget(self.gemini_enable_sub_btn)
        self.gemini_disable_sub_btn = ModernButton("Disable", "danger")
        self.gemini_disable_sub_btn.setFixedHeight(40)
        self.gemini_disable_sub_btn.clicked.connect(self._on_gemini_disable_sub)
        self.gemini_disable_sub_btn.hide()
        gemini_sub_row.addWidget(self.gemini_disable_sub_btn)
        gemini_sub_row.addStretch()
        sub_layout.addLayout(gemini_sub_row)

        self.gemini_sub_status = QLabel("")
        self.gemini_sub_status.setObjectName("mutedText")
        sub_layout.addWidget(self.gemini_sub_status)

        layout.addWidget(sub_card)

        layout.addStretch()
        return self._make_scroll_tab(content)

    # ── Tab 2: AI Config ──────────────────────────────────────────────

    def _build_ai_config_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(20)

        # ── Model Selection Card ──
        model_card = GlassCard()
        model_layout = model_card.get_layout()
        self._icon_header("section_models", "AI Models", model_layout)

        model_row = QHBoxLayout()

        t2_col = QVBoxLayout()
        t2_col.setSpacing(4)
        t2_label = QLabel("Tier 2 — Qualification (Low Cost)")
        t2_label.setObjectName("formLabel")
        t2_col.addWidget(t2_label)
        self.tier2_combo = QComboBox()
        self.tier2_combo.setEditable(True)  # custom model IDs welcome
        self.tier2_combo.addItems([
            "gemini/gemini-3.5-flash",
            "gemini/gemini-3.1-flash-lite",
            "gemini/gemini-3-flash",
            "anthropic/claude-haiku-4-5",
            "openai/gpt-5.6-luna",
            "openai/gpt-4.1-mini",
            "openai/o4-mini",
            "ollama/llama3.1",
            "ollama/llama3",
            "ollama/mistral",
            "ollama/qwen2",
            "ollama/gemma2",
            "ollama/phi3",
            "openrouter/google/gemini-3.5-flash",
            "openrouter/openai/gpt-4.1-mini",
        ])
        t2_col.addWidget(self.tier2_combo)
        model_row.addLayout(t2_col, stretch=1)

        t3_col = QVBoxLayout()
        t3_col.setSpacing(4)
        t3_label = QLabel("Tier 3 — Email Gen (Premium)")
        t3_label.setObjectName("formLabel")
        t3_col.addWidget(t3_label)
        self.tier3_combo = QComboBox()
        self.tier3_combo.setEditable(True)  # custom model IDs welcome
        self.tier3_combo.addItems([
            "anthropic/claude-sonnet-5",
            "anthropic/claude-opus-4-8",
            "anthropic/claude-fable-5",
            "anthropic/claude-sonnet-4-6",
            "openai/gpt-5.6-sol",
            "openai/gpt-5.6-terra",
            "meta/muse-spark-1.1",
            "openai/gpt-5.5",
            "openai/gpt-5.2",
            "openai/gpt-4.1",
            "gemini/gemini-3.5-flash",
            "gemini/gemini-3-flash",
            "ollama/llama3.1",
            "ollama/llama3:70b",
            "ollama/mixtral",
            "openrouter/openai/gpt-5.5",
            "openrouter/auto",
        ])
        t3_col.addWidget(self.tier3_combo)
        model_row.addLayout(t3_col, stretch=1)

        chat_col = QVBoxLayout()
        chat_col.setSpacing(4)
        chat_label = QLabel("Chat — Aura Assistant")
        chat_label.setObjectName("formLabel")
        chat_col.addWidget(chat_label)
        self.chat_model_combo = QComboBox()
        self.chat_model_combo.setEditable(True)  # custom model IDs welcome
        self.chat_model_combo.addItems([
            "anthropic/claude-sonnet-5",
            "anthropic/claude-haiku-4-5",
            "anthropic/claude-opus-4-8",
            "anthropic/claude-fable-5",
            "openai/gpt-5.6-sol",
            "openai/gpt-5.6-terra",
            "meta/muse-spark-1.1",
            "openai/gpt-4.1-mini",
            "gemini/gemini-3.5-flash",
            "gemini/gemini-3-flash",
            "ollama/llama3.1",
            "ollama/llama3",
            "ollama/mistral",
            "openrouter/openai/gpt-5.5",
            "openrouter/auto",
        ])
        chat_col.addWidget(self.chat_model_combo)
        model_row.addLayout(chat_col, stretch=1)

        model_layout.addLayout(model_row)
        save_model_btn = ModernButton("Save Models", "primary")
        save_model_btn.setFixedHeight(36)
        save_model_btn.clicked.connect(self._on_save_models)
        model_layout.addWidget(save_model_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(model_card)

        # ── Autonomy Control Card ──
        autonomy_card = GlassCard()
        autonomy_layout = autonomy_card.get_layout()
        self._icon_header("section_autonomy", "Autonomy Level", autonomy_layout)
        autonomy_info = QLabel(
            "Controls how much the AI agents can do without your approval. "
            "Observer = everything needs approval. Full Trust = fully autonomous."
        )
        autonomy_info.setObjectName("mutedText")
        autonomy_info.setWordWrap(True)
        autonomy_layout.addWidget(autonomy_info)

        autonomy_row = QHBoxLayout()
        autonomy_label = QLabel("Level")
        autonomy_label.setObjectName("formLabel")
        autonomy_row.addWidget(autonomy_label)
        self.autonomy_combo = QComboBox()
        self.autonomy_combo.setObjectName("autonomySelector")
        self.autonomy_combo.addItems(["observer", "supervised", "autonomous", "full_trust"])
        self.autonomy_combo.setCurrentText("supervised")
        self.autonomy_combo.currentTextChanged.connect(
            lambda level: self.autonomy_level_changed.emit(level)
        )
        autonomy_row.addWidget(self.autonomy_combo)
        autonomy_row.addStretch()
        autonomy_layout.addLayout(autonomy_row)

        self.autonomy_description = QLabel("")
        self.autonomy_description.setObjectName("mutedText")
        self.autonomy_description.setWordWrap(True)
        autonomy_layout.addWidget(self.autonomy_description)
        self.autonomy_combo.currentTextChanged.connect(self._update_autonomy_description)
        layout.addWidget(autonomy_card)

        # ── Advanced AI Engines Card ──
        ai_card = GlassCard()
        ai_layout = ai_card.get_layout()
        self._icon_header("section_ai", "Advanced AI Engines", ai_layout)

        self.reflection_toggle = QCheckBox("Enable Reflection (auto-critique task output)")
        self.reflection_toggle.setChecked(True)
        ai_layout.addWidget(self.reflection_toggle)

        self.self_improvement_toggle = QCheckBox("Enable Self-Improvement (daily optimization)")
        ai_layout.addWidget(self.self_improvement_toggle)

        self.knowledge_graph_toggle = QCheckBox("Enable Knowledge Graph (entity tracking)")
        ai_layout.addWidget(self.knowledge_graph_toggle)

        self.conversation_toggle = QCheckBox("Enable Conversation Engine (reply tracking)")
        ai_layout.addWidget(self.conversation_toggle)

        save_ai_btn = ModernButton("Save AI Settings", "primary")
        save_ai_btn.setFixedHeight(36)
        save_ai_btn.clicked.connect(self._on_save_ai_toggles)
        ai_layout.addWidget(save_ai_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(ai_card)

        layout.addStretch()
        return self._make_scroll_tab(content)

    # ── Tab 3: Email & Delivery ───────────────────────────────────────

    def _build_email_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(20)

        # ── Sender Identity Card ──
        sender_card = GlassCard()
        sender_layout = sender_card.get_layout()
        self._icon_header("section_sender", "Sender Identity", sender_layout)

        sender_row = QHBoxLayout()
        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_col.addWidget(self._field_label("Your Name"))
        self.sender_name = QLineEdit()
        self.sender_name.setPlaceholderText("Alex Smith")
        name_col.addWidget(self.sender_name)
        sender_row.addLayout(name_col, stretch=1)

        email_col = QVBoxLayout()
        email_col.setSpacing(4)
        email_col.addWidget(self._field_label("Email Address"))
        self.sender_email = QLineEdit()
        self.sender_email.setPlaceholderText("alex@company.com")
        email_col.addWidget(self.sender_email)
        sender_row.addLayout(email_col, stretch=1)

        company_col = QVBoxLayout()
        company_col.setSpacing(4)
        company_col.addWidget(self._field_label("Company"))
        self.sender_company = QLineEdit()
        self.sender_company.setPlaceholderText("Company Name")
        company_col.addWidget(self.sender_company)
        sender_row.addLayout(company_col, stretch=1)

        sender_layout.addLayout(sender_row)
        save_sender_btn = ModernButton("Save Sender Info", "primary")
        save_sender_btn.setFixedHeight(36)
        save_sender_btn.clicked.connect(self._on_save_sender)
        sender_layout.addWidget(save_sender_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(sender_card)

        # ── SMTP Fallback Card ──
        smtp_card = GlassCard()
        smtp_layout = smtp_card.get_layout()
        self._icon_header("section_smtp", "SMTP Fallback", smtp_layout)
        smtp_info = QLabel("Optional: configure SMTP as a fallback when Resend is unavailable.")
        smtp_info.setObjectName("mutedText")
        smtp_layout.addWidget(smtp_info)

        smtp_row = QHBoxLayout()
        host_col = QVBoxLayout()
        host_col.setSpacing(4)
        host_col.addWidget(self._field_label("SMTP Host"))
        self.smtp_host = QLineEdit()
        self.smtp_host.setPlaceholderText("smtp.gmail.com")
        host_col.addWidget(self.smtp_host)
        smtp_row.addLayout(host_col, stretch=1)

        port_col = QVBoxLayout()
        port_col.setSpacing(4)
        port_col.addWidget(self._field_label("Port"))
        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(587)
        port_col.addWidget(self.smtp_port)
        smtp_row.addLayout(port_col)

        user_col = QVBoxLayout()
        user_col.setSpacing(4)
        user_col.addWidget(self._field_label("Username"))
        self.smtp_user = QLineEdit()
        self.smtp_user.setPlaceholderText("user@gmail.com")
        user_col.addWidget(self.smtp_user)
        smtp_row.addLayout(user_col, stretch=1)

        pass_col = QVBoxLayout()
        pass_col.setSpacing(4)
        pass_col.addWidget(self._field_label("Password"))
        self.smtp_pass = MaskedInput("SMTP password...")
        pass_col.addWidget(self.smtp_pass)
        smtp_row.addLayout(pass_col, stretch=1)

        smtp_layout.addLayout(smtp_row)
        save_smtp_btn = ModernButton("Save SMTP", "primary")
        save_smtp_btn.setFixedHeight(36)
        save_smtp_btn.clicked.connect(self._on_save_smtp)
        smtp_layout.addWidget(save_smtp_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(smtp_card)

        # ── IMAP Configuration Card ──
        imap_card = GlassCard()
        imap_layout = imap_card.get_layout()
        self._icon_header("section_imap", "IMAP (Reply Detection)", imap_layout)

        imap_row1 = QHBoxLayout()
        host_col = QVBoxLayout()
        host_col.addWidget(self._field_label("IMAP Host"))
        self.imap_host = QLineEdit()
        self.imap_host.setPlaceholderText("imap.gmail.com")
        host_col.addWidget(self.imap_host)
        imap_row1.addLayout(host_col, stretch=2)

        port_col = QVBoxLayout()
        port_col.addWidget(self._field_label("Port"))
        self.imap_port = QSpinBox()
        self.imap_port.setRange(1, 65535)
        self.imap_port.setValue(993)
        port_col.addWidget(self.imap_port)
        imap_row1.addLayout(port_col, stretch=1)
        imap_layout.addLayout(imap_row1)

        imap_row2 = QHBoxLayout()
        user_col = QVBoxLayout()
        user_col.addWidget(self._field_label("Username"))
        self.imap_user = QLineEdit()
        self.imap_user.setPlaceholderText("you@gmail.com")
        user_col.addWidget(self.imap_user)
        imap_row2.addLayout(user_col, stretch=1)

        pass_col = QVBoxLayout()
        pass_col.addWidget(self._field_label("Password"))
        self.imap_pass = MaskedInput(placeholder="IMAP password")
        pass_col.addWidget(self.imap_pass)
        imap_row2.addLayout(pass_col, stretch=1)
        imap_layout.addLayout(imap_row2)

        self.imap_ssl = QCheckBox("Use SSL")
        self.imap_ssl.setChecked(True)
        imap_layout.addWidget(self.imap_ssl)

        save_imap_btn = ModernButton("Save IMAP", "primary")
        save_imap_btn.setFixedHeight(36)
        save_imap_btn.clicked.connect(self._on_save_imap)
        imap_layout.addWidget(save_imap_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(imap_card)

        layout.addStretch()
        return self._make_scroll_tab(content)

    # ── Tab 4: Features ───────────────────────────────────────────────

    def _build_features_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(20)

        # ── Feature Toggles Card ──
        toggle_card = GlassCard()
        toggle_layout = toggle_card.get_layout()
        self._icon_header("section_toggles", "Feature Toggles", toggle_layout)

        self.ab_toggle = QCheckBox("Enable A/B Skill Testing")
        toggle_layout.addWidget(self.ab_toggle)

        self.enrichment_toggle = QCheckBox("Enable Lead Enrichment")
        self.enrichment_toggle.setChecked(True)
        toggle_layout.addWidget(self.enrichment_toggle)

        self.suppression_toggle = QCheckBox("Enable Global Suppression List")
        self.suppression_toggle.setChecked(True)
        toggle_layout.addWidget(self.suppression_toggle)

        self.schedule_toggle = QCheckBox("Enable Timezone-Aware Scheduling")
        toggle_layout.addWidget(self.schedule_toggle)

        self.rag_toggle = QCheckBox("Enable RAG Memory & Style Mimicry")
        toggle_layout.addWidget(self.rag_toggle)

        self.cross_channel_toggle = QCheckBox("Enable Cross-Channel Messaging (LinkedIn, Twitter)")
        toggle_layout.addWidget(self.cross_channel_toggle)

        self.triage_toggle = QCheckBox("Enable AI Inbox Triage (Morning Briefing)")
        toggle_layout.addWidget(self.triage_toggle)

        self.fleet_toggle = QCheckBox("Enable Multi-Agent Fleet System")
        toggle_layout.addWidget(self.fleet_toggle)

        self.trends_toggle = QCheckBox("Enable Google Trends Intelligence")
        toggle_layout.addWidget(self.trends_toggle)

        crm_row = QHBoxLayout()
        crm_label = QLabel("CRM Platform")
        crm_label.setObjectName("formLabel")
        crm_row.addWidget(crm_label)
        self.crm_combo = QComboBox()
        self.crm_combo.addItems(["None", "HubSpot", "Pipedrive"])
        crm_row.addWidget(self.crm_combo)
        crm_row.addStretch()
        toggle_layout.addLayout(crm_row)

        save_toggles_btn = ModernButton("Save Toggles", "primary")
        save_toggles_btn.setFixedHeight(36)
        save_toggles_btn.clicked.connect(self._on_save_toggles)
        toggle_layout.addWidget(save_toggles_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(toggle_card)

        # ── Research & Voice Config Card ──
        rv_card = GlassCard()
        rv_layout = rv_card.get_layout()
        self._icon_header("section_ai", "Research & Voice Config", rv_layout)

        self.research_auto_toggle = QCheckBox("Enable Auto-Research (after qualification)")
        self.research_auto_toggle.setChecked(True)
        rv_layout.addWidget(self.research_auto_toggle)

        self.voice_call_toggle = QCheckBox("Enable Voice Calls (Twilio + TTS)")
        rv_layout.addWidget(self.voice_call_toggle)

        rv_row1 = QHBoxLayout()
        rv_row1.setSpacing(16)

        phone_col = QVBoxLayout()
        phone_col.setSpacing(4)
        phone_col.addWidget(self._field_label("Twilio Phone Number"))
        self.twilio_phone_input = QLineEdit()
        self.twilio_phone_input.setPlaceholderText("+15551234567")
        phone_col.addWidget(self.twilio_phone_input)
        rv_row1.addLayout(phone_col, stretch=1)

        voice_id_col = QVBoxLayout()
        voice_id_col.setSpacing(4)
        voice_id_col.addWidget(self._field_label("ElevenLabs Voice ID"))
        self.elevenlabs_voice_id_input = QLineEdit()
        self.elevenlabs_voice_id_input.setPlaceholderText("Voice ID from ElevenLabs dashboard")
        voice_id_col.addWidget(self.elevenlabs_voice_id_input)
        rv_row1.addLayout(voice_id_col, stretch=1)
        rv_layout.addLayout(rv_row1)

        rv_row2 = QHBoxLayout()
        rv_row2.setSpacing(16)

        tts_col = QVBoxLayout()
        tts_col.setSpacing(4)
        tts_col.addWidget(self._field_label("TTS Provider"))
        self.tts_provider_combo = QComboBox()
        self.tts_provider_combo.addItems(["elevenlabs", "openai", "piper"])
        tts_col.addWidget(self.tts_provider_combo)
        rv_row2.addLayout(tts_col, stretch=1)

        stt_col = QVBoxLayout()
        stt_col.setSpacing(4)
        stt_col.addWidget(self._field_label("STT Provider"))
        self.stt_provider_combo = QComboBox()
        self.stt_provider_combo.addItems(["whisper_local", "whisper_api"])
        stt_col.addWidget(self.stt_provider_combo)
        rv_row2.addLayout(stt_col, stretch=1)

        rv_row2.addStretch()
        rv_layout.addLayout(rv_row2)

        save_rv_btn = ModernButton("Save Research & Voice", "primary")
        save_rv_btn.setFixedHeight(36)
        save_rv_btn.clicked.connect(self._on_save_rv_config)
        rv_layout.addWidget(save_rv_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(rv_card)

        layout.addStretch()
        return self._make_scroll_tab(content)

    # ── Tab 5: Business & Invoicing ───────────────────────────────────

    def _build_business_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(20)

        # ── Company Information Card ──
        company_card = GlassCard()
        cl = company_card.get_layout()
        self._icon_header("section_company", "Company Information", cl)
        company_info = QLabel(
            "Your company details used for invoices, email signatures, and agent context."
        )
        company_info.setObjectName("mutedText")
        company_info.setWordWrap(True)
        cl.addWidget(company_info)

        row1 = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Company Legal Name"))
        self.company_legal_name = QLineEdit()
        self.company_legal_name.setPlaceholderText("Acme Corp GmbH")
        col.addWidget(self.company_legal_name)
        row1.addLayout(col, stretch=2)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Tax ID / VAT"))
        self.company_tax_id = QLineEdit()
        self.company_tax_id.setPlaceholderText("DE123456789")
        col.addWidget(self.company_tax_id)
        row1.addLayout(col, stretch=1)
        cl.addLayout(row1)

        row2 = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Company Email"))
        self.company_email = QLineEdit()
        self.company_email.setPlaceholderText("billing@company.com")
        col.addWidget(self.company_email)
        row2.addLayout(col, stretch=1)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Company Phone"))
        self.company_phone = QLineEdit()
        self.company_phone.setPlaceholderText("+49 30 12345678")
        col.addWidget(self.company_phone)
        row2.addLayout(col, stretch=1)
        cl.addLayout(row2)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Company Website"))
        self.company_website = QLineEdit()
        self.company_website.setPlaceholderText("https://www.company.com")
        col.addWidget(self.company_website)
        cl.addLayout(col)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Company Address"))
        self.company_address = QTextEdit()
        self.company_address.setPlaceholderText("123 Main St\nBerlin, 10115\nGermany")
        self.company_address.setFixedHeight(80)
        col.addWidget(self.company_address)
        cl.addLayout(col)

        logo_row = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Company Logo Path"))
        self.company_logo_path = QLineEdit()
        self.company_logo_path.setPlaceholderText("/path/to/logo.png")
        col.addWidget(self.company_logo_path)
        logo_row.addLayout(col, stretch=1)
        browse_btn = ModernButton("Browse", "secondary")
        browse_btn.setFixedHeight(40)
        browse_btn.setMinimumWidth(80)
        browse_btn.clicked.connect(self._on_browse_logo)
        logo_row.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        cl.addLayout(logo_row)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Telegram Owner Chat ID"))
        self.telegram_owner_chat_id = QLineEdit()
        self.telegram_owner_chat_id.setPlaceholderText("123456789")
        col.addWidget(self.telegram_owner_chat_id)
        cl.addLayout(col)

        save_company_btn = ModernButton("Save Company Info", "primary")
        save_company_btn.setFixedHeight(36)
        save_company_btn.clicked.connect(self._on_save_company_info)
        cl.addWidget(save_company_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(company_card)

        # ── Banking Details Card ──
        bank_card = GlassCard()
        bl = bank_card.get_layout()
        self._icon_header("section_banking", "Banking Details", bl)
        bank_info = QLabel(
            "Banking details for invoices. All data is stored locally and encrypted."
        )
        bank_info.setObjectName("mutedText")
        bank_info.setWordWrap(True)
        bl.addWidget(bank_info)

        row = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Bank Name"))
        self.company_bank_name = QLineEdit()
        self.company_bank_name.setPlaceholderText("Deutsche Bank")
        col.addWidget(self.company_bank_name)
        row.addLayout(col, stretch=2)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("SWIFT / BIC"))
        self.company_swift = QLineEdit()
        self.company_swift.setPlaceholderText("DEUTDEDB")
        col.addWidget(self.company_swift)
        row.addLayout(col, stretch=1)
        bl.addLayout(row)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("IBAN"))
        self.company_iban = QLineEdit()
        self.company_iban.setPlaceholderText("DE89 3704 0044 0532 0130 00")
        col.addWidget(self.company_iban)
        bl.addLayout(col)

        save_bank_btn = ModernButton("Save Banking", "primary")
        save_bank_btn.setFixedHeight(36)
        save_bank_btn.clicked.connect(self._on_save_banking)
        bl.addWidget(save_bank_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(bank_card)

        # ── Invoice Configuration Card ──
        inv_card = GlassCard()
        il = inv_card.get_layout()
        self._icon_header("section_invoice", "Invoice Configuration", il)

        inv_row1 = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Invoice Prefix"))
        self.invoice_prefix = QLineEdit()
        self.invoice_prefix.setPlaceholderText("INV-")
        col.addWidget(self.invoice_prefix)
        inv_row1.addLayout(col, stretch=1)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Next Number"))
        self.invoice_next_number = QSpinBox()
        self.invoice_next_number.setRange(1, 999999)
        self.invoice_next_number.setValue(1)
        col.addWidget(self.invoice_next_number)
        inv_row1.addLayout(col, stretch=1)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Currency"))
        self.invoice_currency = QComboBox()
        self.invoice_currency.addItems(["EUR", "USD", "GBP", "CHF", "CAD", "AUD", "JPY"])
        col.addWidget(self.invoice_currency)
        inv_row1.addLayout(col, stretch=1)
        il.addLayout(inv_row1)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Payment Terms"))
        self.payment_terms_days = QSpinBox()
        self.payment_terms_days.setRange(0, 365)
        self.payment_terms_days.setValue(30)
        self.payment_terms_days.setSuffix(" days")
        col.addWidget(self.payment_terms_days)
        il.addLayout(col)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label("Default Invoice Notes"))
        self.invoice_notes = QTextEdit()
        self.invoice_notes.setPlaceholderText("Thank you for your business.\nPayment due within 30 days.")
        self.invoice_notes.setFixedHeight(80)
        col.addWidget(self.invoice_notes)
        il.addLayout(col)

        save_inv_btn = ModernButton("Save Invoice Config", "primary")
        save_inv_btn.setFixedHeight(36)
        save_inv_btn.clicked.connect(self._on_save_invoice_config)
        il.addWidget(save_inv_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(inv_card)

        layout.addStretch()
        return self._make_scroll_tab(content)

    # ── Tab 6: Knowledge Base ──────────────────────────────────────────

    def _build_knowledge_base_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(20)

        # ─── Product Definition ──────────────────────────
        prod_card = GlassCard()
        pl = prod_card.get_layout()
        self._icon_header("tab_knowledge_base", "Product / Service Definition", pl)

        prod_hint = QLabel(
            "Define what you sell. Agents use this to personalize outreach."
        )
        prod_hint.setObjectName("mutedText")
        prod_hint.setWordWrap(True)
        pl.addWidget(prod_hint)

        self.kb_product_name = QLineEdit()
        self.kb_product_name.setPlaceholderText("Product/service name")
        pl.addWidget(self._field_label("Product Name"))
        pl.addWidget(self.kb_product_name)

        self.kb_product_description = QTextEdit()
        self.kb_product_description.setPlaceholderText(
            "Describe your product/service in 2-3 sentences..."
        )
        self.kb_product_description.setMaximumHeight(80)
        pl.addWidget(self._field_label("Description"))
        pl.addWidget(self.kb_product_description)

        self.kb_product_value_prop = QLineEdit()
        self.kb_product_value_prop.setPlaceholderText("Main value proposition")
        pl.addWidget(self._field_label("Value Proposition"))
        pl.addWidget(self.kb_product_value_prop)

        self.kb_product_price_range = QLineEdit()
        self.kb_product_price_range.setPlaceholderText("e.g. $500-$5,000/mo")
        pl.addWidget(self._field_label("Price Range"))
        pl.addWidget(self.kb_product_price_range)

        save_prod_btn = ModernButton("Save Product Info", "primary")
        save_prod_btn.setFixedHeight(36)
        save_prod_btn.clicked.connect(self._on_save_kb_product)
        pl.addWidget(save_prod_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(prod_card)

        # ─── ICP Definition ──────────────────────────────
        icp_card = GlassCard()
        il = icp_card.get_layout()
        self._icon_header("tab_knowledge_base", "Ideal Customer Profile (ICP)", il)

        icp_hint = QLabel(
            "Define your ideal customer. Used for lead scoring and qualification."
        )
        icp_hint.setObjectName("mutedText")
        icp_hint.setWordWrap(True)
        il.addWidget(icp_hint)

        self.kb_icp_industry = QLineEdit()
        self.kb_icp_industry.setPlaceholderText("e.g. SaaS, E-commerce, Healthcare")
        il.addWidget(self._field_label("Target Industries"))
        il.addWidget(self.kb_icp_industry)

        self.kb_icp_company_size = QLineEdit()
        self.kb_icp_company_size.setPlaceholderText("e.g. 10-200 employees")
        il.addWidget(self._field_label("Company Size"))
        il.addWidget(self.kb_icp_company_size)

        self.kb_icp_decision_maker = QLineEdit()
        self.kb_icp_decision_maker.setPlaceholderText("e.g. CEO, CTO, VP Marketing")
        il.addWidget(self._field_label("Decision Maker Titles"))
        il.addWidget(self.kb_icp_decision_maker)

        self.kb_icp_pain_points = QTextEdit()
        self.kb_icp_pain_points.setPlaceholderText(
            "Pain points your product solves (one per line)..."
        )
        self.kb_icp_pain_points.setMaximumHeight(80)
        il.addWidget(self._field_label("Pain Points"))
        il.addWidget(self.kb_icp_pain_points)

        self.kb_icp_disqualifiers = QLineEdit()
        self.kb_icp_disqualifiers.setPlaceholderText("e.g. Non-profit, Government, <5 employees")
        il.addWidget(self._field_label("Disqualifiers"))
        il.addWidget(self.kb_icp_disqualifiers)

        save_icp_btn = ModernButton("Save ICP", "primary")
        save_icp_btn.setFixedHeight(36)
        save_icp_btn.clicked.connect(self._on_save_kb_icp)
        il.addWidget(save_icp_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(icp_card)

        # ─── Sales Approach ──────────────────────────────
        approach_card = GlassCard()
        al = approach_card.get_layout()
        self._icon_header("tab_knowledge_base", "Sales Approach", al)

        approach_hint = QLabel(
            "Define your preferred sales style. Guides email tone and conversation strategy."
        )
        approach_hint.setObjectName("mutedText")
        approach_hint.setWordWrap(True)
        al.addWidget(approach_hint)

        self.kb_approach_tone = QComboBox()
        self.kb_approach_tone.addItems([
            "professional", "casual", "consultative", "direct", "friendly",
        ])
        al.addWidget(self._field_label("Email Tone"))
        al.addWidget(self.kb_approach_tone)

        self.kb_approach_style = QTextEdit()
        self.kb_approach_style.setPlaceholderText(
            "Describe your sales approach (e.g. 'Lead with value, avoid hard sells, "
            "reference specific pain points')..."
        )
        self.kb_approach_style.setMaximumHeight(80)
        al.addWidget(self._field_label("Approach Description"))
        al.addWidget(self.kb_approach_style)

        self.kb_approach_cta = QLineEdit()
        self.kb_approach_cta.setPlaceholderText("e.g. Book a 15-min demo call")
        al.addWidget(self._field_label("Default CTA"))
        al.addWidget(self.kb_approach_cta)

        save_approach_btn = ModernButton("Save Approach", "primary")
        save_approach_btn.setFixedHeight(36)
        save_approach_btn.clicked.connect(self._on_save_kb_approach)
        al.addWidget(save_approach_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(approach_card)

        layout.addStretch()
        return self._make_scroll_tab(content)

    # ─── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _icon_header(icon_key: str, text: str, parent_layout, theme: str = "dark"):
        row = QHBoxLayout()
        row.setSpacing(8)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_pixmap(icon_key, theme, "default", 16))
        icon_lbl.setFixedSize(20, 20)
        text_lbl = QLabel(text)
        text_lbl.setObjectName("cardHeader")
        row.addWidget(icon_lbl)
        row.addWidget(text_lbl, stretch=1)
        parent_layout.addLayout(row)
        return text_lbl

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("formLabel")
        return lbl

    def _add_key_row(self, parent_layout, label: str, provider: str) -> MaskedInput:
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(self._field_label(label))

        masked = MaskedInput(f"Enter {label} API key...")
        hrow = QHBoxLayout()
        hrow.setSpacing(10)
        hrow.addWidget(masked, alignment=Qt.AlignmentFlag.AlignVCenter)

        save_btn = ModernButton("Save", "secondary")
        save_btn.setMinimumWidth(84)
        save_btn.clicked.connect(lambda: self._on_save_key(provider, masked))
        hrow.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        hrow.addStretch()
        col.addLayout(hrow)

        parent_layout.addLayout(col)
        return masked

    # ─── Public Methods ───────────────────────────────────────────────

    def load_settings(self, settings: dict):
        """Populate fields from controller settings dict."""
        # API Keys
        if settings.get("has_gemini"):
            self.gemini_input.set_value(settings["gemini_key"])
        if settings.get("has_anthropic"):
            self.anthropic_input.set_value(settings["anthropic_key"])
        if settings.get("has_openai"):
            self.openai_input.set_value(settings["openai_key"])
        if settings.get("has_resend"):
            self.resend_input.set_value(settings["resend_key"])
        if settings.get("has_apollo"):
            self.apollo_input.set_value(settings["apollo_key"])
        if settings.get("has_hunter"):
            self.hunter_input.set_value(settings["hunter_key"])
        if settings.get("has_hubspot"):
            self.hubspot_input.set_value(settings["hubspot_key"])
        if settings.get("has_pipedrive"):
            self.pipedrive_input.set_value(settings["pipedrive_key"])
        if settings.get("has_openrouter"):
            self.openrouter_input.set_value(settings["openrouter_key"])
        if settings.get("has_tavily"):
            self.tavily_input.set_value(settings["tavily_key"])
        if settings.get("has_firecrawl"):
            self.firecrawl_input.set_value(settings["firecrawl_key"])
        if settings.get("has_apify"):
            self.apify_input.set_value(settings["apify_key"])
        if settings.get("has_twilio"):
            self.twilio_sid_input.set_value(settings["twilio_sid_key"])
            self.twilio_token_input.set_value(settings["twilio_token_key"])
        if settings.get("has_elevenlabs"):
            self.elevenlabs_input.set_value(settings["elevenlabs_key"])

        # Models
        t2_idx = self.tier2_combo.findText(settings.get("tier2_model", ""))
        if t2_idx >= 0:
            self.tier2_combo.setCurrentIndex(t2_idx)
        t3_idx = self.tier3_combo.findText(settings.get("tier3_model", ""))
        if t3_idx >= 0:
            self.tier3_combo.setCurrentIndex(t3_idx)
        chat_idx = self.chat_model_combo.findText(settings.get("chat_model", ""))
        if chat_idx >= 0:
            self.chat_model_combo.setCurrentIndex(chat_idx)

        # Sender
        self.sender_name.setText(settings.get("sender_name", ""))
        self.sender_email.setText(settings.get("sender_email", ""))
        self.sender_company.setText(settings.get("sender_company", ""))

        # SMTP
        self.smtp_host.setText(settings.get("smtp_host", ""))
        self.smtp_port.setValue(settings.get("smtp_port", 587))
        self.smtp_user.setText(settings.get("smtp_user", ""))

        # IMAP
        self.imap_host.setText(settings.get("imap_host", ""))
        self.imap_port.setValue(settings.get("imap_port", 993))
        self.imap_user.setText(settings.get("imap_username", ""))
        self.imap_ssl.setChecked(settings.get("imap_use_ssl", True))

        # Toggles
        self.ab_toggle.setChecked(settings.get("ab_test_enabled", False))
        self.enrichment_toggle.setChecked(settings.get("enrichment_enabled", True))
        self.suppression_toggle.setChecked(settings.get("suppression_enabled", True))
        self.schedule_toggle.setChecked(settings.get("send_schedule_enabled", False))
        self.rag_toggle.setChecked(settings.get("rag_enabled", False))
        self.cross_channel_toggle.setChecked(settings.get("cross_channel_enabled", False))
        self.triage_toggle.setChecked(settings.get("inbox_triage_enabled", False))
        self.fleet_toggle.setChecked(settings.get("fleet_enabled", False))
        self.trends_toggle.setChecked(settings.get("trends_enabled", False))

        # CRM
        crm = settings.get("crm_platform", "")
        crm_map = {"": 0, "hubspot": 1, "pipedrive": 2}
        self.crm_combo.setCurrentIndex(crm_map.get(crm, 0))

        # Autonomy
        autonomy_level = settings.get("autonomy_level", "supervised")
        idx = self.autonomy_combo.findText(autonomy_level)
        if idx >= 0:
            self.autonomy_combo.setCurrentIndex(idx)
        self._update_autonomy_description(autonomy_level)

        # Advanced AI toggles
        self.reflection_toggle.setChecked(settings.get("reflection_enabled", True))
        self.self_improvement_toggle.setChecked(settings.get("self_improvement_enabled", False))
        self.knowledge_graph_toggle.setChecked(settings.get("knowledge_graph_enabled", False))
        self.conversation_toggle.setChecked(settings.get("conversation_engine_enabled", False))

        # Research & Voice config
        self.research_auto_toggle.setChecked(settings.get("research_auto_enabled", True))
        self.voice_call_toggle.setChecked(settings.get("voice_call_enabled", False))
        self.twilio_phone_input.setText(settings.get("twilio_phone_number", ""))
        self.elevenlabs_voice_id_input.setText(settings.get("elevenlabs_voice_id", ""))
        tts_idx = self.tts_provider_combo.findText(settings.get("voice_tts_provider", "elevenlabs"))
        if tts_idx >= 0:
            self.tts_provider_combo.setCurrentIndex(tts_idx)
        stt_idx = self.stt_provider_combo.findText(settings.get("voice_stt_provider", "whisper_local"))
        if stt_idx >= 0:
            self.stt_provider_combo.setCurrentIndex(stt_idx)

        # Auth mode radio buttons
        mode_map = {"none": 0, "api": 1, "subscription": 2}
        anthropic_mode = settings.get("anthropic_auth_mode", "none")
        btn = self.anthropic_mode_group.button(mode_map.get(anthropic_mode, 0))
        if btn:
            btn.setChecked(True)

        openai_mode = settings.get("openai_auth_mode", "none")
        btn = self.openai_mode_group.button(mode_map.get(openai_mode, 0))
        if btn:
            btn.setChecked(True)

        # Subscription auth status
        if settings.get("anthropic_auth_mode") == "subscription":
            self.anthropic_sub_status.setText("Subscription mode enabled (using Claude CLI)")
            self.anthropic_sub_status.setObjectName("statusTextSuccess")
            self.anthropic_sub_status.style().unpolish(self.anthropic_sub_status)
            self.anthropic_sub_status.style().polish(self.anthropic_sub_status)
        elif settings.get("has_anthropic_sub"):
            self.anthropic_sub_status.setText("API key saved")
            self.anthropic_sub_status.setObjectName("statusTextSuccess")
            self.anthropic_sub_status.style().unpolish(self.anthropic_sub_status)
            self.anthropic_sub_status.style().polish(self.anthropic_sub_status)
        else:
            self.anthropic_sub_status.setText("")

        if settings.get("openai_auth_mode") == "subscription":
            self.openai_sub_status.setText("Subscription mode enabled (using Codex CLI)")
            self.openai_sub_status.setObjectName("statusTextSuccess")
            self.openai_sub_status.style().unpolish(self.openai_sub_status)
            self.openai_sub_status.style().polish(self.openai_sub_status)
            self.enable_openai_sub_btn.hide()
            self.disable_openai_sub_btn.show()
        else:
            self.openai_sub_status.setText("")
            self.enable_openai_sub_btn.show()
            self.disable_openai_sub_btn.hide()

        if settings.get("gemini_auth_mode") == "subscription":
            self.gemini_sub_status.setText("Active — using gemini CLI")
            self.gemini_sub_status.setObjectName("statusTextSuccess")
            self.gemini_sub_status.style().unpolish(self.gemini_sub_status)
            self.gemini_sub_status.style().polish(self.gemini_sub_status)
            self.gemini_enable_sub_btn.hide()
            self.gemini_disable_sub_btn.show()
        else:
            self.gemini_sub_status.setText("")
            self.gemini_enable_sub_btn.show()
            self.gemini_disable_sub_btn.hide()

        # Business & Invoicing fields
        self.company_legal_name.setText(settings.get("company_legal_name", ""))
        self.company_address.setPlainText(settings.get("company_address", ""))
        self.company_tax_id.setText(settings.get("company_tax_id", ""))
        self.company_email.setText(settings.get("company_email", ""))
        self.company_phone.setText(settings.get("company_phone", ""))
        self.company_website.setText(settings.get("company_website", ""))
        self.company_logo_path.setText(settings.get("company_logo_path", ""))
        self.telegram_owner_chat_id.setText(settings.get("telegram_owner_chat_id", ""))
        self.company_bank_name.setText(settings.get("company_bank_name", ""))
        self.company_swift.setText(settings.get("company_swift", ""))
        self.company_iban.setText(settings.get("company_iban", ""))
        self.invoice_prefix.setText(settings.get("invoice_prefix", "INV-"))
        self.invoice_next_number.setValue(settings.get("invoice_next_number", 1))
        currency_idx = self.invoice_currency.findText(settings.get("invoice_currency", "EUR"))
        if currency_idx >= 0:
            self.invoice_currency.setCurrentIndex(currency_idx)
        self.payment_terms_days.setValue(settings.get("payment_terms_days", 30))
        self.invoice_notes.setPlainText(settings.get("invoice_notes", ""))

    # ─── Signal Emitters ──────────────────────────────────────────────

    def _on_save_key(self, provider: str, masked_input: MaskedInput):
        key = masked_input.get_value()
        if key:
            self.save_key_requested.emit(provider, key)
            show_toast(self.window(), f"{provider.title()} key saved.", "success")
        else:
            show_toast(self.window(), "Please enter a key.", "warning")

    def _on_save_models(self):
        self.save_models_requested.emit(
            self.tier2_combo.currentText(),
            self.tier3_combo.currentText(),
        )
        self.save_chat_model_requested.emit(self.chat_model_combo.currentText())
        show_toast(self.window(), "Model selection saved.", "success")

    def _on_save_sender(self):
        self.save_sender_requested.emit(
            self.sender_name.text().strip(),
            self.sender_email.text().strip(),
            self.sender_company.text().strip(),
        )
        show_toast(self.window(), "Sender info saved.", "success")

    def _on_save_smtp(self):
        self.save_smtp_requested.emit(
            self.smtp_host.text().strip(),
            self.smtp_port.value(),
            self.smtp_user.text().strip(),
            self.smtp_pass.get_value(),
        )
        show_toast(self.window(), "SMTP configuration saved.", "success")

    def _on_save_imap(self):
        self.save_imap_requested.emit(
            self.imap_host.text().strip(),
            self.imap_port.value(),
            self.imap_user.text().strip(),
            self.imap_pass.get_value(),
            self.imap_ssl.isChecked(),
        )
        show_toast(self.window(), "IMAP configuration saved.", "success")

    def _on_save_toggles(self):
        crm_idx = self.crm_combo.currentIndex()
        crm_platform = {0: "", 1: "hubspot", 2: "pipedrive"}.get(crm_idx, "")
        self.save_toggles_requested.emit({
            "ab_test_enabled": self.ab_toggle.isChecked(),
            "enrichment_enabled": self.enrichment_toggle.isChecked(),
            "suppression_enabled": self.suppression_toggle.isChecked(),
            "send_schedule_enabled": self.schedule_toggle.isChecked(),
            "rag_enabled": self.rag_toggle.isChecked(),
            "cross_channel_enabled": self.cross_channel_toggle.isChecked(),
            "inbox_triage_enabled": self.triage_toggle.isChecked(),
            "fleet_enabled": self.fleet_toggle.isChecked(),
            "trends_enabled": self.trends_toggle.isChecked(),
            "crm_platform": crm_platform,
        })
        show_toast(self.window(), "Feature toggles saved.", "success")

    def _on_verify_claude_cli(self):
        """Verify that the Claude Code CLI is installed and authenticated."""
        import subprocess
        self.save_anthropic_sub_btn.set_loading(True, "Checking...")
        try:
            import shutil
            exe = shutil.which("claude")
            if not exe:
                raise FileNotFoundError
            result = subprocess.run(
                [exe, "-p", "--model", "haiku",
                 "--output-format", "text", "--no-session-persistence",
                 "respond with just the word OK"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                self.anthropic_sub_status.setText(
                    f"Claude CLI verified (response: {result.stdout.strip()[:30]})"
                )
                self.anthropic_sub_status.setObjectName("statusTextSuccess")
                self.anthropic_sub_status.style().unpolish(self.anthropic_sub_status)
                self.anthropic_sub_status.style().polish(self.anthropic_sub_status)
                show_toast(self.window(), "Claude CLI is working!", "success")
            else:
                error = result.stderr.strip()[:100] if result.stderr else "No response"
                self.anthropic_sub_status.setText(f"CLI check failed: {error}")
                show_toast(
                    self.window(),
                    "Claude CLI not responding. Run 'claude login' in your terminal.",
                    "warning",
                )
        except FileNotFoundError:
            self.anthropic_sub_status.setText("Claude CLI not found")
            show_toast(
                self.window(),
                "Claude CLI not installed. Run: npm install -g @anthropic-ai/claude-code",
                "error",
            )
        except subprocess.TimeoutExpired:
            self.anthropic_sub_status.setText("CLI timed out")
            show_toast(self.window(), "Claude CLI timed out — try again.", "warning")
        except Exception as e:
            self.anthropic_sub_status.setText(f"Error: {str(e)[:60]}")
            show_toast(self.window(), f"CLI check error: {e}", "error")
        finally:
            self.save_anthropic_sub_btn.set_loading(False)

    def _on_enable_claude_sub(self):
        """Enable Claude subscription mode (uses CLI instead of API key)."""
        self.auth_mode_changed.emit("anthropic", "subscription")
        self.anthropic_sub_status.setText("Subscription mode enabled (using Claude CLI)")
        self.anthropic_sub_status.setObjectName("statusTextSuccess")
        self.anthropic_sub_status.style().unpolish(self.anthropic_sub_status)
        self.anthropic_sub_status.style().polish(self.anthropic_sub_status)
        show_toast(
            self.window(),
            "Claude subscription enabled! Chat will use your Claude CLI auth.",
            "success",
        )

    def _on_verify_codex_cli(self):
        """Verify that the Codex CLI is installed and authenticated."""
        import subprocess
        self.verify_codex_cli_btn.set_loading(True, "Checking...")
        try:
            import shutil
            exe = shutil.which("codex")
            if not exe:
                raise FileNotFoundError
            result = subprocess.run(
                [exe, "login", "status"],
                capture_output=True, text=True, timeout=15,
            )
            output = (result.stdout + result.stderr).strip()
            if result.returncode == 0:
                self.openai_sub_status.setText(
                    f"Codex CLI verified ({output[:60] or 'logged in'})"
                )
                self.openai_sub_status.setObjectName("statusTextSuccess")
                self.openai_sub_status.style().unpolish(self.openai_sub_status)
                self.openai_sub_status.style().polish(self.openai_sub_status)
                show_toast(self.window(), "Codex CLI is working!", "success")
            else:
                self.openai_sub_status.setText(f"Not logged in: {output[:80]}")
                show_toast(
                    self.window(),
                    "Codex CLI found but not logged in. Run 'codex login' in your terminal.",
                    "warning",
                )
        except FileNotFoundError:
            self.openai_sub_status.setText("Codex CLI not found")
            show_toast(
                self.window(),
                "Codex CLI not installed. Run: npm install -g @openai/codex",
                "error",
            )
        except subprocess.TimeoutExpired:
            self.openai_sub_status.setText("CLI timed out")
            show_toast(self.window(), "Codex CLI timed out — try again.", "warning")
        except Exception as e:
            self.openai_sub_status.setText(f"Error: {str(e)[:60]}")
            show_toast(self.window(), f"CLI check error: {e}", "error")
        finally:
            self.verify_codex_cli_btn.set_loading(False)

    def _on_enable_openai_sub(self):
        """Enable ChatGPT subscription mode (uses the Codex CLI, no API key)."""
        self.auth_mode_changed.emit("openai", "subscription")
        self.openai_sub_status.setText("Subscription mode enabled (using Codex CLI)")
        self.openai_sub_status.setObjectName("statusTextSuccess")
        self.openai_sub_status.style().unpolish(self.openai_sub_status)
        self.openai_sub_status.style().polish(self.openai_sub_status)
        self.enable_openai_sub_btn.hide()
        self.disable_openai_sub_btn.show()
        show_toast(
            self.window(),
            "ChatGPT subscription enabled! OpenAI models will use your Codex CLI auth.",
            "success",
        )

    def _on_disable_openai_sub(self):
        """Disable ChatGPT subscription mode, fall back to API key."""
        self.auth_mode_changed.emit("openai", "none")
        self.openai_sub_status.setText("")
        self.enable_openai_sub_btn.show()
        self.disable_openai_sub_btn.hide()
        show_toast(self.window(), "ChatGPT subscription disabled.", "info")

    def _on_gemini_enable_sub(self):
        """Enable Gemini subscription mode (gemini CLI)."""
        import subprocess
        try:
            import shutil
            exe = shutil.which("gemini")
            if not exe:
                raise FileNotFoundError
            result = subprocess.run(
                [exe, "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                raise FileNotFoundError
        except (FileNotFoundError, Exception):
            show_toast(
                self.window(),
                "gemini CLI not found. Install it and run 'gemini auth login' first.",
                "error",
            )
            return

        self.auth_mode_changed.emit("gemini", "subscription")
        self.gemini_sub_status.setText("Active — using gemini CLI")
        self.gemini_sub_status.setObjectName("statusTextSuccess")
        self.gemini_sub_status.style().unpolish(self.gemini_sub_status)
        self.gemini_sub_status.style().polish(self.gemini_sub_status)
        self.gemini_enable_sub_btn.hide()
        self.gemini_disable_sub_btn.show()
        show_toast(self.window(), "Gemini CLI subscription enabled.", "success")

    def _on_gemini_disable_sub(self):
        """Disable Gemini subscription mode, fall back to API key."""
        self.auth_mode_changed.emit("gemini", "none")
        self.gemini_sub_status.setText("")
        self.gemini_enable_sub_btn.show()
        self.gemini_disable_sub_btn.hide()
        show_toast(self.window(), "Gemini subscription disabled.", "info")

    def _on_auth_mode_changed(self, provider: str, button_id: int):
        mode_map = {0: "none", 1: "api", 2: "subscription"}
        mode = mode_map.get(button_id, "none")
        self.auth_mode_changed.emit(provider, mode)
        show_toast(self.window(), f"{provider.title()} auth mode set to '{mode}'.", "success")

    def _update_autonomy_description(self, level: str):
        descriptions = {
            "observer": "All actions require your approval before execution.",
            "supervised": "Email sending, CRM sync, and skill revision need approval. Scraping and analysis run freely.",
            "autonomous": "Only skill revision and self-improvement need approval. Most actions run automatically.",
            "full_trust": "Fully autonomous — all actions execute without approval.",
        }
        self.autonomy_description.setText(descriptions.get(level, ""))

    def _on_save_ai_toggles(self):
        self.save_toggles_requested.emit({
            "reflection_enabled": self.reflection_toggle.isChecked(),
            "self_improvement_enabled": self.self_improvement_toggle.isChecked(),
            "knowledge_graph_enabled": self.knowledge_graph_toggle.isChecked(),
            "conversation_engine_enabled": self.conversation_toggle.isChecked(),
        })
        show_toast(self.window(), "AI engine settings saved.", "success")

    def _on_save_rv_config(self):
        self.save_toggles_requested.emit({
            "research_auto_enabled": self.research_auto_toggle.isChecked(),
            "voice_call_enabled": self.voice_call_toggle.isChecked(),
            "twilio_phone_number": self.twilio_phone_input.text().strip(),
            "elevenlabs_voice_id": self.elevenlabs_voice_id_input.text().strip(),
            "voice_tts_provider": self.tts_provider_combo.currentText(),
            "voice_stt_provider": self.stt_provider_combo.currentText(),
        })
        show_toast(self.window(), "Research & Voice settings saved.", "success")

    # ── Business tab handlers ─────────────────────────────────────────

    def _on_save_company_info(self):
        self.save_business_requested.emit({
            "company_legal_name": self.company_legal_name.text().strip(),
            "company_address": self.company_address.toPlainText().strip(),
            "company_tax_id": self.company_tax_id.text().strip(),
            "company_email": self.company_email.text().strip(),
            "company_phone": self.company_phone.text().strip(),
            "company_website": self.company_website.text().strip(),
            "company_logo_path": self.company_logo_path.text().strip(),
            "telegram_owner_chat_id": self.telegram_owner_chat_id.text().strip(),
        })
        show_toast(self.window(), "Company information saved.", "success")

    def _on_save_banking(self):
        self.save_business_requested.emit({
            "company_bank_name": self.company_bank_name.text().strip(),
            "company_swift": self.company_swift.text().strip(),
            "company_iban": self.company_iban.text().strip(),
        })
        show_toast(self.window(), "Banking details saved.", "success")

    def _on_save_invoice_config(self):
        self.save_business_requested.emit({
            "invoice_prefix": self.invoice_prefix.text().strip(),
            "invoice_next_number": self.invoice_next_number.value(),
            "invoice_currency": self.invoice_currency.currentText(),
            "payment_terms_days": self.payment_terms_days.value(),
            "invoice_notes": self.invoice_notes.toPlainText().strip(),
        })
        show_toast(self.window(), "Invoice configuration saved.", "success")

    def _on_browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Company Logo", "",
            "Images (*.png *.jpg *.jpeg *.svg *.bmp)"
        )
        if path:
            self.company_logo_path.setText(path)

    # ── Knowledge Base tab handlers ───────────────────────────────────

    def _on_save_kb_product(self):
        fields = {
            "name": self.kb_product_name.text().strip(),
            "description": self.kb_product_description.toPlainText().strip(),
            "value_proposition": self.kb_product_value_prop.text().strip(),
            "price_range": self.kb_product_price_range.text().strip(),
        }
        for key, value in fields.items():
            if value:
                self.save_kb_entry_requested.emit("product", key, value)
        show_toast(self.window(), "Product definition saved.", "success")

    def _on_save_kb_icp(self):
        fields = {
            "industry": self.kb_icp_industry.text().strip(),
            "company_size": self.kb_icp_company_size.text().strip(),
            "decision_maker": self.kb_icp_decision_maker.text().strip(),
            "pain_points": self.kb_icp_pain_points.toPlainText().strip(),
            "disqualifiers": self.kb_icp_disqualifiers.text().strip(),
        }
        for key, value in fields.items():
            if value:
                self.save_kb_entry_requested.emit("icp", key, value)
        show_toast(self.window(), "ICP definition saved.", "success")

    def _on_save_kb_approach(self):
        fields = {
            "tone": self.kb_approach_tone.currentText(),
            "style": self.kb_approach_style.toPlainText().strip(),
            "default_cta": self.kb_approach_cta.text().strip(),
        }
        for key, value in fields.items():
            if value:
                self.save_kb_entry_requested.emit("approach", key, value)
        show_toast(self.window(), "Sales approach saved.", "success")

    def load_kb_entries(self, entries: list):
        """Populate KB tab fields from a list of entry dicts."""
        kb = {}
        for e in entries:
            kb[(e["category"], e["key"])] = e["value"]

        # Product
        self.kb_product_name.setText(kb.get(("product", "name"), ""))
        self.kb_product_description.setPlainText(kb.get(("product", "description"), ""))
        self.kb_product_value_prop.setText(kb.get(("product", "value_proposition"), ""))
        self.kb_product_price_range.setText(kb.get(("product", "price_range"), ""))

        # ICP
        self.kb_icp_industry.setText(kb.get(("icp", "industry"), ""))
        self.kb_icp_company_size.setText(kb.get(("icp", "company_size"), ""))
        self.kb_icp_decision_maker.setText(kb.get(("icp", "decision_maker"), ""))
        self.kb_icp_pain_points.setPlainText(kb.get(("icp", "pain_points"), ""))
        self.kb_icp_disqualifiers.setText(kb.get(("icp", "disqualifiers"), ""))

        # Approach
        tone = kb.get(("approach", "tone"), "professional")
        tone_idx = self.kb_approach_tone.findText(tone)
        if tone_idx >= 0:
            self.kb_approach_tone.setCurrentIndex(tone_idx)
        self.kb_approach_style.setPlainText(kb.get(("approach", "style"), ""))
        self.kb_approach_cta.setText(kb.get(("approach", "default_cta"), ""))

    def receive_context(self, context: dict):
        pass
