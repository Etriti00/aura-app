"""
Aura — Discord Gateway Adapter
Uses discord.py with WebSocket gateway for desktop compatibility.
Listens for DMs (direct messages) only.
"""

import asyncio
import threading
from typing import Callable, Optional

from core.gateway_adapters.base_adapter import BaseAdapter
from utils.logger import get_logger

logger = get_logger("discord_adapter")


class DiscordAdapter(BaseAdapter):
    """Discord bot adapter using WebSocket gateway connection."""

    def __init__(self, bot_token: str, on_message_callback: Callable):
        super().__init__(bot_token, on_message_callback)
        self._client = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def platform(self) -> str:
        return "discord"

    def start(self):
        """Start the Discord bot in a background thread."""
        if self._running:
            logger.warning("Discord adapter already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_bot, daemon=True)
        self._thread.start()
        logger.info("Discord adapter started")

    def _run_bot(self):
        """Run the Discord bot in a dedicated event loop."""
        try:
            import discord

            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            intents = discord.Intents.default()
            intents.message_content = True
            intents.dm_messages = True

            self._client = discord.Client(intents=intents)

            @self._client.event
            async def on_ready():
                logger.info(f"Discord bot connected as {self._client.user}")

            @self._client.event
            async def on_message(message):
                # Only process DMs, ignore own messages
                if message.author == self._client.user:
                    return
                if not isinstance(message.channel, discord.DMChannel):
                    return

                user_id = str(message.author.id)
                text = message.content.strip()
                if not text:
                    return

                logger.debug(f"Discord DM from {user_id}: {text[:50]}")
                try:
                    self.on_message("discord", user_id, text)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

            self._loop.run_until_complete(self._client.start(self.bot_token))

        except ImportError:
            logger.error(
                "discord.py not installed. Run: pip install discord.py"
            )
            self._running = False
        except Exception as e:
            logger.error(f"Discord bot error: {e}")
            self._running = False

    def stop(self):
        """Stop the Discord bot and clean up."""
        self._running = False
        if self._client and self._loop:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._client.close(), self._loop
                )
                future.result(timeout=5)
            except Exception as e:
                logger.warning(f"Discord shutdown error: {e}")

        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._client = None
        self._thread = None
        self._loop = None
        logger.info("Discord adapter stopped")

    def send_message(self, user_id: str, text: str):
        """Send a DM to a Discord user."""
        if not self._client or not self._loop:
            logger.warning("Cannot send: Discord adapter not running")
            return

        async def _send():
            try:
                user = await self._client.fetch_user(int(user_id))
                if user:
                    await user.send(text)
            except Exception as e:
                logger.error(f"Discord send error to {user_id}: {e}")

        try:
            asyncio.run_coroutine_threadsafe(_send(), self._loop)
        except Exception as e:
            logger.error(f"Failed to schedule Discord send: {e}")

    def is_connected(self) -> bool:
        return (
            self._running
            and self._client is not None
            and self._client.is_ready()
        )

    def send_to_channel(self, channel_id: str, text: str):
        """Send a text message to a specific channel."""
        if not self._client or not self._loop:
            logger.warning("Cannot send to channel: Discord adapter not running")
            return

        async def _send():
            try:
                channel = self._client.get_channel(int(channel_id))
                if channel is None:
                    channel = await self._client.fetch_channel(int(channel_id))
                if channel:
                    await channel.send(text)
            except Exception as e:
                logger.error(f"Discord channel send error to {channel_id}: {e}")

        try:
            asyncio.run_coroutine_threadsafe(_send(), self._loop)
        except Exception as e:
            logger.error(f"Failed to schedule channel send: {e}")

    def send_embed(self, channel_id: str, embed_dict: dict):
        """Send a rich embed to a specific channel."""
        if not self._client or not self._loop:
            logger.warning("Cannot send embed: Discord adapter not running")
            return

        async def _send():
            try:
                import discord
                channel = self._client.get_channel(int(channel_id))
                if channel is None:
                    channel = await self._client.fetch_channel(int(channel_id))
                if channel:
                    embed = discord.Embed(
                        title=embed_dict.get("title", ""),
                        description=embed_dict.get("description", ""),
                        color=embed_dict.get("color", 0x4E5BF2),
                    )
                    for field in embed_dict.get("fields", []):
                        embed.add_field(
                            name=field["name"],
                            value=field["value"],
                            inline=field.get("inline", True),
                        )
                    if "footer" in embed_dict:
                        embed.set_footer(text=embed_dict["footer"].get("text", ""))
                    await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Discord embed send error to {channel_id}: {e}")

        try:
            asyncio.run_coroutine_threadsafe(_send(), self._loop)
        except Exception as e:
            logger.error(f"Failed to schedule embed send: {e}")
