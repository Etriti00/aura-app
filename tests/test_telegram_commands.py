"""
Tests for Telegram Command Router and Telegram Notification Sender.
"""

import pytest
from unittest.mock import MagicMock


class TestTelegramCommandRouter:
    """Test command routing and argument parsing."""

    def _make_router(self, gateway_engine=None):
        from core.gateway_adapters.telegram_commands import TelegramCommandRouter
        return TelegramCommandRouter(gateway_engine=gateway_engine)

    def test_unknown_command(self):
        router = self._make_router()
        result = router.handle_command("nonexistent", "", "123")
        assert not result["success"]
        assert "Unknown command" in result["response"]
        assert "/hunt" in result["response"]

    def test_command_without_gateway(self):
        router = self._make_router(gateway_engine=None)
        result = router.handle_command("stats", "", "123")
        assert not result["success"]
        assert "not configured" in result["response"]

    def test_command_with_gateway(self):
        gw = MagicMock()
        gw.handle_inbound.return_value = "Stats: 5 campaigns, 100 leads"
        router = self._make_router(gateway_engine=gw)

        result = router.handle_command("stats", "", "123")
        assert result["success"]
        gw.handle_inbound.assert_called_once()

    def test_hunt_parse_niche_city(self):
        router = self._make_router()
        params = router._parse_args("hunt", "plumbing in Austin")
        assert params["niche"] == "plumbing"
        assert params["city"] == "Austin"

    def test_hunt_parse_niche_only(self):
        router = self._make_router()
        params = router._parse_args("hunt", "plumbing")
        assert params["niche"] == "plumbing"
        assert "city" not in params

    def test_approve_parse_id(self):
        router = self._make_router()
        params = router._parse_args("approve", "42")
        assert params["approval_id"] == 42

    def test_deny_parse_id_reason(self):
        router = self._make_router()
        params = router._parse_args("deny", "42 Not needed")
        assert params["approval_id"] == 42
        assert params["reason"] == "Not needed"

    def test_invoice_create(self):
        router = self._make_router()
        params = router._parse_args("invoice", "create")
        assert params["action"] == "create"

    def test_invoice_status_filter(self):
        router = self._make_router()
        params = router._parse_args("invoice", "paid")
        assert params["status"] == "paid"

    def test_get_command_list(self):
        router = self._make_router()
        commands = router.get_command_list()
        assert len(commands) >= 10
        names = [c["command"] for c in commands]
        assert "hunt" in names
        assert "stats" in names
        assert "invoice" in names
        assert all("description" in c for c in commands)


class TestTelegramCallbacks:
    """Test inline keyboard callback handling."""

    def _make_router(self, gateway_engine=None):
        from core.gateway_adapters.telegram_commands import TelegramCommandRouter
        return TelegramCommandRouter(gateway_engine=gateway_engine)

    def test_approve_callback(self):
        gw = MagicMock()
        gw.handle_inbound.return_value = "Approved"
        router = self._make_router(gateway_engine=gw)

        result = router.handle_callback("approve_42", "123")
        assert result["success"]
        gw.handle_inbound.assert_called_once_with("telegram", "123", "approve 42")

    def test_deny_callback(self):
        gw = MagicMock()
        gw.handle_inbound.return_value = "Denied"
        router = self._make_router(gateway_engine=gw)

        result = router.handle_callback("deny_42", "123")
        assert result["success"]
        gw.handle_inbound.assert_called_once_with("telegram", "123", "deny 42")

    def test_invoice_approve_callback(self):
        gw = MagicMock()
        gw.handle_inbound.return_value = "Invoice approved"
        router = self._make_router(gateway_engine=gw)

        result = router.handle_callback("invoice_approve_5", "123")
        assert result["success"]

    def test_invoice_reject_callback(self):
        gw = MagicMock()
        gw.handle_inbound.return_value = "Invoice rejected"
        router = self._make_router(gateway_engine=gw)

        result = router.handle_callback("invoice_reject_5", "123")
        assert result["success"]

    def test_unknown_callback(self):
        router = self._make_router()
        result = router.handle_callback("random_data", "123")
        assert not result["success"]

    def test_callback_without_gateway(self):
        router = self._make_router(gateway_engine=None)
        result = router.handle_callback("approve_1", "123")
        assert not result["success"]


