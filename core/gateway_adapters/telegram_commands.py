"""
Aura — Telegram Command Router
Handles /command messages from Telegram, routes to gateway engine,
and formats responses. Also handles inline keyboard callbacks for approvals.
"""

from utils.logger import get_logger

logger = get_logger("telegram_commands")

# Command → intent mapping
COMMAND_INTENT_MAP = {
    "hunt": {"intent": "start_campaign"},
    "stats": {"intent": "show_stats"},
    "leads": {"intent": "show_stats"},
    "qualify": {"intent": "enrich_list"},
    "draft": {"intent": "generate_drafts"},
    "send": {"intent": "send_emails"},
    "fleet": {"intent": "fleet_status"},
    "approve": {"intent": "approve_action"},
    "deny": {"intent": "deny_action"},
    "invoice": {"intent": "show_invoices"},
    "config": {"intent": "show_budget"},
    "dashboard": {"intent": "show_stats"},
}


class TelegramCommandRouter:
    """Routes Telegram /commands to the gateway engine and formats responses."""

    def __init__(self, gateway_engine=None, response_formatter=None):
        self.gateway_engine = gateway_engine
        self.response_formatter = response_formatter

    def handle_command(self, command: str, args: str, chat_id: str) -> dict:
        """
        Process a /command and return a result dict.
        Args:
            command: The command name (without /)
            args: Everything after the command
            chat_id: Telegram chat ID
        Returns:
            dict with 'success', 'response' (formatted text), and optionally 'keyboard'
        """
        command = command.lower().strip()
        mapping = COMMAND_INTENT_MAP.get(command)

        if not mapping:
            return {
                "success": False,
                "response": f"Unknown command: /{command}\n\nAvailable: "
                           + ", ".join(f"/{c}" for c in sorted(COMMAND_INTENT_MAP.keys())),
            }

        intent = mapping["intent"]
        params = self._parse_args(command, args)

        if not self.gateway_engine:
            return {"success": False, "response": "Gateway engine not configured."}

        # Route through gateway engine
        try:
            result = self.gateway_engine.handle_inbound(
                platform="telegram",
                sender_id=chat_id,
                text=f"{command} {args}".strip(),
            )
            return {
                "success": True,
                "response": result if isinstance(result, str) else str(result),
            }
        except Exception as e:
            logger.error(f"Command /{command} failed: {e}")
            return {"success": False, "response": f"Error: {str(e)}"}

    def _parse_args(self, command: str, args: str) -> dict:
        """Parse command arguments into intent parameters."""
        params = {}
        args = args.strip()

        if command == "hunt" and args:
            parts = args.rsplit(" in ", 1)
            if len(parts) == 2:
                params["niche"] = parts[0].strip()
                params["city"] = parts[1].strip()
            else:
                params["niche"] = args

        elif command == "approve" and args:
            try:
                params["approval_id"] = int(args)
            except ValueError:
                pass

        elif command == "deny" and args:
            parts = args.split(maxsplit=1)
            if parts:
                try:
                    params["approval_id"] = int(parts[0])
                except ValueError:
                    pass
                if len(parts) > 1:
                    params["reason"] = parts[1]

        elif command == "invoice" and args:
            if args.startswith("create"):
                params["action"] = "create"
            else:
                params["status"] = args

        return params

    def build_approval_keyboard(self, approval_id: int) -> list:
        """
        Build inline keyboard markup data for an approval request.
        Returns list of button rows, each row is a list of (text, callback_data) tuples.
        """
        return [
            [
                ("Approve", f"approve_{approval_id}"),
                ("Deny", f"deny_{approval_id}"),
            ],
        ]

    def handle_callback(self, callback_data: str, chat_id: str) -> dict:
        """
        Handle an inline keyboard callback (e.g. approve/deny button press).
        Returns dict with 'success' and 'response'.
        """
        try:
            if callback_data.startswith("approve_"):
                approval_id = int(callback_data.split("_", 1)[1])
                if self.gateway_engine:
                    result = self.gateway_engine.handle_inbound(
                        "telegram", chat_id, f"approve {approval_id}",
                    )
                    return {"success": True, "response": str(result)}
                return {"success": False, "response": "Gateway not available"}

            elif callback_data.startswith("deny_"):
                approval_id = int(callback_data.split("_", 1)[1])
                if self.gateway_engine:
                    result = self.gateway_engine.handle_inbound(
                        "telegram", chat_id, f"deny {approval_id}",
                    )
                    return {"success": True, "response": str(result)}
                return {"success": False, "response": "Gateway not available"}

            elif callback_data.startswith("invoice_approve_"):
                invoice_id = int(callback_data.split("_", 2)[2])
                return self._handle_invoice_callback("approve", invoice_id, chat_id)

            elif callback_data.startswith("invoice_reject_"):
                invoice_id = int(callback_data.split("_", 2)[2])
                return self._handle_invoice_callback("reject", invoice_id, chat_id)

            return {"success": False, "response": f"Unknown callback: {callback_data}"}

        except Exception as e:
            logger.error(f"Callback handling failed: {e}")
            return {"success": False, "response": f"Error: {str(e)}"}

    def _handle_invoice_callback(self, action: str, invoice_id: int,
                                  chat_id: str) -> dict:
        """Handle invoice approve/reject callbacks."""
        if not self.gateway_engine:
            return {"success": False, "response": "Gateway not available"}

        text = f"invoice {action} {invoice_id}"
        result = self.gateway_engine.handle_inbound("telegram", chat_id, text)
        return {"success": True, "response": str(result)}

    def build_invoice_keyboard(self, invoice_id: int) -> list:
        """Build inline keyboard for invoice approval."""
        return [
            [
                ("Approve", f"invoice_approve_{invoice_id}"),
                ("Reject", f"invoice_reject_{invoice_id}"),
            ],
        ]

    def get_command_list(self) -> list:
        """Return bot commands for Telegram setMyCommands."""
        return [
            {"command": "hunt", "description": "Start a lead hunting campaign"},
            {"command": "stats", "description": "Show pipeline statistics"},
            {"command": "leads", "description": "List recent leads"},
            {"command": "qualify", "description": "AI-qualify pending leads"},
            {"command": "draft", "description": "Generate email drafts"},
            {"command": "send", "description": "Send pending emails"},
            {"command": "fleet", "description": "Agent fleet status"},
            {"command": "approve", "description": "Approve a pending action"},
            {"command": "deny", "description": "Deny a pending action"},
            {"command": "invoice", "description": "Invoice operations"},
            {"command": "config", "description": "Show configuration"},
            {"command": "dashboard", "description": "Dashboard overview"},
        ]
