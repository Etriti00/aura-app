"""
Aura — Settings Page (Full Implementation)
API key management, model selection, sender identity, SMTP config, theme toggle.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QSpinBox, QScrollArea, QFrame, QCheckBox,
    QRadioButton, QButtonGroup, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon

from ui.components.glass_card import GlassCard
from ui.components.modern_button import ModernButton
from ui.components.masked_input import MaskedInput
from ui.components.toast_notification import show_toast
from ui.icons import get_icon, get_pixmap


class SettingsPage(QWidget):
    """Settings page — API keys, models, SMTP, sender info, theme."""

    # Signals to controller
    save_key_requested = Signal(str, str)             # provider, key
    save_models_requested = Signal(str, str)           # tier2, tier3
    save_chat_model_requested = Signal(str)            # chat model
    save_sender_requested = Signal(str, str, str)      # name, email, company
    save_smtp_requested = Signal(str, int, str, str)   # host, port, user, pass
    save_imap_requested = Signal(str, int, str, str, bool) # host, port, user, pass, use_ssl
    save_toggles_requested = Signal(dict)              # dict of feature_name: bool
    theme_change_requested = Signal(str)               # "light" or "dark"
    save_anthropic_sub_requested = Signal(str)         # setup-token
    openai_oauth_requested = Signal()                  # trigger OAuth flow
    openai_disconnect_requested = Signal()             # clear OpenAI sub tokens
    auth_mode_changed = Signal(str, str)               # provider, mode
    autonomy_level_changed = Signal(str)                # new autonomy level

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(0)
        scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        content = QWidget()
        content.setObjectName("centralWidget")
        content.setMinimumWidth(0)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        # Header
        header_text = QVBoxLayout()
        title = QLabel("Settings")
        title.setObjectName("sectionHeader")
        header_text.addWidget(title)
        subtitle = QLabel("Configure API keys, models, and delivery")
        subtitle.setObjectName("sectionSubheader")
        header_text.addWidget(subtitle)
        layout.addLayout(header_text)

        # ─── API Keys Section ──────────────────────────────────────────
        key_card = GlassCard()
        key_layout = key_card.get_layout()
        self._icon_header("section_keys", "API Keys", key_layout)
        key_info = QLabel("Keys are encrypted with hardware-bound encryption and stored locally.")
        key_info.setObjectName("mutedText")
        key_layout.addWidget(key_info)

        # Gemini
        self.gemini_input = self._add_key_row(key_layout, "Google Gemini", "gemini")
        # Anthropic
        self.anthropic_input = self._add_key_row(key_layout, "Anthropic", "anthropic")
        # OpenAI
        self.openai_input = self._add_key_row(key_layout, "OpenAI", "openai")
        # Resend
        self.resend_input = self._add_key_row(key_layout, "Resend (Email)", "resend")
        # Apollo.io
        self.apollo_input = self._add_key_row(key_layout, "Apollo.io", "apollo")
        # Hunter.io
        self.hunter_input = self._add_key_row(key_layout, "Hunter.io", "hunter")
        # HubSpot
        self.hubspot_input = self._add_key_row(key_layout, "HubSpot CRM", "hubspot")
        # Pipedrive
        self.pipedrive_input = self._add_key_row(key_layout, "Pipedrive CRM", "pipedrive")
        # OpenRouter
        self.openrouter_input = self._add_key_row(key_layout, "OpenRouter", "openrouter")
        # Research APIs
        self.tavily_input = self._add_key_row(key_layout, "Tavily (AI Search)", "tavily")
        self.firecrawl_input = self._add_key_row(key_layout, "Firecrawl (Web Crawl)", "firecrawl")
        self.apify_input = self._add_key_row(key_layout, "Apify (Scraping)", "apify")
        # Voice APIs
        self.twilio_sid_input = self._add_key_row(key_layout, "Twilio Account SID", "twilio_sid")
        self.twilio_token_input = self._add_key_row(key_layout, "Twilio Auth Token", "twilio_token")
        self.elevenlabs_input = self._add_key_row(key_layout, "ElevenLabs (TTS)", "elevenlabs")
        or_info = QLabel(
            "Don't have individual API keys? Use OpenRouter for one-key access "
            "to all models (OpenAI, Anthropic, Google) at openrouter.ai"
        )
        or_info.setObjectName("mutedText")
        or_info.setWordWrap(True)
        key_layout.addWidget(or_info)

        layout.addWidget(key_card)

        # ─── Authentication Mode ──────────────────────────────────────
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

        # ─── Subscription Auth ────────────────────────────────────────
        sub_card = GlassCard()
        sub_layout = sub_card.get_layout()
        self._icon_header("section_subscription", "Subscription Auth", sub_layout)
        sub_info = QLabel(
            "Use your existing Claude Pro/Max or ChatGPT Plus subscription "
            "instead of separate API keys."
        )
        sub_info.setObjectName("mutedText")
        sub_info.setWordWrap(True)
        sub_layout.addWidget(sub_info)

        # Anthropic (Claude) subscription
        anthropic_sub_label = QLabel("Anthropic — Claude Subscription")
        anthropic_sub_label.setObjectName("formLabel")
        sub_layout.addWidget(anthropic_sub_label)
        anthropic_sub_info = QLabel(
            "Run 'claude setup-token' in your terminal (requires Claude Code CLI), "
            "then paste the token below."
        )
        anthropic_sub_info.setObjectName("mutedText")
        anthropic_sub_info.setWordWrap(True)
        sub_layout.addWidget(anthropic_sub_info)

        anthropic_sub_row = QHBoxLayout()
        self.anthropic_sub_input = MaskedInput("Paste setup-token here...")
        anthropic_sub_row.addWidget(self.anthropic_sub_input, stretch=1)
        self.save_anthropic_sub_btn = ModernButton("Save Token", "secondary")
        self.save_anthropic_sub_btn.setFixedHeight(40)
        self.save_anthropic_sub_btn.setMinimumWidth(100)
        self.save_anthropic_sub_btn.clicked.connect(self._on_save_anthropic_sub)
        anthropic_sub_row.addWidget(self.save_anthropic_sub_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        sub_layout.addLayout(anthropic_sub_row)

        self.anthropic_sub_status = QLabel("")
        self.anthropic_sub_status.setObjectName("mutedText")
        sub_layout.addWidget(self.anthropic_sub_status)

        # OpenAI (ChatGPT) subscription
        openai_sub_label = QLabel("OpenAI — ChatGPT Subscription")
        openai_sub_label.setObjectName("formLabel")
        sub_layout.addWidget(openai_sub_label)
        openai_sub_info = QLabel(
            "Sign in with your ChatGPT account to use your subscription. "
            "A browser window will open for authentication."
        )
        openai_sub_info.setObjectName("mutedText")
        openai_sub_info.setWordWrap(True)
        sub_layout.addWidget(openai_sub_info)

        openai_sub_row = QHBoxLayout()
        self.openai_sign_in_btn = ModernButton("Sign in with ChatGPT", "primary")
        self.openai_sign_in_btn.setFixedHeight(40)
        self.openai_sign_in_btn.clicked.connect(self._on_openai_sign_in)
        openai_sub_row.addWidget(self.openai_sign_in_btn)
        self.openai_disconnect_btn = ModernButton("Disconnect", "danger")
        self.openai_disconnect_btn.setFixedHeight(40)
        self.openai_disconnect_btn.clicked.connect(self._on_openai_disconnect)
        self.openai_disconnect_btn.hide()
        openai_sub_row.addWidget(self.openai_disconnect_btn)
        openai_sub_row.addStretch()
        sub_layout.addLayout(openai_sub_row)

        self.openai_sub_status = QLabel("")
        self.openai_sub_status.setObjectName("mutedText")
        sub_layout.addWidget(self.openai_sub_status)

        # Google Gemini note
        gemini_sub_label = QLabel("Google — Gemini")
        gemini_sub_label.setObjectName("formLabel")
        sub_layout.addWidget(gemini_sub_label)
        gemini_sub_info = QLabel(
            "Gemini API keys are free to generate at aistudio.google.com — "
            "no paid subscription required. Enter your key in the API Keys section above."
        )
        gemini_sub_info.setObjectName("mutedText")
        gemini_sub_info.setWordWrap(True)
        sub_layout.addWidget(gemini_sub_info)

        layout.addWidget(sub_card)

        # ─── Model Selection ───────────────────────────────────────────
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
        t2_col.addWidget(self.tier2_combo)
        model_row.addLayout(t2_col, stretch=1)

        t3_col = QVBoxLayout()
        t3_col.setSpacing(4)
        t3_label = QLabel("Tier 3 — Email Gen (Premium)")
        t3_label.setObjectName("formLabel")
        t3_col.addWidget(t3_label)
        self.tier3_combo = QComboBox()
        self.tier3_combo.addItems([
            "anthropic/claude-sonnet-4-6",
            "anthropic/claude-sonnet-4-5",
            "openai/gpt-4.1",
            "openai/gpt-4o",
            "gemini/gemini-2.5-pro-preview",
            "gemini/gemini-1.5-pro-latest",
            "openrouter/anthropic/claude-sonnet-4-5",
            "openrouter/openai/gpt-4.1",
            "openrouter/auto",
            "ollama/llama3:70b",
        ])
        t3_col.addWidget(self.tier3_combo)
        model_row.addLayout(t3_col, stretch=1)

        chat_col = QVBoxLayout()
        chat_col.setSpacing(4)
        chat_label = QLabel("Chat — Aura Assistant")
        chat_label.setObjectName("formLabel")
        chat_col.addWidget(chat_label)
        self.chat_model_combo = QComboBox()
        self.chat_model_combo.addItems([
            "anthropic/claude-sonnet-4-6",
            "anthropic/claude-sonnet-4-5",
            "anthropic/claude-haiku-4-5",
            "openai/gpt-4.1",
            "openai/gpt-4.1-mini",
            "openai/gpt-4o",
            "gemini/gemini-2.5-pro-preview",
            "gemini/gemini-2.0-flash",
            "openrouter/anthropic/claude-sonnet-4-5",
            "openrouter/openai/gpt-4.1",
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

        # ─── Sender Info ───────────────────────────────────────────────
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

        # ─── SMTP Config ──────────────────────────────────────────────
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

        # ─── Theme Toggle ─────────────────────────────────────────────
        theme_card = GlassCard()
        theme_layout = theme_card.get_layout()
        self._icon_header("section_appearance", "Appearance", theme_layout)

        theme_row = QHBoxLayout()
        theme_label = QLabel("Theme")
        theme_label.setObjectName("formLabel")
        theme_row.addWidget(theme_label)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()

        theme_layout.addLayout(theme_row)
        layout.addWidget(theme_card)

        # ─── IMAP Configuration ──────────────────────────────────────
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

        # ─── Feature Toggles ─────────────────────────────────────────
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

        # CRM platform selector
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

        # ─── Research & Voice Config ─────────────────────────────────
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

        # ─── Autonomy Control ────────────────────────────────────────
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

        # ─── Advanced AI Toggles ─────────────────────────────────────
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
        scroll.setWidget(content)

        # Main layout wraps the scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # ─── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _icon_header(icon_key: str, text: str, parent_layout, theme: str = "dark"):
        """Add a section header with icon + text to a layout."""
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
        """Add a key input row with a save button."""
        row = QHBoxLayout()

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label(label))
        masked = MaskedInput(f"Enter {label} API key...")
        col.addWidget(masked)
        row.addLayout(col, stretch=1)

        save_btn = ModernButton("Save", "secondary")
        save_btn.setFixedHeight(40)
        save_btn.setMinimumWidth(80)  # Flexible width
        save_btn.clicked.connect(lambda: self._on_save_key(provider, masked))
        row.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        parent_layout.addLayout(row)
        return masked

    # ─── Public Methods ────────────────────────────────────────────────

    def load_settings(self, settings: dict):
        """Populate fields from controller settings dict."""
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

        # Research & Voice API keys
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

        # Theme
        theme_idx = self.theme_combo.findText(settings.get("theme", "light"))
        if theme_idx >= 0:
            self.theme_combo.setCurrentIndex(theme_idx)

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

        # Autonomy level
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
        if settings.get("has_anthropic_sub"):
            self.anthropic_sub_status.setText("Connected (setup-token active)")
            self.anthropic_sub_status.setObjectName("statusTextSuccess")
            self.anthropic_sub_status.style().unpolish(self.anthropic_sub_status)
            self.anthropic_sub_status.style().polish(self.anthropic_sub_status)
        else:
            self.anthropic_sub_status.setText("")

        if settings.get("has_openai_sub"):
            self.openai_sub_status.setText("Connected (ChatGPT subscription active)")
            self.openai_sub_status.setObjectName("statusTextSuccess")
            self.openai_sub_status.style().unpolish(self.openai_sub_status)
            self.openai_sub_status.style().polish(self.openai_sub_status)
            self.openai_sign_in_btn.hide()
            self.openai_disconnect_btn.show()
        else:
            self.openai_sub_status.setText("")
            self.openai_sign_in_btn.show()
            self.openai_disconnect_btn.hide()

    # ─── Signal Emitters ───────────────────────────────────────────────

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

    def _on_save_anthropic_sub(self):
        token = self.anthropic_sub_input.get_value()
        if token:
            self.save_anthropic_sub_requested.emit(token)
            self.anthropic_sub_input.clear()
            self.anthropic_sub_status.setText("Connected (setup-token active)")
            self.anthropic_sub_status.setObjectName("statusTextSuccess")
            self.anthropic_sub_status.style().unpolish(self.anthropic_sub_status)
            self.anthropic_sub_status.style().polish(self.anthropic_sub_status)
            show_toast(self.window(), "Anthropic subscription token saved.", "success")
        else:
            show_toast(self.window(), "Please paste a setup-token.", "warning")

    def _on_openai_sign_in(self):
        self.openai_sign_in_btn.setEnabled(False)
        self.openai_sign_in_btn.setText("Waiting for browser...")
        self.openai_oauth_requested.emit()

    def _on_openai_disconnect(self):
        self.openai_disconnect_requested.emit()
        self.openai_sub_status.setText("")
        self.openai_sign_in_btn.show()
        self.openai_disconnect_btn.hide()
        show_toast(self.window(), "OpenAI subscription disconnected.", "info")

    def on_openai_oauth_complete(self, success: bool, error: str = ""):
        """Called by controller after OAuth flow completes."""
        self.openai_sign_in_btn.setEnabled(True)
        self.openai_sign_in_btn.setText("Sign in with ChatGPT")
        if success:
            self.openai_sub_status.setText("Connected (ChatGPT subscription)")
            self.openai_sub_status.setObjectName("statusTextSuccess")
            self.openai_sub_status.style().unpolish(self.openai_sub_status)
            self.openai_sub_status.style().polish(self.openai_sub_status)
            self.openai_sign_in_btn.hide()
            self.openai_disconnect_btn.show()
            show_toast(self.window(), "ChatGPT subscription connected!", "success")
        else:
            show_toast(self.window(), f"OAuth failed: {error}", "error")

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

    def _on_theme_changed(self, theme: str):
        self.theme_change_requested.emit(theme)

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        pass
