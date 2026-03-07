"""
Tests for config.py — constants, enums, paths, design tokens, ticket config.
"""

import pytest
from pathlib import Path


class TestAppIdentity:
    def test_app_name(self):
        from config import APP_NAME
        assert APP_NAME == "Aura"

    def test_app_version(self):
        from config import APP_VERSION
        assert APP_VERSION  # Not empty


class TestPaths:
    def test_assets_dir_exists(self):
        from config import ASSETS_DIR
        assert ASSETS_DIR.exists(), f"ASSETS_DIR does not exist: {ASSETS_DIR}"

    def test_themes_dir_exists(self):
        from config import THEMES_DIR
        assert THEMES_DIR.exists(), f"THEMES_DIR does not exist: {THEMES_DIR}"

    def test_data_dir_exists(self):
        from config import DATA_DIR
        assert DATA_DIR.exists()


class TestEnums:
    def test_campaign_statuses(self):
        from config import CampaignStatus
        assert CampaignStatus.DRAFT == "draft"
        assert CampaignStatus.ACTIVE == "active"
        assert CampaignStatus.PAUSED == "paused"
        assert CampaignStatus.COMPLETED == "completed"

    def test_lead_statuses(self):
        from config import LeadStatus
        assert LeadStatus.NEW == "new"
        assert LeadStatus.EMAIL_SENT == "emailed"
        assert LeadStatus.REPLIED == "replied"


class TestTicketConfig:
    def test_ticket_statuses(self):
        from config import TICKET_STATUSES
        assert TICKET_STATUSES == ["backlog", "todo", "in_progress", "review", "done"]

    def test_ticket_priorities(self):
        from config import TICKET_PRIORITIES
        assert TICKET_PRIORITIES == ["critical", "high", "medium", "low"]

    def test_ticket_priority_colors(self):
        from config import TICKET_PRIORITY_COLORS
        assert len(TICKET_PRIORITY_COLORS) == 4
        for priority in ["critical", "high", "medium", "low"]:
            assert priority in TICKET_PRIORITY_COLORS
            assert TICKET_PRIORITY_COLORS[priority].startswith("#")

    def test_agent_ranks(self):
        from config import AGENT_RANKS
        assert AGENT_RANKS == {1: "C-Level", 2: "Specialist Lead", 3: "Worker"}

    def test_escalation_interval(self):
        from config import ESCALATION_CHECK_INTERVAL_MS
        assert ESCALATION_CHECK_INTERVAL_MS == 5 * 60 * 1000  # 5 minutes

    def test_due_warning_hours(self):
        from config import TICKET_DUE_WARNING_HOURS
        assert TICKET_DUE_WARNING_HOURS == 4


class TestAgentConfig:
    def test_agent_roles(self):
        from config import AGENT_ROLES
        assert "orchestrator" in AGENT_ROLES
        assert "worker" in AGENT_ROLES
        assert "canary" in AGENT_ROLES
        assert "observer" in AGENT_ROLES

    def test_fleet_max_concurrent(self):
        from config import FLEET_MAX_CONCURRENT_TASKS
        assert FLEET_MAX_CONCURRENT_TASKS > 0

    def test_heartbeat_default(self):
        from config import AGENT_HEARTBEAT_DEFAULT_MINS
        assert AGENT_HEARTBEAT_DEFAULT_MINS == 30


class TestRouterConfig:
    def test_tier_map_has_entries(self):
        from config import ROUTER_TASK_TIER_MAP
        assert len(ROUTER_TASK_TIER_MAP) > 0
        assert "generate_email" in ROUTER_TASK_TIER_MAP
        assert ROUTER_TASK_TIER_MAP["generate_email"] == "sonnet"

    def test_tier_cost_map(self):
        from config import TIER_COST_PER_1K_TOKENS
        assert TIER_COST_PER_1K_TOKENS["local"] == 0.0
        assert TIER_COST_PER_1K_TOKENS["ollama"] == 0.0
        assert TIER_COST_PER_1K_TOKENS["haiku"] > 0
        assert TIER_COST_PER_1K_TOKENS["sonnet"] > TIER_COST_PER_1K_TOKENS["haiku"]


class TestEmailConfig:
    def test_max_daily_emails(self):
        from config import MAX_DAILY_EMAILS
        assert MAX_DAILY_EMAILS == 100

    def test_warning_threshold(self):
        from config import DAILY_EMAIL_WARNING_THRESHOLD, MAX_DAILY_EMAILS
        assert DAILY_EMAIL_WARNING_THRESHOLD < MAX_DAILY_EMAILS


class TestScraperConfig:
    def test_sources(self):
        from config import SCRAPER_SOURCES
        assert "duckduckgo" in SCRAPER_SOURCES

    def test_user_agents(self):
        from config import USER_AGENTS
        assert len(USER_AGENTS) >= 3

    def test_aggregator_keywords(self):
        from config import AGGREGATOR_KEYWORDS
        assert "yelp" in AGGREGATOR_KEYWORDS
        assert "facebook" in AGGREGATOR_KEYWORDS


class TestGeometry:
    def test_card_radius(self):
        from config import Geometry
        assert Geometry.CARD_RADIUS > 0

    def test_sidebar_width(self):
        from config import Geometry
        assert Geometry.SIDEBAR_WIDTH > 0

    def test_window_min(self):
        from config import Geometry
        assert len(Geometry.WINDOW_MIN) == 2
        assert Geometry.WINDOW_MIN[0] > 0
        assert Geometry.WINDOW_MIN[1] > 0
