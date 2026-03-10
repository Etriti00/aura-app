"""
Aura — Main Window
Application shell with sidebar navigation, stacked pages, controller wiring,
chat panel, and new feature integration.
"""

from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QStackedWidget, QPushButton, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QShortcut, QKeySequence

from config import (
    APP_NAME, Geometry
)
from ui.components.sidebar import Sidebar
from ui.pages.dashboard import DashboardPage
from ui.pages.hunter import HunterPage
from ui.pages.forge import ForgePage
from ui.pages.outreach import OutreachPage
from ui.pages.fleet import FleetPage
from ui.pages.kanban import KanbanPage
from ui.pages.history import HistoryPage
from ui.pages.trends import TrendsPage
from ui.pages.budget import BudgetPage
from ui.pages.integrations import IntegrationsPage
from ui.pages.settings import SettingsPage
from ui.pages.suppression import SuppressionPage
from ui.pages.research import ResearchPage
from ui.pages.calls import CallsPage
from ui.components.chat_panel import ChatPanel

from controllers.hunter_controller import HunterController
from controllers.dashboard_controller import DashboardController
from controllers.forge_controller import ForgeController
from controllers.outreach_controller import OutreachController
from controllers.settings_controller import SettingsController
from controllers.sequence_controller import SequenceController
from controllers.reply_controller import ReplyController
from controllers.chat_controller import ChatController
from controllers.fleet_controller import FleetController
from controllers.trends_controller import TrendsController
from controllers.budget_controller import BudgetController
from controllers.gateway_controller import GatewayController
from controllers.kanban_controller import KanbanController
from controllers.command_history_controller import CommandHistoryController

from core.suppression_engine import SuppressionEngine
from core.report_engine import ReportEngine
from core.enrichment_engine import EnrichmentEngine
from core.api_queue import APIQueue
from core.apollo_engine import ApolloEngine
from core.hunter_engine import HunterEngine
from core.router_engine import RouterEngine
from core.rag_engine import RAGEngine
from core.channel_engine import ChannelEngine
from core.crm_engine import CRMEngine
from core.triage_engine import TriageEngine
from core.pacing_engine import PacingEngine
from core.gateway_engine import GatewayEngine
from core.batch_importer import BatchImporter
from core.ticket_engine import TicketEngine
from core.escalation_engine import EscalationEngine
from core.ticket_scheduler import TicketScheduler
from core.command_history import CommandHistoryEngine
from core.reflection_engine import ReflectionEngine
from core.lead_lifecycle_engine import LeadLifecycleEngine
from core.knowledge_graph_engine import KnowledgeGraphEngine
from core.conversation_engine import ConversationEngine
from core.self_improvement_engine import SelfImprovementEngine
from core.strategy_engine import StrategyEngine
from core.analyst_engine import AnalystEngine
from controllers.autonomy_controller import AutonomyController
from controllers.enrichment_api_controller import EnrichmentApiController

from core.hubspot_engine import HubSpotEngine
from core.linkedin_engine import LinkedInEngine
from core.navigation_service import NavigationService
from core.skill_registry import SkillRegistry
from core.token_manager import TokenManager
from core.case_engine import CaseEngine
from core.subagent_engine import SubagentEngine
from core.research_engine import ResearchEngine
from core.voice_call_engine import VoiceCallEngine
from controllers.research_controller import ResearchController
from controllers.voice_controller import VoiceController
from ui.components.command_palette import CommandPalette
from ui.components.toast_notification import show_toast
from ui.icons import get_icon


