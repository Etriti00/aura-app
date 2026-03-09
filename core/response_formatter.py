"""
Aura v2.0 — Structured Response Formatter
Renders unified StructuredResponse objects to platform-specific formats:
CLI (ANSI), Discord (Markdown/embed), Telegram (HTML), GUI (rich HTML).
"""

import enum
from dataclasses import dataclass, field
from typing import Optional


class Platform(str, enum.Enum):
    CLI = "cli"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    GUI = "gui"


@dataclass
class TableData:
    """Tabular data for structured display."""
    headers: list[str]
    rows: list[list[str]]
    title: str = ""


@dataclass
class StructuredResponse:
    """Platform-agnostic response container."""
    title: str = ""
    body: str = ""
    status: str = "success"           # success / error / warning / info
    tables: list[TableData] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)      # key→value pairs
    actions: list[str] = field(default_factory=list)  # suggested next actions
    attachments: list[str] = field(default_factory=list)
    progress: Optional[float] = None                  # 0.0-1.0
    agent_name: str = ""
    agent_emoji: str = ""


# ─── Status Symbols ───────────────────────────────────────────────────────────

_CLI_STATUS = {"success": "\033[32m✓\033[0m", "error": "\033[31m✗\033[0m",
               "warning": "\033[33m!\033[0m", "info": "\033[34mℹ\033[0m"}
_DISCORD_STATUS = {"success": ":white_check_mark:", "error": ":x:",
                   "warning": ":warning:", "info": ":information_source:"}
_TELEGRAM_STATUS = {"success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️"}
_DISCORD_COLORS = {"success": 0x22C55E, "error": 0xEF4444,
                   "warning": 0xF59E0B, "info": 0x4E5BF2}


