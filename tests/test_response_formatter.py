"""Tests for the v2.0 Structured Response Formatter."""

import pytest
from core.response_formatter import (
    Platform, TableData, StructuredResponse, ResponseFormatter,
    from_intent_result,
)


class TestStructuredResponse:
    """Basic StructuredResponse dataclass tests."""

    def test_defaults(self):
        r = StructuredResponse()
        assert r.title == ""
        assert r.body == ""
        assert r.status == "success"
        assert r.tables == []
        assert r.metrics == {}
        assert r.actions == []
        assert r.progress is None

    def test_custom_fields(self):
        r = StructuredResponse(
            title="Test", body="Body", status="error",
            metrics={"key": "val"}, agent_name="Scout", agent_emoji="🔍",
        )
        assert r.title == "Test"
        assert r.status == "error"
        assert r.agent_name == "Scout"
        assert r.metrics["key"] == "val"


class TestTableData:
    def test_table_creation(self):
        t = TableData(headers=["A", "B"], rows=[["1", "2"]], title="T")
        assert t.headers == ["A", "B"]
        assert len(t.rows) == 1
        assert t.title == "T"


class TestPlatformEnum:
    def test_values(self):
        assert Platform.CLI.value == "cli"
        assert Platform.DISCORD.value == "discord"
        assert Platform.TELEGRAM.value == "telegram"
        assert Platform.GUI.value == "gui"


class TestCLIRenderer:
    """Test CLI rendering output."""

    def setup_method(self):
        self.fmt = ResponseFormatter()

    def test_simple_title(self):
        r = StructuredResponse(title="Hello", status="success")
        out = self.fmt.render(r, Platform.CLI)
        assert "Hello" in out
        assert "\033[1m" in out  # bold

    def test_metrics_aligned(self):
        r = StructuredResponse(metrics={"Leads": 42, "Emails": 10})
        out = self.fmt.render(r, Platform.CLI)
        assert "Leads" in out
        assert "42" in out
        assert "Emails" in out

    def test_table_rendering(self):
        table = TableData(headers=["Name", "Score"], rows=[["Lead A", "85"]])
        r = StructuredResponse(tables=[table])
        out = self.fmt.render(r, Platform.CLI)
        assert "Name" in out
        assert "Lead A" in out
        assert "85" in out
        assert "─" in out  # separator

    def test_progress_bar(self):
        r = StructuredResponse(progress=0.5)
        out = self.fmt.render(r, Platform.CLI)
        assert "50%" in out
        assert "█" in out

    def test_actions(self):
        r = StructuredResponse(actions=["hunt", "status"])
        out = self.fmt.render(r, Platform.CLI)
        assert "→ hunt" in out
        assert "→ status" in out

    def test_agent_prefix(self):
        r = StructuredResponse(title="Task Done", agent_emoji="🔍")
        out = self.fmt.render(r, Platform.CLI)
        assert "🔍" in out

    def test_error_status(self):
        r = StructuredResponse(title="Failed", status="error")
        out = self.fmt.render(r, Platform.CLI)
        assert "\033[31m" in out  # red


class TestDiscordRenderer:
    def setup_method(self):
        self.fmt = ResponseFormatter()

    def test_markdown_bold(self):
        r = StructuredResponse(title="Stats", status="info")
        out = self.fmt.render(r, Platform.DISCORD)
        assert "**" in out
        assert "Stats" in out

    def test_metrics_piped(self):
        r = StructuredResponse(metrics={"A": 1, "B": 2})
        out = self.fmt.render(r, Platform.DISCORD)
        assert "**A:**" in out
        assert "|" in out

    def test_table_in_code_block(self):
        table = TableData(headers=["X"], rows=[["Y"]])
        r = StructuredResponse(tables=[table])
        out = self.fmt.render(r, Platform.DISCORD)
        assert "```" in out

    def test_progress_bold(self):
        r = StructuredResponse(progress=0.75)
        out = self.fmt.render(r, Platform.DISCORD)
        assert "**75%**" in out

    def test_actions_as_code(self):
        r = StructuredResponse(actions=["approve"])
        out = self.fmt.render(r, Platform.DISCORD)
        assert "`approve`" in out


class TestTelegramRenderer:
    def setup_method(self):
        self.fmt = ResponseFormatter()

    def test_html_bold(self):
        r = StructuredResponse(title="Report", status="success")
        out = self.fmt.render(r, Platform.TELEGRAM)
        assert "<b>" in out
        assert "Report" in out

    def test_pre_table(self):
        table = TableData(headers=["H"], rows=[["V"]])
        r = StructuredResponse(tables=[table])
        out = self.fmt.render(r, Platform.TELEGRAM)
        assert "<pre>" in out

    def test_metrics_html(self):
        r = StructuredResponse(metrics={"Rate": "5%"})
        out = self.fmt.render(r, Platform.TELEGRAM)
        assert "<b>Rate:</b>" in out

    def test_code_actions(self):
        r = StructuredResponse(actions=["deny"])
        out = self.fmt.render(r, Platform.TELEGRAM)
        assert "<code>deny</code>" in out


