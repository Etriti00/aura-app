"""
Aura — Gateway Controller
Manages platform adapter lifecycle (start/stop), routes inbound messages
through the GatewayEngine, and handles proactive notifications.
"""

from PySide6.QtCore import QObject, Signal

from core.gateway_engine import GatewayEngine
from core.gateway_adapters.telegram_adapter import TelegramAdapter
from core.gateway_adapters.discord_adapter import DiscordAdapter
from utils.logger import get_logger
from utils.thread_worker import ThreadWorker

logger = get_logger("gateway_controller")

ADAPTER_CLASSES = {
    "telegram": TelegramAdapter,
    "discord": DiscordAdapter,
}


class GatewayController(QObject):
    """Controls external platform connections and message routing."""

    # Signals
    message_received = Signal(str, str, str)   # platform, sender_id, text
    response_sent = Signal(str, str)           # platform, user_id
    connection_status = Signal(str, bool)      # platform, connected
    error = Signal(str)                        # error message
    notification_sent = Signal(str, int)       # message, recipient_count

    def __init__(self, gateway_engine: GatewayEngine, parent=None):
        super().__init__(parent)
        self.gateway_engine = gateway_engine
        self._adapters = {}       # platform → adapter instance
        self._workers = {}        # track active ThreadWorkers

    # ─── Platform lifecycle ────────────────────────────────────────

    def start_platform(self, platform: str, bot_token: str):
        """Connect to a messaging platform."""
        if platform in self._adapters:
            self.stop_platform(platform)

        adapter_cls = ADAPTER_CLASSES.get(platform)
        if not adapter_cls:
            self.error.emit(f"Unknown platform: {platform}")
            return

        if not bot_token:
            self.error.emit(f"No bot token provided for {platform}")
            return

        try:
            adapter = adapter_cls(bot_token, self._on_inbound_message)
            adapter.start()
            self._adapters[platform] = adapter

            # Register adapter with gateway engine for broadcasts
            self.gateway_engine._adapters[platform] = adapter

            # Save config
            self.gateway_engine.save_gateway_config(platform, bot_token, True)

            self.connection_status.emit(platform, True)
            logger.info(f"Platform {platform} connected")

        except Exception as e:
            self.error.emit(f"Failed to connect {platform}: {str(e)}")
            logger.error(f"Platform start error ({platform}): {e}")

    def stop_platform(self, platform: str):
        """Disconnect from a messaging platform."""
        adapter = self._adapters.pop(platform, None)
        if adapter:
            try:
                adapter.stop()
            except Exception as e:
                logger.warning(f"Error stopping {platform}: {e}")

        # Remove from gateway engine
        self.gateway_engine._adapters.pop(platform, None)

        # Update config
        config = self.gateway_engine.get_gateway_config(platform)
        if config.get("has_token"):
            self.gateway_engine.save_gateway_config(
                platform, config.get("token", ""), False
            )

        self.connection_status.emit(platform, False)
        logger.info(f"Platform {platform} disconnected")

    def stop_all(self):
        """Stop all running adapters."""
        for platform in list(self._adapters.keys()):
            self.stop_platform(platform)

    # ─── Inbound message handling ──────────────────────────────────

    def _on_inbound_message(self, platform: str, sender_id: str, text: str):
        """
        Called by adapters when a message arrives.
        Routes through GatewayEngine in a background thread.
        """
        self.message_received.emit(platform, sender_id, text)

        def _work():
            return self.gateway_engine.handle_inbound(platform, sender_id, text)

        def _done(result):
            if not result:
                return

            if not result.get("authorized"):
                logger.debug(f"Unauthorized message from {platform}:{sender_id}")
                return

            response_text = result.get("response_text")
            if response_text:
                adapter = self._adapters.get(platform)
                if adapter and adapter.is_connected():
                    adapter.send_message(sender_id, response_text)
                    self.response_sent.emit(platform, sender_id)

        def _error(err):
            logger.error(f"Gateway processing error: {err}")

        worker = ThreadWorker(_work)
        worker.finished.connect(_done)
        worker.error.connect(_error)
        self._workers[f"{platform}_{sender_id}"] = worker
        worker.start()

    # ─── Proactive notifications ───────────────────────────────────

    def send_notification(self, message: str):
        """Send a proactive notification to all authorized users."""
        if not self._adapters:
            return  # No platforms connected

        def _work():
            return self.gateway_engine.broadcast(message)

        def _done(result):
            count = result.get("total", 0)
            if count > 0:
                self.notification_sent.emit(message, count)

        worker = ThreadWorker(_work)
        worker.finished.connect(_done)
        self._workers["broadcast"] = worker
        worker.start()

    # ─── Authorized user management ────────────────────────────────

    def add_authorized_user(self, platform: str, user_id: str,
                            display_name: str = ""):
        """Add an authorized user."""
        result = self.gateway_engine.add_authorized_user(
            platform, user_id, display_name
        )
        if not result.get("success"):
            self.error.emit(
                f"Failed to add user: {result.get('error', 'Unknown error')}"
            )

    def remove_authorized_user(self, platform: str, user_id: str):
        """Remove an authorized user."""
        result = self.gateway_engine.remove_authorized_user(platform, user_id)
        if not result.get("success"):
            self.error.emit(
                f"Failed to remove user: {result.get('error', 'Unknown error')}"
            )

    # ─── Status ────────────────────────────────────────────────────

    def get_platform_status(self) -> dict:
        """Get connection status for all configured platforms."""
        status = {}
        for platform in ADAPTER_CLASSES:
            adapter = self._adapters.get(platform)
            status[platform] = adapter.is_connected() if adapter else False
        return status
