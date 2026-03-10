"""
Shared fixtures for Aura test suite.
Uses an in-memory SQLite database and fresh engine instances for each test.
"""

import sys
import os
import pytest
from pathlib import Path
from datetime import datetime, timedelta

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.db_manager import DatabaseManager
from database.schema import (
    Base, Agent, AgentTask, AgentMessage, AgentMemoryLog,
    AgentTicket, TicketComment, TicketDependency,
    Campaign, Lead, Skill, Settings, CommandLog,
    AgentReflection, PerformanceMetric, AgentLearnedRule,
    LeadStateTransition,
    KnowledgeNode, KnowledgeEdge,
    ConversationThread,
    StrategicGoal, GoalMilestone,
    PendingApproval,
    CaseNote, CaseMemory, CachedSummary, SubagentTask,
    ResearchReport, VoiceCall,
    Service, Invoice, InvoiceLineItem, FinanceNote, DiscordServerConfig,
    KnowledgeBase,
)


class InMemoryDatabaseManager(DatabaseManager):
    """DatabaseManager using in-memory SQLite for tests."""

    def __init__(self):
        import threading
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker

        self.db_path = Path(":memory:")
        self._write_lock = threading.RLock()
        self.engine = create_engine(
            "sqlite:///:memory:",
            echo=False,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

        self.SessionFactory = sessionmaker(bind=self.engine)

    def init_db(self):
        Base.metadata.create_all(self.engine)

    def migrate_schema(self):
        """No-op for in-memory — tables are created fresh with all columns."""
        pass


@pytest.fixture
def db():
    """Fresh in-memory database with all tables created."""
    db_manager = InMemoryDatabaseManager()
    db_manager.init_db()
    return db_manager


@pytest.fixture
def db_with_agents(db):
    """Database seeded with default agents and hierarchy."""
    # Seed agents manually (not using seed_default_agents which relies on file-based DB)
    with db.session_scope() as session:
        agents_data = [
            ("Commander", "orchestrator", "🎖️", "haiku", 1, None),
            ("Scheduler", "worker", "📅", "local", 2, "Commander"),
            ("Triage Lead", "worker", "🎯", "haiku", 2, "Commander"),
            ("Analyst", "worker", "📈", "sonnet", 2, "Commander"),
            ("Forger", "worker", "🔨", "haiku", 2, "Commander"),
            ("Observer", "observer", "👁️", "local", 2, "Commander"),
            ("Scout", "worker", "🔍", "local", 3, "Triage Lead"),
            ("Enricher", "worker", "💎", "haiku", 3, "Triage Lead"),
            ("Qualifier", "worker", "✅", "haiku", 3, "Triage Lead"),
            ("Closer", "worker", "🤝", "sonnet", 3, "Commander"),
            ("Postman", "worker", "📬", "local", 3, "Commander"),
            ("Tracker", "worker", "📡", "local", 3, "Triage Lead"),
            ("Archivist", "worker", "🗄️", "ollama", 3, "Commander"),
            ("Syncer", "worker", "🔄", "local", 3, "Commander"),
            ("Suppressor", "worker", "🛡️", "local", 3, "Triage Lead"),
            ("Trend Spotter", "worker", "🌊", "haiku", 3, "Analyst"),
            ("Reporter", "worker", "📄", "local", 3, "Analyst"),
            ("Canary", "canary", "🐤", "haiku", 3, "Observer"),
            ("Caller", "worker", "📞", "sonnet", 3, "Commander"),
            ("Accountant", "worker", "💰", "haiku", 3, "Commander"),
        ]

        # First pass: create agents without reports_to
        agent_objects = {}
        for name, role, emoji, tier, rank, _ in agents_data:
            agent = Agent(
                name=name, role=role, identity_emoji=emoji,
                model_tier=tier, rank=rank, status="idle",
            )
            session.add(agent)
            agent_objects[name] = agent
        session.flush()

        # Second pass: set hierarchy
        for name, _, _, _, _, reports_to in agents_data:
            if reports_to and reports_to in agent_objects:
                agent_objects[name].reports_to_id = agent_objects[reports_to].id

    return db


@pytest.fixture
def db_with_skills(db):
    """Database with sample skills."""
    with db.session_scope() as session:
        session.add(Skill(
            name="The Closer", system_prompt="You write emails that convert.",
            tone="confident", preferred_tier="sonnet", temperature=0.7,
            max_tokens=512, is_default=True, is_builtin=True,
        ))
        session.add(Skill(
            name="Lead Scoring Expert", system_prompt="You score leads.",
            tone="analytical", preferred_tier="haiku", temperature=0.3,
            max_tokens=600, is_default=False, is_builtin=True,
        ))
    return db


@pytest.fixture
def db_full(db_with_agents):
    """Database with agents + skills + settings."""
    db = db_with_agents
    with db.session_scope() as session:
        session.add(Settings(id=1))
        session.add(Skill(
            name="The Closer", system_prompt="You write emails that convert.",
            tone="confident", preferred_tier="sonnet", temperature=0.7,
            max_tokens=512, is_default=True, is_builtin=True,
        ))
    return db


# ─── Engine Fixtures ───────────────────────────────────────

@pytest.fixture
def ticket_engine(db_with_agents):
    from core.ticket_engine import TicketEngine
    return TicketEngine(db_with_agents), db_with_agents


@pytest.fixture
def agent_engine(db_full):
    from core.agent_engine import AgentEngine
    from core.key_vault import KeyVault
    kv = KeyVault()
    return AgentEngine(db_full, kv), db_full


@pytest.fixture
def fleet_orchestrator(db_full):
    from core.agent_engine import AgentEngine
    from core.fleet_orchestrator import FleetOrchestrator
    from core.key_vault import KeyVault
    kv = KeyVault()
    ae = AgentEngine(db_full, kv)
    return FleetOrchestrator(db_full, ae), db_full


@pytest.fixture
def observer_engine(db_full):
    from core.agent_engine import AgentEngine
    from core.observer_engine import ObserverEngine
    from core.key_vault import KeyVault
    kv = KeyVault()
    ae = AgentEngine(db_full, kv)
    return ObserverEngine(db_full, ae), db_full


@pytest.fixture
def escalation_engine(db_with_agents):
    from core.ticket_engine import TicketEngine
    from core.escalation_engine import EscalationEngine
    from core.agent_engine import AgentEngine
    from core.key_vault import KeyVault
    kv = KeyVault()
    te = TicketEngine(db_with_agents)
    ae = AgentEngine(db_with_agents, kv)
    ee = EscalationEngine(db_with_agents, te, ae)
    return ee, te, ae, db_with_agents


@pytest.fixture
def ticket_scheduler(db_with_agents):
    from core.ticket_engine import TicketEngine
    from core.ticket_scheduler import TicketScheduler
    from core.agent_engine import AgentEngine
    from core.key_vault import KeyVault
    kv = KeyVault()
    te = TicketEngine(db_with_agents)
    ae = AgentEngine(db_with_agents, kv)
    ts = TicketScheduler(db_with_agents, te, ae)
    return ts, te, ae, db_with_agents


@pytest.fixture
def command_history(db_with_agents):
    from core.command_history import CommandHistoryEngine
    return CommandHistoryEngine(db_with_agents), db_with_agents


@pytest.fixture
def reflection_engine(db_full):
    from core.reflection_engine import ReflectionEngine
    return ReflectionEngine(db_full), db_full


@pytest.fixture
def lifecycle_engine(db_full):
    from core.lead_lifecycle_engine import LeadLifecycleEngine
    return LeadLifecycleEngine(db_full), db_full


@pytest.fixture
def knowledge_graph(db_full):
    from core.knowledge_graph_engine import KnowledgeGraphEngine
    return KnowledgeGraphEngine(db_full), db_full


@pytest.fixture
def conversation_engine(db_full):
    from core.conversation_engine import ConversationEngine
    return ConversationEngine(db_full), db_full


@pytest.fixture
def self_improvement_engine(db_full):
    from core.self_improvement_engine import SelfImprovementEngine
    from core.reflection_engine import ReflectionEngine
    reflection = ReflectionEngine(db_full)
    return SelfImprovementEngine(db_full, reflection_engine=reflection), db_full


@pytest.fixture
def strategy_engine(db_full):
    from core.strategy_engine import StrategyEngine
    return StrategyEngine(db_full), db_full


@pytest.fixture
def autonomy_controller(db_full):
    from controllers.autonomy_controller import AutonomyController
    return AutonomyController(db_full), db_full


@pytest.fixture
def token_manager(db):
    from core.token_manager import TokenManager
    return TokenManager(db), db


@pytest.fixture
def case_engine(db):
    from core.case_engine import CaseEngine
    return CaseEngine(db), db


@pytest.fixture
def subagent_engine(db):
    from core.subagent_engine import SubagentEngine
    return SubagentEngine(db), db


@pytest.fixture
def db_with_lead(db):
    """Database with a Campaign and Lead seeded."""
    with db.session_scope() as session:
        camp = Campaign(name="Test Campaign", search_query="test")
        session.add(camp)
        session.flush()
        lead = Lead(
            campaign_id=camp.id, business_name="Test Business",
            city="Austin", category="plumbing", email="test@test.com",
            phone="555-1234", website_url="https://test.com",
            status="new", lifecycle_state="new",
        )
        session.add(lead)
        session.flush()
        lead_id = lead.id
        camp_id = camp.id
    return db, lead_id, camp_id


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QApplication instance exists for signal and widget tests."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ─── Helpers ───────────────────────────────────────────────

def get_agent_id_by_name(db, name):
    """Get an agent's ID by name."""
    with db.session_scope() as session:
        agent = session.query(Agent).filter_by(name=name).first()
        return agent.id if agent else None