class TestGUIRenderer:
    def setup_method(self):
        self.fmt = ResponseFormatter()

    def test_html_structure(self):
        r = StructuredResponse(title="GUI Test", body="Content", status="success")
        out = self.fmt.render(r, Platform.GUI)
        assert "<div" in out
        assert "GUI Test" in out
        assert "Content" in out

    def test_table_html(self):
        table = TableData(headers=["Col1"], rows=[["Val1"]])
        r = StructuredResponse(tables=[table])
        out = self.fmt.render(r, Platform.GUI)
        assert "<table" in out
        assert "<th" in out
        assert "Col1" in out
        assert "Val1" in out

    def test_progress_div(self):
        r = StructuredResponse(progress=0.3, status="info")
        out = self.fmt.render(r, Platform.GUI)
        assert "30%" in out
        assert "width:30%" in out


class TestDiscordEmbed:
    def setup_method(self):
        self.fmt = ResponseFormatter()

    def test_embed_structure(self):
        r = StructuredResponse(title="Embed", body="Desc", status="success",
                               agent_name="Scout", agent_emoji="🔍")
        embed = self.fmt.render_embed(r)
        assert embed["title"] == "Embed"
        assert embed["description"] == "Desc"
        assert embed["color"] == 0x22C55E
        assert embed["footer"]["text"] == "🔍 Scout"

    def test_embed_metrics_as_fields(self):
        r = StructuredResponse(metrics={"A": 1, "B": 2})
        embed = self.fmt.render_embed(r)
        assert len(embed["fields"]) == 2
        assert embed["fields"][0]["inline"] is True

    def test_embed_no_footer_without_agent(self):
        r = StructuredResponse(title="No agent")
        embed = self.fmt.render_embed(r)
        assert "footer" not in embed


class TestFromIntentResult:
    """Test the intent→StructuredResponse factory."""

    def test_failed_result(self):
        r = from_intent_result("any", {"success": False, "error": "Boom"})
        assert r.status == "error"
        assert "Boom" in r.body

    def test_show_stats(self):
        r = from_intent_result("show_stats", {
            "success": True,
            "data": {"campaigns": 5, "leads": 100, "_internal": "x"},
        })
        assert r.status == "info"
        assert r.metrics["campaigns"] == 5
        assert "_internal" not in r.metrics

    def test_start_campaign(self):
        r = from_intent_result("start_campaign", {
            "success": True,
            "data": {"niche": "plumbing", "city": "Austin", "campaign_id": 42},
        })
        assert r.status == "success"
        assert "plumbing" in r.body
        assert r.metrics["Campaign ID"] == 42

    def test_crm_sync(self):
        r = from_intent_result("crm_sync", {
            "success": True,
            "data": {"synced": 10, "failed": 2},
        })
        assert r.metrics["Synced"] == 10
        assert r.metrics["Failed"] == 2

    def test_enrich_list(self):
        r = from_intent_result("enrich_list", {
            "success": True,
            "data": {"emails_found": 8, "total_attempted": 10},
        })
        assert r.progress == pytest.approx(0.8)

    def test_inbox_triage(self):
        r = from_intent_result("inbox_triage", {
            "success": True,
            "data": {"total_emails": 50, "replies": 5, "bounces": 2},
        })
        assert r.metrics["Replies"] == 5

    def test_export_report(self):
        r = from_intent_result("export_report", {
            "success": True,
            "data": {"campaign_name": "Test", "path": "/tmp/report.pdf"},
        })
        assert "Test" in r.body
        assert "/tmp/report.pdf" in r.attachments

    def test_set_budget(self):
        r = from_intent_result("set_budget", {"success": True, "data": {}})
        assert r.status == "success"

    def test_show_budget(self):
        r = from_intent_result("show_budget", {
            "success": True,
            "data": {"budget_usd": 100, "spent_usd": 25,
                     "current_max_tier": "sonnet", "status": "active"},
        })
        assert "$100.00" in r.metrics["Budget"]
        assert "$25.00" in r.metrics["Spent"]

    def test_show_invoices(self):
        r = from_intent_result("show_invoices", {
            "success": True,
            "data": [
                {"invoice_number": "INV-001", "client_name": "Acme",
                 "total": 500, "status": "draft"},
            ],
        })
        assert len(r.tables) == 1
        assert r.tables[0].rows[0][0] == "INV-001"

    def test_create_invoice(self):
        r = from_intent_result("create_invoice", {
            "success": True,
            "data": {"invoice_number": "INV-002", "total": 1500},
        })
        assert r.metrics["Invoice #"] == "INV-002"
        assert "invoice-pdf" in r.actions

    def test_fallback_with_answer(self):
        r = from_intent_result("unknown_intent", {
            "success": True,
            "data": {"answer": "Custom answer"},
        })
        assert r.body == "Custom answer"

    def test_fallback_string(self):
        r = from_intent_result("unknown", {"success": True, "data": {}},
                               fallback="Fallback text")
        assert r.body == "Fallback text"

    def test_fallback_done(self):
        r = from_intent_result("unknown", {"success": True, "data": {}})
        assert r.body == "Done."
