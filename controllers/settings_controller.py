"""
Aura — Settings Controller
Manages app settings: API keys, model selection, SMTP config, theme, sender info.
"""

from PySide6.QtCore import QObject, Signal

from database.db_manager import DatabaseManager
from database.schema import Settings
from core.key_vault import KeyVault
from utils.logger import get_logger

logger = get_logger("settings_controller")


class SettingsController(QObject):
    """CRUD for application settings with encrypted key storage."""

    settings_saved = Signal()
    settings_error = Signal(str)
    theme_changed = Signal(str)  # "light" or "dark"
    auth_mode_changed = Signal(str, str)  # provider, mode

    def __init__(self, db_manager: DatabaseManager, key_vault: KeyVault):
        super().__init__()
        self.db_manager = db_manager
        self.key_vault = key_vault

    def get_settings(self) -> dict:
        """Load current settings as a dict with masked keys."""
        settings = self.db_manager.get_settings()
        if not settings:
            return {}

        return {
            "gemini_key": self._mask_key(settings.gemini_key_enc),
            "anthropic_key": self._mask_key(settings.anthropic_key_enc),
            "openai_key": self._mask_key(settings.openai_key_enc),
            "resend_key": self._mask_key(settings.resend_key_enc),
            "has_gemini": bool(settings.gemini_key_enc),
            "has_anthropic": bool(settings.anthropic_key_enc),
            "has_openai": bool(settings.openai_key_enc),
            "has_resend": bool(settings.resend_key_enc),
            "tier2_model": settings.tier2_model or "",
            "tier3_model": settings.tier3_model or "",
            "theme": settings.theme or "light",
            "sender_name": settings.sender_name or "",
            "sender_email": settings.sender_email or "",
            "sender_company": settings.sender_company or "",
            "smtp_host": settings.smtp_host or "",
            "smtp_port": settings.smtp_port or 587,
            "smtp_user": settings.smtp_user or "",
            "has_smtp_password": bool(settings.smtp_password_enc),
            # Apollo & Hunter
            "apollo_key": self._mask_key(settings.apollo_key_enc),
            "hunter_key": self._mask_key(settings.hunter_key_enc),
            "has_apollo": bool(settings.apollo_key_enc),
            "has_hunter": bool(settings.hunter_key_enc),
            # CRM
            "hubspot_key": self._mask_key(settings.hubspot_key_enc),
            "pipedrive_key": self._mask_key(settings.pipedrive_key_enc),
            "has_hubspot": bool(settings.hubspot_key_enc),
            "has_pipedrive": bool(settings.pipedrive_key_enc),
            "crm_platform": settings.crm_platform or "",
            # IMAP
            "imap_host": settings.imap_host or "",
            "imap_port": settings.imap_port or 993,
            "imap_username": settings.imap_username or "",
            "imap_use_ssl": getattr(settings, "imap_use_ssl", True),
            "has_imap_password": bool(settings.imap_password_enc),
            # Feature toggles
            "ab_test_enabled": getattr(settings, "ab_test_enabled", False),
            "send_schedule_enabled": getattr(settings, "send_schedule_enabled", False),
            "enrichment_enabled": getattr(settings, "enrichment_enabled", True),
            "suppression_enabled": getattr(settings, "suppression_enabled", True),
            "rag_enabled": getattr(settings, "rag_enabled", False),
            "cross_channel_enabled": getattr(settings, "cross_channel_enabled", False),
            "inbox_triage_enabled": getattr(settings, "inbox_triage_enabled", False),
            "fleet_enabled": getattr(settings, "agent_system_enabled", False),
            "trends_enabled": getattr(settings, "trends_enabled", True),
            # Chat model
            "chat_model": settings.chat_model or "anthropic/claude-sonnet-4-5",
            # OpenRouter
            "openrouter_key": self._mask_key(getattr(settings, "openrouter_key_enc", "")),
            "has_openrouter": bool(getattr(settings, "openrouter_key_enc", "")),
            # Subscription auth
            "has_anthropic_sub": bool(getattr(settings, "anthropic_sub_token_enc", "")),
            "has_openai_sub": bool(getattr(settings, "openai_sub_token_enc", "")),
            # Auth modes
            "anthropic_auth_mode": getattr(settings, "anthropic_auth_mode", "none"),
            "openai_auth_mode": getattr(settings, "openai_auth_mode", "none"),
            # Autonomy & advanced AI
            "autonomy_level": getattr(settings, "autonomy_level", "supervised"),
            "reflection_enabled": getattr(settings, "reflection_enabled", True),
            "self_improvement_enabled": getattr(settings, "self_improvement_enabled", False),
            "knowledge_graph_enabled": getattr(settings, "knowledge_graph_enabled", False),
            "conversation_engine_enabled": getattr(settings, "conversation_engine_enabled", False),
            # Research APIs
            "tavily_key": self._mask_key(getattr(settings, "tavily_key_enc", "")),
            "firecrawl_key": self._mask_key(getattr(settings, "firecrawl_key_enc", "")),
            "apify_key": self._mask_key(getattr(settings, "apify_key_enc", "")),
            "has_tavily": bool(getattr(settings, "tavily_key_enc", "")),
            "has_firecrawl": bool(getattr(settings, "firecrawl_key_enc", "")),
            "has_apify": bool(getattr(settings, "apify_key_enc", "")),
            "research_auto_enabled": getattr(settings, "research_auto_enabled", True),
            # Voice
            "twilio_sid_key": self._mask_key(getattr(settings, "twilio_account_sid_enc", "")),
            "twilio_token_key": self._mask_key(getattr(settings, "twilio_auth_token_enc", "")),
            "elevenlabs_key": self._mask_key(getattr(settings, "elevenlabs_key_enc", "")),
            "has_twilio": bool(getattr(settings, "twilio_account_sid_enc", "")),
            "has_elevenlabs": bool(getattr(settings, "elevenlabs_key_enc", "")),
            "voice_call_enabled": getattr(settings, "voice_call_enabled", False),
            "twilio_phone_number": getattr(settings, "twilio_phone_number", ""),
            "elevenlabs_voice_id": getattr(settings, "elevenlabs_voice_id", ""),
            "voice_tts_provider": getattr(settings, "voice_tts_provider", "elevenlabs"),
            "voice_stt_provider": getattr(settings, "voice_stt_provider", "whisper_local"),
        }

    def save_api_key(self, provider: str, key: str):
        """Save a single API key (encrypted)."""
        field_map = {
            "gemini": "gemini_key_enc",
            "anthropic": "anthropic_key_enc",
            "openai": "openai_key_enc",
            "resend": "resend_key_enc",
            "apollo": "apollo_key_enc",
            "hunter": "hunter_key_enc",
            "hubspot": "hubspot_key_enc",
            "pipedrive": "pipedrive_key_enc",
            "openrouter": "openrouter_key_enc",
            "tavily": "tavily_key_enc",
            "firecrawl": "firecrawl_key_enc",
            "apify": "apify_key_enc",
            "twilio_sid": "twilio_account_sid_enc",
            "twilio_token": "twilio_auth_token_enc",
            "elevenlabs": "elevenlabs_key_enc",
        }

        field = field_map.get(provider)
        if not field:
            self.settings_error.emit(f"Unknown provider: {provider}")
            return

        try:
            encrypted = self.key_vault.encrypt(key) if key else ""
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    setattr(settings, field, encrypted)

            # Auto-set auth mode when saving a key
            if key and provider in ("anthropic", "openai"):
                with self.db_manager.session_scope() as session:
                    s = session.query(Settings).first()
                    if s:
                        setattr(s, f"{provider}_auth_mode", "api")

            self.settings_saved.emit()
            logger.info(f"Saved API key for {provider}")
        except Exception as e:
            self.settings_error.emit(f"Failed to save key: {e}")

    def save_auth_mode(self, provider: str, mode: str):
        """Save auth mode for a provider (api/subscription/none)."""
        field = f"{provider}_auth_mode"
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings and hasattr(settings, field):
                    setattr(settings, field, mode)
            self.auth_mode_changed.emit(provider, mode)
            self.settings_saved.emit()
            logger.info(f"Auth mode for {provider} set to '{mode}'")
        except Exception as e:
            self.settings_error.emit(f"Failed to save auth mode: {e}")

    def save_models(self, tier2: str, tier3: str):
        """Save model selections."""
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    settings.tier2_model = tier2
                    settings.tier3_model = tier3

            self.settings_saved.emit()
            logger.info(f"Models saved: T2={tier2}, T3={tier3}")
        except Exception as e:
            self.settings_error.emit(f"Failed to save models: {e}")

    def save_sender_info(self, name: str, email: str, company: str):
        """Save sender identity."""
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    settings.sender_name = name
                    settings.sender_email = email
                    settings.sender_company = company

            self.settings_saved.emit()
        except Exception as e:
            self.settings_error.emit(f"Failed to save sender info: {e}")

    def save_smtp(self, host: str, port: int, user: str, password: str):
        """Save SMTP configuration."""
        try:
            enc_pass = self.key_vault.encrypt(password) if password else ""
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    settings.smtp_host = host
                    settings.smtp_port = port
                    settings.smtp_user = user
                    settings.smtp_password_enc = enc_pass

            self.settings_saved.emit()
        except Exception as e:
            self.settings_error.emit(f"Failed to save SMTP: {e}")

    def save_imap(self, host: str, port: int, username: str, password: str, use_ssl: bool):
        """Save IMAP configuration."""
        try:
            enc_pass = self.key_vault.encrypt(password) if password else ""
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    settings.imap_host = host
                    settings.imap_port = port
                    settings.imap_username = username
                    settings.imap_password_enc = enc_pass
                    settings.imap_use_ssl = use_ssl

            self.settings_saved.emit()
        except Exception as e:
            self.settings_error.emit(f"Failed to save IMAP: {e}")

    def save_toggles(self, toggles: dict):
        """Save feature toggles."""
        # Map UI toggle names to schema column names
        field_map = {
            "fleet_enabled": "agent_system_enabled",
        }
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    for key, value in toggles.items():
                        col = field_map.get(key, key)
                        if hasattr(settings, col):
                            setattr(settings, col, value)

            self.settings_saved.emit()
            logger.info(f"Feature toggles saved: {list(toggles.keys())}")
        except Exception as e:
            self.settings_error.emit(f"Failed to save toggles: {e}")

    def save_chat_model(self, model: str):
        """Save chat model selection."""
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    settings.chat_model = model

            self.settings_saved.emit()
            logger.info(f"Chat model saved: {model}")
        except Exception as e:
            self.settings_error.emit(f"Failed to save chat model: {e}")

    def set_theme(self, theme: str):
        """Switch theme and persist."""
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    settings.theme = theme
            self.theme_changed.emit(theme)
        except Exception as e:
            self.settings_error.emit(f"Failed to change theme: {e}")

    def save_anthropic_sub_token(self, token: str):
        """Save Anthropic subscription (setup-token)."""
        try:
            encrypted = self.key_vault.encrypt(token) if token else ""
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    settings.anthropic_sub_token_enc = encrypted

            # Auto-set auth mode to subscription
            with self.db_manager.session_scope() as session:
                s = session.query(Settings).first()
                if s:
                    s.anthropic_auth_mode = "subscription"

            self.settings_saved.emit()
            logger.info("Anthropic subscription token saved")
        except Exception as e:
            self.settings_error.emit(f"Failed to save Anthropic token: {e}")

    def save_openai_sub_tokens(self, access_token: str, refresh_token: str):
        """Save OpenAI subscription OAuth tokens."""
        try:
            enc_access = self.key_vault.encrypt(access_token) if access_token else ""
            enc_refresh = self.key_vault.encrypt(refresh_token) if refresh_token else ""
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    settings.openai_sub_token_enc = enc_access
                    settings.openai_sub_refresh_enc = enc_refresh

            # Auto-set auth mode to subscription
            if access_token:
                with self.db_manager.session_scope() as session:
                    s = session.query(Settings).first()
                    if s:
                        s.openai_auth_mode = "subscription"

            self.settings_saved.emit()
            logger.info("OpenAI subscription tokens saved")
        except Exception as e:
            self.settings_error.emit(f"Failed to save OpenAI tokens: {e}")

    def clear_sub_token(self, provider: str):
        """Clear a subscription token."""
        field_map = {
            "anthropic": "anthropic_sub_token_enc",
            "openai_access": "openai_sub_token_enc",
            "openai_refresh": "openai_sub_refresh_enc",
        }
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    if provider == "openai":
                        settings.openai_sub_token_enc = ""
                        settings.openai_sub_refresh_enc = ""
                    elif provider in field_map:
                        setattr(settings, field_map[provider], "")
            self.settings_saved.emit()
        except Exception as e:
            self.settings_error.emit(f"Failed to clear token: {e}")

    def get_decrypted_sub_tokens(self) -> dict:
        """Get decrypted subscription tokens for AI engine use."""
        settings = self.db_manager.get_settings()
        if not settings:
            return {}
        tokens = {}
        for name, field in [
            ("anthropic_sub", "anthropic_sub_token_enc"),
            ("openai_sub", "openai_sub_token_enc"),
            ("openai_refresh", "openai_sub_refresh_enc"),
        ]:
            enc = getattr(settings, field, "")
            if enc:
                try:
                    tokens[name] = self.key_vault.decrypt(enc)
                except Exception:
                    pass
        return tokens

    def _mask_key(self, encrypted_key: str) -> str:
        """Return a masked version of an encrypted key."""
        if not encrypted_key:
            return ""
        try:
            decrypted = self.key_vault.decrypt(encrypted_key)
            return self.key_vault.mask(decrypted)
        except Exception:
            return "****"
