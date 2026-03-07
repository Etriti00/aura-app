"""
Tests for core/fleet_orchestrator.py — dispatch, triage, pipeline execution,
batch dispatch, fleet status, boot/shutdown, canary, agent lookup.
"""

import pytest
from database.schema import Agent, AgentTask
from tests.conftest import get_agent_id_by_name


class TestDispatch:
    def test_dispatch_to_specialist(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        # Boot the Scout agent first
        scout_id = get_agent_id_by_name(db, "Scout")
        fo.agent_engine.boot_agent(scout_id)

        result = fo.dispatch("scrape_leads", {"query": "plumbers"})
        assert result["success"] is True
        assert result["dispatched"] is True
        assert result["agent_name"] == "Scout"

    def test_dispatch_queues_when_no_idle(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        # Set all agents to running
        with db.session_scope() as s:
            for agent in s.query(Agent).all():
                agent.status = "running"

        result = fo.dispatch("scrape_leads", {"query": "test"})
        assert result["success"] is True
        assert result["queued"] is True
        assert result["dispatched"] is False

    def test_dispatch_fallback_to_idle_worker(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        # Boot a worker but not the specialist
        enricher_id = get_agent_id_by_name(db, "Enricher")
        fo.agent_engine.boot_agent(enricher_id)

        # Make all agents except enricher non-idle
        with db.session_scope() as s:
            for a in s.query(Agent).filter(Agent.id != enricher_id).all():
                a.status = "running"

        result = fo.dispatch("unknown_task_type", {"data": "test"})
        assert result["success"] is True

    def test_dispatch_respects_fleet_capacity(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        from config import FLEET_MAX_CONCURRENT_TASKS
        # Create running tasks at capacity
        with db.session_scope() as s:
            agent = s.query(Agent).first()
            for i in range(FLEET_MAX_CONCURRENT_TASKS):
                s.add(AgentTask(
                    agent_id=agent.id, task_type="test",
                    status="running",
                ))
        result = fo.dispatch("scrape_leads", {"query": "test"})
        assert result["success"] is False
        assert "capacity" in result["error"].lower()


class TestTriageIncomingWork:
    def test_triage_fallback(self, fleet_orchestrator):
        """Without a router, triage should return a single fallback task."""
        fo, db = fleet_orchestrator
        result = fo.triage_incoming_work("Find plumbers in NYC and email them")
        assert result["success"] is True
        assert len(result["subtasks"]) >= 1


class TestExecutePipeline:
    def test_empty_pipeline(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        result = fo.execute_pipeline([])
        assert result["success"] is True
        assert result["completed"] == 0

    def test_single_task_pipeline(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        scout_id = get_agent_id_by_name(db, "Scout")
        fo.agent_engine.boot_agent(scout_id)

        result = fo.execute_pipeline([
            {"task_type": "scrape_leads", "payload": {"query": "test"}, "depends_on": []},
        ])
        assert result["success"] is True
        assert result["completed"] == 1

    def test_pipeline_with_dependencies(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        # Boot multiple agents
        for name in ["Scout", "Enricher", "Qualifier"]:
            aid = get_agent_id_by_name(db, name)
            fo.agent_engine.boot_agent(aid)

        result = fo.execute_pipeline([
            {"task_type": "scrape_leads", "payload": {"query": "test"}, "depends_on": []},
            {"task_type": "enrich_lead", "payload": {"lead": "data"}, "depends_on": [0]},
        ])
        assert result["completed"] == 2


class TestBatchDispatch:
    def test_batch_dispatch(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        scout_id = get_agent_id_by_name(db, "Scout")
        fo.agent_engine.boot_agent(scout_id)

        result = fo.batch_dispatch([
            {"task_type": "scrape_leads", "payload": {"q": "1"}, "tier": "local"},
            {"task_type": "scrape_leads", "payload": {"q": "2"}, "tier": "haiku"},
        ])
        assert result["success"] is True
        assert result["dispatched"] == 2


class TestFleetStatus:
    def test_fleet_status(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        result = fo.get_fleet_status()
        assert result["success"] is True
        data = result["data"]
        assert data["total_agents"] == 19
        assert data["idle"] == 19  # All idle initially
        assert data["running"] == 0
        assert data["health_pct"] == 100

    def test_fleet_status_with_running_agent(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        with db.session_scope() as s:
            agent = s.query(Agent).first()
            agent.status = "running"
        result = fo.get_fleet_status()
        assert result["data"]["running"] == 1
        assert result["data"]["idle"] == 18


class TestBootFleet:
    def test_boot_fleet(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        result = fo.boot_fleet()
        assert result["success"] is True
        assert result["data"]["booted"] == 19
        assert result["data"]["errors"] == 0

        with db.session_scope() as s:
            for agent in s.query(Agent).all():
                assert agent.status == "idle"
                assert agent.heartbeat_last is not None


class TestShutdownFleet:
    def test_shutdown_fleet(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        # Boot first, then set some agents to running
        fo.boot_fleet()
        with db.session_scope() as s:
            agent = s.query(Agent).first()
            agent.status = "running"
            agent.current_task = "some_task"

        result = fo.shutdown_fleet()
        assert result["success"] is True

        with db.session_scope() as s:
            for agent in s.query(Agent).all():
                assert agent.status == "idle"
                assert agent.current_task is None


class TestCanaryUpdate:
    def test_canary_passes(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        canary_id = get_agent_id_by_name(db, "Canary")
        fo.agent_engine.boot_agent(canary_id)
        result = fo.apply_canary_update({"soul": "Updated canary soul"})
        assert result["success"] is True
        assert result["canary_passed"] is True

    def test_no_canary_fails(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        # Remove canary
        with db.session_scope() as s:
            canary = s.query(Agent).filter_by(role="canary").first()
            if canary:
                canary.role = "worker"
        result = fo.apply_canary_update({"soul": "test"})
        assert result["success"] is False


class TestGetAgentByName:
    def test_find_agent(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        result = fo.get_agent_by_name("Scout")
        assert result["success"] is True
        assert result["data"]["name"] == "Scout"

    def test_case_insensitive(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        result = fo.get_agent_by_name("scout")
        assert result["success"] is True

    def test_not_found(self, fleet_orchestrator):
        fo, db = fleet_orchestrator
        result = fo.get_agent_by_name("NonExistentBot")
        assert result["success"] is False


class TestTaskSpecialtyMap:
    def test_all_mapped_tasks(self, fleet_orchestrator):
        from core.fleet_orchestrator import TASK_SPECIALTY_MAP
        expected_mappings = {
            "scrape_leads": "Scout",
            "enrich_lead": "Enricher",
            "qualify_lead": "Qualifier",
            "generate_email": "Closer",
            "send_email": "Postman",
            "check_replies": "Tracker",
            "rag_store": "Archivist",
            "analyze_performance": "Analyst",
            "create_skill": "Forger",
            "crm_sync": "Syncer",
            "check_trends": "Trend Spotter",
            "suppress_email": "Suppressor",
            "generate_report": "Reporter",
            "schedule_followup": "Scheduler",
            "triage_inbox": "Triage Lead",
            "manage_ticket": "Commander",
            "escalate_ticket": "Commander",
        }
        for task_type, agent_name in expected_mappings.items():
            assert TASK_SPECIALTY_MAP.get(task_type) == agent_name, (
                f"Task '{task_type}' should map to '{agent_name}'"
            )