class ResponseFormatter:
    """Renders StructuredResponse objects to platform-specific output."""

    def render(self, response: StructuredResponse, platform: Platform) -> str:
        """Render a StructuredResponse for the given platform."""
        renderers = {
            Platform.CLI: self._render_cli,
            Platform.DISCORD: self._render_discord,
            Platform.TELEGRAM: self._render_telegram,
            Platform.GUI: self._render_gui,
        }
        return renderers[platform](response)

    def render_embed(self, response: StructuredResponse) -> dict:
        """Return a Discord embed dict for rich display."""
        embed = {
            "title": response.title or "Aura",
            "description": response.body[:4096] if response.body else "",
            "color": _DISCORD_COLORS.get(response.status, 0x4E5BF2),
        }
        fields = []
        for k, v in response.metrics.items():
            fields.append({"name": str(k), "value": str(v), "inline": True})
        if fields:
            embed["fields"] = fields[:25]  # Discord limit
        if response.agent_name:
            embed["footer"] = {"text": f"{response.agent_emoji} {response.agent_name}"}
        return embed

    # ─── CLI Renderer ─────────────────────────────────────────────────────

    def _render_cli(self, r: StructuredResponse) -> str:
        lines = []
        status_sym = _CLI_STATUS.get(r.status, "")

        # Title
        if r.title:
            agent_prefix = f"{r.agent_emoji} " if r.agent_emoji else ""
            lines.append(f"{status_sym} {agent_prefix}\033[1m{r.title}\033[0m")

        # Body
        if r.body:
            lines.append(r.body)

        # Metrics
        if r.metrics:
            lines.append("")
            max_key = max(len(str(k)) for k in r.metrics) if r.metrics else 0
            for k, v in r.metrics.items():
                lines.append(f"  {str(k).ljust(max_key)}  {v}")

        # Tables
        for table in r.tables:
            lines.append("")
            if table.title:
                lines.append(f"  \033[1m{table.title}\033[0m")
            lines.append(self._cli_table(table.headers, table.rows))

        # Progress
        if r.progress is not None:
            pct = int(r.progress * 100)
            bar_len = 20
            filled = int(bar_len * r.progress)
            bar = "█" * filled + "░" * (bar_len - filled)
            lines.append(f"  [{bar}] {pct}%")

        # Actions
        if r.actions:
            lines.append("")
            for action in r.actions:
                lines.append(f"  → {action}")

        return "\n".join(lines)

    def _cli_table(self, headers: list[str], rows: list[list[str]]) -> str:
        """Format a table with aligned columns for CLI."""
        if not headers:
            return ""
        all_rows = [headers] + rows
        col_widths = []
        for i in range(len(headers)):
            w = max(len(str(row[i])) if i < len(row) else 0 for row in all_rows)
            col_widths.append(w)

        lines = []
        # Header
        header_line = "  " + "  ".join(
            str(headers[i]).ljust(col_widths[i]) for i in range(len(headers))
        )
        lines.append(f"\033[1m{header_line}\033[0m")
        lines.append("  " + "  ".join("─" * w for w in col_widths))
        # Rows
        for row in rows:
            cells = []
            for i in range(len(headers)):
                val = str(row[i]) if i < len(row) else ""
                cells.append(val.ljust(col_widths[i]))
            lines.append("  " + "  ".join(cells))
        return "\n".join(lines)

    # ─── Discord Renderer ──────────────────────────────────────────────────

    def _render_discord(self, r: StructuredResponse) -> str:
        lines = []
        status_sym = _DISCORD_STATUS.get(r.status, "")

        if r.title:
            agent_prefix = f"{r.agent_emoji} " if r.agent_emoji else ""
            lines.append(f"{status_sym} **{agent_prefix}{r.title}**")

        if r.body:
            lines.append(r.body)

        if r.metrics:
            metric_lines = [f"**{k}:** {v}" for k, v in r.metrics.items()]
            lines.append(" | ".join(metric_lines))

        for table in r.tables:
            if table.title:
                lines.append(f"\n**{table.title}**")
            # Discord code block table
            header_line = " | ".join(table.headers)
            sep_line = " | ".join("---" for _ in table.headers)
            lines.append(f"```\n{header_line}\n{sep_line}")
            for row in table.rows[:20]:  # limit rows for Discord
                lines.append(" | ".join(str(c) for c in row))
            lines.append("```")

        if r.progress is not None:
            pct = int(r.progress * 100)
            lines.append(f"Progress: **{pct}%**")

        if r.actions:
            lines.append("\n" + " ".join(f"`{a}`" for a in r.actions))

        return "\n".join(lines)

    # ─── Telegram Renderer ──────────────────────────────────────────────────

    def _render_telegram(self, r: StructuredResponse) -> str:
        lines = []
        status_sym = _TELEGRAM_STATUS.get(r.status, "")

        if r.title:
            agent_prefix = f"{r.agent_emoji} " if r.agent_emoji else ""
            lines.append(f"{status_sym} <b>{agent_prefix}{r.title}</b>")

        if r.body:
            lines.append(r.body)

        if r.metrics:
            metric_parts = []
            for k, v in r.metrics.items():
                metric_parts.append(f"<b>{k}:</b> {v}")
            lines.append("\n".join(metric_parts))

        for table in r.tables:
            if table.title:
                lines.append(f"\n<b>{table.title}</b>")
            lines.append("<pre>")
            lines.append(" | ".join(table.headers))
            for row in table.rows[:30]:
                lines.append(" | ".join(str(c) for c in row))
            lines.append("</pre>")

        if r.progress is not None:
            pct = int(r.progress * 100)
            lines.append(f"Progress: <b>{pct}%</b>")

        if r.actions:
            lines.append("\n" + " | ".join(f"<code>{a}</code>" for a in r.actions))

        return "\n".join(lines)

    # ─── GUI Renderer ───────────────────────────────────────────────────────

    def _render_gui(self, r: StructuredResponse) -> str:
        parts = []
        status_color = {"success": "#22C55E", "error": "#EF4444",
                        "warning": "#F59E0B", "info": "#4E5BF2"}.get(r.status, "#4E5BF2")

        if r.title:
            agent_prefix = f"{r.agent_emoji} " if r.agent_emoji else ""
            parts.append(
                f'<div style="font-weight:600;font-size:14px;color:{status_color};'
                f'margin-bottom:6px;">{agent_prefix}{r.title}</div>'
            )

        if r.body:
            parts.append(f'<div style="margin-bottom:8px;">{r.body}</div>')

        if r.metrics:
            metric_html = []
            for k, v in r.metrics.items():
                metric_html.append(
                    f'<span style="margin-right:16px;"><b>{k}:</b> {v}</span>'
                )
            parts.append(f'<div style="margin-bottom:8px;">{"".join(metric_html)}</div>')

        for table in r.tables:
            if table.title:
                parts.append(f'<div style="font-weight:600;margin:8px 0 4px;">{table.title}</div>')
            parts.append('<table style="border-collapse:collapse;width:100%;font-size:12px;">')
            parts.append("<tr>")
            for h in table.headers:
                parts.append(
                    f'<th style="text-align:left;padding:4px 8px;border-bottom:1px solid '
                    f'rgba(255,255,255,0.1);color:{status_color};">{h}</th>'
                )
            parts.append("</tr>")
            for i, row in enumerate(table.rows):
                bg = "rgba(255,255,255,0.02)" if i % 2 else "transparent"
                parts.append(f'<tr style="background:{bg};">')
                for c in row:
                    parts.append(f'<td style="padding:4px 8px;">{c}</td>')
                parts.append("</tr>")
            parts.append("</table>")

        if r.progress is not None:
            pct = int(r.progress * 100)
            parts.append(
                f'<div style="margin:8px 0;"><div style="background:rgba(255,255,255,0.1);'
                f'border-radius:4px;height:8px;overflow:hidden;">'
                f'<div style="background:{status_color};width:{pct}%;height:100%;"></div>'
                f'</div><div style="font-size:11px;margin-top:2px;">{pct}%</div></div>'
            )

        if r.actions:
            action_btns = " ".join(
                f'<span style="background:rgba(78,91,242,0.15);padding:2px 8px;'
                f'border-radius:4px;font-size:11px;margin-right:4px;">{a}</span>'
                for a in r.actions
            )
            parts.append(f'<div style="margin-top:8px;">{action_btns}</div>')

        return "\n".join(parts)