class TestApprovalKeyboard:
    def test_build_approval_keyboard(self):
        from core.gateway_adapters.telegram_commands import TelegramCommandRouter
        router = TelegramCommandRouter()

        kb = router.build_approval_keyboard(42)
        assert len(kb) == 1  # 1 row
        assert len(kb[0]) == 2  # 2 buttons
        assert kb[0][0] == ("Approve", "approve_42")
        assert kb[0][1] == ("Deny", "deny_42")

    def test_build_invoice_keyboard(self):
        from core.gateway_adapters.telegram_commands import TelegramCommandRouter
        router = TelegramCommandRouter()

        kb = router.build_invoice_keyboard(5)
        assert kb[0][0] == ("Approve", "invoice_approve_5")
        assert kb[0][1] == ("Reject", "invoice_reject_5")


class TestTelegramNotificationSender:
    """Test notification formatting and sending."""

    def _make_sender(self, owner_chat_id="12345"):
        from core.gateway_adapters.telegram_notifications import TelegramNotificationSender
        adapter = MagicMock()
        sender = TelegramNotificationSender(adapter, owner_chat_id=owner_chat_id)
        return sender, adapter

    def test_route_event_sends_html(self):
        sender, adapter = self._make_sender()
        sender.route_event("lead_found", {"business_name": "Acme", "city": "Austin"})
        adapter.send_message.assert_called_once()
        html = adapter.send_message.call_args[0][1]
        assert "<b>Lead Found</b>" in html
        assert "Acme" in html
        assert "Austin" in html

    def test_route_event_no_owner(self):
        sender, adapter = self._make_sender(owner_chat_id=None)
        sender.route_event("lead_found", {"name": "X"})
        adapter.send_message.assert_not_called()

    def test_urgent_prefix(self):
        sender, adapter = self._make_sender()
        sender.route_event("invoice_escalated", {"urgent": True, "total": 5000})
        html = adapter.send_message.call_args[0][1]
        assert "URGENT" in html

    def test_emoji_prefix(self):
        sender, adapter = self._make_sender()
        sender.route_event("reply_detected", {"from": "test@test.com"})
        html = adapter.send_message.call_args[0][1]
        assert "💬" in html

    def test_approval_notification(self):
        sender, adapter = self._make_sender()
        result = sender.send_approval_notification(42, "Send emails", "send_email")
        assert result["success"]
        html = adapter.send_message.call_args[0][1]
        assert "Approval Required" in html
        assert "42" in html
        assert "/approve 42" in html

    def test_approval_no_owner(self):
        sender, adapter = self._make_sender(owner_chat_id=None)
        result = sender.send_approval_notification(1, "Test", "test")
        assert not result["success"]

    def test_invoice_notification(self):
        sender, adapter = self._make_sender()
        result = sender.send_invoice_notification(
            5, "INV-0001", "Acme Corp", 1500.0, "EUR"
        )
        assert result["success"]
        html = adapter.send_message.call_args[0][1]
        assert "INV-0001" in html
        assert "Acme Corp" in html
        assert "1500.00" in html

    def test_invoice_no_owner(self):
        sender, adapter = self._make_sender(owner_chat_id=None)
        result = sender.send_invoice_notification(1, "INV-1", "X", 100.0)
        assert not result["success"]


class TestCommandIntentMapping:
    def test_all_commands_have_intents(self):
        from core.gateway_adapters.telegram_commands import COMMAND_INTENT_MAP
        assert "hunt" in COMMAND_INTENT_MAP
        assert "stats" in COMMAND_INTENT_MAP
        assert "approve" in COMMAND_INTENT_MAP
        assert "invoice" in COMMAND_INTENT_MAP
        assert "fleet" in COMMAND_INTENT_MAP

    def test_intents_are_valid(self):
        from core.gateway_adapters.telegram_commands import COMMAND_INTENT_MAP
        for cmd, mapping in COMMAND_INTENT_MAP.items():
            assert "intent" in mapping, f"Command /{cmd} missing 'intent' key"
            assert isinstance(mapping["intent"], str)
