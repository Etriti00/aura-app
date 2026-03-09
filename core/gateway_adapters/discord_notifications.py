"""
Aura — Discord Notification Router
Routes real-time event notifications to the appropriate Discord channels
with rich embed formatting.
"""

from utils.logger import get_logger

logger = get_logger("discord_notifications")

# Status colors for embeds
EMBED_COLORS = {
    "success": 0x22C55E,
    "info": 0x3B82F6,
    "warning": 0xF59E0B,
    "error": 0xEF4444,
    "default": 0x4E5BF2,
}

# Map event types to channel types
EVENT_CHANNEL_MAP = {
    "lead_found": "leads",
    "lead_qualified": "leads",
    "lead_disqualified": "leads",
    "email_drafted": "outreach",
    "email_sent": "outreach",
    "reply_detected": "outreach",
    "fleet_boot": "fleet",
    "fleet_status": "fleet",
    "agent_task_completed": "fleet",
    "agent_escalation": "fleet",
    "approval_needed": "approvals",
    "action_approved": "approvals",
    "action_denied": "approvals",
    "invoice_approval_needed": "invoices",
    "invoice_approved": "invoices",
    "invoice_rejected": "invoices",
    "invoice_escalated": "invoices",
    "system_log": "logs",
    "error": "logs",
    "stats_update": "dashboard",
}


class DiscordNotificationRouter:
    """Routes notifications to the correct Discord channels with embeds."""

    def __init__(self, server_manager, adapter):
        """
        Args:
            server_manager: DiscordServerManager instance
            adapter: DiscordAdapter with send_to_channel/send_embed methods
        """
        self.server_manager = server_manager
        self.adapter = adapter

    def route_event(self, event_type: str, data: dict):
        """Route an event notification to the correct channel(s)."""
        channel_type = EVENT_CHANNEL_MAP.get(event_type, "logs")
        embed = self._build_embed(event_type, data)

        # Send to all configured guilds
        for guild_id, config in self.server_manager._guild_configs.items():
            channel_id = config.get(channel_type)
            if channel_id:
                try:
                    self.adapter.send_embed(channel_id, embed)
                except Exception as e:
                    logger.error(
                        f"Failed to send {event_type} to {channel_type} in {guild_id}: {e}"
                    )

    def _build_embed(self, event_type: str, data: dict) -> dict:
        """Build a Discord embed dict for an event."""
        title = self._event_title(event_type)
        color = self._event_color(event_type)
        description = data.get("message", "")

        fields = []
        # Add key data as embed fields
        skip_keys = {"message", "type", "urgent"}
        for key, value in data.items():
            if key in skip_keys:
                continue
            fields.append({
                "name": key.replace("_", " ").title(),
                "value": str(value),
                "inline": True,
            })

        embed = {
            "title": title,
            "color": color,
            "fields": fields[:25],  # Discord limit
        }

        if description:
            embed["description"] = description

        if data.get("urgent"):
            embed["title"] = f"🚨 URGENT: {title}"

        return embed

    def _event_title(self, event_type: str) -> str:
        """Generate a human-readable title for an event type."""
        titles = {
            "lead_found": "New Lead Found",
            "lead_qualified": "Lead Qualified",
            "lead_disqualified": "Lead Disqualified",
            "email_drafted": "Email Draft Ready",
            "email_sent": "Email Sent",
            "reply_detected": "Reply Detected",
            "fleet_boot": "Fleet Booted",
            "fleet_status": "Fleet Status",
            "agent_task_completed": "Task Completed",
            "agent_escalation": "Agent Escalation",
            "approval_needed": "Approval Needed",
            "action_approved": "Action Approved",
            "action_denied": "Action Denied",
            "invoice_approval_needed": "Invoice Needs Approval",
            "invoice_approved": "Invoice Approved",
            "invoice_rejected": "Invoice Rejected",
            "invoice_escalated": "Invoice Escalated",
            "stats_update": "Dashboard Update",
        }
        return titles.get(event_type, event_type.replace("_", " ").title())

    def _event_color(self, event_type: str) -> int:
        """Get embed color for an event type."""
        if "error" in event_type or "rejected" in event_type or "denied" in event_type:
            return EMBED_COLORS["error"]
        if "approved" in event_type or "sent" in event_type or "qualified" in event_type:
            return EMBED_COLORS["success"]
        if "warning" in event_type or "escalat" in event_type:
            return EMBED_COLORS["warning"]
        if "approval" in event_type or "pending" in event_type:
            return EMBED_COLORS["info"]
        return EMBED_COLORS["default"]

    def send_to_channel(self, guild_id: str, channel_type: str,
                        message: str = None, embed: dict = None):
        """Send a message or embed to a specific channel in a guild."""
        channel_id = self.server_manager.get_channel_id(guild_id, channel_type)
        if not channel_id:
            logger.warning(f"No {channel_type} channel configured for guild {guild_id}")
            return

        if embed:
            self.adapter.send_embed(channel_id, embed)
        elif message:
            self.adapter.send_to_channel(channel_id, message)