# ─── Factory from intent result ──────────────────────────────────────────────

def from_intent_result(intent: str, result: dict,
                       fallback: str = "") -> StructuredResponse:
    """Convert an orchestrator execution result into a StructuredResponse."""
    if not result.get("success"):
        return StructuredResponse(
            title="Action Failed",
            body=result.get("error", fallback or "Unknown error"),
            status="error",
        )

    data = result.get("data", {})

    if intent == "show_stats":
        metrics = {}
        if isinstance(data, dict):
            metrics = {k: v for k, v in data.items() if not str(k).startswith("_")}
        return StructuredResponse(
            title="Dashboard Stats",
            status="info",
            metrics=metrics,
        )

    if intent == "start_campaign":
        return StructuredResponse(
            title="Campaign Created",
            body=f"{data.get('niche', '')} in {data.get('city', '')}",
            status="success",
            metrics={"Campaign ID": data.get("campaign_id", "")},
            actions=["hunt", "status"],
        )

    if intent == "crm_sync":
        return StructuredResponse(
            title="CRM Sync Complete",
            status="success",
            metrics={
                "Synced": data.get("synced", 0),
                "Failed": data.get("failed", 0),
            },
        )

    if intent == "enrich_list":
        total = data.get("total_attempted", 0)
        found = data.get("emails_found", 0)
        progress = found / total if total > 0 else 0
        return StructuredResponse(
            title="Enrichment Complete",
            status="success",
            metrics={
                "Emails Found": found,
                "Total Attempted": total,
            },
            progress=progress,
        )

    if intent == "inbox_triage":
        return StructuredResponse(
            title="Inbox Triage Complete",
            status="success",
            metrics={
                "Emails": data.get("total_emails", 0),
                "Replies": data.get("replies", 0),
                "Bounces": data.get("bounces", 0),
            },
        )

    if intent == "export_report":
        return StructuredResponse(
            title="Report Ready",
            body=f"Report for {data.get('campaign_name', 'campaign')}",
            status="success",
            attachments=[data.get("path", "")] if data.get("path") else [],
        )

    if intent == "set_budget":
        return StructuredResponse(
            title="Budget Updated",
            body=fallback or "Budget settings saved.",
            status="success",
        )

    if intent == "show_budget":
        if isinstance(data, dict):
            return StructuredResponse(
                title="Budget Status",
                status="info",
                metrics={
                    "Budget": f"${data.get('budget_usd', 0):.2f}",
                    "Spent": f"${data.get('spent_usd', 0):.2f}",
                    "Tier": data.get("current_max_tier", "N/A"),
                    "Status": data.get("status", "N/A"),
                },
            )

    if intent == "show_invoices":
        if isinstance(data, list):
            headers = ["#", "Client", "Total", "Status"]
            rows = []
            for inv in data:
                rows.append([
                    inv.get("invoice_number", ""),
                    inv.get("client_name", ""),
                    f"${inv.get('total', 0):.2f}",
                    inv.get("status", ""),
                ])
            return StructuredResponse(
                title="Invoices",
                status="info",
                tables=[TableData(headers=headers, rows=rows)],
            )

    if intent == "create_invoice":
        return StructuredResponse(
            title="Invoice Created",
            status="success",
            metrics={
                "Invoice #": data.get("invoice_number", ""),
                "Total": f"${data.get('total', 0):.2f}",
            },
            actions=["invoice-pdf", "invoice-approve"],
        )

    # Fallback
    body = fallback
    if not body and isinstance(data, dict) and data.get("answer"):
        body = data["answer"]
    if not body:
        body = "Done."

    return StructuredResponse(
        title="",
        body=body,
        status="success",
    )