class MainWindow(QMainWindow):
    """Aura main application window with sidebar navigation and page stack."""

    def __init__(self, db_manager, key_vault):
        super().__init__()
        self.db_manager = db_manager
        self.key_vault = key_vault

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(*Geometry.WINDOW_MIN)
        self.resize(*Geometry.WINDOW_DEFAULT)
        self._current_theme = "dark"

        self._setup_ui()
        self._init_controllers()
        self._wire_signals()
        self._load_initial_data()

    def _setup_ui(self):
        """Build the main UI structure."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)

        # Right content area
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Top bar
        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(56)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(24, 0, 24, 0)

        top_bar_layout.addStretch()

        # Floating chat button
        self.chat_toggle_btn = QPushButton()
        self.chat_toggle_btn.setIcon(get_icon("chat_toggle", self._current_theme))
        self.chat_toggle_btn.setIconSize(QSize(20, 20))
        self.chat_toggle_btn.setObjectName("chatToggleButton")
        self.chat_toggle_btn.setFixedSize(40, 40)
        self.chat_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chat_toggle_btn.setToolTip("Toggle AI Chat (Ctrl+Space)")
        top_bar_layout.addWidget(self.chat_toggle_btn)

        content_layout.addWidget(top_bar)

        # Page-and-chat wrapper (horizontal: pages | chat panel)
        page_chat_wrapper = QWidget()
        page_chat_layout = QHBoxLayout(page_chat_wrapper)
        page_chat_layout.setContentsMargins(0, 0, 0, 0)
        page_chat_layout.setSpacing(0)

        # Page stack — Ignored policy + minWidth(0) so it yields space to chat panel
        self.page_stack = QStackedWidget()
        self.page_stack.setMinimumWidth(0)
        self.page_stack.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        self.dashboard_page = DashboardPage()
        self.hunter_page = HunterPage()
        self.forge_page = ForgePage()
        self.outreach_page = OutreachPage()
        self.fleet_page = FleetPage()
        self.kanban_page = KanbanPage()
        self.history_page = HistoryPage()
        self.trends_page = TrendsPage()
        self.budget_page = BudgetPage()
        self.integrations_page = IntegrationsPage()
        self.settings_page = SettingsPage()
        self.suppression_page = SuppressionPage()
        self.research_page = ResearchPage()
        self.calls_page = CallsPage()

        self.page_stack.addWidget(self.dashboard_page)     # 0
        self.page_stack.addWidget(self.hunter_page)         # 1
        self.page_stack.addWidget(self.forge_page)          # 2
        self.page_stack.addWidget(self.outreach_page)       # 3
        self.page_stack.addWidget(self.fleet_page)          # 4
        self.page_stack.addWidget(self.kanban_page)         # 5
        self.page_stack.addWidget(self.history_page)        # 6
        self.page_stack.addWidget(self.trends_page)         # 7
        self.page_stack.addWidget(self.budget_page)         # 8
        self.page_stack.addWidget(self.integrations_page)   # 9
        self.page_stack.addWidget(self.settings_page)       # 10
        self.page_stack.addWidget(self.suppression_page)    # 11
        self.page_stack.addWidget(self.research_page)       # 12
        self.page_stack.addWidget(self.calls_page)          # 13

        page_chat_layout.addWidget(self.page_stack, stretch=1)

        # Chat panel (initially hidden)
        self.chat_panel = ChatPanel()
        self.chat_panel.hide()
        page_chat_layout.addWidget(self.chat_panel)

        content_layout.addWidget(page_chat_wrapper, stretch=1)

        # Status bar
        status_bar = QWidget()
        status_bar.setObjectName("statusBar")
        status_bar.setFixedHeight(32)
        status_bar_layout = QHBoxLayout(status_bar)
        status_bar_layout.setContentsMargins(16, 0, 16, 0)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusText")
        status_bar_layout.addWidget(self.status_label)
        status_bar_layout.addStretch()

        self.db_status = QLabel("DB: Connected")
        self.db_status.setObjectName("statusTextSuccess")
        status_bar_layout.addWidget(self.db_status)

        content_layout.addWidget(status_bar)
        main_layout.addWidget(content_area, stretch=1)

        # Navigation
        self.sidebar.page_changed.connect(self._on_page_changed)

        # Page titles and subtitles
        self._page_info = {
            0: ("Dashboard", "Your campaign performance at a glance"),
            1: ("Hunter", "Find and scrape business leads"),
            2: ("Forge", "Create and manage AI personas"),
            3: ("Outreach", "Generate and send personalized emails"),
            4: ("Fleet", "Multi-agent command center"),
            5: ("Kanban", "Track and manage agent tickets"),
            6: ("History", "Command history and activity log"),
            7: ("Trends", "Google Trends intelligence"),
            8: ("Budget", "Cost pacing and budget monitoring"),
            9: ("Integrations", "External chat and platform connections"),
            10: ("Settings", "Configure API keys, models, and delivery"),
            11: ("Suppression", "Manage global email suppression list"),
        }

        # Chat toggle shortcut (Ctrl+Space)
        chat_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        chat_shortcut.activated.connect(self._toggle_chat)
        self.chat_toggle_btn.clicked.connect(self._toggle_chat)

        # Escape to close chat panel or command palette
        esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        esc_shortcut.activated.connect(self._close_chat_if_open)

        # Ctrl+K to open command palette
        palette_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        palette_shortcut.activated.connect(self._toggle_command_palette)

    def _init_controllers(self):
        """Initialize all controllers."""
        # New controllers for expansion features
        self.suppression_engine = SuppressionEngine(self.db_manager)
        self.report_engine = ReportEngine(self.db_manager)
        self.enrichment_engine = EnrichmentEngine(self.db_manager)

        self.hunter_ctrl = HunterController(self.db_manager, enrichment_engine=self.enrichment_engine)
        self.dashboard_ctrl = DashboardController(self.db_manager)
        self.forge_ctrl = ForgeController(self.db_manager)
        self.outreach_ctrl = OutreachController(self.db_manager, self.key_vault)
        self.settings_ctrl = SettingsController(self.db_manager, self.key_vault)

        from core.sequence_engine import SequenceEngine
        self.sequence_engine = SequenceEngine(self.db_manager)
        self.sequence_ctrl = SequenceController(
            self.db_manager,
            self.sequence_engine,
            self.outreach_ctrl.ai_engine,
            self.outreach_ctrl.delivery,
        )
        from core.reply_detector import ReplyDetector
        self.reply_detector = ReplyDetector(self.db_manager, self.key_vault)
        self.reply_ctrl = ReplyController(self.db_manager, self.reply_detector)

        # ─── Router Engine (4-tier LLM routing) ────────────────
        self.router_engine = RouterEngine(self.db_manager, self.key_vault)
        self.outreach_ctrl.ai_engine.set_router(self.router_engine)

        # ─── RAG Engine ───────────────────────────────────────
        self.rag_engine = RAGEngine(self.db_manager)
        self.outreach_ctrl.ai_engine.set_rag_engine(self.rag_engine)
        self.outreach_ctrl.delivery.rag_engine = self.rag_engine
        self.reply_detector.rag_engine = self.rag_engine

        # ─── Channel Engine (multi-channel outreach) ──────────
        self.channel_engine = ChannelEngine(self.db_manager, self.outreach_ctrl.ai_engine)
        self.outreach_ctrl.channel_engine = self.channel_engine

        # ─── CRM Engine ────────────────────────────────────────
        self.crm_engine = CRMEngine(self.db_manager, self.key_vault)

        # ─── Triage Engine ─────────────────────────────────────
        self.triage_engine = TriageEngine(
            self.db_manager, self.key_vault,
            ai_engine=self.outreach_ctrl.ai_engine,
            suppression_engine=self.suppression_engine,
        )

        # ─── API Queue + Apollo/Hunter/HubSpot/LinkedIn ────────
        self.api_queue = APIQueue(self.db_manager)
        self.apollo_engine = ApolloEngine(self.db_manager, self.key_vault, self.api_queue)
        self.hunter_engine = HunterEngine(self.db_manager, self.key_vault, self.api_queue)
        self.hubspot_engine = HubSpotEngine(self.db_manager, self.key_vault, self.api_queue)
        self.linkedin_engine = LinkedInEngine()
        self.enrichment_api_ctrl = EnrichmentApiController(
            self.db_manager, self.apollo_engine, self.hunter_engine, self.suppression_engine
        )

        # Wire waterfall enrichment engines
        self.enrichment_engine.apollo_engine = self.apollo_engine
        self.enrichment_engine.hunter_engine = self.hunter_engine

        # Inject API engines into hunter controller
        self.hunter_ctrl.apollo_engine = self.apollo_engine
        self.hunter_ctrl.hunter_engine = self.hunter_engine
        self.hunter_ctrl.hubspot_engine = self.hubspot_engine
        self.hunter_ctrl.linkedin_engine = self.linkedin_engine
        # AI + lifecycle engines injected later (after advanced engines init)

        # ─── Navigation Service ──────────────────────────────
        self.navigation_service = NavigationService(self)
        self.navigation_service.navigate_requested.connect(self._on_navigation)

        # ─── Skill Registry ──────────────────────────────────
        self.skill_registry = SkillRegistry(self.db_manager)
        self.skill_registry.seed_builtin_skills()

        # ─── Command Palette ─────────────────────────────────
        self.command_palette = CommandPalette(self)
        self.command_palette.command_selected.connect(self._on_palette_command)
        self.command_palette.set_commands(
            self.navigation_service.get_navigation_commands()
        )

        # ─── Pacing Engine ─────────────────────────────────────
        self.pacing_engine = PacingEngine(self.db_manager, self.router_engine)
        self.router_engine.pacing_engine = self.pacing_engine

        # ─── Rate limit callback ──────────────────────────────
        self.router_engine.on_rate_limit_callback = self._on_rate_limit_detected

        # ─── Batch Importer ───────────────────────────────────
        self.batch_importer = BatchImporter(self.db_manager)

        # ─── Budget Controller ─────────────────────────────────
        self.budget_ctrl = BudgetController(self.pacing_engine)

        # ─── Orchestrator + Chat ───────────────────────────────
        from core.orchestrator_engine import OrchestratorEngine
        self.orchestrator_engine = OrchestratorEngine(self.db_manager, self.key_vault)
        engines_dict = {
            "suppression": self.suppression_engine,
            "report": self.report_engine,
            "enrichment": self.enrichment_engine,
            "apollo": self.apollo_engine,
            "hunter": self.hunter_engine,
            "hubspot": self.hubspot_engine,
            "linkedin": self.linkedin_engine,
            "enrichment_api": self.enrichment_api_ctrl,
            "router": self.router_engine,
            "rag": self.rag_engine,
            "channel": self.channel_engine,
            "crm": self.crm_engine,
            "triage": self.triage_engine,
            "pacing": self.pacing_engine,
            "navigation": self.navigation_service,
            "skill_registry": self.skill_registry,
        }
        self.chat_ctrl = ChatController(
            self.db_manager, self.orchestrator_engine, engines_dict
        )

        # ─── Gateway Engine + Controller ──────────────────────
        self.gateway_engine = GatewayEngine(
            self.db_manager, self.key_vault,
            self.orchestrator_engine, engines_dict,
        )
        self.gateway_ctrl = GatewayController(self.gateway_engine)
        engines_dict["gateway"] = self.gateway_engine

        # ─── Agent/Fleet/Observer/Trends Engines ──────────────
        from core.agent_engine import AgentEngine
        from core.fleet_orchestrator import FleetOrchestrator
        from core.observer_engine import ObserverEngine
        from core.trends_engine import TrendsEngine

        self.agent_engine = AgentEngine(
            self.db_manager, self.key_vault, self.router_engine,
            forge_controller=self.forge_ctrl,
            pacing_engine=self.pacing_engine,
        )
        self.fleet_orchestrator = FleetOrchestrator(
            self.db_manager, self.agent_engine
        )
        self.observer_engine = ObserverEngine(
            self.db_manager, self.agent_engine
        )
        self.trends_engine = TrendsEngine(self.db_manager)

        self.fleet_ctrl = FleetController(
            self.db_manager, self.agent_engine,
            self.fleet_orchestrator, self.observer_engine,
        )
        # Inject pipeline automation controllers into fleet controller
        self.fleet_ctrl.reply_ctrl = self.reply_ctrl
        self.fleet_ctrl.sequence_ctrl = self.sequence_ctrl
        self.fleet_ctrl.outreach_ctrl = self.outreach_ctrl

        self.trends_ctrl = TrendsController(
            self.db_manager, self.trends_engine
        )

        # ─── Ticket Engine + Escalation + Scheduler + Kanban ──
        self.ticket_engine = TicketEngine(self.db_manager)
        self.escalation_engine = EscalationEngine(
            self.db_manager, self.ticket_engine, self.agent_engine,
        )
        self.ticket_scheduler = TicketScheduler(
            self.db_manager, self.ticket_engine, self.agent_engine,
        )
        self.agent_engine.escalation_engine = self.escalation_engine
        self.kanban_ctrl = KanbanController(
            self.db_manager, self.ticket_engine, self.ticket_scheduler,
        )

        # Pass escalation engine + kanban_ctrl to fleet controller
        self.fleet_ctrl.escalation_engine = self.escalation_engine
        self.fleet_ctrl.kanban_ctrl = self.kanban_ctrl

        # ─── Command History Engine + Controller ────────────
        self.command_history_engine = CommandHistoryEngine(self.db_manager)
        self.command_history_ctrl = CommandHistoryController(
            self.db_manager, self.command_history_engine,
        )

        # Inject command history into engines that log activity
        self.gateway_engine.command_history = self.command_history_engine
        self.agent_engine.command_history = self.command_history_engine
        self.fleet_orchestrator.command_history = self.command_history_engine
        self.chat_ctrl.command_history = self.command_history_engine

        # Register new engines for orchestrator
        engines_dict["agent"] = self.agent_engine
        engines_dict["fleet"] = self.fleet_orchestrator
        engines_dict["observer"] = self.observer_engine
        engines_dict["trends"] = self.trends_engine
        engines_dict["ticket"] = self.ticket_engine
        engines_dict["escalation"] = self.escalation_engine
        engines_dict["ticket_scheduler"] = self.ticket_scheduler
        engines_dict["command_history"] = self.command_history_engine

        # ─── Advanced Engines (Phase 1-8) ────────────────────
        self.reflection_engine = ReflectionEngine(
            self.db_manager, router_engine=self.router_engine
        )
        self.lead_lifecycle_engine = LeadLifecycleEngine(
            self.db_manager, fleet_orchestrator=self.fleet_orchestrator
        )
        self.knowledge_graph_engine = KnowledgeGraphEngine(
            self.db_manager, rag_engine=self.rag_engine
        )
        self.conversation_engine = ConversationEngine(
            self.db_manager, router_engine=self.router_engine,
            rag_engine=self.rag_engine,
            knowledge_graph=self.knowledge_graph_engine,
        )
        self.self_improvement_engine = SelfImprovementEngine(
            self.db_manager, reflection_engine=self.reflection_engine,
            rag_engine=self.rag_engine,
            fleet_orchestrator=self.fleet_orchestrator,
            forge_controller=self.forge_ctrl,
        )
        self.strategy_engine = StrategyEngine(
            self.db_manager, fleet_orchestrator=self.fleet_orchestrator,
            knowledge_graph=self.knowledge_graph_engine,
        )
        self.autonomy_controller = AutonomyController(self.db_manager)
        self.analyst_engine = AnalystEngine(self.db_manager, self.key_vault)

        # Cross-wire advanced engines into agent system
        self.agent_engine.reflection_engine = self.reflection_engine
        self.agent_engine.knowledge_graph = self.knowledge_graph_engine
        self.agent_engine.self_improvement_engine = self.self_improvement_engine
        self.agent_engine.autonomy_controller = self.autonomy_controller

        # Wire into reply detector
        self.reply_detector.conversation_engine = self.conversation_engine
        self.reply_detector.lead_lifecycle_engine = self.lead_lifecycle_engine
        self.reply_detector.knowledge_graph_engine = self.knowledge_graph_engine
        self.reply_detector.strategy_engine = self.strategy_engine

        # Register lifecycle callbacks for strategy progress
        self.lead_lifecycle_engine.register_on_enter(
            "closed_won", self._on_lead_closed_won,
        )

        # Wire into enrichment engine
        self.enrichment_engine.lead_lifecycle_engine = self.lead_lifecycle_engine
        self.enrichment_engine.knowledge_graph_engine = self.knowledge_graph_engine
        self.enrichment_engine.router_engine = self.router_engine
        self.enrichment_engine.case_engine = getattr(self, 'case_engine', None)

        # Wire deal stage callback for pricing when lead reaches negotiating/closed_won
        def _on_deal_stage(lead_id, from_state, to_state):
            if to_state in ("negotiating", "closed_won"):
                try:
                    if hasattr(self, 'fleet_ctrl') and self.fleet_ctrl:
                        self.fleet_ctrl.dispatch_task("evaluate_pricing", {"lead_id": lead_id})
                except Exception:
                    pass

        self.lead_lifecycle_engine.register_on_enter("negotiating", lambda lid, fs, ts: _on_deal_stage(lid, fs, ts))
        self.lead_lifecycle_engine.register_on_enter("closed_won", lambda lid, fs, ts: _on_deal_stage(lid, fs, ts))

        # Wire AI + lifecycle into hunter controller for auto-qualification
        self.hunter_ctrl.ai_engine = self.outreach_ctrl.ai_engine
        self.hunter_ctrl.lead_lifecycle_engine = self.lead_lifecycle_engine

        # Wire self-improvement into fleet controller for periodic timer
        self.fleet_ctrl.self_improvement_engine = self.self_improvement_engine

        # Inject command history into advanced engines
        self.autonomy_controller.command_history = self.command_history_engine
        self.lead_lifecycle_engine.command_history = self.command_history_engine
        self.reflection_engine.command_history = self.command_history_engine

        # ─── Token Manager, Case Engine, Subagent Engine ─────────────
        self.token_manager = TokenManager(
            self.db_manager, router_engine=self.router_engine,
        )
        self.case_engine = CaseEngine(
            self.db_manager,
            router_engine=self.router_engine,
            token_manager=self.token_manager,
        )
        self.subagent_engine = SubagentEngine(
            self.db_manager, router_engine=self.router_engine,
        )

        # Inject into agent_engine
        self.agent_engine.token_manager = self.token_manager
        self.agent_engine.case_engine = self.case_engine
        self.agent_engine.subagent_engine = self.subagent_engine

        # Inject case_engine into lifecycle + reflection + enrichment for auto-note logging
        self.lead_lifecycle_engine.case_engine = self.case_engine
        self.reflection_engine.case_engine = self.case_engine
        self.enrichment_engine.case_engine = self.case_engine

        # Register new engines for orchestrator
        engines_dict["reflection"] = self.reflection_engine
        engines_dict["lifecycle"] = self.lead_lifecycle_engine
        engines_dict["knowledge_graph"] = self.knowledge_graph_engine
        engines_dict["conversation"] = self.conversation_engine
        engines_dict["self_improvement"] = self.self_improvement_engine
        engines_dict["strategy"] = self.strategy_engine
        engines_dict["autonomy"] = self.autonomy_controller
        engines_dict["analyst"] = self.analyst_engine
        engines_dict["token_manager"] = self.token_manager
        engines_dict["case"] = self.case_engine
        engines_dict["subagent"] = self.subagent_engine

        # ─── Research Engine + Controller ─────────────────────────
        self.research_engine = ResearchEngine(
            self.db_manager,
            router_engine=self.router_engine,
            key_vault=self.key_vault,
        )
        self.research_engine.case_engine = self.case_engine
        self.research_engine.configure(self.key_vault)
        self.research_ctrl = ResearchController(self.research_engine)

        # ─── Voice Call Engine + Controller ───────────────────────
        self.voice_engine = VoiceCallEngine(
            self.db_manager,
            router_engine=self.router_engine,
            key_vault=self.key_vault,
        )
        self.voice_engine.case_engine = self.case_engine
        self.voice_engine.research_engine = self.research_engine
        self.voice_engine.lead_lifecycle_engine = self.lead_lifecycle_engine
        self.voice_engine.configure(self.key_vault)
        self.voice_ctrl = VoiceController(self.voice_engine)

        # Inject research into hunter controller for auto-research after qualification
        self.hunter_ctrl.research_engine = self.research_engine

        # Inject research + case into outreach controller for email personalization
        self.outreach_ctrl.research_engine = self.research_engine
        self.outreach_ctrl.case_engine = self.case_engine

        # Inject voice/autonomy into fleet controller for caller agent
        self.fleet_ctrl.voice_ctrl = self.voice_ctrl
        self.fleet_ctrl.voice_engine = self.voice_engine
        self.fleet_ctrl.autonomy_ctrl = self.autonomy_controller

        # ─── Pricing + Invoice Approval Engines ──────────────
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        self.pricing_engine = PricingEngine(self.db_manager, router_engine=self.router_engine)
        self.invoice_approval_engine = InvoiceApprovalEngine(
            self.db_manager,
            gateway_engine=self.gateway_engine,
            pricing_engine=self.pricing_engine,
        )

        engines_dict["pricing"] = self.pricing_engine
        engines_dict["invoice_approval"] = self.invoice_approval_engine
        engines_dict["research"] = self.research_engine
        engines_dict["voice"] = self.voice_engine
        engines_dict["hunter_ctrl"] = self.hunter_ctrl

        # Set suppression engine on the page
        self.suppression_page.set_engine(self.suppression_engine)

        # Wire triage engine to reply controller
        self.reply_ctrl.triage_engine = self.triage_engine

    def _wire_signals(self):
        """Connect all controller-page signal wiring."""

        # ─── Hunter signals ───────────────────────────────────
        self.hunter_page.start_requested.connect(self.hunter_ctrl.start_scrape)
        self.hunter_page.stop_requested.connect(self.hunter_ctrl.stop_scrape)

        self.hunter_ctrl.lead_found.connect(self.hunter_page.add_lead_row)
        self.hunter_ctrl.scrape_progress.connect(self.hunter_page.set_progress)
        self.hunter_ctrl.scrape_finished.connect(self.hunter_page.on_scrape_finished)
        self.hunter_ctrl.scrape_error.connect(
            lambda msg: show_toast(self, msg, "error")
        )
        self.hunter_ctrl.kill_switch_activated.connect(
            self.hunter_page.on_kill_switch
        )
        self.hunter_ctrl.lead_qualified.connect(
            lambda lid, r: show_toast(
                self,
                f"Lead #{lid}: {'Qualified' if r.get('qualified') else 'Disqualified'} ({r.get('score', 0)}/10)",
                "success" if r.get("qualified") else "info",
            )
        )

        # Batch CSV import
        self.hunter_page.batch_import_requested.connect(self._on_batch_import)

        # ─── Apollo / Hunter API signals ──────────────────────
        self.hunter_page.apollo_search_requested.connect(
            lambda niche, city, keywords, limit: self.enrichment_api_ctrl.search_apollo_for_campaign(
                0, niche, city, keywords, 50, limit
            )
        )
        self.enrichment_api_ctrl.search_finished.connect(
            self.hunter_page.on_apollo_search_finished
        )
        self.enrichment_api_ctrl.error.connect(
            lambda msg: show_toast(self, msg, "error")
        )
        self.enrichment_api_ctrl.rate_limited.connect(
            lambda svc, secs: show_toast(self, f"{svc} rate-limited — retry in {secs}s", "warning")
        )
        self.enrichment_api_ctrl.status_message.connect(
            lambda msg: self.status_label.setText(msg)
        )

        # ─── HubSpot / LinkedIn signals ────────────────────────
        self.hunter_page.hubspot_search_requested.connect(
            self._on_hubspot_search
        )
        self.hunter_page.linkedin_import_requested.connect(
            self._on_linkedin_import
        )
        self.hunter_ctrl.hubspot_search_finished.connect(
            self.hunter_page.on_hubspot_search_finished
        )
        self.hunter_ctrl.linkedin_import_finished.connect(
            self.hunter_page.on_linkedin_import_finished
        )

        # ─── Navigation signals ────────────────────────────────
        self.hunter_page.navigate_requested.connect(
            lambda idx, ctx: self.navigation_service.navigate_by_index(idx, ctx)
        )

        # ─── Dashboard signals ─────────────────────────────────
        self.dashboard_ctrl.stats_ready.connect(self.dashboard_page.update_stats)
        self.dashboard_page.export_requested.connect(self._on_export_report)

        # ─── Forge signals ─────────────────────────────────────
        self.forge_page.save_requested.connect(self._on_forge_save)
        self.forge_page.delete_requested.connect(self._on_forge_delete)
        self.forge_page.import_requested.connect(self._on_forge_import)
        self.forge_page.export_requested.connect(self._on_forge_export)

        self.forge_ctrl.skills_changed.connect(self._refresh_forge)
        self.forge_ctrl.skill_saved.connect(
            lambda name: show_toast(self, f"Skill '{name}' saved.", "success")
        )
        self.forge_ctrl.skill_error.connect(
            lambda msg: show_toast(self, msg, "error")
        )

        # RAG memory signals from forge page
        self.forge_page.rag_import_requested.connect(self._on_rag_import)
        self.forge_page.rag_clear_requested.connect(self._on_rag_clear)

        # ─── Outreach signals ─────────────────────────────────
        self.outreach_page.generate_requested.connect(
            self.outreach_ctrl.generate_draft
        )
        self.outreach_page.send_requested.connect(
            lambda lid, to, subj, body: self.outreach_ctrl.send_email(lid, to, subj, body)
        )

        self.outreach_ctrl.email_generated.connect(self.outreach_page.show_draft)
        self.outreach_ctrl.email_sent.connect(self.outreach_page.on_email_sent)
        self.outreach_ctrl.error.connect(
            lambda msg: show_toast(self, msg, "error")
        )

        # Multi-channel signals
        self.outreach_page.generate_channels_requested.connect(
            self.outreach_ctrl.generate_all_channel_drafts
        )
        self.outreach_ctrl.all_channels_drafted.connect(
            self.outreach_page.show_channel_drafts
        )

        # CRM sync signal
        self.outreach_page.crm_sync_requested.connect(self._on_crm_sync_campaign)

        # Campaign selection → load qualified leads
        self.outreach_page.campaign_combo.currentIndexChanged.connect(
            self._on_outreach_campaign_changed
        )

        # ─── Settings signals ─────────────────────────────────
        self.settings_page.save_key_requested.connect(self.settings_ctrl.save_api_key)
        self.settings_page.save_models_requested.connect(self.settings_ctrl.save_models)
        self.settings_page.save_chat_model_requested.connect(self.settings_ctrl.save_chat_model)
        self.settings_page.save_sender_requested.connect(self.settings_ctrl.save_sender_info)
        self.settings_page.save_smtp_requested.connect(self.settings_ctrl.save_smtp)
        self.settings_page.theme_change_requested.connect(self._on_theme_change)

        # New settings signals
        self.settings_page.save_imap_requested.connect(
            lambda h, p, u, pw, ssl: self.settings_ctrl.save_imap(h, p, u, pw, ssl)
        )
        self.settings_page.save_toggles_requested.connect(
            lambda toggles: self.settings_ctrl.save_toggles(toggles)
        )

        # Autonomy level signal
        self.settings_page.autonomy_level_changed.connect(
            lambda level: self.autonomy_controller.set_autonomy_level(level)
        )

        # Auth mode signals
        self.settings_page.auth_mode_changed.connect(
            self.settings_ctrl.save_auth_mode
        )

        # Subscription auth signals
        self.settings_page.save_anthropic_sub_requested.connect(
            self.settings_ctrl.save_anthropic_sub_token
        )
        self.settings_page.openai_oauth_requested.connect(self._on_openai_oauth)
        self.settings_page.openai_disconnect_requested.connect(
            lambda: self.settings_ctrl.clear_sub_token("openai")
        )

        self.settings_page.save_business_requested.connect(
            self.settings_ctrl.save_business_settings
        )

        self.settings_ctrl.settings_saved.connect(
            lambda: show_toast(self, "Settings saved.", "success")
        )

        # ─── Sequence controller signals ──────────────────────
        self.sequence_ctrl.followup_sent.connect(
            lambda lead_id, step: show_toast(self, f"Follow-up sent to lead #{lead_id}", "success")
        )
        self.sequence_ctrl.followup_error.connect(
            lambda lead_id, msg: show_toast(self, f"Follow-up error (lead #{lead_id}): {msg}", "error")
        )

        # ─── Reply controller signals ────────────────────────
        self.reply_ctrl.reply_detected.connect(
            lambda lead_id, name: show_toast(self, f"Reply from {name}!", "info")
        )
        self.reply_ctrl.check_error.connect(
            lambda msg: show_toast(self, msg, "error")
        )

        # ─── Triage signals ───────────────────────────────────
        self.dashboard_page.triage_requested.connect(self._on_run_triage)
        self.reply_ctrl.triage_complete.connect(self.dashboard_page.show_triage_results)

        # ─── Budget signals ───────────────────────────────────
        self.budget_page.pacing_start_requested.connect(self.budget_ctrl.start_pacing)
        self.budget_page.pacing_stop_requested.connect(self.budget_ctrl.stop_pacing)
        self.budget_page.preflight_requested.connect(self.budget_ctrl.run_preflight)
        self.budget_ctrl.status_updated.connect(self.budget_page.update_pacing_status)
        self.budget_ctrl.tier_downgraded.connect(
            lambda f, t: show_toast(self, f"Eco-Mode: {f} → {t}", "warning")
        )
        self.budget_ctrl.budget_warning.connect(
            lambda msg: show_toast(self, msg, "warning")
        )
        self.budget_ctrl.budget_expired.connect(
            lambda: show_toast(self, "Budget time window expired", "info")
        )
        self.budget_ctrl.preflight_result.connect(self.budget_page.show_preflight_result)

        # ─── Gateway signals ──────────────────────────────────
        self.integrations_page.platform_connect_requested.connect(
            self.gateway_ctrl.start_platform
        )
        self.integrations_page.platform_disconnect_requested.connect(
            self.gateway_ctrl.stop_platform
        )
        self.integrations_page.user_add_requested.connect(
            self.gateway_ctrl.add_authorized_user
        )
        self.integrations_page.user_remove_requested.connect(
            self.gateway_ctrl.remove_authorized_user
        )
        self.gateway_ctrl.connection_status.connect(
            self.integrations_page.update_connection_status
        )
        self.gateway_ctrl.error.connect(
            lambda msg: show_toast(self, msg, "error")
        )

        # Proactive notifications: pacing → gateway
        self.budget_ctrl.budget_warning.connect(
            lambda msg: self.gateway_ctrl.send_notification(msg)
        )
        self.budget_ctrl.tier_downgraded.connect(
            lambda f, t: self.gateway_ctrl.send_notification(
                f"Model downgraded: {f} -> {t}"
            )
        )

        # ─── Fleet signals ───────────────────────────────────
        self.fleet_page.boot_fleet_requested.connect(self.fleet_ctrl.boot_fleet)
        self.fleet_page.shutdown_fleet_requested.connect(self.fleet_ctrl.shutdown_fleet)
        self.fleet_page.health_check_requested.connect(self.fleet_ctrl.run_health_check)
        self.fleet_page.boot_agent_requested.connect(self.fleet_ctrl.boot_agent)
        self.fleet_page.shutdown_agent_requested.connect(self.fleet_ctrl.shutdown_agent)

        # Agent detail dialog wiring
        self.fleet_page.agent_selected.connect(self.fleet_ctrl.get_agent_status)
        self.fleet_ctrl.agent_status_ready.connect(self.fleet_page.show_agent_detail)
        self.fleet_page.detail_dialog.edit_field.connect(self.fleet_ctrl.update_agent_field)
        self.fleet_page.detail_dialog.boot_requested.connect(self.fleet_ctrl.boot_agent)
        self.fleet_page.detail_dialog.shutdown_requested.connect(self.fleet_ctrl.shutdown_agent)

        self.fleet_ctrl.pipeline_complete.connect(self._on_pipeline_complete)
        self.fleet_ctrl.fleet_status_ready.connect(self.fleet_page.update_fleet_status)
        self.fleet_ctrl.health_check_ready.connect(self.fleet_page.update_health_check)
        self.fleet_ctrl.fleet_booted.connect(
            lambda r: (
                self.fleet_page.set_fleet_running(True),
                self.fleet_ctrl.refresh_fleet_status(),
                show_toast(self, f"Fleet booted: {r.get('data', {}).get('booted', 0)} agents", "success"),
            )
        )
        self.fleet_ctrl.fleet_shutdown.connect(
            lambda: (
                self.fleet_page.set_fleet_running(False),
                self.fleet_ctrl.refresh_fleet_status(),
                show_toast(self, "Fleet shut down", "info"),
            )
        )
        self.fleet_ctrl.error.connect(
            lambda msg: show_toast(self, msg, "error")
        )
        # Fleet → Dashboard widget
        self.fleet_ctrl.fleet_status_ready.connect(
            self.dashboard_page.update_fleet_widget
        )
        # Fleet → Escalation notifications
        self.fleet_ctrl.escalation_triggered.connect(
            lambda r: show_toast(
                self,
                f"{r.get('count', 0)} ticket(s) escalated",
                "warning",
            )
        )
        self.fleet_ctrl.escalation_triggered.connect(
            lambda r: self.kanban_ctrl.refresh_board()
        )

        # ─── Trends signals ──────────────────────────────────
        self.trends_page.search_requested.connect(self.trends_ctrl.fetch_interest)
        self.trends_page.related_requested.connect(self.trends_ctrl.fetch_related_queries)
        self.trends_page.opportunities_requested.connect(self.trends_ctrl.find_opportunities)
        self.trends_page.refresh_alerts_requested.connect(self.trends_ctrl.refresh_alerts)

        self.trends_ctrl.interest_ready.connect(self.trends_page.update_interest)
        self.trends_ctrl.related_ready.connect(self.trends_page.update_related)
        self.trends_ctrl.opportunities_ready.connect(self.trends_page.update_opportunities)
        self.trends_ctrl.alerts_ready.connect(self.trends_page.update_alerts)
        self.trends_ctrl.error.connect(
            lambda msg: show_toast(self, msg, "error")
        )
        # Trends → Dashboard widget
        self.trends_ctrl.alerts_ready.connect(
            self.dashboard_page.update_trends_widget
        )

        # ─── Kanban signals ──────────────────────────────────
        self.kanban_page.create_ticket_requested.connect(
            lambda data: self.kanban_ctrl.create_ticket(**data)
        )
        self.kanban_page.move_ticket_requested.connect(self.kanban_ctrl.move_ticket)
        self.kanban_page.ticket_selected.connect(self.kanban_ctrl.get_ticket_detail)
        self.kanban_page.update_ticket_requested.connect(
            lambda tid, fields: self.kanban_ctrl.update_ticket(tid, **fields)
        )
        self.kanban_page.delete_ticket_requested.connect(self.kanban_ctrl.delete_ticket)
        self.kanban_page.add_comment_requested.connect(self.kanban_ctrl.add_comment)
        self.kanban_page.refresh_requested.connect(self.kanban_ctrl.refresh_board)
        self.kanban_page.filter_changed.connect(
            lambda f: self.kanban_ctrl.refresh_board(
                assignee_id=f.get("assignee_id"),
                priority=f.get("priority"),
                label=f.get("label"),
            )
        )

        self.kanban_ctrl.board_ready.connect(self.kanban_page.update_board)
        self.kanban_ctrl.ticket_detail_ready.connect(self.kanban_page.show_ticket_detail)
        self.kanban_ctrl.ticket_created.connect(
            lambda t: (
                self.kanban_ctrl.refresh_board(),
                show_toast(self, f"Ticket '{t.get('title')}' created", "success"),
            )
        )
        self.kanban_ctrl.ticket_moved.connect(
            lambda tid, s: self.kanban_ctrl.refresh_board()
        )
        self.kanban_ctrl.ticket_deleted.connect(
            lambda tid: (
                self.kanban_ctrl.refresh_board(),
                show_toast(self, "Ticket deleted", "info"),
            )
        )
        self.kanban_ctrl.error.connect(lambda msg: show_toast(self, msg, "error"))

        # Kanban detail dialog wiring
        self.kanban_page.detail_dialog.ticket_updated.connect(
            lambda tid, fields: self.kanban_ctrl.update_ticket(tid, **fields)
        )
        self.kanban_page.detail_dialog.comment_added.connect(self.kanban_ctrl.add_comment)
        self.kanban_page.detail_dialog.ticket_deleted.connect(self.kanban_ctrl.delete_ticket)
        self.kanban_page.detail_dialog.move_requested.connect(self.kanban_ctrl.move_ticket)

        # Kanban → Due-date alert toasts
        self.kanban_ctrl.due_date_alerts.connect(
            lambda r: (
                show_toast(
                    self,
                    f"{r.get('overdue_count', 0)} overdue, {r.get('upcoming_count', 0)} due soon",
                    "error" if r.get("overdue_count", 0) > 0 else "warning",
                )
                if r.get("overdue_count", 0) > 0 or r.get("upcoming_count", 0) > 0
                else None
            )
        )
        # Kanban stats → Dashboard ticket widget
        self.kanban_ctrl.stats_ready.connect(
            self.dashboard_page.update_ticket_widget
        )

        # ─── History signals ─────────────────────────────────
        self.history_page.refresh_requested.connect(
            self.command_history_ctrl.refresh_history
        )
        self.history_page.filter_changed.connect(
            lambda f: self.command_history_ctrl.refresh_history(
                source=f.get("source"),
                agent_id=f.get("agent_id"),
                command_type=f.get("command_type"),
                status=f.get("status"),
                search_text=f.get("search_text"),
            )
        )
        self.history_page.command_selected.connect(
            self.command_history_ctrl.get_command_tree
        )
        self.history_page.page_changed.connect(
            lambda p: self.command_history_ctrl.refresh_history(page=p)
        )
        self.history_page.prune_requested.connect(
            self.command_history_ctrl.prune_history
        )
        self.command_history_ctrl.history_ready.connect(
            self.history_page.update_history
        )
        self.command_history_ctrl.command_tree_ready.connect(
            self.history_page.show_command_tree
        )
        self.command_history_ctrl.stats_ready.connect(
            self.history_page.update_stats
        )
        self.command_history_ctrl.prune_complete.connect(
            lambda n: show_toast(self, f"Pruned {n} old history entries", "info")
        )
        self.command_history_ctrl.error.connect(
            lambda msg: show_toast(self, msg, "error")
        )

        # ─── Chat signals ────────────────────────────────────
        self.chat_panel.message_sent.connect(self._on_chat_message)
        self.chat_ctrl.response_ready.connect(self._on_chat_response)
        self.chat_ctrl.error.connect(
            lambda msg: self._on_chat_error(msg)
        )
        self.chat_panel.action_confirmed.connect(self._on_chat_action_confirmed)
        self.chat_panel.draft_approved.connect(self._on_chat_draft_approved)

        # ─── Research signals ────────────────────────────────
        self.research_page.refresh_requested.connect(
            self.research_ctrl.load_reports
        )
        self.research_ctrl.reports_ready.connect(
            self.research_page.update_reports
        )
        self.research_ctrl.report_detail_ready.connect(
            self.research_page.update_report_detail
        )
        self.research_ctrl.provider_status_ready.connect(
            self.research_page.update_provider_status
        )
        self.research_ctrl.research_completed.connect(
            lambda lid, data: show_toast(
                self, f"Research completed for lead #{lid}", "success"
            )
        )
        self.research_ctrl.research_failed.connect(
            lambda lid, err: show_toast(
                self, f"Research failed for lead #{lid}: {err}", "error"
            )
        )

        # ─── Voice call signals ──────────────────────────────
        self.calls_page.refresh_requested.connect(
            self.voice_ctrl.load_call_history
        )
        self.voice_ctrl.call_history_ready.connect(
            self.calls_page.update_call_history
        )
        self.voice_ctrl.active_calls_ready.connect(
            self.calls_page.update_active_calls
        )
        self.voice_ctrl.call_detail_ready.connect(
            self.calls_page.update_call_detail
        )
        self.voice_ctrl.provider_status_ready.connect(
            self.calls_page.update_provider_status
        )
        self.calls_page.end_call_requested.connect(
            self.voice_ctrl.end_call
        )
        self.calls_page.call_requested.connect(
            self.voice_ctrl.initiate_call
        )
        self.calls_page.view_transcript_requested.connect(
            self.voice_ctrl.load_call_detail
        )
        self.voice_ctrl.call_started.connect(
            lambda cid, data: show_toast(
                self, f"Call started: {data.get('lead_name', '')}", "success"
            )
        )
        self.voice_ctrl.call_ended.connect(
            lambda cid, data: show_toast(
                self, f"Call ended — {data.get('outcome', 'completed')}", "info"
            )
        )
        self.voice_ctrl.call_failed.connect(
            lambda cid, err: show_toast(self, f"Call failed: {err}", "error")
        )

    def _load_initial_data(self):
        """Load initial data for all pages."""
        from PySide6.QtCore import QTimer as _QTimer
        from database.schema import Settings
        from utils.logger import get_logger as _get_logger
        _logger = _get_logger("main_window")

        # Dashboard
        self.dashboard_ctrl.refresh_stats()
        self.kanban_ctrl.refresh_stats()

        # Forge
        self._refresh_forge()

        # Settings
        settings = self.settings_ctrl.get_settings()
        if settings:
            self.settings_page.load_settings(settings)

        # Dashboard auto-refresh timer (60s, only when dashboard is active)
        self._dashboard_timer = _QTimer(self)
        self._dashboard_timer.timeout.connect(self._refresh_dashboard_if_active)
        self._dashboard_timer.start(60_000)

        # Auto-boot fleet if AI provider keys are configured
        self._auto_boot_fleet()

        # Auto-reconnect previously saved gateway platforms (3s delay for UI)
        _QTimer.singleShot(3000, self._auto_connect_gateways)

    def _refresh_dashboard_if_active(self):
        """Refresh dashboard stats only when dashboard is the active page."""
        if self.page_stack.currentIndex() == 0:
            self.dashboard_ctrl.refresh_stats()

    def _auto_boot_fleet(self):
        """Auto-boot the fleet if at least one AI provider is configured."""
        from PySide6.QtCore import QTimer as _QTimer
        from database.schema import Settings
        from utils.logger import get_logger as _get_logger
        _logger = _get_logger("main_window")
        try:
            with self.db_manager.session_scope() as session:
                s = session.query(Settings).first()
                if not s:
                    return
                has_key = any([
                    s.anthropic_key_enc,
                    s.openai_key_enc,
                    s.gemini_key_enc,
                    s.openrouter_key_enc,
                    getattr(s, "anthropic_sub_token_enc", None),
                    getattr(s, "openai_sub_token_enc", None),
                ])
            if has_key:
                _QTimer.singleShot(2000, self.fleet_ctrl.boot_fleet)
        except Exception as e:
            _logger.warning(f"Auto-boot check failed: {e}")

    def _auto_connect_gateways(self):
        """Auto-reconnect previously connected Telegram/Discord platforms."""
        from utils.logger import get_logger as _get_logger
        _logger = _get_logger("main_window")
        for platform in ["telegram", "discord"]:
            try:
                config = self.gateway_engine.get_gateway_config(platform)
                if config.get("is_enabled") and config.get("has_token"):
                    self.gateway_ctrl.start_platform(platform, config["token"])
                    _logger.info(f"Auto-reconnected {platform}")
            except Exception as e:
                _logger.warning(f"Auto-connect {platform} failed: {e}")

    def _on_page_changed(self, index: int):
        """Handle sidebar navigation."""
        self.page_stack.setCurrentIndex(index)

        # Refresh data when navigating to certain pages
        if index == 0:  # Dashboard
            self.dashboard_ctrl.refresh_stats()
            self.kanban_ctrl.refresh_stats()
        elif index == 2:  # Forge
            self._refresh_forge()
        elif index == 3:  # Outreach
            self._refresh_outreach()
        elif index == 4:  # Fleet
            self.fleet_ctrl.refresh_fleet_status()
        elif index == 5:  # Kanban
            self.kanban_ctrl.refresh_board()
            agents = self.kanban_ctrl.get_agents_list()
            self.kanban_page.set_agents_list(agents)
        elif index == 6:  # History
            self.command_history_ctrl.refresh_history()
            self.command_history_ctrl.refresh_stats()
            agents = self.command_history_ctrl.get_agents_list()
            self.history_page.set_agents_list(agents)
        elif index == 7:  # Trends
            self.trends_ctrl.refresh_alerts()
        elif index == 9:  # Integrations
            users = self.gateway_engine.get_authorized_users()
            self.integrations_page.load_authorized_users(users)
        elif index == 10:  # Settings
            settings = self.settings_ctrl.get_settings()
            if settings:
                self.settings_page.load_settings(settings)
        elif index == 12:  # Research
            self.research_ctrl.load_reports()
            self.research_ctrl.check_providers()
        elif index == 13:  # Calls
            self.voice_ctrl.load_call_history()
            self.voice_ctrl.load_active_calls()
            self.voice_ctrl.check_providers()

    def _refresh_forge(self):
        """Reload skills into the forge page."""
        skills = self.forge_ctrl.get_all_skills()
        self.forge_page.load_skills(skills)
        self._refresh_rag_stats()

    def _refresh_outreach(self):
        """Reload campaigns and skills into the outreach page."""
        campaigns = self.outreach_ctrl.get_campaigns()
        self.outreach_page.load_campaigns(campaigns)
        skills = self.forge_ctrl.get_all_skills()
        self.outreach_page.load_skills(skills)

    # ─── Forge handlers ───────────────────────────────────────

    def _on_forge_save(self, skill_id: int, skill_data: object):
        if skill_id > 0:
            self.forge_ctrl.update_skill(skill_id, skill_data)
        else:
            self.forge_ctrl.create_skill(skill_data)

    def _on_forge_delete(self, skill_id: int):
        self.forge_ctrl.delete_skill(skill_id)
        self.forge_page.clear_editor()

    def _on_forge_import(self, file_path: str):
        self.forge_ctrl.import_skill(file_path)

    def _on_forge_export(self, skill_id: int, file_path: str):
        self.forge_ctrl.export_skill(skill_id, file_path)

    def _on_rag_import(self, file_path: str):
        result = self.rag_engine.import_from_csv(file_path)
        if result.get("success"):
            show_toast(self, f"Imported {result['imported']} emails to RAG memory.", "success")
            self._refresh_rag_stats()
        else:
            show_toast(self, f"Import failed: {result.get('error')}", "error")

    def _on_rag_clear(self):
        self.rag_engine.clear_all()
        show_toast(self, "RAG memory cleared.", "info")
        self._refresh_rag_stats()

    def _refresh_rag_stats(self):
        stats = self.rag_engine.get_stats()
        self.forge_page.update_rag_stats(stats.get("total", 0), stats.get("replied", 0))

    # ─── CRM handler ──────────────────────────────────────────

    def _on_crm_sync_campaign(self, campaign_id: int):
        """Sync a campaign's leads to the configured CRM."""
        from utils.thread_worker import ThreadWorker

        def _work():
            return self.crm_engine.sync_campaign_to_crm(campaign_id)

        def _done(result):
            if result.get("success"):
                synced = result.get("synced", 0)
                failed = result.get("failed", 0)
                show_toast(self, f"CRM sync: {synced} synced, {failed} failed.", "success")
            else:
                show_toast(self, f"CRM sync error: {result.get('error')}", "error")

        worker = ThreadWorker(_work)
        worker.finished.connect(_done)
        worker.error.connect(lambda e: show_toast(self, f"CRM sync failed: {e}", "error"))
        self._crm_worker = worker
        worker.start()

    # ─── Batch import handler ─────────────────────────────────

    def _on_lead_closed_won(self, lead_id, from_state, to_state):
        """Update strategy goal progress when a lead converts."""
        try:
            from database.schema import GoalMilestone, StrategicGoal
            goals = self.strategy_engine.get_all_goals(status="active")
            for goal in goals.get("data", []):
                if goal.get("target_metric") == "conversions":
                    goal_id = goal["id"]
                    # Increment the active conversion milestone
                    with self.db_manager.session_scope() as session:
                        milestone = (
                            session.query(GoalMilestone)
                            .filter_by(goal_id=goal_id, status="active")
                            .first()
                        )
                        if milestone:
                            milestone.actual_value = (milestone.actual_value or 0) + 1
                            if milestone.actual_value >= milestone.target_value:
                                milestone.status = "completed"
                                milestone.completed_at = datetime.utcnow()
                                # Activate next pending milestone
                                next_ms = (
                                    session.query(GoalMilestone)
                                    .filter_by(goal_id=goal_id, status="pending")
                                    .order_by(GoalMilestone.phase)
                                    .first()
                                )
                                if next_ms:
                                    next_ms.status = "active"
                    self.strategy_engine.update_progress(goal_id)
        except Exception as e:
            from utils.logger import get_logger
            get_logger("main_window").debug(f"Strategy progress update failed: {e}")

    def _on_batch_import(self, csv_path: str):
        """Import leads from a CSV file via BatchImporter."""
        from utils.thread_worker import ThreadWorker

        def _work():
            return self.batch_importer.create_campaigns_from_csv(csv_path)

        def _done(result):
            if isinstance(result, dict) and result.get("success"):
                count = result.get("leads_imported", 0)
                show_toast(self, f"Imported {count} leads from CSV.", "success")
                self.hunter_page.import_path_label.setText("Import complete")
                self.hunter_page.import_btn.setEnabled(True)
            elif isinstance(result, dict):
                show_toast(self, f"Import error: {result.get('error')}", "error")
                self.hunter_page.import_path_label.setText("Import failed")
                self.hunter_page.import_btn.setEnabled(True)

        worker = ThreadWorker(_work)
        worker.finished.connect(_done)
        worker.error.connect(lambda e: show_toast(self, f"Import failed: {e}", "error"))
        self._batch_worker = worker
        worker.start()

    # ─── Outreach campaign changed handler ────────────────────

    def _on_outreach_campaign_changed(self, index: int):
        """Load qualified leads when the outreach campaign selector changes."""
        campaign_id = self.outreach_page.campaign_combo.currentData()
        if not campaign_id:
            return
        leads = self.outreach_ctrl.get_outreach_leads(campaign_id)
        self.outreach_page.load_leads(leads)

    # ─── Triage handler ───────────────────────────────────────

    def _on_run_triage(self):
        """Run the morning inbox triage."""
        from utils.thread_worker import ThreadWorker

        def _work():
            return self.triage_engine.run_morning_triage()

        def _done(result):
            self.dashboard_page.show_triage_results(result)
            total = result.get("total_emails", 0)
            replies = result.get("replies", 0)
            show_toast(self, f"Triage complete: {total} emails, {replies} replies.", "info")

        worker = ThreadWorker(_work)
        worker.finished.connect(_done)
        worker.error.connect(lambda e: show_toast(self, f"Triage failed: {e}", "error"))
        self._triage_worker = worker
        worker.start()

    # ─── OpenAI OAuth handler ────────────────────────────────

    def _on_openai_oauth(self):
        """Run OpenAI OAuth PKCE flow in a background thread."""
        from utils.thread_worker import ThreadWorker
        from core.subscription_auth import start_openai_oauth

        def _work():
            return start_openai_oauth()

        def _done(result):
            if result.get("success"):
                self.settings_ctrl.save_openai_sub_tokens(
                    result["access_token"],
                    result.get("refresh_token", ""),
                )
                self.settings_page.on_openai_oauth_complete(True)
            else:
                self.settings_page.on_openai_oauth_complete(
                    False, result.get("error", "Unknown error")
                )

        worker = ThreadWorker(_work)
        worker.finished.connect(_done)
        worker.error.connect(
            lambda e: self.settings_page.on_openai_oauth_complete(False, str(e))
        )
        self._oauth_worker = worker
        worker.start()

    # ─── Pipeline handler ──────────────────────────────────

    def _on_pipeline_complete(self, result: dict):
        """Show toast with pipeline execution results."""
        completed = result.get("completed", 0)
        total = result.get("total", 0)
        cost = result.get("total_cost", 0.0)
        show_toast(
            self,
            f"Pipeline done: {completed}/{total} steps, ${cost:.4f} total cost",
            "success" if completed == total else "warning",
        )

    # ─── Rate limit handler ─────────────────────────────────

    def _on_rate_limit_detected(self, tier: str, error_msg: str):
        """Notify user of rate limiting and suggest switching auth mode."""
        show_toast(
            self,
            f"Rate limit hit on {tier}. Consider switching auth mode in Settings.",
            "warning",
        )

    # ─── Theme handler ────────────────────────────────────────

    def _on_theme_change(self, theme: str):
        self.settings_ctrl.set_theme(theme)
        self._apply_theme(theme)

    def _apply_theme(self, theme: str):
        """Load and apply a QSS theme file."""
        from utils.paths import get_asset_path
        self._current_theme = theme

        # Failsafe: Set dark background immediately to prevent white flash
        if "dark" in theme:
            self.setStyleSheet("QMainWindow { background-color: #09090F; color: #FFFFFF; }")

        try:
            theme_file = get_asset_path("themes", f"neon_{theme}.qss")
            if theme_file.exists():
                with open(theme_file, "r", encoding="utf-8") as f:
                    new_style = f.read()
                    self.setStyleSheet(new_style)
            else:
                print(f"Theme file not found: {theme_file}")
        except Exception as e:
            print(f"Error loading theme: {e}")

        self._refresh_all_icons(theme)

    def _refresh_all_icons(self, theme: str):
        """Rebuild all qtawesome icons for the new theme."""
        if hasattr(self, 'sidebar'):
            self.sidebar.update_icons(theme)
        if hasattr(self, 'chat_toggle_btn'):
            self.chat_toggle_btn.setIcon(get_icon("chat_toggle", theme))

    # ─── Chat handlers ────────────────────────────────────────

    def _toggle_chat(self):
        """Toggle the chat panel visibility."""
        self.chat_panel.toggle()
        # Force the wrapper layout to recalculate space allocation
        wrapper = self.chat_panel.parentWidget()
        if wrapper and wrapper.layout():
            wrapper.layout().invalidate()
            wrapper.layout().activate()

    def _close_chat_if_open(self):
        """Close chat panel if it's open (Escape key)."""
        if self.chat_panel.is_panel_visible:
            self.chat_panel.toggle()

    def _on_chat_message(self, message: str):
        """Handle a chat message from the user."""
        self.chat_panel.show_typing(True)
        self.chat_ctrl.process_message(message)

    def _on_chat_response(self, response: dict):
        """Handle orchestrator response."""
        self.chat_panel.handle_response(response)

    def _on_chat_error(self, error_msg: str):
        """Handle chat error."""
        self.chat_panel.show_typing(False)
        self.chat_panel.add_message(f"Error: {error_msg}", is_user=False)

    def _on_chat_action_confirmed(self, intent_dict: dict):
        """Handle confirmed action from chat panel."""
        self.chat_panel.show_typing(True)
        self.chat_ctrl.execute_confirmed_action(intent_dict)

    def _on_chat_draft_approved(self, subject: str, body: str, lead_email: str):
        """Handle draft approved from inline editor in chat."""
        if not lead_email or not subject or not body:
            show_toast(self, "Missing email, subject, or body.", "warning")
            return
        # Find the lead by email and send
        from database.schema import Lead
        with self.db_manager.session_scope() as session:
            lead = session.query(Lead).filter(Lead.email.ilike(lead_email)).first()
            if lead:
                self.outreach_ctrl.send_email(lead.id, lead_email, subject, body)
                self.chat_panel.add_message(f"Sending email to {lead_email}...", is_user=False)
            else:
                show_toast(self, f"Lead not found for {lead_email}", "warning")

    # ─── Navigation + Command Palette handlers ─────────────────

    def _on_navigation(self, index: int, context: dict):
        """Handle cross-page navigation from NavigationService."""
        self.page_stack.setCurrentIndex(index)
        self.sidebar.set_page(index)
        # Refresh page data
        self._on_page_changed(index)
        # Pass context to the target page
        page = self.page_stack.widget(index)
        if hasattr(page, "receive_context") and context:
            page.receive_context(context)

    def _on_palette_command(self, cmd: dict):
        """Handle command palette selection."""
        cmd_type = cmd.get("type", "navigate")
        if cmd_type == "navigate":
            index = cmd.get("page_index", cmd.get("index", 0))
            self.navigation_service.navigate_by_index(index)
        elif cmd_type == "action":
            action_name = cmd.get("action", "")
            self.navigation_service.execute_action(action_name)

    def _toggle_command_palette(self):
        """Toggle the command palette visibility (Ctrl+K)."""
        if self.command_palette.isVisible():
            self.command_palette.hide()
        else:
            self.command_palette.show_palette()

    # ─── HubSpot / LinkedIn handlers ─────────────────────────

    def _on_hubspot_search(self, niche: str, city: str, company: str, limit: int):
        """Handle HubSpot search request from Hunter page."""
        self.hunter_ctrl.search_hubspot(niche, city, company, limit=limit)

    def _on_linkedin_import(self, csv_path: str):
        """Handle LinkedIn CSV import request from Hunter page."""
        self.hunter_ctrl.import_linkedin_csv(csv_path)

    # ─── Export handler ───────────────────────────────────────

    def _on_export_report(self, format_type: str):
        """Handle dashboard export request."""
        if format_type == "pdf":
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export PDF Report", "aura_report.pdf", "PDF Files (*.pdf)"
            )
            if file_path:
                result = self.report_engine.export_all_campaigns_pdf(file_path)
                if result.get("success"):
                    show_toast(self, "PDF report exported!", "success")
                else:
                    show_toast(self, f"Export failed: {result.get('error')}", "error")
        elif format_type == "csv":
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export CSV Report", "aura_report.csv", "CSV Files (*.csv)"
            )
            if file_path:
                result = self.report_engine.export_all_campaigns_csv(file_path)
                if result.get("success"):
                    show_toast(self, "CSV report exported!", "success")
                else:
                    show_toast(self, f"Export failed: {result.get('error')}", "error")

    # ─── Graceful Shutdown ─────────────────────────────────────

    def closeEvent(self, event):
        """Stop all background resources before closing."""
        logger.info("Shutting down Aura…")

        # Stop dashboard refresh timer
        if hasattr(self, "_dashboard_timer"):
            self._dashboard_timer.stop()

        # Stop fleet (agents, escalation timer, caller timer, sequence/reply timers)
        if hasattr(self, "fleet_ctrl"):
            try:
                self.fleet_ctrl.shutdown_fleet()
            except Exception as e:
                logger.warning(f"Fleet shutdown error: {e}")

        # Close IMAP reply detector connection
        if hasattr(self, "reply_detector"):
            try:
                self.reply_detector.close_connection()
            except Exception as e:
                logger.warning(f"Reply detector close error: {e}")

        # Stop gateway adapters (Telegram, Discord)
        if hasattr(self, "gateway_ctrl"):
            try:
                self.gateway_ctrl.stop_all()
            except Exception as e:
                logger.warning(f"Gateway stop error: {e}")

        # Close batch browser if open
        if hasattr(self, "enrichment_engine"):
            try:
                self.enrichment_engine.end_batch()
            except Exception as e:
                logger.warning(f"Batch browser close error: {e}")

        # Stop voice engine WebSocket server
        if hasattr(self, "voice_engine"):
            try:
                self.voice_engine.shutdown()
            except Exception as e:
                logger.warning(f"Voice engine shutdown error: {e}")

        logger.info("Shutdown complete.")
        super().closeEvent(event)
