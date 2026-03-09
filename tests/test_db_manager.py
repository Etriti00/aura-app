"""
Tests for database/db_manager.py — session management, seeding, hierarchy, migrations.
"""

import pytest
from database.schema import Agent, Settings, Skill, AgentTicket


class TestSessionScope:
    def test_session_commits_on_success(self, db):
        with db.session_scope() as s:
            s.add(Settings(id=1))
        with db.session_scope() as s:
            assert s.query(Settings).count() == 1

    def test_session_rollbacks_on_exception(self, db):
        with db.session_scope() as s:
            s.add(Settings(id=1))
        try:
            with db.session_scope() as s:
                s.add(Settings(id=2))
                raise ValueError("Simulated error")
        except ValueError:
            pass
        with db.session_scope() as s:
            # Only the first settings should exist
            assert s.query(Settings).count() == 1


class TestInitDb:
    def test_tables_created(self, db):
        """All expected tables should exist after init_db."""
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        expected = [
            "campaigns", "leads", "skills", "settings",
            "follow_up_sequences", "follow_up_steps", "follow_up_sends",
            "suppression_list", "enrichment_data", "api_usage_log",
            "rag_memory", "crm_sync_log", "channel_drafts",
            "budget_config", "gateway_config", "authorized_users",
            "agents", "agent_tasks", "agent_messages", "agent_memory_log",
            "agent_tickets", "ticket_comments", "ticket_dependencies",
            "trends_data", "trends_alerts",
        ]
        for table_name in expected:
            assert table_name in tables, f"Missing table: {table_name}"


class TestAgentSeeding:
    def test_all_18_agents_present(self, db_with_agents):
        with db_with_agents.session_scope() as s:
            count = s.query(Agent).count()
            assert count == 20, f"Expected 20 agents, got {count}"

    def test_commander_is_rank_1(self, db_with_agents):
        with db_with_agents.session_scope() as s:
            commander = s.query(Agent).filter_by(name="Commander").first()
            assert commander is not None
            assert commander.rank == 1
            assert commander.reports_to_id is None

    def test_specialist_leads_are_rank_2(self, db_with_agents):
        rank_2_names = ["Scheduler", "Triage Lead", "Analyst", "Forger", "Observer"]
        with db_with_agents.session_scope() as s:
            for name in rank_2_names:
                agent = s.query(Agent).filter_by(name=name).first()
                assert agent is not None, f"Agent '{name}' not found"
                assert agent.rank == 2, f"{name} should be rank 2, got {agent.rank}"

    def test_workers_are_rank_3(self, db_with_agents):
        rank_3_names = [
            "Scout", "Enricher", "Qualifier", "Closer", "Postman",
            "Tracker", "Archivist", "Syncer", "Suppressor",
            "Trend Spotter", "Reporter", "Canary",
        ]
        with db_with_agents.session_scope() as s:
            for name in rank_3_names:
                agent = s.query(Agent).filter_by(name=name).first()
                assert agent is not None, f"Agent '{name}' not found"
                assert agent.rank == 3, f"{name} should be rank 3, got {agent.rank}"

    def test_hierarchy_reports_to(self, db_with_agents):
        """Validate reports_to chains."""
        expected = {
            "Scout": "Triage Lead",
            "Enricher": "Triage Lead",
            "Qualifier": "Triage Lead",
            "Tracker": "Triage Lead",
            "Suppressor": "Triage Lead",
            "Closer": "Commander",
            "Postman": "Commander",
            "Archivist": "Commander",
            "Syncer": "Commander",
            "Trend Spotter": "Analyst",
            "Reporter": "Analyst",
            "Canary": "Observer",
            "Scheduler": "Commander",
            "Triage Lead": "Commander",
            "Analyst": "Commander",
            "Forger": "Commander",
            "Observer": "Commander",
        }
        with db_with_agents.session_scope() as s:
            agents = {a.name: a for a in s.query(Agent).all()}
            for name, supervisor_name in expected.items():
                agent = agents[name]
                supervisor = agents[supervisor_name]
                assert agent.reports_to_id == supervisor.id, (
                    f"{name} should report to {supervisor_name} (id={supervisor.id}), "
                    f"but reports_to_id={agent.reports_to_id}"
                )

    def test_commander_has_no_supervisor(self, db_with_agents):
        with db_with_agents.session_scope() as s:
            commander = s.query(Agent).filter_by(name="Commander").first()
            assert commander.reports_to_id is None

    def test_agent_roles_correct(self, db_with_agents):
        with db_with_agents.session_scope() as s:
            commander = s.query(Agent).filter_by(name="Commander").first()
            assert commander.role == "orchestrator"
            observer = s.query(Agent).filter_by(name="Observer").first()
            assert observer.role == "observer"
            canary = s.query(Agent).filter_by(name="Canary").first()
            assert canary.role == "canary"
            scout = s.query(Agent).filter_by(name="Scout").first()
            assert scout.role == "worker"

    def test_agent_emojis_set(self, db_with_agents):
        with db_with_agents.session_scope() as s:
            agents = s.query(Agent).all()
            for a in agents:
                assert a.identity_emoji, f"Agent '{a.name}' has no emoji"
