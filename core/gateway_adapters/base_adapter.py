"""
Aura — Base Gateway Adapter
Abstract base class for all platform-specific gateway adapters.
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional

from utils.logger import get_logger

logger = get_logger("gateway_adapter")


class BaseAdapter(ABC):
    """
    Abstract adapter for a messaging platform.
    Subclasses implement platform-specific connection, polling, and send logic.
    """

    def __init__(self, bot_token: str, on_message_callback: Callable):
        """
        Args:
            bot_token: Platform-specific bot token or API key.
            on_message_callback: Callable(platform, sender_id, text)
                called when an inbound message is received.
        """
        self.bot_token = bot_token
        self.on_message = on_message_callback
        self._running = False

    @property
    def platform(self) -> str:
        """Return the platform name (e.g. 'telegram', 'discord')."""
        raise NotImplementedError

    @abstractmethod
    def start(self):
        """Begin polling or WebSocket connection. Should be non-blocking or run in a thread."""
        ...

    @abstractmethod
    def stop(self):
        """Gracefully shutdown the adapter."""
        ...

    @abstractmethod
    def send_message(self, user_id: str, text: str):
        """Send a text message to a specific user on this platform."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the adapter is currently connected and running."""
        ...
