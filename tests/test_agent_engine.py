"""
Tests for core/agent_engine.py — boot, shutdown, run_task, delegate, send_message,
heartbeat, memory, status, field updates, request_ticket_creation.
"""

import pytest
from datetime import datetime
from database.schema import Agent, AgentTask, AgentMessage, AgentMemoryLog
from tests.conftest import get_agent_id_by_name


class TestBootAgent:
    def test_boot_sets_idle(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        result = ae.boot_agent(agent_id)
        assert result["success"] is True
        assert result["name"] == "Scout"

        with db.session_scope() as s:
            agent = s.query(Agent).filter_by(id=agent_id).first()
            assert agent.status == "idle"
            assert agent.heartbeat_last is not None
            assert agent.current_task is None

    def test_boot_creates_memory_log(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        ae.boot_agent(agent_id)
        with db.session_scope() as s:
            logs = s.query(AgentMemoryLog).filter_by(agent_id=agent_id).all()
            assert len(logs) >= 1
            assert "booted" in logs[0].content.lower()

    def test_boot_nonexistent_agent(self, agent_engine):
        ae, db = agent_engine
        result = ae.boot_agent(99999)
        assert result["success"] is False


class TestShutdownAgent:
    def test_shutdown_sets_idle(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        ae.boot_agent(agent_id)
        result = ae.shutdown_agent(agent_id)
        assert result["success"] is True

        with db.session_scope() as s:
            agent = s.query(Agent).filter_by(id=agent_id).first()
            assert agent.status == "idle"
            assert agent.current_task is None

    def test_shutdown_nonexistent(self, agent_engine):
        ae, db = agent_engine
        result = ae.shutdown_agent(99999)
        assert result["success"] is False


class TestRunTask:
    def test_run_task_completes(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        ae.boot_agent(agent_id)
        result = ae.run_task(agent_id, "scrape_leads", {"query": "test"})
        assert result["success"] is True
        assert result["agent_name"] == "Scout"
        assert result["task_id"] is not None

        # Agent should be idle after task
        with db.session_scope() as s:
            agent = s.query(Agent).filter_by(id=agent_id).first()
            assert agent.status == "idle"
            assert agent.tasks_completed >= 1

    def test_run_task_creates_task_record(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        ae.boot_agent(agent_id)
        result = ae.run_task(agent_id, "scrape_leads", {"query": "test"})
        with db.session_scope() as s:
            task = s.query(AgentTask).filter_by(id=result["task_id"]).first()
            assert task is not None
            assert task.status == "completed"
            assert task.task_type == "scrape_leads"

    def test_run_task_nonexistent_agent(self, agent_engine):
        ae, db = agent_engine
        result = ae.run_task(99999, "test", {})
        assert result["success"] is False

    def test_run_task_error_agent(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        with db.session_scope() as s:
            agent = s.query(Agent).filter_by(id=agent_id).first()
            agent.status = "error"
        result = ae.run_task(agent_id, "test", {})
        assert result["success"] is False

    def test_run_task_updates_daily_memory(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        ae.boot_agent(agent_id)
        ae.run_task(agent_id, "scrape_leads", {"query": "test"})
        with db.session_scope() as s:
            agent = s.query(Agent).filter_by(id=agent_id).first()
            assert agent.memory_today is not None
            assert "scrape_leads" in agent.memory_today


class TestDelegateTask:
    def test_delegate_creates_message(self, agent_engine):
        ae, db = agent_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        enricher_id = get_agent_id_by_name(db, "Enricher")
        ae.boot_agent(scout_id)
        ae.boot_agent(enricher_id)
        result = ae.delegate_task(scout_id, enricher_id, "enrich_lead", {"lead_id": 1})
        assert result["success"] is True
        assert result["message_id"] is not None

        with db.session_scope() as s:
            msg = s.query(AgentMessage).filter_by(id=result["message_id"]).first()
            assert msg is not None
            assert msg.message_type == "task_delegation"


class TestSendMessage:
    def test_send_message(self, agent_engine):
        ae, db = agent_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        commander_id = get_agent_id_by_name(db, "Commander")
        result = ae.send_message(scout_id, commander_id, "info", {"text": "hello"})
        assert result["success"] is True
        assert result["message_id"] is not None

    def test_get_messages(self, agent_engine):
        ae, db = agent_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        commander_id = get_agent_id_by_name(db, "Commander")
        ae.send_message(scout_id, commander_id, "info", {"text": "msg1"})
        ae.send_message(scout_id, commander_id, "alert", {"text": "msg2"})
        result = ae.get_messages(commander_id, unread_only=True)
        assert result["success"] is True
        assert len(result["data"]) == 2

    def test_get_messages_unread_only(self, agent_engine):
        ae, db = agent_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        commander_id = get_agent_id_by_name(db, "Commander")
        ae.send_message(scout_id, commander_id, "info", {"text": "msg"})

        # Acknowledge the message
        with db.session_scope() as s:
            msg = s.query(AgentMessage).filter_by(to_agent_id=commander_id).first()
            msg.acknowledged = True

        result = ae.get_messages(commander_id, unread_only=True)
        assert len(result["data"]) == 0


class TestHeartbeat:
    def test_heartbeat(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        ae.boot_agent(agent_id)
        result = ae.run_heartbeat(agent_id)
        assert result["success"] is True
        assert result["status"] == "healthy"
        assert result["pending_tasks"] == 0
        assert result["unread_messages"] == 0

    def test_heartbeat_updates_timestamp(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        ae.boot_agent(agent_id)
        result = ae.run_heartbeat(agent_id)
        with db.session_scope() as s:
            agent = s.query(Agent).filter_by(id=agent_id).first()
            assert agent.heartbeat_last is not None

    def test_heartbeat_creates_log(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        ae.boot_agent(agent_id)
        ae.run_heartbeat(agent_id)
        with db.session_scope() as s:
            logs = s.query(AgentMemoryLog).filter_by(
                agent_id=agent_id, memory_type="heartbeat_report"
            ).all()
            assert len(logs) >= 1

    def test_heartbeat_nonexistent(self, agent_engine):
        ae, db = agent_engine
        result = ae.run_heartbeat(99999)
        assert result["success"] is False


class TestAgentMemory:
    def test_update_daily_notes(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        result = ae.update_agent_memory(agent_id, "Learned something new")
        assert result["success"] is True

        with db.session_scope() as s:
            agent = s.query(Agent).filter_by(id=agent_id).first()
            assert "Learned something new" in agent.memory_today

    def test_update_long_term_memory(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        result = ae.update_agent_memory(agent_id, "Important fact", "long_term")
        assert result["success"] is True

        with db.session_scope() as s:
            agent = s.query(Agent).filter_by(id=agent_id).first()
            assert "Important fact" in agent.long_term_memory

    def test_reset_daily_memory(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        ae.update_agent_memory(agent_id, "Will be reset")
        result = ae.reset_daily_memory(agent_id)
        assert result["success"] is True

        with db.session_scope() as s:
            agent = s.query(Agent).filter_by(id=agent_id).first()
            assert agent.memory_today == ""

    def test_reset_creates_archive_log(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        ae.update_agent_memory(agent_id, "Archive this")
        ae.reset_daily_memory(agent_id)
        with db.session_scope() as s:
            logs = s.query(AgentMemoryLog).filter_by(
                agent_id=agent_id, memory_type="daily_notes"
            ).all()
            assert len(logs) >= 1


class TestAgentStatus:
    def test_get_agent_status(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        result = ae.get_agent_status(agent_id)
        assert result["success"] is True
        data = result["data"]
        assert data["name"] == "Scout"
        assert data["role"] == "worker"
        assert "recent_tasks" in data

    def test_get_all_agents(self, agent_engine):
        ae, db = agent_engine
        result = ae.get_all_agents()
        assert result["success"] is True
        assert len(result["data"]) == 20


class TestUpdateAgentField:
    def test_update_allowed_field(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        result = ae.update_agent_field(agent_id, "soul", "New soul description")
        assert result["success"] is True

        with db.session_scope() as s:
            agent = s.query(Agent).filter_by(id=agent_id).first()
            assert agent.soul == "New soul description"

    def test_update_disallowed_field(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        result = ae.update_agent_field(agent_id, "status", "running")
        assert result["success"] is False

    def test_all_allowed_fields(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        allowed = [
            "soul", "mission", "playbook", "boundaries", "boot_script",
            "long_term_memory", "model_tier", "heartbeat_interval_mins",
            "name", "identity_emoji",
        ]
        for field in allowed:
            result = ae.update_agent_field(agent_id, field, "test_value")
            assert result["success"] is True, f"Failed to update '{field}'"


class TestRequestTicketCreation:
    def test_without_escalation_engine(self, agent_engine):
        ae, db = agent_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        result = ae.request_ticket_creation(agent_id, {"title": "Test"})
        assert result["success"] is False
        assert "not available" in result["error"].lower()

    def test_with_escalation_engine(self, db_full):
        from core.agent_engine import AgentEngine
        from core.ticket_engine import TicketEngine
        from core.escalation_engine import EscalationEngine
        from core.key_vault import KeyVault
        kv = KeyVault()
        te = TicketEngine(db_full)
        ae = AgentEngine(db_full, kv)
        ee = EscalationEngine(db_full, te, ae)
        ae.escalation_engine = ee

        agent_id = get_agent_id_by_name(db_full, "Scout")
        result = ae.request_ticket_creation(agent_id, {
            "title": "Agent ticket",
            "assignee_id": agent_id,
            "priority": "medium",
        })
        assert result["success"] is True
