"""
Aura — Telegram Notification Sender
Sends HTML-formatted notifications to the Telegram owner chat.
Supports inline keyboards for approvals.
"""

from utils.logger import get_logger

logger = get_logger("telegram_notifications")

# Event type → emoji prefix
EVENT_EMOJI = {
    "lead_found": "🔍",
    "lead_qualified": "✅",
    "lead_disqualified": "❌",
    "email_drafted": "📝",
    "email_sent": "📤",
    "reply_detected": "💬",
    "fleet_boot": "🚀",
    "fleet_status": "📊",
    "agent_task_completed": "✔️",
    "agent_escalation": "⚠️",
    "approval_needed": "🔔",
    "action_approved": "✅",
    "action_denied": "❌",
    "invoice_approval_needed": "💰",
    "invoice_approved": "✅",
    "invoice_rejected": "❌",
    "invoice_escalated": "🚨",
    "stats_update": "📊",
    "error": "🔴",
}


class TelegramNotificationSender:
    """Sends formatted notifications to Telegram owner chat."""

    def __init__(self, adapter, owner_chat_id: str = None):
        """
        Args:
            adapter: TelegramAdapter instance with send_message method
            owner_chat_id: Default chat ID for notifications
        """
        self.adapter = adapter
        self.owner_chat_id = owner_chat_id

    def route_event(self, event_type: str, data: dict):
        """Route an event as an HTML-formatted notification to the owner chat."""
        if not self.owner_chat_id:
            logger.debug(f"No owner_chat_id set, skipping notification: {event_type}")
            return

        html = self._format_notification(event_type, data)
        try:
            self.adapter.send_message(self.owner_chat_id, html)
        except Exception as e:
            logger.error(f"Telegram notification failed for {event_type}: {e}")

    def _format_notification(self, event_type: str, data: dict) -> str:
        """Build HTML-formatted notification text."""
        emoji = EVENT_EMOJI.get(event_type, "ℹ️")
        title = event_type.replace("_", " ").title()

        lines = [f"{emoji} <b>{title}</b>"]

        # Add message if present
        if "message" in data:
            lines.append(data["message"])

        # Add key-value fields
        skip_keys = {"message", "type", "urgent"}
        for key, value in data.items():
            if key in skip_keys:
                continue
            label = key.replace("_", " ").title()
            lines.append(f"<b>{label}:</b> {value}")

        if data.get("urgent"):
            lines.insert(0, "🚨 <b>URGENT</b>")

        return "\n".join(lines)

    def send_approval_notification(self, approval_id: int, description: str,
                                    action_type: str) -> dict:
        """Send an approval request with inline keyboard data."""
        if not self.owner_chat_id:
            return {"success": False, "error": "No owner_chat_id configured"}

        html = (
            f"🔔 <b>Approval Required</b>\n"
            f"<b>Action:</b> {action_type}\n"
            f"<b>Description:</b> {description}\n"
            f"<b>ID:</b> {approval_id}\n\n"
            f"Reply with:\n"
            f"<code>/approve {approval_id}</code> or <code>/deny {approval_id}</code>"
        )

        try:
            self.adapter.send_message(self.owner_chat_id, html)
            return {"success": True, "chat_id": self.owner_chat_id}
        except Exception as e:
            logger.error(f"Approval notification failed: {e}")
            return {"success": False, "error": str(e)}

    def send_invoice_notification(self, invoice_id: int, invoice_number: str,
                                   client_name: str, total: float,
                                   currency: str = "EUR") -> dict:
        """Send invoice approval notification."""
        if not self.owner_chat_id:
            return {"success": False, "error": "No owner_chat_id configured"}

        html = (
            f"💰 <b>Invoice Approval Needed</b>\n"
            f"<b>Invoice:</b> {invoice_number}\n"
            f"<b>Client:</b> {client_name}\n"
            f"<b>Total:</b> {currency} {total:.2f}\n\n"
            f"Reply with:\n"
            f"<code>/approve invoice {invoice_id}</code> or "
            f"<code>/deny invoice {invoice_id}</code>"
        )

        try:
            self.adapter.send_message(self.owner_chat_id, html)
            return {"success": True, "chat_id": self.owner_chat_id}
        except Exception as e:
            logger.error(f"Invoice notification failed: {e}")
            return {"success": False, "error": str(e)}
