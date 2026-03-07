"""
Aura — Telegram Gateway Adapter
Uses python-telegram-bot with polling mode for desktop compatibility.
"""

import asyncio
import threading
from typing import Callable, Optional

from core.gateway_adapters.base_adapter import BaseAdapter
from utils.logger import get_logger

logger = get_logger("telegram_adapter")


class TelegramAdapter(BaseAdapter):
    """Telegram Bot API adapter using long-polling."""

    def __init__(self, bot_token: str, on_message_callback: Callable):
        super().__init__(bot_token, on_message_callback)
        self._app = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def platform(self) -> str:
        return "telegram"

    def start(self):
        """Start polling in a background thread."""
        if self._running:
            logger.warning("Telegram adapter already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_polling, daemon=True)
        self._thread.start()
        logger.info("Telegram adapter started")

    def _run_polling(self):
        """Run the Telegram bot polling loop in a dedicated event loop."""
        try:
            from telegram.ext import ApplicationBuilder, MessageHandler, filters

            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            self._app = (
                ApplicationBuilder()
                .token(self.bot_token)
                .build()
            )

            # Handle all text messages (private DMs)
            async def _handle_message(update, context):
                if update.message and update.message.text:
                    chat_id = str(update.message.chat_id)
                    text = update.message.text.strip()
                    logger.debug(f"Telegram inbound from {chat_id}: {text[:50]}")
                    try:
                        self.on_message("telegram", chat_id, text)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

            self._app.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message)
            )

            # Run polling (blocking)
            self._loop.run_until_complete(self._app.initialize())
            self._loop.run_until_complete(self._app.start())
            self._loop.run_until_complete(
                self._app.updater.start_polling(drop_pending_updates=True)
            )
            self._loop.run_forever()

        except ImportError:
            logger.error(
                "python-telegram-bot not installed. "
                "Run: pip install python-telegram-bot"
            )
            self._running = False
        except Exception as e:
            logger.error(f"Telegram polling error: {e}")
            self._running = False

    def stop(self):
        """Stop the polling loop and clean up."""
        self._running = False
        if self._app and self._loop:
            try:
                async def _shutdown():
                    if self._app.updater and self._app.updater.running:
                        await self._app.updater.stop()
                    await self._app.stop()
                    await self._app.shutdown()

                asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception as e:
                logger.warning(f"Telegram shutdown error: {e}")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._app = None
        self._thread = None
        self._loop = None
        logger.info("Telegram adapter stopped")

    def send_message(self, user_id: str, text: str):
        """Send a message to a Telegram chat."""
        if not self._app or not self._loop:
            logger.warning("Cannot send: Telegram adapter not running")
            return

        async def _send():
            try:
                await self._app.bot.send_message(
                    chat_id=int(user_id),
                    text=text,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Telegram send error to {user_id}: {e}")

        try:
            asyncio.run_coroutine_threadsafe(_send(), self._loop)
        except Exception as e:
            logger.error(f"Failed to schedule Telegram send: {e}")

    def is_connected(self) -> bool:
        return self._running and self._app is not None
