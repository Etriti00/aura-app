#!/usr/bin/env python3
"""
Aura CLI — Advanced Terminal Interface
Full feature parity with the GUI application.
"""

import sys
import os
import argparse
import json
import logging
import shlex
import signal
import subprocess
import textwrap
import warnings
from datetime import datetime, timedelta
from collections import OrderedDict

# Fix Windows terminal encoding — enable UTF-8 output for Unicode chars
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import APP_NAME, APP_VERSION
from utils.logger import get_logger

logger = get_logger("cli")


# ═══════════════════════════════════════════════════════════════════════════════
#  Formatter — ANSI Terminal Output
# ═══════════════════════════════════════════════════════════════════════════════

class Formatter:
    """ANSI terminal output formatting with auto-detection."""

    _use_color = True

    @classmethod
    def init(cls):
        """Detect terminal color support."""
        if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
            cls._use_color = False
            return
        if sys.platform == "win32":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except Exception:
                cls._use_color = False

    @classmethod
    def _wrap(cls, code: str, text: str) -> str:
        if not cls._use_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    @classmethod
    def bold(cls, text: str) -> str:
        return cls._wrap("1", text)

    @classmethod
    def dim(cls, text: str) -> str:
        return cls._wrap("2", text)

    @classmethod
    def green(cls, text: str) -> str:
        return cls._wrap("32", text)

    @classmethod
    def red(cls, text: str) -> str:
        return cls._wrap("31", text)

    @classmethod
    def yellow(cls, text: str) -> str:
        return cls._wrap("33", text)

    @classmethod
    def cyan(cls, text: str) -> str:
        return cls._wrap("36", text)

    @classmethod
    def blue(cls, text: str) -> str:
        return cls._wrap("34", text)

    @classmethod
    def magenta(cls, text: str) -> str:
        return cls._wrap("35", text)

    @classmethod
    def header(cls, text: str):
        """Print a bold section header."""
        print(f"\n{cls.bold(text)}")
        print(cls.dim("─" * min(len(text) + 4, 60)))

    @classmethod
    def success(cls, text: str):
        print(f"  {cls.green('✓')} {text}")

    @classmethod
    def error(cls, text: str):
        print(f"  {cls.red('✗')} {text}")

    @classmethod
    def warn(cls, text: str):
        print(f"  {cls.yellow('!')} {text}")

    @classmethod
    def info(cls, text: str):
        print(f"  {cls.cyan('→')} {text}")

    @classmethod
    def badge(cls, label: str, color_fn=None) -> str:
        fn = color_fn or cls.cyan
        return fn(f"[{label}]")

    @classmethod
    def kv(cls, key: str, value, pad: int = 18):
        """Print a key-value pair with aligned padding."""
        print(f"  {cls.dim(key.ljust(pad))} {value}")

    @classmethod
    def table(cls, headers: list, rows: list, col_widths: list = None):
        """Print a simple table with headers and rows."""
        if not rows:
            print(cls.dim("  (no data)"))
            return
        if not col_widths:
            col_widths = []
            for i, h in enumerate(headers):
                max_w = len(str(h))
                for row in rows:
                    if i < len(row):
                        max_w = max(max_w, len(str(row[i])))
                col_widths.append(min(max_w + 2, 40))

        # Header
        header_line = ""
        for i, h in enumerate(headers):
            header_line += cls.bold(str(h).ljust(col_widths[i]))
        print(f"  {header_line}")
        print(f"  {cls.dim('─' * sum(col_widths))}")

        # Rows
        for row in rows:
            line = ""
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    s = str(cell) if cell is not None else ""
                    if len(s) > col_widths[i] - 2:
                        s = s[:col_widths[i] - 4] + "…"
                    line += s.ljust(col_widths[i])
            print(f"  {line}")

    @classmethod
    def progress_bar(cls, current: int, total: int, width: int = 30):
        """Print an inline progress bar."""
        if total <= 0:
            return
        pct = min(current / total, 1.0)
        filled = int(width * pct)
        bar = "█" * filled + "░" * (width - filled)
        print(f"\r  {bar} {current}/{total} ({pct:.0%})", end="", flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  CommandRegistry — Decorator-based command registration
# ═══════════════════════════════════════════════════════════════════════════════

_COMMAND_REGISTRY = OrderedDict()

COMMAND_GROUPS = OrderedDict([
    ("pipeline",      "Lead Pipeline"),
    ("campaigns",     "Campaigns"),
    ("leads",         "Leads"),
    ("fleet",         "Fleet & Agents"),
    ("kanban",        "Kanban & Tickets"),
    ("skills",        "Skills"),
    ("research",      "Research"),
    ("voice",         "Voice Calls"),
    ("budget",        "Budget & Pacing"),
    ("trends",        "Trends"),
    ("autonomy",      "Autonomy"),
    ("suppression",   "Suppression"),
    ("integrations",  "Integrations"),
    ("history",       "History"),
    ("knowledge",     "Knowledge & Memory"),
    ("config",        "Configuration"),
    ("system",        "System"),
])


def command(name: str, group: str, help_text: str, usage: str = ""):
    """Decorator to register a CLI command."""
    def decorator(fn):
        _COMMAND_REGISTRY[name] = {
            "fn": fn,
            "group": group,
            "help": help_text,
            "usage": usage or f"/{name}",
            "name": name,
        }
        return fn
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
#  HelpSystem — Grouped /help pages
# ═══════════════════════════════════════════════════════════════════════════════

class HelpSystem:
    """Terminal help system with grouped pages and per-command help."""

    @staticmethod
    def show_overview():
        f = Formatter
        print(f"\n{f.bold(APP_NAME)} v{APP_VERSION} — AI Sales Agent CLI")
        print(f.dim("Type /help <group> or /help <command> for details.\n"))

        for group_key, group_label in COMMAND_GROUPS.items():
            cmds = [c for c in _COMMAND_REGISTRY.values() if c["group"] == group_key]
            if not cmds:
                continue
            cmd_names = ", ".join(f.cyan(f"/{c['name']}") for c in cmds)
            print(f"  {f.bold(group_label.ljust(20))} {cmd_names}")
        print()

    @staticmethod
    def show_group(group_key: str):
        f = Formatter
        label = COMMAND_GROUPS.get(group_key, group_key)
        cmds = [c for c in _COMMAND_REGISTRY.values() if c["group"] == group_key]
        if not cmds:
            f.error(f"Unknown group: {group_key}")
            print(f"  Available groups: {', '.join(COMMAND_GROUPS.keys())}")
            return
        f.header(f"{label} Commands")
        for c in cmds:
            print(f"  {f.cyan(c['usage'].ljust(40))} {c['help']}")
        print()

    @staticmethod
    def show_command(cmd_name: str):
        f = Formatter
        name = cmd_name.lstrip("/")
        cmd = _COMMAND_REGISTRY.get(name)
        if not cmd:
            f.error(f"Unknown command: /{name}")
            return
        group_label = COMMAND_GROUPS.get(cmd["group"], cmd["group"])
        print(f"\n  {f.bold('Command:')}  {f.cyan('/' + name)}")
        print(f"  {f.bold('Group:')}    {group_label}")
        print(f"  {f.bold('Usage:')}    {cmd['usage']}")
        print(f"  {f.bold('About:')}    {cmd['help']}")
        print()


# ═══════════════════════════════════════════════════════════════════════════════
#  AuraCLI — Main CLI Application
# ═══════════════════════════════════════════════════════════════════════════════

class AuraCLI:
    """Advanced CLI with full engine initialization and REPL."""

    def __init__(self, skip_init: bool = False):
        self.db = None
        self.key_vault = None
        self.engines = {}
        self._engines_dict = {}
        if not skip_init:
            self._init_engines()

    # ─── Engine Initialization (mirrors main_window.py) ─────────────────────

    def _init_engines(self):
        """Full engine initialization mirroring GUI's main_window._init_controllers."""
        from database.db_manager import DatabaseManager
        from core.key_vault import KeyVault

        # Phase 1: Database
        self.db = DatabaseManager()
        self.db.init_db()
        self.db.migrate_schema()
        self.db.seed_defaults()
        self.db.seed_default_agents()

        # Phase 2: Key Vault + migration
        self.key_vault = KeyVault()
        self._migrate_keys()

        # Phase 3: Safety Guard
        from core.safety_guard import SafetyGuard
        self.engines["safety"] = SafetyGuard()

        # Phase 4: AI Engine + Router
        from core.ai_engine import AIEngine
        from core.router_engine import RouterEngine
        self.engines["ai"] = AIEngine(safety_guard=self.engines["safety"])
        self.engines["router"] = RouterEngine(self.db, self.key_vault)
        self.engines["ai"].set_router(self.engines["router"])

        # Phase 5: Suppression
        from core.suppression_engine import SuppressionEngine
        self.engines["suppression"] = SuppressionEngine(self.db)

        # Phase 6: Scraper
        from core.scraper_engine import ScraperEngine
        self.engines["scraper"] = ScraperEngine(
            suppression_engine=self.engines["suppression"]
        )

        # Phase 7: Enrichment
        from core.enrichment_engine import EnrichmentEngine
        self.engines["enrichment"] = EnrichmentEngine(self.db)

        # Phase 8: Delivery
        from core.delivery_engine import DeliveryEngine
        self.engines["delivery"] = DeliveryEngine()

        # Phase 9: Reply Detector
        from core.reply_detector import ReplyDetector
        self.engines["reply"] = ReplyDetector(self.db, self.key_vault)

        # Phase 10: RAG
        from core.rag_engine import RAGEngine
        self.engines["rag"] = RAGEngine(self.db)
        self.engines["ai"].set_rag_engine(self.engines["rag"])
        self.engines["delivery"].rag_engine = self.engines["rag"]
        self.engines["reply"].rag_engine = self.engines["rag"]

        # Phase 11: Channel + CRM + Triage
        from core.channel_engine import ChannelEngine
        from core.crm_engine import CRMEngine
        from core.triage_engine import TriageEngine
        self.engines["channel"] = ChannelEngine(self.db, self.engines["ai"])
        self.engines["crm"] = CRMEngine(self.db, self.key_vault)
        self.engines["triage"] = TriageEngine(
            self.db, self.key_vault,
            ai_engine=self.engines["ai"],
            suppression_engine=self.engines["suppression"],
        )

        # Phase 12: API Queue + Apollo/Hunter/HubSpot/LinkedIn
        from core.api_queue import APIQueue
        from core.apollo_engine import ApolloEngine
        from core.hunter_engine import HunterEngine
        from core.hubspot_engine import HubSpotEngine
        from core.linkedin_engine import LinkedInEngine
        self.engines["api_queue"] = APIQueue(self.db)
        self.engines["apollo"] = ApolloEngine(self.db, self.key_vault, self.engines["api_queue"])
        self.engines["hunter"] = HunterEngine(self.db, self.key_vault, self.engines["api_queue"])
        self.engines["hubspot"] = HubSpotEngine(self.db, self.key_vault, self.engines["api_queue"])
        self.engines["linkedin"] = LinkedInEngine()

        # Wire waterfall enrichment
        self.engines["enrichment"].apollo_engine = self.engines["apollo"]
        self.engines["enrichment"].hunter_engine = self.engines["hunter"]
        self.engines["enrichment"].router_engine = self.engines["router"]

        # Response formatter for structured CLI output
        from core.response_formatter import ResponseFormatter, Platform
        self.formatter = ResponseFormatter()
        self._platform = Platform.CLI

        # Phase 13: Skill Registry
        from core.skill_registry import SkillRegistry
        self.engines["skill_registry"] = SkillRegistry(self.db)
        self.engines["skill_registry"].seed_builtin_skills()

        # Phase 14: Pacing + Batch
        from core.pacing_engine import PacingEngine
        from core.batch_importer import BatchImporter
        self.engines["pacing"] = PacingEngine(self.db, self.engines["router"])
        self.engines["router"].pacing_engine = self.engines["pacing"]
        self.engines["batch"] = BatchImporter(self.db)

        # Phase 15: Sequence + AB + Scheduler
        from core.sequence_engine import SequenceEngine
        from core.ab_engine import ABEngine
        from core.scheduler_engine import SchedulerEngine
        self.engines["sequence"] = SequenceEngine(self.db)
        self.engines["ab"] = ABEngine(self.db)
        self.engines["scheduler"] = SchedulerEngine(self.db)

        # Phase 16: Report + Analyst
        from core.report_engine import ReportEngine
        from core.analyst_engine import AnalystEngine
        self.engines["report"] = ReportEngine(self.db)
        self.engines["analyst"] = AnalystEngine(self.db, self.key_vault)

        # Phase 17: Orchestrator
        from core.orchestrator_engine import OrchestratorEngine
        self.engines["orchestrator"] = OrchestratorEngine(self.db, self.key_vault)

        # Build engines dict for orchestrator
        self._engines_dict = {
            "suppression": self.engines["suppression"],
            "report": self.engines["report"],
            "enrichment": self.engines["enrichment"],
            "apollo": self.engines["apollo"],
            "hunter": self.engines["hunter"],
            "hubspot": self.engines["hubspot"],
            "linkedin": self.engines["linkedin"],
            "router": self.engines["router"],
            "rag": self.engines["rag"],
            "channel": self.engines["channel"],
            "crm": self.engines["crm"],
            "triage": self.engines["triage"],
            "pacing": self.engines["pacing"],
            "skill_registry": self.engines["skill_registry"],
        }

        # Phase 18: Gateway
        from core.gateway_engine import GatewayEngine
        self.engines["gateway"] = GatewayEngine(
            self.db, self.key_vault,
            self.engines["orchestrator"], self._engines_dict,
        )
        self._engines_dict["gateway"] = self.engines["gateway"]

        # Phase 19: Agent + Fleet + Observer + Trends
        from core.agent_engine import AgentEngine
        from core.fleet_orchestrator import FleetOrchestrator
        from core.observer_engine import ObserverEngine
        from core.trends_engine import TrendsEngine
        self.engines["agent"] = AgentEngine(
            self.db, self.key_vault, self.engines["router"],
            pacing_engine=self.engines["pacing"],
        )
        self.engines["fleet"] = FleetOrchestrator(self.db, self.engines["agent"])
        self.engines["observer"] = ObserverEngine(self.db, self.engines["agent"])
        self.engines["trends"] = TrendsEngine(self.db)

        # Phase 20: Ticket + Escalation + Scheduler
        from core.ticket_engine import TicketEngine
        from core.escalation_engine import EscalationEngine
        from core.ticket_scheduler import TicketScheduler
        self.engines["ticket"] = TicketEngine(self.db)
        self.engines["escalation"] = EscalationEngine(
            self.db, self.engines["ticket"], self.engines["agent"],
        )
        self.engines["ticket_scheduler"] = TicketScheduler(
            self.db, self.engines["ticket"], self.engines["agent"],
        )
        self.engines["agent"].escalation_engine = self.engines["escalation"]

        # Phase 21: Command History
        from core.command_history import CommandHistoryEngine
        self.engines["command_history"] = CommandHistoryEngine(self.db)
        self.engines["gateway"].command_history = self.engines["command_history"]
        self.engines["agent"].command_history = self.engines["command_history"]
        self.engines["fleet"].command_history = self.engines["command_history"]

        # Register into engines dict
        self._engines_dict.update({
            "agent": self.engines["agent"],
            "fleet": self.engines["fleet"],
            "observer": self.engines["observer"],
            "trends": self.engines["trends"],
            "ticket": self.engines["ticket"],
            "escalation": self.engines["escalation"],
            "ticket_scheduler": self.engines["ticket_scheduler"],
            "command_history": self.engines["command_history"],
        })

        # Phase 22: Advanced AI engines
        from core.reflection_engine import ReflectionEngine
        from core.lead_lifecycle_engine import LeadLifecycleEngine
        from core.knowledge_graph_engine import KnowledgeGraphEngine
        from core.conversation_engine import ConversationEngine
        from core.self_improvement_engine import SelfImprovementEngine
        from core.strategy_engine import StrategyEngine
        from controllers.autonomy_controller import AutonomyController

        self.engines["reflection"] = ReflectionEngine(
            self.db, router_engine=self.engines["router"]
        )
        self.engines["lifecycle"] = LeadLifecycleEngine(
            self.db, fleet_orchestrator=self.engines["fleet"]
        )
        self.engines["knowledge_graph"] = KnowledgeGraphEngine(
            self.db, rag_engine=self.engines["rag"]
        )
        self.engines["conversation"] = ConversationEngine(
            self.db, router_engine=self.engines["router"],
            rag_engine=self.engines["rag"],
            knowledge_graph=self.engines["knowledge_graph"],
        )
        self.engines["self_improvement"] = SelfImprovementEngine(
            self.db, reflection_engine=self.engines["reflection"],
            rag_engine=self.engines["rag"],
            fleet_orchestrator=self.engines["fleet"],
        )
        self.engines["strategy"] = StrategyEngine(
            self.db, fleet_orchestrator=self.engines["fleet"],
            knowledge_graph=self.engines["knowledge_graph"],
        )
        self.engines["autonomy"] = AutonomyController(self.db)

        # Cross-wire advanced engines into agent
        self.engines["agent"].reflection_engine = self.engines["reflection"]
        self.engines["agent"].knowledge_graph = self.engines["knowledge_graph"]
        self.engines["agent"].self_improvement_engine = self.engines["self_improvement"]
        self.engines["agent"].autonomy_controller = self.engines["autonomy"]

        # Wire into reply detector
        self.engines["reply"].conversation_engine = self.engines["conversation"]
        self.engines["reply"].lead_lifecycle_engine = self.engines["lifecycle"]
        self.engines["reply"].knowledge_graph_engine = self.engines["knowledge_graph"]
        self.engines["reply"].strategy_engine = self.engines["strategy"]

        # Wire into enrichment
        self.engines["enrichment"].lead_lifecycle_engine = self.engines["lifecycle"]
        self.engines["enrichment"].knowledge_graph_engine = self.engines["knowledge_graph"]

        # Wire command history into advanced engines
        self.engines["autonomy"].command_history = self.engines["command_history"]
        self.engines["lifecycle"].command_history = self.engines["command_history"]
        self.engines["reflection"].command_history = self.engines["command_history"]

        # Phase 23: Token Manager + Case + Subagent
        from core.token_manager import TokenManager
        from core.case_engine import CaseEngine
        from core.subagent_engine import SubagentEngine
        self.engines["token_manager"] = TokenManager(
            self.db, router_engine=self.engines["router"],
        )
        self.engines["case"] = CaseEngine(
            self.db, router_engine=self.engines["router"],
            token_manager=self.engines["token_manager"],
        )
        self.engines["subagent"] = SubagentEngine(
            self.db, router_engine=self.engines["router"],
        )

        # Inject into agent
        self.engines["agent"].token_manager = self.engines["token_manager"]
        self.engines["agent"].case_engine = self.engines["case"]
        self.engines["agent"].subagent_engine = self.engines["subagent"]

        # Inject case into lifecycle + reflection
        self.engines["lifecycle"].case_engine = self.engines["case"]
        self.engines["reflection"].case_engine = self.engines["case"]

        # Phase 24: Research
        from core.research_engine import ResearchEngine
        self.engines["research"] = ResearchEngine(
            self.db, router_engine=self.engines["router"],
            key_vault=self.key_vault,
        )
        self.engines["research"].case_engine = self.engines["case"]
        self.engines["research"].configure(self.key_vault)

        # Phase 25: Voice
        from core.voice_call_engine import VoiceCallEngine
        self.engines["voice"] = VoiceCallEngine(
            self.db, router_engine=self.engines["router"],
            key_vault=self.key_vault,
        )
        self.engines["voice"].case_engine = self.engines["case"]
        self.engines["voice"].research_engine = self.engines["research"]
        self.engines["voice"].lead_lifecycle_engine = self.engines["lifecycle"]
        self.engines["voice"].configure(self.key_vault)

        # Register remaining engines
        self._engines_dict.update({
            "reflection": self.engines["reflection"],
            "lifecycle": self.engines["lifecycle"],
            "knowledge_graph": self.engines["knowledge_graph"],
            "conversation": self.engines["conversation"],
            "self_improvement": self.engines["self_improvement"],
            "strategy": self.engines["strategy"],
            "autonomy": self.engines["autonomy"],
            "analyst": self.engines["analyst"],
            "token_manager": self.engines["token_manager"],
            "case": self.engines["case"],
            "subagent": self.engines["subagent"],
            "research": self.engines["research"],
            "voice": self.engines["voice"],
        })

        # Configure AI engine with saved keys
        self._configure_ai()
        logger.debug("CLI engine initialization complete (%d engines)", len(self.engines))

    def _migrate_keys(self):
        """Migrate legacy encryption keys if needed."""
        settings = self.db.get_settings()
        if not settings:
            return
        enc_fields = [
            "gemini_key_enc", "anthropic_key_enc", "openai_key_enc",
            "openrouter_key_enc", "resend_key_enc", "smtp_password_enc",
            "apollo_key_enc", "hunter_key_enc", "hubspot_key_enc",
            "tavily_key_enc", "firecrawl_key_enc", "apify_key_enc",
            "twilio_account_sid_enc", "twilio_auth_token_enc",
            "elevenlabs_key_enc",
        ]
        updated = False
        for field in enc_fields:
            val = getattr(settings, field, None)
            if val:
                new_val = self.key_vault.migrate_ciphertext(val)
                if new_val:
                    with self.db.session_scope() as session:
                        from database.schema import Settings as S
                        s = session.query(S).first()
                        setattr(s, field, new_val)
                    updated = True
        if updated:
            logger.info("Migrated encryption keys to new salt")

    def _configure_ai(self):
        """Load API keys and configure AI engine."""
        settings = self.db.get_settings()
        if not settings:
            return

        api_keys = {}
        for provider in ["gemini", "anthropic", "openai", "openrouter"]:
            enc_val = getattr(settings, f"{provider}_key_enc", None)
            if enc_val:
                decrypted = self.key_vault.decrypt(enc_val)
                if decrypted:
                    api_keys[provider] = decrypted

        models = {}
        if settings.tier2_model:
            models["tier2"] = settings.tier2_model
        if settings.tier3_model:
            models["tier3"] = settings.tier3_model

        if api_keys:
            self.engines["ai"].configure(api_keys, models)

        # Configure delivery
        if settings.resend_key_enc:
            key = self.key_vault.decrypt(settings.resend_key_enc)
            if key:
                self.engines["delivery"].configure_resend(key)
        if settings.smtp_host:
            smtp_pass = ""
            if settings.smtp_password_enc:
                smtp_pass = self.key_vault.decrypt(settings.smtp_password_enc) or ""
            self.engines["delivery"].configure_smtp(
                settings.smtp_host, settings.smtp_port or 587,
                settings.smtp_user or "", smtp_pass,
            )

    def _shutdown(self):
        """Gracefully stop all background resources."""
        logger.debug("Shutting down Aura CLI…")
        try:
            if "reply" in self.engines:
                self.engines["reply"].close_connection()
        except Exception:
            pass
        try:
            if "fleet" in self.engines:
                self.engines["fleet"].shutdown_fleet()
        except Exception:
            pass
        try:
            if "enrichment" in self.engines:
                self.engines["enrichment"].end_batch()
        except Exception:
            pass
        try:
            if "voice" in self.engines:
                self.engines["voice"].stop_server()
        except Exception:
            pass
        logger.debug("Shutdown complete.")

    # ─── Helper Methods ─────────────────────────────────────────────────────

    def _get_settings(self):
        return self.db.get_settings()

    def _get_lead_dict(self, lead):
        """Convert a Lead ORM object to a dict."""
        return {
            "id": lead.id,
            "business_name": lead.business_name,
            "category": lead.category,
            "city": lead.city,
            "phone": lead.phone,
            "email": lead.email,
            "source_url": lead.source_url,
            "website_url": lead.website_url,
            "status": lead.status,
            "lifecycle_state": getattr(lead, "lifecycle_state", None),
            "snippet": lead.notes or "",
        }

    def _parse_args(self, text: str) -> list:
        """Parse command arguments respecting quotes."""
        try:
            return shlex.split(text)
        except ValueError:
            return text.split()

    # ═══════════════════════════════════════════════════════════════════════════
    #  PIPELINE COMMANDS
    # ═══════════════════════════════════════════════════════════════════════════

    @command("hunt", "pipeline", "Scrape leads for a niche",
             "/hunt <niche> --city <city> [--limit N] [--sources s1,s2]")
    def cmd_hunt(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/hunt", add_help=False)
        parser.add_argument("niche", nargs="?", help="Business niche")
        parser.add_argument("--city", default="", help="Target city")
        parser.add_argument("--limit", "-n", type=int, default=50)
        parser.add_argument("--sources", default="", help="Comma-separated sources")
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            print(f"  Usage: /hunt <niche> --city <city> [--limit N]")
            return

        if not opts.niche:
            f.error("Niche is required. Usage: /hunt <niche> --city <city>")
            return

        from database.schema import Campaign, Lead

        f.info(f"Hunting for {opts.limit} leads: '{opts.niche}' in '{opts.city}'…")

        kwargs = {
            "query": f"{opts.niche} {opts.city}".strip(),
            "city": opts.city,
            "niche": opts.niche,
            "limit": opts.limit,
        }
        if opts.sources:
            kwargs["sources"] = opts.sources.split(",")

        def on_progress(pct):
            Formatter.progress_bar(pct, 100)

        kwargs["_progress_callback"] = on_progress

        leads = self.engines["scraper"].run(**kwargs)
        print()  # Clear progress bar line

        # Save to campaign
        with self.db.session_scope() as session:
            campaign = Campaign(
                name=f"{opts.niche} — {opts.city}",
                target_niche=opts.niche,
                target_city=opts.city,
                status="active",
            )
            session.add(campaign)
            session.flush()
            campaign_id = campaign.id

        saved = 0
        for ld in leads:
            with self.db.session_scope() as session:
                lead = Lead(
                    campaign_id=campaign_id,
                    business_name=ld.business_name,
                    category=ld.category,
                    city=ld.city,
                    phone=ld.phone,
                    email=ld.email,
                    source_url=ld.source_url,
                    source_platform=ld.source_platform,
                    has_website=ld.has_website,
                    website_url=ld.website_url,
                    status="new",
                )
                session.add(lead)
            saved += 1

        f.success(f"Found {len(leads)} leads, saved {saved} to campaign ID {campaign_id}")

    @command("qualify", "pipeline", "AI-qualify leads in a campaign",
             "/qualify <campaign_id>")
    def cmd_qualify(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /qualify <campaign_id>")
            return
        campaign_id = int(args[0])

        from database.schema import Campaign, Lead
        with self.db.session_scope() as session:
            leads = session.query(Lead).filter_by(
                campaign_id=campaign_id, status="new"
            ).all()
            lead_dicts = [self._get_lead_dict(l) for l in leads]
            campaign = session.query(Campaign).filter_by(id=campaign_id).first()
            niche = campaign.target_niche if campaign else ""

        if not lead_dicts:
            f.warn("No new leads to qualify.")
            return

        f.info(f"Qualifying {len(lead_dicts)} leads…")
        qualified = 0
        for i, ld in enumerate(lead_dicts):
            result = self.engines["ai"].qualify_lead(ld, niche)
            status = "qualified" if result.get("qualified") else "disqualified"
            with self.db.session_scope() as session:
                lead = session.query(Lead).filter_by(id=ld["id"]).first()
                if lead:
                    lead.status = status
                    lead.notes = (lead.notes or "") + f"\n[{status.title()}] Score: {result.get('score', 0)}/10"
            if result.get("qualified"):
                qualified += 1
                f.success(f"{ld['business_name']}: qualified ({result.get('score', 0)}/10)")
            else:
                f.warn(f"{ld['business_name']}: disqualified ({result.get('score', 0)}/10)")
            Formatter.progress_bar(i + 1, len(lead_dicts))
        print()
        f.success(f"Qualified: {qualified}/{len(lead_dicts)}")

    @command("enrich", "pipeline", "Enrich leads with contact data",
             "/enrich <campaign_id> [--waterfall]")
    def cmd_enrich(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /enrich <campaign_id>")
            return
        campaign_id = int(args[0])

        from database.schema import Lead
        with self.db.session_scope() as session:
            leads = session.query(Lead).filter_by(campaign_id=campaign_id).filter(
                Lead.status.in_(["new", "qualified"])
            ).all()
            lead_ids = [l.id for l in leads]

        if not lead_ids:
            f.warn("No leads to enrich.")
            return

        f.info(f"Enriching {len(lead_ids)} leads…")
        for i, lid in enumerate(lead_ids):
            result = self.engines["enrichment"].waterfall_enrich_lead(lid)
            if result.get("success"):
                f.success(f"Lead {lid}: enriched")
            else:
                f.warn(f"Lead {lid}: {result.get('error', 'failed')}")
            Formatter.progress_bar(i + 1, len(lead_ids))
        print()

    @command("draft", "pipeline", "Generate email drafts for qualified leads",
             "/draft <campaign_id>")
    def cmd_draft(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /draft <campaign_id>")
            return
        campaign_id = int(args[0])

        from database.schema import Campaign, Lead, Skill
        with self.db.session_scope() as session:
            leads = session.query(Lead).filter_by(
                campaign_id=campaign_id, status="qualified"
            ).all()
            lead_dicts = [self._get_lead_dict(l) for l in leads]
            campaign = session.query(Campaign).filter_by(id=campaign_id).first()
            niche = campaign.target_niche if campaign else ""

            skill_dict = {}
            if campaign and campaign.skill_id:
                skill = session.query(Skill).filter_by(id=campaign.skill_id).first()
                if skill:
                    skill_dict = {
                        "name": skill.name, "tone": skill.tone,
                        "template": skill.template, "niche": niche,
                    }
            if not skill_dict:
                skill_dict = {"name": "Default", "tone": "professional", "template": "", "niche": niche}

        if not lead_dicts:
            f.warn("No qualified leads to draft emails for.")
            return

        settings = self._get_settings()
        sender_name = settings.sender_name if settings else APP_NAME

        f.info(f"Drafting emails for {len(lead_dicts)} leads…")
        drafted = 0
        for ld in lead_dicts:
            result = self.engines["ai"].generate_email(ld, skill_dict, sender_name=sender_name)
            if result.get("subject") and result.get("body"):
                with self.db.session_scope() as session:
                    from database.schema import Lead as L
                    lead = session.query(L).filter_by(id=ld["id"]).first()
                    if lead:
                        lead.email_subject = result["subject"]
                        lead.email_body = result["body"]
                        lead.status = "email_drafted"
                drafted += 1
                f.success(f"{ld['business_name']}: {result['subject'][:50]}…")
            else:
                f.error(f"{ld['business_name']}: draft failed")
        f.success(f"Drafted: {drafted}/{len(lead_dicts)}")

    @command("send", "pipeline", "Send drafted emails",
             "/send <campaign_id> [--count N]")
    def cmd_send(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/send", add_help=False)
        parser.add_argument("campaign_id", type=int)
        parser.add_argument("--count", "-n", type=int, default=None)
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            print("  Usage: /send <campaign_id> [--count N]")
            return

        from database.schema import Lead
        with self.db.session_scope() as session:
            query = session.query(Lead).filter_by(
                campaign_id=opts.campaign_id, status="email_drafted"
            )
            leads = query.limit(opts.count).all() if opts.count else query.all()
            lead_dicts = [{
                "id": l.id, "business_name": l.business_name, "email": l.email,
                "email_subject": l.email_subject, "email_body": l.email_body,
            } for l in leads if l.email]

        settings = self._get_settings()
        from_email = settings.sender_email if settings else ""
        from_name = settings.sender_name if settings else APP_NAME

        if not from_email:
            f.error("No sender email configured. Run /config-smtp first.")
            return
        if not lead_dicts:
            f.warn("No drafted emails to send.")
            return

        f.info(f"Sending {len(lead_dicts)} emails from {from_email}…")
        sent = 0
        for ld in lead_dicts:
            result = self.engines["delivery"].send_email(
                to_email=ld["email"], from_email=from_email,
                subject=ld["email_subject"], body=ld["email_body"],
                from_name=from_name,
            )
            if result.get("success"):
                with self.db.session_scope() as session:
                    lead = session.query(Lead).filter_by(id=ld["id"]).first()
                    if lead:
                        lead.status = "emailed"
                        lead.email_sent_at = datetime.utcnow()
                sent += 1
                f.success(f"{ld['business_name']} ({ld['email']})")
            else:
                f.error(f"{ld['business_name']}: {result.get('error', 'unknown')}")
        f.success(f"Sent: {sent}/{len(lead_dicts)}")

    @command("replies", "pipeline", "Check inbox for email replies", "/replies")
    def cmd_replies(self, args: list):
        f = Formatter
        f.info("Checking inbox for replies…")
        results = self.engines["reply"].check_inbox()
        if results:
            f.success(f"Found {len(results)} new replies:")
            for r in results:
                print(f"    Lead #{r.get('lead_id', '?')}: {r.get('subject', 'No subject')}")
        else:
            f.info("No new replies found.")

    @command("sequence", "pipeline", "Manage follow-up sequences",
             "/sequence <list|create|run> [campaign_id]")
    def cmd_sequence(self, args: list):
        f = Formatter
        action = args[0] if args else "list"

        if action == "list":
            campaign_id = int(args[1]) if len(args) > 1 else None
            seqs = self.engines["sequence"].get_sequences_for_campaign(campaign_id)
            if not seqs:
                f.info("No sequences found.")
                return
            f.header("Sequences")
            for s in seqs:
                print(f"  ID {s.get('id', '?')}  {s.get('name', 'Unnamed')}  "
                      f"Steps: {s.get('step_count', '?')}")

        elif action == "run":
            if len(args) < 2:
                f.error("Usage: /sequence run <campaign_id>")
                return
            campaign_id = int(args[1])
            leads = self.engines["sequence"].get_leads_due_for_followup(campaign_id)
            if not leads:
                f.info("No leads due for follow-up.")
                return
            f.info(f"Processing {len(leads)} follow-ups…")
            for ld in leads:
                f.success(f"Follow-up sent for lead {ld.get('lead_id', ld.get('id', '?'))}")
        else:
            f.error(f"Unknown action: {action}. Use list, create, or run.")

    # ═══════════════════════════════════════════════════════════════════════════
    #  CAMPAIGN COMMANDS
    # ═══════════════════════════════════════════════════════════════════════════

    @command("campaigns", "campaigns", "List all campaigns", "/campaigns")
    def cmd_campaigns(self, args: list):
        f = Formatter
        from database.schema import Campaign
        with self.db.session_scope() as session:
            campaigns = session.query(Campaign).all()
            if not campaigns:
                f.info("No campaigns yet. Run /hunt to create one.")
                return
            f.header("Campaigns")
            rows = []
            for c in campaigns:
                rows.append([c.id, c.status, c.name, c.target_niche or "", c.target_city or ""])
            f.table(["ID", "Status", "Name", "Niche", "City"], rows)

    @command("campaign-create", "campaigns", "Create a new campaign",
             "/campaign-create <name> --niche <n> --city <c>")
    def cmd_campaign_create(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/campaign-create", add_help=False)
        parser.add_argument("name", nargs="?")
        parser.add_argument("--niche", default="")
        parser.add_argument("--city", default="")
        parser.add_argument("--skill-id", type=int, default=None)
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            print("  Usage: /campaign-create <name> --niche <n> --city <c>")
            return

        if not opts.name:
            f.error("Campaign name is required.")
            return

        from database.schema import Campaign
        with self.db.session_scope() as session:
            c = Campaign(
                name=opts.name, target_niche=opts.niche,
                target_city=opts.city, status="draft",
                skill_id=opts.skill_id,
            )
            session.add(c)
            session.flush()
            f.success(f"Created campaign '{opts.name}' (ID: {c.id})")

    @command("campaign-status", "campaigns", "Show campaign statistics",
             "/campaign-status [campaign_id]")
    def cmd_campaign_status(self, args: list):
        f = Formatter
        from database.schema import Campaign, Lead

        with self.db.session_scope() as session:
            if args:
                campaigns = [session.query(Campaign).filter_by(id=int(args[0])).first()]
            else:
                campaigns = session.query(Campaign).all()

            if not campaigns or not campaigns[0]:
                f.warn("No campaigns found.")
                return

            for c in campaigns:
                if not c:
                    continue
                total = session.query(Lead).filter_by(campaign_id=c.id).count()
                qualified = session.query(Lead).filter_by(campaign_id=c.id, status="qualified").count()
                drafted = session.query(Lead).filter_by(campaign_id=c.id, status="email_drafted").count()
                sent = session.query(Lead).filter_by(campaign_id=c.id, status="emailed").count()
                replied = session.query(Lead).filter_by(campaign_id=c.id, status="replied").count()

                f.header(f"Campaign: {c.name} (ID: {c.id})")
                f.kv("Status", f.badge(c.status))
                f.kv("Total Leads", total)
                f.kv("Qualified", qualified)
                f.kv("Drafted", drafted)
                f.kv("Sent", sent)
                f.kv("Replied", replied)
                if sent > 0:
                    f.kv("Reply Rate", f"{replied/sent*100:.1f}%")

    @command("campaign-pause", "campaigns", "Pause a campaign", "/campaign-pause <id>")
    def cmd_campaign_pause(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /campaign-pause <campaign_id>")
            return
        from database.schema import Campaign
        with self.db.session_scope() as session:
            c = session.query(Campaign).filter_by(id=int(args[0])).first()
            if c:
                c.status = "paused"
                f.success(f"Campaign '{c.name}' paused.")
            else:
                f.error("Campaign not found.")

    @command("campaign-resume", "campaigns", "Resume a paused campaign", "/campaign-resume <id>")
    def cmd_campaign_resume(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /campaign-resume <campaign_id>")
            return
        from database.schema import Campaign
        with self.db.session_scope() as session:
            c = session.query(Campaign).filter_by(id=int(args[0])).first()
            if c:
                c.status = "active"
                f.success(f"Campaign '{c.name}' resumed.")
            else:
                f.error("Campaign not found.")

    # ═══════════════════════════════════════════════════════════════════════════
    #  LEAD COMMANDS
    # ═══════════════════════════════════════════════════════════════════════════

    @command("leads", "leads", "List leads with filters",
             "/leads [campaign_id] [--status s] [--limit N]")
    def cmd_leads(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/leads", add_help=False)
        parser.add_argument("campaign_id", type=int, nargs="?")
        parser.add_argument("--status", default=None)
        parser.add_argument("--limit", "-n", type=int, default=50)
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            print("  Usage: /leads [campaign_id] [--status s] [--limit N]")
            return

        from database.schema import Lead
        with self.db.session_scope() as session:
            query = session.query(Lead)
            if opts.campaign_id:
                query = query.filter_by(campaign_id=opts.campaign_id)
            if opts.status:
                query = query.filter_by(status=opts.status)
            leads = query.limit(opts.limit).all()

            if not leads:
                f.info("No leads found.")
                return

            f.header(f"Leads ({len(leads)})")
            rows = []
            for l in leads:
                rows.append([l.id, l.business_name or "", l.status, l.email or "", l.city or ""])
            f.table(["ID", "Business", "Status", "Email", "City"], rows)

    @command("lead-detail", "leads", "Show lead details", "/lead-detail <lead_id>")
    def cmd_lead_detail(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /lead-detail <lead_id>")
            return

        from database.schema import Lead
        with self.db.session_scope() as session:
            lead = session.query(Lead).filter_by(id=int(args[0])).first()
            if not lead:
                f.error("Lead not found.")
                return
            f.header(f"Lead: {lead.business_name} (ID: {lead.id})")
            f.kv("Status", lead.status)
            f.kv("Lifecycle", getattr(lead, "lifecycle_state", "n/a"))
            f.kv("Email", lead.email or "—")
            f.kv("Phone", lead.phone or "—")
            f.kv("City", lead.city or "—")
            f.kv("Category", lead.category or "—")
            f.kv("Website", lead.website_url or "—")
            f.kv("Campaign ID", lead.campaign_id)
            if lead.email_subject:
                f.kv("Email Subject", lead.email_subject)
            if lead.notes:
                print(f"\n  {f.dim('Notes:')}")
                for line in lead.notes.strip().split("\n"):
                    print(f"    {line}")

    @command("lead-lifecycle", "leads", "Show/change lead lifecycle state",
             "/lead-lifecycle <lead_id> [new_state]")
    def cmd_lead_lifecycle(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /lead-lifecycle <lead_id> [new_state]")
            return

        lead_id = int(args[0])
        if len(args) > 1:
            result = self.engines["lifecycle"].transition(lead_id, args[1], triggered_by="cli_user")
            if result.get("success"):
                f.success(f"Lead {lead_id} → {args[1]}")
            else:
                f.error(result.get("error", "Transition failed"))
        else:
            result = self.engines["lifecycle"].get_valid_transitions(lead_id)
            if result.get("success"):
                current = result["data"].get("current_state", "unknown")
                valid = result["data"].get("valid_transitions", [])
                f.kv("Current State", f.badge(current))
                f.kv("Valid Next", ", ".join(valid) if valid else "none (terminal)")
            else:
                f.error(result.get("error", "Failed"))

    @command("lead-search", "leads", "Search leads by keyword",
             "/lead-search <query>")
    def cmd_lead_search(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /lead-search <query>")
            return
        query = " ".join(args)

        from database.schema import Lead
        with self.db.session_scope() as session:
            leads = session.query(Lead).filter(
                Lead.business_name.ilike(f"%{query}%") |
                Lead.email.ilike(f"%{query}%") |
                Lead.category.ilike(f"%{query}%")
            ).limit(50).all()

            if not leads:
                f.info(f"No leads matching '{query}'.")
                return

            f.header(f"Search: '{query}' ({len(leads)} results)")
            rows = [[l.id, l.business_name or "", l.status, l.email or ""] for l in leads]
            f.table(["ID", "Business", "Status", "Email"], rows)

    # ═══════════════════════════════════════════════════════════════════════════
    #  FLEET & AGENTS
    # ═══════════════════════════════════════════════════════════════════════════

    @command("fleet-status", "fleet", "Show fleet status", "/fleet-status")
    def cmd_fleet_status(self, args: list):
        f = Formatter
        result = self.engines["fleet"].get_fleet_status()
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        data = result.get("data", {})
        f.header("Fleet Status")
        f.kv("Total Agents", data.get("total_agents", 0))
        f.kv("Active", data.get("active_agents", 0))
        f.kv("Idle", data.get("idle_agents", 0))
        f.kv("Running Tasks", data.get("running_tasks", 0))
        f.kv("Queued Tasks", data.get("queued_tasks", 0))

        agents = data.get("agents", [])
        if agents:
            print()
            rows = []
            for a in agents:
                rows.append([
                    a.get("id", ""), a.get("name", ""),
                    a.get("role", ""), a.get("status", ""),
                    a.get("current_task", "—"),
                ])
            f.table(["ID", "Name", "Role", "Status", "Task"], rows)

    @command("fleet-boot", "fleet", "Boot the agent fleet", "/fleet-boot")
    def cmd_fleet_boot(self, args: list):
        f = Formatter
        f.info("Booting fleet…")
        result = self.engines["fleet"].boot_fleet()
        if result.get("success"):
            f.success("Fleet booted successfully.")
        else:
            f.error(result.get("error", "Boot failed"))

    @command("fleet-shutdown", "fleet", "Shutdown the agent fleet", "/fleet-shutdown")
    def cmd_fleet_shutdown(self, args: list):
        f = Formatter
        result = self.engines["fleet"].shutdown_fleet()
        if result.get("success"):
            f.success("Fleet shut down.")
        else:
            f.error(result.get("error", "Shutdown failed"))

    @command("agents", "fleet", "List all agents", "/agents")
    def cmd_agents(self, args: list):
        f = Formatter
        from database.schema import Agent
        with self.db.session_scope() as session:
            agents = session.query(Agent).all()
            if not agents:
                f.info("No agents found.")
                return
            f.header(f"Agents ({len(agents)})")
            rows = []
            for a in agents:
                rank_label = {1: "C-Level", 2: "Specialist", 3: "Worker"}.get(a.rank, str(a.rank))
                rows.append([a.id, a.name, a.role, rank_label, a.status])
            f.table(["ID", "Name", "Role", "Rank", "Status"], rows)

    @command("agent-assign", "fleet", "Assign a task to an agent",
             "/agent-assign <task_type> [payload_json]")
    def cmd_agent_assign(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /agent-assign <task_type> [payload_json]")
            return
        task_type = args[0]
        payload = json.loads(args[1]) if len(args) > 1 else {}

        result = self.engines["fleet"].dispatch(task_type, payload)
        if result.get("success"):
            f.success(f"Task '{task_type}' dispatched. ID: {result.get('data', {}).get('task_id', '?')}")
        else:
            f.error(result.get("error", "Dispatch failed"))

    # ═══════════════════════════════════════════════════════════════════════════
    #  KANBAN & TICKETS
    # ═══════════════════════════════════════════════════════════════════════════

    @command("tickets", "kanban", "List tickets with filters",
             "/tickets [--status s] [--priority p] [--assignee id]")
    def cmd_tickets(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/tickets", add_help=False)
        parser.add_argument("--status", default=None)
        parser.add_argument("--priority", default=None)
        parser.add_argument("--assignee", type=int, default=None)
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            print("  Usage: /tickets [--status s] [--priority p] [--assignee id]")
            return

        result = self.engines["ticket"].get_all_tickets(
            status=opts.status, assignee_id=opts.assignee, priority=opts.priority,
        )
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        tickets = result.get("data", [])
        if not tickets:
            f.info("No tickets found.")
            return
        f.header(f"Tickets ({len(tickets)})")
        rows = []
        for t in tickets:
            rows.append([
                t.get("id"), t.get("title", "")[:30],
                t.get("status"), t.get("priority"),
                t.get("assignee_name", "—"),
            ])
        f.table(["ID", "Title", "Status", "Priority", "Assignee"], rows)

    @command("ticket-create", "kanban", "Create a new ticket",
             "/ticket-create <title> [--priority p] [--assignee id] [--desc text]")
    def cmd_ticket_create(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/ticket-create", add_help=False)
        parser.add_argument("title", nargs="*")
        parser.add_argument("--priority", default="medium")
        parser.add_argument("--assignee", type=int, default=None)
        parser.add_argument("--desc", default="")
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            print("  Usage: /ticket-create <title> [--priority p] [--assignee id]")
            return

        title = " ".join(opts.title) if opts.title else ""
        if not title:
            f.error("Title is required.")
            return

        result = self.engines["ticket"].create_ticket(
            title=title, description=opts.desc,
            priority=opts.priority, assignee_id=opts.assignee,
        )
        if result.get("success"):
            f.success(f"Ticket created: #{result['data'].get('id', '?')} — {title}")
        else:
            f.error(result.get("error", "Failed"))

    @command("ticket-update", "kanban", "Update a ticket",
             "/ticket-update <id> --status <s> | --priority <p> | --assignee <id>")
    def cmd_ticket_update(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/ticket-update", add_help=False)
        parser.add_argument("ticket_id", type=int)
        parser.add_argument("--status", default=None)
        parser.add_argument("--priority", default=None)
        parser.add_argument("--assignee", type=int, default=None)
        parser.add_argument("--title", default=None)
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            print("  Usage: /ticket-update <id> --status s --priority p --assignee id")
            return

        fields = {}
        if opts.status:
            fields["status"] = opts.status
        if opts.priority:
            fields["priority"] = opts.priority
        if opts.assignee:
            fields["assignee_id"] = opts.assignee
        if opts.title:
            fields["title"] = opts.title

        if not fields:
            f.warn("Nothing to update. Use --status, --priority, --assignee, or --title.")
            return

        result = self.engines["ticket"].update_ticket(opts.ticket_id, **fields)
        if result.get("success"):
            f.success(f"Ticket #{opts.ticket_id} updated.")
        else:
            f.error(result.get("error", "Failed"))

    @command("ticket-comment", "kanban", "Add a comment to a ticket",
             "/ticket-comment <ticket_id> <text>")
    def cmd_ticket_comment(self, args: list):
        f = Formatter
        if len(args) < 2:
            f.error("Usage: /ticket-comment <ticket_id> <text>")
            return
        ticket_id = int(args[0])
        content = " ".join(args[1:])
        result = self.engines["ticket"].add_comment(ticket_id, content, author_type="user")
        if result.get("success"):
            f.success("Comment added.")
        else:
            f.error(result.get("error", "Failed"))

    @command("ticket-stats", "kanban", "Show ticket statistics", "/ticket-stats")
    def cmd_ticket_stats(self, args: list):
        f = Formatter
        result = self.engines["ticket"].get_ticket_stats()
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        data = result.get("data", {})
        f.header("Ticket Statistics")
        for key, val in data.items():
            if isinstance(val, dict):
                print(f"  {f.bold(key)}:")
                for k, v in val.items():
                    f.kv(f"  {k}", v)
            else:
                f.kv(key, val)

    # ═══════════════════════════════════════════════════════════════════════════
    #  SKILLS
    # ═══════════════════════════════════════════════════════════════════════════

    @command("skills", "skills", "List all skills", "/skills [--category c]")
    def cmd_skills(self, args: list):
        f = Formatter
        category = None
        if len(args) >= 2 and args[0] == "--category":
            category = args[1]

        if category:
            skills = self.engines["skill_registry"].get_skills_by_category(category)
        else:
            skills = self.engines["skill_registry"].get_all_skills()

        if not skills:
            f.info("No skills found.")
            return
        f.header(f"Skills ({len(skills)})")
        rows = []
        for s in skills:
            rows.append([
                s.get("id"), s.get("name"), s.get("category", "—"),
                s.get("tone", "—"), f"v{s.get('version', '1')}",
            ])
        f.table(["ID", "Name", "Category", "Tone", "Version"], rows)

    @command("skill-detail", "skills", "Show skill details", "/skill-detail <skill_id>")
    def cmd_skill_detail(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /skill-detail <skill_id>")
            return
        from database.schema import Skill
        with self.db.session_scope() as session:
            skill = session.query(Skill).filter_by(id=int(args[0])).first()
            if not skill:
                f.error("Skill not found.")
                return
            f.header(f"Skill: {skill.name} (ID: {skill.id})")
            f.kv("Category", getattr(skill, "category", "—"))
            f.kv("Tone", skill.tone or "—")
            f.kv("Version", getattr(skill, "version", "1"))
            desc = getattr(skill, "description", None)
            if desc:
                f.kv("Description", desc)
            instructions = getattr(skill, "instructions", None)
            if instructions:
                print(f"\n  {f.dim('Instructions:')}")
                for line in instructions.strip().split("\n"):
                    print(f"    {line}")

    # ═══════════════════════════════════════════════════════════════════════════
    #  RESEARCH
    # ═══════════════════════════════════════════════════════════════════════════

    @command("research", "research", "Research a lead",
             "/research <lead_id> [--depth quick|deep]")
    def cmd_research(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /research <lead_id> [--depth quick|deep]")
            return
        lead_id = int(args[0])
        depth = "auto"
        if len(args) > 1 and args[1] == "--depth" and len(args) > 2:
            depth = args[2]

        f.info(f"Researching lead {lead_id} (depth={depth})…")
        result = self.engines["research"].research_lead(lead_id, depth=depth)
        if result.get("success"):
            data = result.get("data", {})
            f.success("Research complete.")
            f.kv("Sources Used", data.get("sources_used", 0))
            overview = data.get("company_overview", "")
            if overview:
                print(f"\n  {f.dim('Company Overview:')}")
                for line in textwrap.wrap(overview, 70):
                    print(f"    {line}")
        else:
            f.error(result.get("error", "Research failed"))

    @command("research-report", "research", "View a research report",
             "/research-report <lead_id>")
    def cmd_research_report(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /research-report <lead_id>")
            return
        result = self.engines["research"].get_report(int(args[0]))
        if not result.get("success"):
            f.error(result.get("error", "No report found"))
            return
        data = result.get("data", {})
        f.header(f"Research Report — Lead #{args[0]}")
        for key in ["company_overview", "pain_points", "gaps_opportunities"]:
            val = data.get(key)
            if val:
                print(f"\n  {f.bold(key.replace('_', ' ').title())}:")
                for line in textwrap.wrap(str(val), 70):
                    print(f"    {line}")

    @command("research-queue", "research", "View research queue", "/research-queue")
    def cmd_research_queue(self, args: list):
        f = Formatter
        result = self.engines["research"].get_research_queue()
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        items = result.get("data", [])
        if not items:
            f.info("Research queue is empty.")
            return
        f.header(f"Research Queue ({len(items)})")
        rows = [[i.get("lead_id"), i.get("business_name", ""), i.get("status")] for i in items]
        f.table(["Lead ID", "Business", "Status"], rows)

    # ═══════════════════════════════════════════════════════════════════════════
    #  VOICE CALLS
    # ═══════════════════════════════════════════════════════════════════════════

    @command("call", "voice", "Initiate a voice call", "/call <lead_id>")
    def cmd_call(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /call <lead_id>")
            return
        lead_id = int(args[0])
        f.info(f"Initiating call to lead {lead_id}…")
        result = self.engines["voice"].initiate_call(lead_id)
        if result.get("success"):
            f.success(f"Call initiated. SID: {result.get('data', {}).get('call_sid', '?')}")
        else:
            f.error(result.get("error", "Call failed"))

    @command("call-log", "voice", "View call history", "/call-log [--lead id] [--limit N]")
    def cmd_call_log(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/call-log", add_help=False)
        parser.add_argument("--lead", type=int, default=None)
        parser.add_argument("--limit", "-n", type=int, default=20)
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            return

        result = self.engines["voice"].get_call_history(lead_id=opts.lead, limit=opts.limit)
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        calls = result.get("data", [])
        if not calls:
            f.info("No call history.")
            return
        f.header(f"Call History ({len(calls)})")
        rows = []
        for c in calls:
            rows.append([
                c.get("id"), c.get("lead_id"),
                c.get("direction", "out"), c.get("status"),
                c.get("duration_s", "—"), c.get("outcome", "—"),
            ])
        f.table(["ID", "Lead", "Dir", "Status", "Duration", "Outcome"], rows)

    @command("call-transcript", "voice", "View call transcript", "/call-transcript <call_id>")
    def cmd_call_transcript(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /call-transcript <call_id>")
            return
        result = self.engines["voice"].get_call_transcript(int(args[0]))
        if not result.get("success"):
            f.error(result.get("error", "No transcript"))
            return
        entries = result.get("data", {}).get("transcript", [])
        f.header(f"Transcript — Call #{args[0]}")
        for entry in entries:
            speaker = entry.get("speaker", "?")
            text = entry.get("text", "")
            color = f.cyan if speaker == "ai" else f.green
            print(f"  {color(speaker.upper())}: {text}")

    # ═══════════════════════════════════════════════════════════════════════════
    #  BUDGET & PACING
    # ═══════════════════════════════════════════════════════════════════════════

    @command("budget", "budget", "Show budget and pacing status", "/budget")
    def cmd_budget(self, args: list):
        f = Formatter
        result = self.engines["pacing"].get_status()
        if not result.get("success"):
            f.info("No active budget. Use /budget-set to configure.")
            return
        data = result.get("data", {})
        f.header("Budget & Pacing")
        f.kv("Budget", f"${data.get('budget_usd', 0):.2f}")
        f.kv("Spent", f"${data.get('spent_usd', 0):.2f}")
        f.kv("Remaining", f"${data.get('remaining_usd', 0):.2f}")
        f.kv("Max Tier", data.get("allowed_tier", "—"))
        f.kv("Eco Mode", "On" if data.get("eco_mode") else "Off")

    @command("budget-set", "budget", "Set a cost budget",
             "/budget-set <amount_usd> [--hours N] [--eco]")
    def cmd_budget_set(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/budget-set", add_help=False)
        parser.add_argument("amount", type=float)
        parser.add_argument("--hours", type=float, default=24)
        parser.add_argument("--eco", action="store_true", default=True)
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            print("  Usage: /budget-set <amount_usd> [--hours N]")
            return

        result = self.engines["pacing"].activate(opts.amount, opts.hours, eco_mode=opts.eco)
        if result.get("success"):
            f.success(f"Budget set: ${opts.amount:.2f} over {opts.hours}h")
        else:
            f.error(result.get("error", "Failed"))

    @command("token-usage", "budget", "Show token usage statistics", "/token-usage")
    def cmd_token_usage(self, args: list):
        f = Formatter
        stats = self.engines["command_history"].get_stats()
        if not stats.get("success"):
            f.warn("No usage data.")
            return
        data = stats.get("data", {})
        f.header("Token Usage")
        f.kv("Total Commands", data.get("total_commands", 0))
        f.kv("Total Tokens", data.get("total_tokens", 0))
        f.kv("Total Cost", f"${data.get('total_cost_usd', 0):.4f}")

    # ═══════════════════════════════════════════════════════════════════════════
    #  TRENDS
    # ═══════════════════════════════════════════════════════════════════════════

    @command("trends", "trends", "Check keyword trends",
             "/trends <keyword1> [keyword2] [--region US]")
    def cmd_trends(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /trends <keyword1> [keyword2] [--region US]")
            return
        region = "US"
        keywords = []
        i = 0
        while i < len(args):
            if args[i] == "--region" and i + 1 < len(args):
                region = args[i + 1]
                i += 2
            else:
                keywords.append(args[i])
                i += 1

        f.info(f"Fetching trends for: {', '.join(keywords)}…")
        result = self.engines["trends"].fetch_interest_over_time(keywords, region=region)
        if result.get("success"):
            data = result.get("data", {})
            f.success("Trend data retrieved.")
            for kw, vals in data.items():
                if isinstance(vals, list) and vals:
                    latest = vals[-1] if vals else "—"
                    f.kv(kw, f"Latest: {latest}")
        else:
            f.error(result.get("error", "Failed"))

    @command("trends-opportunities", "trends", "Find niche opportunities",
             "/trends-opportunities <keyword1> [keyword2]")
    def cmd_trends_opportunities(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /trends-opportunities <keyword1> [keyword2]")
            return
        result = self.engines["trends"].find_opportunity_niches(args)
        if result.get("success"):
            data = result.get("data", {})
            opps = data.get("opportunities", []) if isinstance(data, dict) else data
            if not opps:
                f.info("No opportunities found.")
                return
            f.header("Niche Opportunities")
            for o in opps:
                niche = o.get("niche", "?")
                score = o.get("trend_score", 0)
                reason = o.get("reason", "")
                line = f"  {f.cyan(niche)}  Score: {score}"
                if reason:
                    line += f"  ({reason})"
                print(line)
        else:
            f.error(result.get("error", "Failed"))

    @command("trends-alerts", "trends", "View trend alerts", "/trends-alerts")
    def cmd_trends_alerts(self, args: list):
        f = Formatter
        result = self.engines["trends"].get_alerts()
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        alerts = result.get("data", [])
        if not alerts:
            f.info("No trend alerts.")
            return
        f.header(f"Trend Alerts ({len(alerts)})")
        for a in alerts:
            print(f"  {f.yellow('!')} {a.get('keyword', '?')}: {a.get('message', '')}")

    # ═══════════════════════════════════════════════════════════════════════════
    #  AUTONOMY
    # ═══════════════════════════════════════════════════════════════════════════

    @command("autonomy-level", "autonomy", "Show current autonomy level", "/autonomy-level")
    def cmd_autonomy_level(self, args: list):
        f = Formatter
        result = self.engines["autonomy"].get_autonomy_level()
        if result.get("success"):
            level = result["data"].get("level", "unknown")
            f.kv("Autonomy Level", f.badge(level))
            from config import AUTONOMY_REQUIRES_APPROVAL
            needs = AUTONOMY_REQUIRES_APPROVAL.get(level, [])
            f.kv("Requires Approval", ", ".join(needs) if needs else "nothing")
        else:
            f.error(result.get("error", "Failed"))

    @command("autonomy-set", "autonomy", "Set autonomy level",
             "/autonomy-set <observer|supervised|autonomous|full_trust>")
    def cmd_autonomy_set(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /autonomy-set <observer|supervised|autonomous|full_trust>")
            return
        result = self.engines["autonomy"].set_autonomy_level(args[0])
        if result.get("success"):
            f.success(f"Autonomy level set to: {args[0]}")
        else:
            f.error(result.get("error", "Failed"))

    @command("approvals", "autonomy", "List pending approvals", "/approvals")
    def cmd_approvals(self, args: list):
        f = Formatter
        result = self.engines["autonomy"].get_pending_approvals()
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        items = result.get("data", [])
        if not items:
            f.info("No pending approvals.")
            return
        f.header(f"Pending Approvals ({len(items)})")
        rows = []
        for a in items:
            rows.append([
                a.get("id"), a.get("action_type"),
                a.get("description", "")[:40], a.get("created_at", ""),
            ])
        f.table(["ID", "Action", "Description", "Created"], rows)

    @command("approve", "autonomy", "Approve a pending action", "/approve <approval_id>")
    def cmd_approve(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /approve <approval_id>")
            return
        result = self.engines["autonomy"].approve_action(int(args[0]))
        if result.get("success"):
            f.success(f"Approval #{args[0]} approved.")
        else:
            f.error(result.get("error", "Failed"))

    @command("deny", "autonomy", "Deny a pending action", "/deny <approval_id>")
    def cmd_deny(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /deny <approval_id>")
            return
        result = self.engines["autonomy"].deny_action(int(args[0]))
        if result.get("success"):
            f.success(f"Approval #{args[0]} denied.")
        else:
            f.error(result.get("error", "Failed"))

    # ═══════════════════════════════════════════════════════════════════════════
    #  SUPPRESSION
    # ═══════════════════════════════════════════════════════════════════════════

    @command("suppression-list", "suppression", "View suppression list", "/suppression-list")
    def cmd_suppression_list(self, args: list):
        f = Formatter
        entries = self.engines["suppression"].get_all_entries()
        if not entries:
            f.info("Suppression list is empty.")
            return
        f.header(f"Suppression List ({len(entries)})")
        rows = []
        for e in entries:
            rows.append([
                e.get("id"), e.get("email", "—"),
                e.get("domain", "—"), e.get("reason", ""),
            ])
        f.table(["ID", "Email", "Domain", "Reason"], rows)

    @command("suppress", "suppression", "Add to suppression list",
             "/suppress [--email e] [--domain d] [--reason r]")
    def cmd_suppress(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/suppress", add_help=False)
        parser.add_argument("--email", default=None)
        parser.add_argument("--domain", default=None)
        parser.add_argument("--reason", default="manual")
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            print("  Usage: /suppress --email <e> --domain <d> --reason <r>")
            return

        if not opts.email and not opts.domain:
            f.error("Provide --email or --domain.")
            return

        result = self.engines["suppression"].add_suppression(
            email=opts.email, domain=opts.domain, reason=opts.reason,
        )
        if result.get("success"):
            f.success("Added to suppression list.")
        else:
            f.error(result.get("error", "Failed"))

    @command("unsuppress", "suppression", "Remove from suppression list",
             "/unsuppress <entry_id>")
    def cmd_unsuppress(self, args: list):
        f = Formatter
        if not args or not args[0].isdigit():
            f.error("Usage: /unsuppress <entry_id>  (find IDs with /suppression-list)")
            return
        result = self.engines["suppression"].remove_suppression(int(args[0]))
        if result.get("success"):
            f.success(f"Entry #{args[0]} removed.")
        else:
            f.error(result.get("error", "Failed"))

    # ═══════════════════════════════════════════════════════════════════════════
    #  INTEGRATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    @command("gateway-status", "integrations", "Show gateway connection status",
             "/gateway-status")
    def cmd_gateway_status(self, args: list):
        f = Formatter
        from config import GATEWAY_PLATFORMS
        f.header("Gateway Status")
        for platform in GATEWAY_PLATFORMS:
            config = self.engines["gateway"].get_gateway_config(platform)
            enabled = config.get("is_enabled", False) if config.get("success") else False
            status = f.green("connected") if enabled else f.dim("disconnected")
            f.kv(platform.title(), status)

        users = self.engines["gateway"].get_authorized_users()
        if users:
            print()
            f.info(f"Authorized users: {len(users)}")
            for u in users:
                print(f"    {u.get('platform', '?')}: {u.get('display_name', u.get('user_id', '?'))}")

    @command("gateway-connect", "integrations", "Connect a gateway platform",
             "/gateway-connect <telegram|discord> <bot_token>")
    def cmd_gateway_connect(self, args: list):
        f = Formatter
        if len(args) < 2:
            f.error("Usage: /gateway-connect <telegram|discord> <bot_token>")
            return
        platform, token = args[0], args[1]
        result = self.engines["gateway"].save_gateway_config(platform, token, is_enabled=True)
        if result.get("success"):
            f.success(f"{platform.title()} gateway connected.")
        else:
            f.error(result.get("error", "Failed"))

    @command("gateway-disconnect", "integrations", "Disconnect a gateway",
             "/gateway-disconnect <telegram|discord>")
    def cmd_gateway_disconnect(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /gateway-disconnect <telegram|discord>")
            return
        result = self.engines["gateway"].save_gateway_config(args[0], "", is_enabled=False)
        if result.get("success"):
            f.success(f"{args[0].title()} gateway disconnected.")
        else:
            f.error(result.get("error", "Failed"))

    @command("crm-sync", "integrations", "Sync leads to CRM",
             "/crm-sync <campaign_id> [--status s]")
    def cmd_crm_sync(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /crm-sync <campaign_id> [--status s]")
            return
        campaign_id = int(args[0])
        status_filter = args[2] if len(args) > 2 and args[1] == "--status" else None

        f.info(f"Syncing campaign {campaign_id} to CRM…")
        result = self.engines["crm"].sync_campaign_to_crm(campaign_id, status_filter=status_filter)
        if result.get("success"):
            f.success(f"Synced {result.get('data', {}).get('synced', 0)} leads.")
        else:
            f.error(result.get("error", "Sync failed"))

    @command("gateway-auth", "integrations", "Manage authorized gateway users",
             "/gateway-auth <add|remove> <platform> <user_id> [display_name]")
    def cmd_gateway_auth(self, args: list):
        f = Formatter
        if len(args) < 3:
            f.error("Usage: /gateway-auth <add|remove> <platform> <user_id>")
            return
        action, platform, user_id = args[0], args[1], args[2]
        if action == "add":
            display_name = args[3] if len(args) > 3 else ""
            result = self.engines["gateway"].add_authorized_user(platform, user_id, display_name)
            if result.get("success"):
                f.success(f"User {user_id} authorized on {platform}.")
            else:
                f.error(result.get("error", "Failed"))
        elif action == "remove":
            result = self.engines["gateway"].remove_authorized_user(platform, user_id)
            if result.get("success"):
                f.success(f"User {user_id} removed from {platform}.")
            else:
                f.error(result.get("error", "Failed"))

    # ═══════════════════════════════════════════════════════════════════════════
    #  HISTORY
    # ═══════════════════════════════════════════════════════════════════════════

    @command("history", "history", "View command history",
             "/history [--source s] [--type t] [--limit N]")
    def cmd_history(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/history", add_help=False)
        parser.add_argument("--source", default=None)
        parser.add_argument("--type", default=None)
        parser.add_argument("--agent", type=int, default=None)
        parser.add_argument("--limit", "-n", type=int, default=20)
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            return

        result = self.engines["command_history"].get_history(
            source=opts.source, command_type=opts.type,
            agent_id=opts.agent, page_size=opts.limit,
        )
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        items = result.get("data", {}).get("items", [])
        if not items:
            f.info("No history entries.")
            return
        total = result.get("data", {}).get("total", len(items))
        f.header(f"Command History ({total} total, showing {len(items)})")
        rows = []
        for h in items:
            rows.append([
                h.get("id"), h.get("source", "—"),
                h.get("command_type", "—"), h.get("status", "—"),
                str(h.get("created_at", ""))[:19],
            ])
        f.table(["ID", "Source", "Type", "Status", "Created"], rows)

    @command("history-detail", "history", "View command detail", "/history-detail <id>")
    def cmd_history_detail(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /history-detail <command_id>")
            return
        result = self.engines["command_history"].get_command(int(args[0]))
        if not result.get("success"):
            f.error(result.get("error", "Not found"))
            return
        data = result.get("data", {})
        f.header(f"Command #{data.get('id')}")
        for key in ["source", "command_type", "command_text", "status",
                     "intent", "cost_usd", "tokens_used", "created_at"]:
            val = data.get(key)
            if val is not None:
                f.kv(key, val)
        params = data.get("parameters")
        if params:
            print(f"\n  {f.dim('Parameters:')}")
            print(f"    {json.dumps(params, indent=2, default=str)}")

    @command("history-tree", "history", "View command execution tree",
             "/history-tree <id>")
    def cmd_history_tree(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /history-tree <command_id>")
            return
        result = self.engines["command_history"].get_command_tree(int(args[0]))
        if not result.get("success"):
            f.error(result.get("error", "Not found"))
            return
        data = result.get("data", {})

        def print_node(node, indent=0):
            prefix = "  " + "  | " * indent
            status = node.get("status", "?")
            color = f.green if status == "completed" else f.yellow if status == "pending" else f.red
            node_id = node.get("id", "?")
            cmd_type = node.get("command_type", "?")
            print(f"{prefix}+- {color(f'[{status}]')} {cmd_type} {f.dim(f'(#{node_id})')}")
            for child in node.get("children", []):
                print_node(child, indent + 1)

        f.header(f"Command Tree #{args[0]}")
        print_node(data)

    # ═══════════════════════════════════════════════════════════════════════════
    #  CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════════

    @command("config", "config", "Show current configuration", "/config")
    def cmd_config(self, args: list):
        f = Formatter
        settings = self._get_settings()
        if not settings:
            f.warn("No settings configured.")
            return

        f.header("Configuration")
        # API Keys
        print(f"  {f.bold('API Keys:')}")
        for provider in ["gemini", "anthropic", "openai", "openrouter"]:
            enc_val = getattr(settings, f"{provider}_key_enc", None)
            status = f.green("configured") if enc_val else f.dim("not set")
            f.kv(f"  {provider.title()}", status)

        # SMTP
        print(f"\n  {f.bold('Email Delivery:')}")
        f.kv("  SMTP Host", settings.smtp_host or "not set")
        f.kv("  Sender Email", settings.sender_email or "not set")
        f.kv("  Sender Name", settings.sender_name or "not set")

        # Models
        print(f"\n  {f.bold('AI Models:')}")
        f.kv("  Tier 2 (fast)", settings.tier2_model or "default")
        f.kv("  Tier 3 (smart)", settings.tier3_model or "default")

        # Research/Voice
        print(f"\n  {f.bold('Integrations:')}")
        for key, label in [("tavily_key_enc", "Tavily"), ("firecrawl_key_enc", "Firecrawl"),
                           ("apify_key_enc", "Apify"), ("twilio_account_sid_enc", "Twilio")]:
            enc_val = getattr(settings, key, None)
            status = f.green("configured") if enc_val else f.dim("not set")
            f.kv(f"  {label}", status)

    @command("config-set", "config", "Set a configuration value",
             "/config-set <key> <value>")
    def cmd_config_set(self, args: list):
        f = Formatter
        if len(args) < 2:
            f.error("Usage: /config-set <key> <value>")
            print(f"  Keys: sender_name, sender_email, tier2_model, tier3_model")
            return
        key, value = args[0], " ".join(args[1:])

        allowed = ["sender_name", "sender_email", "tier2_model", "tier3_model",
                   "chat_model", "custom_models"]
        if key not in allowed:
            f.error(f"Key must be one of: {', '.join(allowed)}")
            return

        from database.schema import Settings
        with self.db.session_scope() as session:
            s = session.query(Settings).first()
            if s:
                setattr(s, key, value)
                f.success(f"{key} = {value}")
            else:
                f.error("Settings not found.")

    @command("config-api-keys", "config", "Configure API keys interactively",
             "/config-api-keys")
    def cmd_config_api_keys(self, args: list):
        f = Formatter
        settings = self._get_settings()
        providers = [
            ("gemini", "Gemini (Google)"),
            ("anthropic", "Anthropic (Claude)"),
            ("openai", "OpenAI"),
            ("openrouter", "OpenRouter"),
            ("apollo", "Apollo.io"),
            ("hunter", "Hunter.io"),
            ("hubspot", "HubSpot"),
            ("tavily", "Tavily"),
            ("firecrawl", "Firecrawl"),
            ("apify", "Apify"),
        ]
        f.header("API Key Configuration")
        for key_name, label in providers:
            enc_field = f"{key_name}_key_enc"
            current = getattr(settings, enc_field, None) if settings else None
            status = f.green("[set]") if current else f.dim("[empty]")
            print(f"  {label}: {status}")
            try:
                new_key = input(f"  Enter {label} key (Enter to skip): ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if new_key:
                encrypted = self.key_vault.encrypt(new_key)
                from database.schema import Settings
                with self.db.session_scope() as session:
                    s = session.query(Settings).first()
                    setattr(s, enc_field, encrypted)
                f.success(f"{label} key saved.")

        # Reload config
        self._configure_ai()
        f.success("Configuration updated.")

    @command("config-smtp", "config", "Configure SMTP email delivery",
             "/config-smtp")
    def cmd_config_smtp(self, args: list):
        f = Formatter
        settings = self._get_settings()
        f.header("SMTP Configuration")
        try:
            host = input(f"  SMTP host [{getattr(settings, 'smtp_host', '') or ''}]: ").strip()
            if not host:
                f.info("Skipped.")
                return
            port = input("  SMTP port [587]: ").strip() or "587"
            user = input("  SMTP username: ").strip()
            password = input("  SMTP password: ").strip()
            sender_email = input("  Sender email: ").strip()
            sender_name = input(f"  Sender name [{APP_NAME}]: ").strip() or APP_NAME
        except (EOFError, KeyboardInterrupt):
            print()
            return

        from database.schema import Settings
        with self.db.session_scope() as session:
            s = session.query(Settings).first()
            s.smtp_host = host
            s.smtp_port = int(port)
            s.smtp_user = user
            s.smtp_password_enc = self.key_vault.encrypt(password) if password else ""
            s.sender_email = sender_email
            s.sender_name = sender_name

        self.engines["delivery"].configure_smtp(host, int(port), user, password)
        f.success("SMTP configured.")

    # ═══════════════════════════════════════════════════════════════════════════
    #  ADVANCED — Strategy, Reflection, Knowledge Graph, Conversations
    # ═══════════════════════════════════════════════════════════════════════════

    @command("goals", "fleet", "List strategic goals", "/goals [--status s]")
    def cmd_goals(self, args: list):
        f = Formatter
        status = args[1] if len(args) > 1 and args[0] == "--status" else None
        result = self.engines["strategy"].get_all_goals(status=status)
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        goals = result.get("data", [])
        if not goals:
            f.info("No strategic goals.")
            return
        f.header(f"Strategic Goals ({len(goals)})")
        rows = []
        for g in goals:
            rows.append([
                g.get("id"), g.get("goal_text", "")[:35],
                g.get("status"), f"{g.get('current_value', 0)}/{g.get('target_value', 0)}",
            ])
        f.table(["ID", "Goal", "Status", "Progress"], rows)

    @command("goal-create", "fleet", "Create a strategic goal",
             "/goal-create <goal_text> --target N [--metric m] [--budget B]")
    def cmd_goal_create(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/goal-create", add_help=False)
        parser.add_argument("goal", nargs="*")
        parser.add_argument("--target", type=int, required=True)
        parser.add_argument("--metric", default="conversions")
        parser.add_argument("--budget", type=float, default=None)
        parser.add_argument("--niche", default="")
        parser.add_argument("--city", default="")
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            print("  Usage: /goal-create <text> --target N [--metric m] [--budget B]")
            return

        goal_text = " ".join(opts.goal)
        result = self.engines["strategy"].create_goal(
            goal_text, target_metric=opts.metric, target_value=opts.target,
            budget=opts.budget, niche=opts.niche, city=opts.city,
        )
        if result.get("success"):
            f.success(f"Goal created: {goal_text}")
        else:
            f.error(result.get("error", "Failed"))

    @command("reflections", "fleet", "View agent reflections",
             "/reflections [--agent id] [--limit N]")
    def cmd_reflections(self, args: list):
        f = Formatter
        parser = argparse.ArgumentParser(prog="/reflections", add_help=False)
        parser.add_argument("--agent", type=int, default=None)
        parser.add_argument("--limit", "-n", type=int, default=20)
        try:
            opts = parser.parse_args(args)
        except SystemExit:
            return
        result = self.engines["reflection"].get_reflections(
            agent_id=opts.agent, limit=opts.limit,
        )
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        items = result.get("data", [])
        if not items:
            f.info("No reflections found.")
            return
        f.header(f"Reflections ({len(items)})")
        rows = []
        for r in items:
            rows.append([
                r.get("id"), r.get("agent_id"),
                r.get("task_type", ""), r.get("score", "—"),
                "Yes" if r.get("needs_revision") else "No",
            ])
        f.table(["ID", "Agent", "Task", "Score", "Revision?"], rows)

    @command("knowledge-graph", "fleet", "Query the knowledge graph",
             "/knowledge-graph <node_type> <key>")
    def cmd_knowledge_graph(self, args: list):
        f = Formatter
        if len(args) < 2:
            f.error("Usage: /knowledge-graph <node_type> <key>")
            return
        result = self.engines["knowledge_graph"].get_related_entities(args[0], args[1])
        if not result.get("success"):
            f.error(result.get("error", "No results"))
            return
        entities = result.get("data", [])
        f.header(f"Related to {args[0]}:{args[1]}")
        for e in entities:
            print(f"  {f.cyan(e.get('node_type', '?'))}:{e.get('node_key', '?')} "
                  f"({f.dim(e.get('edge_type', ''))})")

    @command("conversations", "fleet", "View conversation threads",
             "/conversations [--campaign id]")
    def cmd_conversations(self, args: list):
        f = Formatter
        campaign_id = None
        if len(args) > 1 and args[0] == "--campaign":
            campaign_id = int(args[1])
        result = self.engines["conversation"].get_thread_stats(campaign_id=campaign_id)
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        data = result.get("data", {})
        f.header("Conversation Threads")
        for key, val in data.items():
            if isinstance(val, dict):
                print(f"  {f.bold(key)}:")
                for k, v in val.items():
                    f.kv(f"  {k}", v)
            else:
                f.kv(key, val)

    @command("ask", "fleet", "Ask the AI analyst a question", "/ask <question>")
    def cmd_ask(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /ask <question>")
            return
        question = " ".join(args)
        f.info("Thinking…")
        context = self.engines["analyst"].gather_context()
        answer = self.engines["analyst"].ask(question, context=context)
        print(f"\n  {answer}\n")

    @command("case", "leads", "View lead case file", "/case <lead_id>")
    def cmd_case(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /case <lead_id>")
            return
        lead_id = int(args[0])
        context_str = self.engines["case"].build_case_context(lead_id)
        if context_str:
            f.header(f"Case File — Lead #{lead_id}")
            print(f"  {context_str}")
        else:
            f.info("No case data for this lead.")

    @command("export-csv", "campaigns", "Export leads to CSV",
             "/export-csv <campaign_id> <output_path>")
    def cmd_export_csv(self, args: list):
        f = Formatter
        if len(args) < 2:
            f.error("Usage: /export-csv <campaign_id> <output_path>")
            return
        result = self.engines["report"].export_leads_csv(int(args[0]), args[1])
        if result.get("success"):
            f.success(f"Exported to {args[1]}")
        else:
            f.error(result.get("error", "Export failed"))

    @command("export-pdf", "campaigns", "Export campaign report as PDF",
             "/export-pdf <campaign_id> <output_path>")
    def cmd_export_pdf(self, args: list):
        f = Formatter
        if len(args) < 2:
            f.error("Usage: /export-pdf <campaign_id> <output_path>")
            return
        result = self.engines["report"].export_campaign_pdf(int(args[0]), args[1])
        if result.get("success"):
            f.success(f"Exported to {args[1]}")
        else:
            f.error(result.get("error", "Export failed"))

    @command("export-xlsx", "campaigns", "Export campaign to Excel",
             "/export-xlsx <campaign_id> <output_path>")
    def cmd_export_xlsx(self, args: list):
        f = Formatter
        if len(args) < 2:
            f.error("Usage: /export-xlsx <campaign_id> <output_path>")
            return
        try:
            from core.excel_export_engine import ExcelExportEngine
            engine = ExcelExportEngine(self.db)
            path = engine.export_campaign_xlsx(int(args[0]), args[1])
            f.success(f"Excel exported to {path}")
        except Exception as e:
            f.error(f"Export failed: {e}")

    @command("export-finance", "budget", "Export finance report to Excel",
             "/export-finance <output_path>")
    def cmd_export_finance(self, args: list):
        f = Formatter
        if len(args) < 1:
            f.error("Usage: /export-finance <output_path>")
            return
        try:
            from core.excel_export_engine import ExcelExportEngine
            engine = ExcelExportEngine(self.db)
            path = engine.export_finance_xlsx(args[0])
            f.success(f"Finance report exported to {path}")
        except Exception as e:
            f.error(f"Export failed: {e}")

    @command("improvement", "fleet", "Run self-improvement cycle",
             "/improvement [--dry-run]")
    def cmd_improvement(self, args: list):
        f = Formatter
        f.info("Running improvement cycle…")
        result = self.engines["self_improvement"].run_improvement_cycle()
        if result.get("success"):
            data = result.get("data", {})
            f.success("Improvement cycle complete.")
            f.kv("Rules Extracted", data.get("rules_extracted", 0))
            f.kv("Underperformers", data.get("underperformers_found", 0))
        else:
            f.error(result.get("error", "Failed"))

    # ═══════════════════════════════════════════════════════════════════════════
    #  KNOWLEDGE & MEMORY COMMANDS
    # ═══════════════════════════════════════════════════════════════════════════

    @command("models", "config", "List the model fleet",
             "/models")
    def cmd_models(self, args: list):
        f = Formatter
        from core.model_fleet import PROVIDERS, custom_models
        settings = self.db.get_settings()
        f.header("Model Fleet")
        for key, provider in PROVIDERS.items():
            keyed = "local" if not provider["key_field"] else (
                "key set" if getattr(settings, provider["key_field"], "") else "no key"
            )
            print(f"  {f.bold(provider['label'])}  [{keyed}]")
            for m in provider["models"]:
                print(f"    {f.cyan(m)}")
        extra = custom_models(settings)
        if extra:
            print(f"  {f.bold('Custom')}")
            for m in extra:
                print(f"    {f.cyan(m)}")
        f.info('Verify any model with /model-verify <model_id>. '
               'Register custom IDs: /config-set custom_models "id1, id2"')

    @command("model-verify", "config",
             "Verify a model authenticates and answers a test prompt",
             "/model-verify <model_id>")
    def cmd_model_verify(self, args: list):
        f = Formatter
        if not args:
            f.error("Usage: /model-verify <model_id>")
            return
        model_id = args[0]
        from core.model_verifier import ModelVerifier
        f.info(f"Step 1/2: authenticating {model_id}…")
        verifier = ModelVerifier(self.db, self.key_vault)
        result = verifier.verify(model_id)
        if result.get("auth_ok"):
            f.success("Step 1/2: authentication OK")
        else:
            f.error(f"Step 1/2 failed: {result.get('error', 'unknown error')}")
            return
        if result.get("roundtrip_ok"):
            f.success(
                f"Step 2/2: round trip OK ({result.get('latency_ms', 0)}ms) "
                f"— response: {result.get('response', '')[:60]}"
            )
        else:
            f.error(f"Step 2/2 failed: {result.get('error', 'no response')}")

    @command("kb-set", "knowledge", "Set a knowledge base entry",
             "/kb-set <category> <key> <value>")
    def cmd_kb_set(self, args: list):
        f = Formatter
        if len(args) < 3:
            f.error("Usage: /kb-set <category> <key> <value>")
            print("  Categories: product, icp, approach, general")
            return
        category, key = args[0], args[1]
        value = " ".join(args[2:])
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(self.db)
        result = kb.set_entry(category, key, value)
        if result.get("success"):
            action = result["data"]["action"]
            f.success(f"KB entry {action}: [{category}] {key}")
        else:
            f.error(result.get("error", "Failed"))

    @command("kb-list", "knowledge", "List knowledge base entries",
             "/kb-list [category]")
    def cmd_kb_list(self, args: list):
        f = Formatter
        category = args[0] if args else None
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(self.db)
        result = kb.get_entries(category)
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        entries = result["data"]
        if not entries:
            f.warn("No knowledge base entries found.")
            return
        f.header(f"Knowledge Base ({len(entries)} entries)")
        for e in entries:
            print(f"  [{f.cyan(e['category'])}] {f.bold(e['key'])}: {e['value'][:80]}")

    @command("kb-delete", "knowledge", "Delete a knowledge base entry",
             "/kb-delete <category> <key>")
    def cmd_kb_delete(self, args: list):
        f = Formatter
        if len(args) < 2:
            f.error("Usage: /kb-delete <category> <key>")
            return
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(self.db)
        result = kb.delete_entry(category=args[0], key=args[1])
        if result.get("success"):
            f.success(f"Deleted {result['data']['deleted']} entry(ies)")
        else:
            f.error(result.get("error", "Failed"))

    @command("memory-list", "knowledge", "List learned rules (correction memory)",
             "/memory-list [agent_name]")
    def cmd_memory_list(self, args: list):
        f = Formatter
        agent_name = args[0] if args else None
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(self.db)
        result = cm.list_rules(agent_name)
        if not result.get("success"):
            f.error(result.get("error", "Failed"))
            return
        rules = result["data"]
        if not rules:
            f.warn("No learned rules found.")
            return
        f.header(f"Learned Rules ({len(rules)})")
        for r in rules:
            agent = f" ({r['agent_name']})" if r.get("agent_name") else ""
            print(f"  [{r['type']}]{agent} {r['text'][:80]}  "
                  f"(conf={r['confidence']:.1f}, src={r['source']})")

    @command("memory-clear", "knowledge", "Clear learned rules",
             "/memory-clear [agent_name]")
    def cmd_memory_clear(self, args: list):
        f = Formatter
        agent_name = args[0] if args else None
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(self.db)
        result = cm.clear_rules(agent_name)
        if result.get("success"):
            scope = f" for agent '{agent_name}'" if agent_name else ""
            f.success(f"Cleared {result['data']['cleared']} rule(s){scope}")
        else:
            f.error(result.get("error", "Failed"))

    # ═══════════════════════════════════════════════════════════════════════════
    #  SYSTEM COMMANDS
    # ═══════════════════════════════════════════════════════════════════════════

    @command("help", "system", "Show help", "/help [group|command]")
    def cmd_help(self, args: list):
        if not args:
            HelpSystem.show_overview()
        elif args[0] in COMMAND_GROUPS:
            HelpSystem.show_group(args[0])
        else:
            HelpSystem.show_command(args[0])

    @command("status", "system", "Show system status overview", "/status")
    def cmd_status(self, args: list):
        f = Formatter
        from database.schema import Campaign, Lead, Agent
        f.header(f"{APP_NAME} v{APP_VERSION} — System Status")

        with self.db.session_scope() as session:
            campaigns = session.query(Campaign).count()
            leads = session.query(Lead).count()
            agents = session.query(Agent).count()
            qualified = session.query(Lead).filter_by(status="qualified").count()
            sent = session.query(Lead).filter_by(status="emailed").count()
            replied = session.query(Lead).filter_by(status="replied").count()

        f.kv("Campaigns", campaigns)
        f.kv("Leads", leads)
        f.kv("Agents", agents)
        f.kv("Qualified", qualified)
        f.kv("Emails Sent", sent)
        f.kv("Replies", replied)
        if sent > 0:
            f.kv("Reply Rate", f"{replied/sent*100:.1f}%")

        # Engine count
        f.kv("Engines Loaded", len(self.engines))

        # Pacing
        pacing = self.engines["pacing"].get_status()
        if pacing.get("success"):
            data = pacing.get("data", {})
            f.kv("Budget", f"${data.get('remaining_usd', 0):.2f} remaining")

    @command("version", "system", "Show version", "/version")
    def cmd_version(self, args: list):
        print(f"{APP_NAME} v{APP_VERSION}")

    @command("clear", "system", "Clear the terminal", "/clear")
    def cmd_clear(self, args: list):
        # Use subprocess with fixed arguments only — no user input
        if sys.platform == "win32":
            subprocess.run(["cmd", "/c", "cls"], check=False)
        else:
            subprocess.run(["clear"], check=False)

    @command("exit", "system", "Exit Aura CLI", "/exit")
    def cmd_exit(self, args: list):
        raise SystemExit(0)

    # ─── REPL ───────────────────────────────────────────────────────────────

    def run_repl(self):
        """Run the interactive REPL."""
        f = Formatter
        f.init()

        print(f"\n{f.bold(APP_NAME)} v{APP_VERSION} — AI Sales Agent")
        print(f"{f.dim('Type /help for commands, or type naturally.')}\n")

        def signal_handler(sig, frame):
            print(f"\n{f.dim('Use /exit to quit.')}")

        signal.signal(signal.SIGINT, signal_handler)

        while True:
            try:
                # Piped input on Windows may carry a UTF-8 BOM — strip it so
                # commands like "/status" still dispatch correctly
                user_input = input(f"{f.cyan('aura')}> ").strip()
                # A UTF-8 BOM decodes as \ufeff (utf-8 stdin) or "\xef\xbb\xbf"
                # (cp1252 stdin) — drop either so "/commands" still dispatch
                for _bom in ("\ufeff", "\xef\xbb\xbf"):
                    if user_input.startswith(_bom):
                        user_input = user_input[len(_bom):].strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                self._handle_command(user_input)
            else:
                self._handle_natural_language(user_input)

    def _handle_command(self, text: str):
        """Parse and execute a /command."""
        parts = self._parse_args(text)
        cmd_name = parts[0].lstrip("/")
        cmd_args = parts[1:]

        cmd = _COMMAND_REGISTRY.get(cmd_name)
        if not cmd:
            # Try fuzzy match
            matches = [n for n in _COMMAND_REGISTRY if n.startswith(cmd_name)]
            if len(matches) == 1:
                cmd = _COMMAND_REGISTRY[matches[0]]
            else:
                Formatter.error(f"Unknown command: /{cmd_name}")
                if matches:
                    print(f"  Did you mean: {', '.join('/' + m for m in matches)}?")
                else:
                    print("  Type /help for available commands.")
                return

        try:
            cmd["fn"](self, cmd_args)
        except Exception as e:
            Formatter.error(f"Command error: {e}")
            logger.exception(f"Error in /{cmd_name}")

    def _handle_natural_language(self, text: str):
        """Send natural language input to the orchestrator."""
        f = Formatter
        f.info("Processing…")

        try:
            result = self.engines["orchestrator"].parse_intent(text)
            if result.get("success"):
                intent = result.get("intent", result.get("action", ""))
                f.info(f"Intent: {f.badge(intent)}")
                exec_result = self.engines["orchestrator"].execute_intent(
                    result, self._engines_dict,
                )
                if exec_result.get("success"):
                    msg = exec_result.get("message", "Done.")
                    print(f"\n  {msg}")
                    data = exec_result.get("data")
                    if data:
                        print(f"  {json.dumps(data, indent=2, default=str)}")
                else:
                    f.error(exec_result.get("error", "Execution failed"))
            else:
                f.warn(f"Could not understand: {result.get('error', 'Unknown')}")
                print("  Try a /command or rephrase.")
        except Exception as e:
            f.error(f"Error: {e}")
            logger.exception("Natural language processing error")

    def run_command(self, cmd_name: str, cmd_args: list):
        """Run a single command (for one-shot mode)."""
        cmd = _COMMAND_REGISTRY.get(cmd_name)
        if not cmd:
            Formatter.error(f"Unknown command: {cmd_name}")
            return 1
        try:
            cmd["fn"](self, cmd_args)
            return 0
        except Exception as e:
            Formatter.error(f"Error: {e}")
            return 1


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    Formatter.init()

    parser = argparse.ArgumentParser(
        prog="aura",
        description=f"{APP_NAME} v{APP_VERSION} — AI Sales Agent (CLI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              aura                        Start interactive REPL
              aura hunt "plumber" --city "Austin TX"
              aura qualify 1
              aura draft 1
              aura send 1 --count 10
              aura campaigns
              aura status
              aura --help

            In REPL mode, prefix commands with /:
              /hunt plumber --city "Austin TX"
              /help pipeline
              /status
        """),
    )
    parser.add_argument("--version", "-v", action="store_true", help="Show version")
    parser.add_argument("--verbose", "-V", action="store_true",
                        help="Show detailed log output")
    parser.add_argument("command", nargs="?", help="Command to run (or start REPL if omitted)")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Command arguments")

    args = parser.parse_args()

    if args.version:
        print(f"{APP_NAME} v{APP_VERSION}")
        return

    # One-shot commands that don't need engine init
    if args.command == "version":
        print(f"{APP_NAME} v{APP_VERSION}")
        return

    if args.command == "help":
        Formatter.init()
        if args.args:
            if args.args[0] in COMMAND_GROUPS:
                HelpSystem.show_group(args.args[0])
            else:
                HelpSystem.show_command(args.args[0])
        else:
            HelpSystem.show_overview()
        return

    # Silence all noise unless --verbose
    if not args.verbose:
        warnings.filterwarnings("ignore")
        from utils.logger import set_console_level
        set_console_level(logging.ERROR)

    # Initialize CLI
    cli = AuraCLI()

    try:
        if args.command is None:
            # Default: REPL mode
            cli.run_repl()
        else:
            # One-shot command
            sys.exit(cli.run_command(args.command, args.args))
    except KeyboardInterrupt:
        print()
    finally:
        cli._shutdown()


if __name__ == "__main__":
    main()
