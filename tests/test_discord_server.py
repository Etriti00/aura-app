"""
Tests for Discord Server Manager and Discord Notification Router.
Tests the channel config, event routing, embed building, and slash command defs.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestDiscordServerManager:
    """Test DiscordServerManager channel config management."""

    def test_save_and_get_config(self, db):
        from core.gateway_adapters.discord_server import DiscordServerManager

        mgr = DiscordServerManager(db_manager=db)
        channel_map = {
            "dashboard": "111",
            "leads": "222",
            "outreach": "333",
            "fleet": "444",
            "approvals": "555",
            "invoices": "666",
            "logs": "777",
        }
        result = mgr.save_channel_config("guild_1", "Test Guild", channel_map)
        assert result["success"]

        loaded = mgr.get_channel_config("guild_1")
        assert loaded["dashboard"] == "111"
        assert loaded["leads"] == "222"
        assert loaded["logs"] == "777"

    def test_get_config_from_cache(self):
        from core.gateway_adapters.discord_server import DiscordServerManager

        mgr = DiscordServerManager()
        mgr._guild_configs["guild_x"] = {"dashboard": "999"}

        config = mgr.get_channel_config("guild_x")
        assert config["dashboard"] == "999"

    def test_get_config_empty(self):
        from core.gateway_adapters.discord_server import DiscordServerManager

        mgr = DiscordServerManager()
        config = mgr.get_channel_config("nonexistent")
        assert config == {}

    def test_get_channel_id(self):
        from core.gateway_adapters.discord_server import DiscordServerManager

        mgr = DiscordServerManager()
        mgr._guild_configs["g1"] = {"leads": "123", "fleet": "456"}

        assert mgr.get_channel_id("g1", "leads") == "123"
        assert mgr.get_channel_id("g1", "fleet") == "456"
        assert mgr.get_channel_id("g1", "unknown") is None
        assert mgr.get_channel_id("nonexistent", "leads") is None

    def test_get_slash_command_definitions(self):
        from core.gateway_adapters.discord_server import DiscordServerManager

        mgr = DiscordServerManager()
        commands = mgr.get_slash_command_definitions()
        assert len(commands) >= 10
        names = [c["name"] for c in commands]
        assert "hunt" in names
        assert "stats" in names
        assert "approve" in names
        assert "invoice" in names

    def test_save_updates_existing_config(self, db):
        from core.gateway_adapters.discord_server import DiscordServerManager

        mgr = DiscordServerManager(db_manager=db)
        mgr.save_channel_config("g1", "Guild 1", {"dashboard": "100"})
        mgr.save_channel_config("g1", "Guild 1 Updated", {"dashboard": "200"})

        # Clear cache to force DB read
        mgr._guild_configs.clear()
        loaded = mgr.get_channel_config("g1")
        assert loaded["dashboard"] == "200"

    def test_config_persists_to_db(self, db):
        from core.gateway_adapters.discord_server import DiscordServerManager
        from database.schema import DiscordServerConfig

        mgr = DiscordServerManager(db_manager=db)
        mgr.save_channel_config("g1", "Test", {"leads": "123", "fleet": "456"})

        with db.session_scope() as session:
            config = session.query(DiscordServerConfig).filter_by(guild_id="g1").first()
            assert config is not None
            assert config.channel_leads == "123"
            assert config.channel_fleet == "456"
            assert config.guild_name == "Test"


class TestDiscordNotificationRouter:
    """Test event routing and embed building."""

    def _make_router(self):
        from core.gateway_adapters.discord_server import DiscordServerManager
        from core.gateway_adapters.discord_notifications import DiscordNotificationRouter

        mgr = DiscordServerManager()
        mgr._guild_configs["g1"] = {
            "dashboard": "100", "leads": "200", "outreach": "300",
            "fleet": "400", "approvals": "500", "invoices": "600", "logs": "700",
        }
        adapter = MagicMock()
        router = DiscordNotificationRouter(mgr, adapter)
        return router, adapter

    def test_route_lead_found(self):
        router, adapter = self._make_router()
        router.route_event("lead_found", {"business_name": "Acme", "city": "Austin"})
        adapter.send_embed.assert_called_once()
        call_args = adapter.send_embed.call_args
        assert call_args[0][0] == "200"  # leads channel

    def test_route_email_sent(self):
        router, adapter = self._make_router()
        router.route_event("email_sent", {"to": "test@example.com"})
        adapter.send_embed.assert_called_once()
        assert adapter.send_embed.call_args[0][0] == "300"  # outreach channel

    def test_route_fleet_boot(self):
        router, adapter = self._make_router()
        router.route_event("fleet_boot", {"booted": 20})
        adapter.send_embed.assert_called_once()
        assert adapter.send_embed.call_args[0][0] == "400"

    def test_route_approval_needed(self):
        router, adapter = self._make_router()
        router.route_event("approval_needed", {"action": "send_email"})
        adapter.send_embed.assert_called_once()
        assert adapter.send_embed.call_args[0][0] == "500"

    def test_route_invoice_approval(self):
        router, adapter = self._make_router()
        router.route_event("invoice_approval_needed", {
            "invoice_number": "INV-001", "total": 1000,
        })
        adapter.send_embed.assert_called_once()
        assert adapter.send_embed.call_args[0][0] == "600"

    def test_route_unknown_to_logs(self):
        router, adapter = self._make_router()
        router.route_event("some_unknown_event", {"data": "test"})
        adapter.send_embed.assert_called_once()
        assert adapter.send_embed.call_args[0][0] == "700"  # logs fallback

    def test_embed_has_title_and_fields(self):
        router, adapter = self._make_router()
        router.route_event("lead_qualified", {
            "business_name": "Acme", "score": 85,
        })
        embed = adapter.send_embed.call_args[0][1]
        assert embed["title"] == "Lead Qualified"
        assert len(embed["fields"]) == 2
        field_names = [f["name"] for f in embed["fields"]]
        assert "Business Name" in field_names
        assert "Score" in field_names

    def test_embed_urgent_prefix(self):
        router, adapter = self._make_router()
        router.route_event("invoice_escalated", {"urgent": True, "total": 5000})
        embed = adapter.send_embed.call_args[0][1]
        assert "URGENT" in embed["title"]

    def test_embed_color_success(self):
        from core.gateway_adapters.discord_notifications import EMBED_COLORS
        router, adapter = self._make_router()
        router.route_event("invoice_approved", {"invoice_number": "INV-001"})
        embed = adapter.send_embed.call_args[0][1]
        assert embed["color"] == EMBED_COLORS["success"]

    def test_embed_color_error(self):
        from core.gateway_adapters.discord_notifications import EMBED_COLORS
        router, adapter = self._make_router()
        router.route_event("invoice_rejected", {"reason": "Too high"})
        embed = adapter.send_embed.call_args[0][1]
        assert embed["color"] == EMBED_COLORS["error"]

    def test_embed_color_warning(self):
        from core.gateway_adapters.discord_notifications import EMBED_COLORS
        router, adapter = self._make_router()
        router.route_event("invoice_escalated", {"total": 1000})
        embed = adapter.send_embed.call_args[0][1]
        assert embed["color"] == EMBED_COLORS["warning"]

    def test_send_to_channel_text(self):
        from core.gateway_adapters.discord_server import DiscordServerManager
        from core.gateway_adapters.discord_notifications import DiscordNotificationRouter

        mgr = DiscordServerManager()
        mgr._guild_configs["g1"] = {"leads": "200"}
        adapter = MagicMock()
        router = DiscordNotificationRouter(mgr, adapter)

        router.send_to_channel("g1", "leads", message="Hello leads!")
        adapter.send_to_channel.assert_called_once_with("200", "Hello leads!")

    def test_send_to_channel_embed(self):
        from core.gateway_adapters.discord_server import DiscordServerManager
        from core.gateway_adapters.discord_notifications import DiscordNotificationRouter

        mgr = DiscordServerManager()
        mgr._guild_configs["g1"] = {"fleet": "400"}
        adapter = MagicMock()
        router = DiscordNotificationRouter(mgr, adapter)

        embed = {"title": "Test", "color": 0xFF0000}
        router.send_to_channel("g1", "fleet", embed=embed)
        adapter.send_embed.assert_called_once_with("400", embed)

    def test_send_to_unconfigured_channel(self):
        from core.gateway_adapters.discord_server import DiscordServerManager
        from core.gateway_adapters.discord_notifications import DiscordNotificationRouter

        mgr = DiscordServerManager()
        mgr._guild_configs["g1"] = {}
        adapter = MagicMock()
        router = DiscordNotificationRouter(mgr, adapter)

        router.send_to_channel("g1", "leads", message="Test")
        adapter.send_to_channel.assert_not_called()

    def test_multiple_guilds(self):
        from core.gateway_adapters.discord_server import DiscordServerManager
        from core.gateway_adapters.discord_notifications import DiscordNotificationRouter

        mgr = DiscordServerManager()
        mgr._guild_configs["g1"] = {"leads": "100"}
        mgr._guild_configs["g2"] = {"leads": "200"}
        adapter = MagicMock()
        router = DiscordNotificationRouter(mgr, adapter)

        router.route_event("lead_found", {"name": "X"})
        assert adapter.send_embed.call_count == 2


class TestEventChannelMapping:
    """Verify event type → channel mapping is correct."""

    def test_all_events_mapped(self):
        from core.gateway_adapters.discord_notifications import EVENT_CHANNEL_MAP

        expected_events = [
            "lead_found", "lead_qualified", "email_sent", "reply_detected",
            "fleet_boot", "approval_needed", "invoice_approval_needed",
            "invoice_approved", "invoice_rejected",
        ]
        for event in expected_events:
            assert event in EVENT_CHANNEL_MAP, f"Missing event mapping: {event}"

    def test_channel_types_valid(self):
        from core.gateway_adapters.discord_notifications import EVENT_CHANNEL_MAP
        from core.gateway_adapters.discord_server import AURA_CHANNELS

        valid_channels = set(AURA_CHANNELS.keys())
        for event, channel in EVENT_CHANNEL_MAP.items():
            assert channel in valid_channels, (
                f"Event '{event}' maps to invalid channel '{channel}'"
            )


class TestAuraChannels:
    def test_channel_definitions(self):
        from core.gateway_adapters.discord_server import AURA_CHANNELS

        assert "dashboard" in AURA_CHANNELS
        assert "leads" in AURA_CHANNELS
        assert "outreach" in AURA_CHANNELS
        assert "fleet" in AURA_CHANNELS
        assert "approvals" in AURA_CHANNELS
        assert "invoices" in AURA_CHANNELS
        assert "logs" in AURA_CHANNELS

        for key, info in AURA_CHANNELS.items():
            assert "name" in info
            assert "topic" in info
