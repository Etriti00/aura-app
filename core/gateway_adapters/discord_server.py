"""
Aura — Discord Server Manager
Manages Aura HQ guild: auto-creates server with dedicated channels,
registers slash commands, and routes messages to channels.
"""

from utils.logger import get_logger

logger = get_logger("discord_server")

# Channel types for Aura HQ
AURA_CHANNELS = {
    "dashboard": {"name": "dashboard", "topic": "Live Aura dashboard updates"},
    "leads": {"name": "leads", "topic": "New leads and qualification updates"},
    "outreach": {"name": "outreach", "topic": "Email drafts, sends, and replies"},
    "fleet": {"name": "fleet", "topic": "Agent fleet status and tasks"},
    "approvals": {"name": "approvals", "topic": "Pending approvals and actions"},
    "invoices": {"name": "invoices", "topic": "Invoice notifications and approvals"},
    "logs": {"name": "logs", "topic": "Aura system logs"},
}


class DiscordServerManager:
    """Manages Aura HQ Discord server setup and channel routing."""

    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self._guild_configs = {}  # guild_id → channel_map

    def get_channel_config(self, guild_id: str) -> dict:
        """Get channel configuration for a guild from cache or DB."""
        if guild_id in self._guild_configs:
            return self._guild_configs[guild_id]

        if self.db_manager:
            try:
                from database.schema import DiscordServerConfig
                with self.db_manager.session_scope() as session:
                    config = session.query(DiscordServerConfig).filter_by(
                        guild_id=guild_id
                    ).first()
                    if config:
                        channel_map = {
                            "dashboard": config.channel_dashboard,
                            "leads": config.channel_leads,
                            "outreach": config.channel_outreach,
                            "fleet": config.channel_fleet,
                            "approvals": config.channel_approvals,
                            "invoices": config.channel_invoices,
                            "logs": config.channel_logs,
                        }
                        self._guild_configs[guild_id] = channel_map
                        return channel_map
            except Exception as e:
                logger.error(f"Failed to load guild config: {e}")

        return {}

    def save_channel_config(self, guild_id: str, guild_name: str,
                            channel_map: dict) -> dict:
        """Save channel configuration for a guild."""
        self._guild_configs[guild_id] = channel_map

        if self.db_manager:
            try:
                from database.schema import DiscordServerConfig
                with self.db_manager.session_scope() as session:
                    config = session.query(DiscordServerConfig).filter_by(
                        guild_id=guild_id
                    ).first()
                    if not config:
                        config = DiscordServerConfig(
                            guild_id=guild_id, guild_name=guild_name,
                        )
                        session.add(config)

                    config.guild_name = guild_name
                    config.channel_dashboard = channel_map.get("dashboard")
                    config.channel_leads = channel_map.get("leads")
                    config.channel_outreach = channel_map.get("outreach")
                    config.channel_fleet = channel_map.get("fleet")
                    config.channel_approvals = channel_map.get("approvals")
                    config.channel_invoices = channel_map.get("invoices")
                    config.channel_logs = channel_map.get("logs")

                return {"success": True}
            except Exception as e:
                logger.error(f"Failed to save guild config: {e}")
                return {"success": False, "error": str(e)}

        return {"success": True}

    async def ensure_aura_server(self, guild, bot_user):
        """
        Ensure all Aura HQ channels exist in a guild.
        Creates missing channels and saves config.
        Called on_ready for each guild the bot is in.
        """
        try:
            import discord

            guild_id = str(guild.id)
            existing_channels = {ch.name: ch for ch in guild.text_channels}
            channel_map = {}

            for key, info in AURA_CHANNELS.items():
                ch_name = f"aura-{info['name']}"
                if ch_name in existing_channels:
                    channel_map[key] = str(existing_channels[ch_name].id)
                else:
                    # Create the channel
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(
                            read_messages=True, send_messages=False,
                        ),
                        bot_user: discord.PermissionOverwrite(
                            read_messages=True, send_messages=True,
                            manage_messages=True,
                        ),
                    }
                    new_ch = await guild.create_text_channel(
                        ch_name,
                        topic=info["topic"],
                        overwrites=overwrites,
                    )
                    channel_map[key] = str(new_ch.id)
                    logger.info(f"Created channel #{ch_name} in {guild.name}")

            self.save_channel_config(guild_id, guild.name, channel_map)
            logger.info(f"Aura HQ channels configured for {guild.name}")
            return channel_map

        except Exception as e:
            logger.error(f"ensure_aura_server failed: {e}")
            return {}

    def get_channel_id(self, guild_id: str, channel_type: str) -> str | None:
        """Get the channel ID for a specific channel type in a guild."""
        config = self.get_channel_config(guild_id)
        return config.get(channel_type)

    def get_slash_command_definitions(self) -> list:
        """Return slash command definitions for registration."""
        return [
            {"name": "hunt", "description": "Start a lead hunting campaign"},
            {"name": "stats", "description": "Show pipeline statistics"},
            {"name": "leads", "description": "List recent leads"},
            {"name": "qualify", "description": "Run AI qualification on pending leads"},
            {"name": "draft", "description": "Generate email drafts for qualified leads"},
            {"name": "send", "description": "Send pending email drafts"},
            {"name": "fleet", "description": "Show agent fleet status"},
            {"name": "approve", "description": "Approve a pending action"},
            {"name": "deny", "description": "Deny a pending action"},
            {"name": "invoice", "description": "Create or list invoices"},
            {"name": "config", "description": "Show Aura configuration"},
        ]
