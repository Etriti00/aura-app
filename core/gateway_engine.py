"""
Aura — Gateway Engine
Central message router between external messaging platforms and
Aura's orchestrator. Handles authorization, message normalization,
intent routing, and response formatting.
"""

from typing import Optional

from database.db_manager import DatabaseManager
from database.schema import GatewayConfig, AuthorizedUser
from core.key_vault import KeyVault
from core.response_formatter import ResponseFormatter, from_intent_result, Platform
from config import GATEWAY_MAX_MESSAGE_LENGTH
from utils.logger import get_logger

logger = get_logger("gateway_engine")


class GatewayEngine:
    """
    Central gateway for external messaging platforms.
    Routes inbound messages through the orchestrator and formats responses.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        key_vault: KeyVault,
        orchestrator_engine=None,
        engines_dict: dict = None,
    ):
        self.db_manager = db_manager
        self.key_vault = key_vault
        self.orchestrator = orchestrator_engine
        self.engines = engines_dict or {}
        self._adapters = {}  # platform → adapter instance (set by controller)
        self.command_history = None  # injected by main_window
        self._formatter = ResponseFormatter()

    # ─── Inbound message handling ──────────────────────────────────

    def handle_inbound(self, platform: str, sender_id: str, text: str,
                       media=None) -> dict:
        """
        Process an inbound message from an external platform.
        1. Authorize sender
        2. Parse intent via orchestrator
        3. Execute if confident
        4. Format and return response
        """
        # Step 1: Authorization check
        if not self.is_authorized(platform, sender_id):
            logger.warning(
                f"Unauthorized message from {platform}:{sender_id} — dropped"
            )
            return {"authorized": False, "response_text": None}

        if not self.orchestrator:
            return {
                "authorized": True,
                "response_text": "Aura orchestrator not available.",
                "intent": None,
            }

        # Log inbound command
        root_cmd_id = None
        if self.command_history:
            try:
                cmd_entry = self.command_history.log_user_command(
                    source=platform, text=text, sender_id=str(sender_id),
                )
                root_cmd_id = cmd_entry.get("data", {}).get("id") if cmd_entry.get("success") else None
            except Exception:
                pass

        try:
            # Step 2: Parse intent
            context = {"source": f"gateway:{platform}", "sender_id": sender_id}
            intent_dict = self.orchestrator.parse_intent(text, context)

            intent = intent_dict.get("intent", "general_question")
            confidence = intent_dict.get("confidence", 0)
            response_text = intent_dict.get("response_text", "")

            # Step 3: Execute if confident
            if not intent_dict.get("clarification_needed") and confidence >= 0.5:
                result = self.orchestrator.execute_intent(intent_dict, self.engines)
                # Build a response from the execution result
                response_text = self._build_response_for_platform(intent, result, response_text, platform)

            # Step 4: Format for platform
            formatted = self._format_response(platform, response_text)

            # Update command history with result
            if self.command_history and root_cmd_id:
                try:
                    self.command_history.update_command_status(
                        root_cmd_id, "completed",
                        result={"intent": intent, "response": formatted[:500], "confidence": confidence},
                    )
                except Exception:
                    pass

            return {
                "authorized": True,
                "response_text": formatted,
                "intent": intent,
                "confidence": confidence,
            }

        except Exception as e:
            logger.error(f"Gateway inbound error: {e}")
            if self.command_history and root_cmd_id:
                try:
                    self.command_history.update_command_status(
                        root_cmd_id, "failed", result={"error": str(e)[:500]},
                    )
                except Exception:
                    pass
            return {
                "authorized": True,
                "response_text": f"Error processing request: {str(e)[:200]}",
                "intent": None,
            }

    def _build_response_for_platform(self, intent: str, result: dict,
                                      fallback: str, platform: str) -> str:
        """Build a platform-specific response."""
        structured = from_intent_result(intent, result, fallback)
        platform_map = {
            "telegram": Platform.TELEGRAM,
            "discord": Platform.DISCORD,
            "cli": Platform.CLI,
        }
        target = platform_map.get(platform, Platform.DISCORD)
        return self._formatter.render(structured, target)

    # ─── Authorization ─────────────────────────────────────────────

    def is_authorized(self, platform: str, sender_id: str) -> bool:
        """Check if a sender is in the authorized users list."""
        try:
            with self.db_manager.session_scope() as session:
                user = (
                    session.query(AuthorizedUser)
                    .filter_by(
                        platform=platform,
                        platform_user_id=str(sender_id),
                        is_active=True,
                    )
                    .first()
                )
                return user is not None
        except Exception as e:
            logger.error(f"Authorization check error: {e}")
            return False

    def add_authorized_user(self, platform: str, user_id: str,
                            display_name: str = "") -> dict:
        """Add a user to the authorized list."""
        try:
            with self.db_manager.session_scope() as session:
                existing = (
                    session.query(AuthorizedUser)
                    .filter_by(platform=platform, platform_user_id=str(user_id))
                    .first()
                )
                if existing:
                    existing.is_active = True
                    existing.display_name = display_name or existing.display_name
                    return {"success": True, "action": "reactivated"}

                user = AuthorizedUser(
                    platform=platform,
                    platform_user_id=str(user_id),
                    display_name=display_name,
                    is_active=True,
                )
                session.add(user)
                return {"success": True, "action": "added"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_authorized_user(self, platform: str, user_id: str) -> dict:
        """Remove (deactivate) a user from the authorized list."""
        try:
            with self.db_manager.session_scope() as session:
                user = (
                    session.query(AuthorizedUser)
                    .filter_by(platform=platform, platform_user_id=str(user_id))
                    .first()
                )
                if user:
                    user.is_active = False
                    return {"success": True}
                return {"success": False, "error": "User not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_authorized_users(self) -> list:
        """Get all authorized users."""
        try:
            with self.db_manager.session_scope() as session:
                users = session.query(AuthorizedUser).filter_by(is_active=True).all()
                return [
                    {
                        "platform": u.platform,
                        "user_id": u.platform_user_id,
                        "display_name": u.display_name,
                    }
                    for u in users
                ]
        except Exception:
            return []

    # ─── Response formatting ───────────────────────────────────────

    def _format_response(self, platform: str, text: str) -> str:
        """Format response text for a specific platform."""
        if not text:
            return ""

        # Truncate to platform limit
        if len(text) > GATEWAY_MAX_MESSAGE_LENGTH:
            text = text[:GATEWAY_MAX_MESSAGE_LENGTH - 20] + "\n\n[truncated]"

        if platform == "telegram":
            # Telegram supports HTML: convert markdown bold to HTML
            text = text.replace("**", "<b>").replace("__", "<i>")

        # Discord supports markdown natively — no conversion needed

        return text

    # ─── Proactive notifications ───────────────────────────────────

    def broadcast(self, message: str) -> dict:
        """
        Send a proactive notification to all authorized users
        on all connected platforms.
        """
        sent_to = []
        users = self.get_authorized_users()

        for user in users:
            platform = user["platform"]
            user_id = user["user_id"]
            adapter = self._adapters.get(platform)

            if adapter and adapter.is_connected():
                try:
                    formatted = self._format_response(platform, message)
                    adapter.send_message(user_id, formatted)
                    sent_to.append({"platform": platform, "user_id": user_id})
                except Exception as e:
                    logger.error(
                        f"Broadcast failed to {platform}:{user_id}: {e}"
                    )

        return {"sent_to": sent_to, "total": len(sent_to)}

    # ─── Event notifications (real-time channel updates) ────────────

    def notify_event(self, event_type: str, data: dict):
        """
        Send a real-time notification to appropriate channels on all platforms.
        Used by engines to push updates (lead found, reply detected, approval needed, etc.).
        """
        for platform, adapter in self._adapters.items():
            if adapter and adapter.is_connected():
                try:
                    # Adapters with server mode (discord_server, telegram_notifications)
                    # will handle routing to the correct channel
                    notification_router = getattr(adapter, "notification_router", None)
                    if notification_router:
                        notification_router.route_event(event_type, data)
                    else:
                        # Fallback: broadcast to all authorized users as text
                        text = f"[{event_type}] {data.get('message', str(data))}"
                        formatted = self._format_response(platform, text)
                        users = self.get_authorized_users()
                        for user in users:
                            if user["platform"] == platform:
                                adapter.send_message(user["user_id"], formatted)
                except Exception as e:
                    logger.error(f"Notify event '{event_type}' failed on {platform}: {e}")

    # ─── Gateway config persistence ────────────────────────────────

    def save_gateway_config(self, platform: str, bot_token: str,
                            is_enabled: bool) -> dict:
        """Save or update gateway configuration for a platform."""
        try:
            with self.db_manager.session_scope() as session:
                config = (
                    session.query(GatewayConfig)
                    .filter_by(platform=platform)
                    .first()
                )
                enc_token = self.key_vault.encrypt(bot_token) if bot_token else ""

                if config:
                    config.bot_token_enc = enc_token
                    config.is_enabled = is_enabled
                else:
                    config = GatewayConfig(
                        platform=platform,
                        bot_token_enc=enc_token,
                        is_enabled=is_enabled,
                    )
                    session.add(config)
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_gateway_config(self, platform: str) -> dict:
        """Load gateway config for a platform."""
        try:
            with self.db_manager.session_scope() as session:
                config = (
                    session.query(GatewayConfig)
                    .filter_by(platform=platform)
                    .first()
                )
                if config:
                    token = ""
                    if config.bot_token_enc:
                        try:
                            token = self.key_vault.decrypt(config.bot_token_enc)
                        except Exception:
                            pass
                    return {
                        "platform": platform,
                        "has_token": bool(token),
                        "is_enabled": config.is_enabled,
                        "token": token,
                    }
            return {"platform": platform, "has_token": False, "is_enabled": False}
        except Exception:
            return {"platform": platform, "has_token": False, "is_enabled": False}
