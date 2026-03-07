"""
Tests for core/observer_engine.py — fleet health checks, daily reports, anomaly detection.
"""

import pytest
from datetime import datetime, timedelta
from database.schema import Agent, AgentTask
from tests.conftest import get_agent_id_by_name


class TestFleetHealthCheck:
    def test_all_healthy(self, observer_engine):
        oe, db = observer_engine
        # Boot all agents so they have heartbeats
        with db.session_scope() as s:
            for a in s.query(Agent).all():
                a.heartbeat_last = datetime.utcnow()
                a.status = "idle"
        result = oe.run_fleet_health_check()
        assert result["success"] is True
        assert result["data"]["health_pct"] == 100
        assert result["data"]["critical_count"] == 0

    def test_stale_heartbeat_warning(self, observer_engine):
        oe, db = observer_engine
        with db.session_scope() as s:
            for a in s.query(Agent).all():
                a.heartbeat_last = datetime.utcnow()
                a.status = "idle"
            # Make one agent stale
            scout = s.query(Agent).filter_by(name="Scout").first()
            scout.heartbeat_last = datetime.utcnow() - timedelta(hours=2)
        result = oe.run_fleet_health_check()
        assert result["data"]["warning_count"] >= 1
        warning_names = [w["name"] for w in result["data"]["warning"]]
        assert "Scout" in warning_names

    def test_error_state_critical(self, observer_engine):
        oe, db = observer_engine
        with db.session_scope() as s:
            for a in s.query(Agent).all():
                a.heartbeat_last = datetime.utcnow()
                a.status = "idle"
            scout = s.query(Agent).filter_by(name="Scout").first()
            scout.status = "error"
        result = oe.run_fleet_health_check()
        assert result["data"]["critical_count"] >= 1

    def test_high_failure_rate_warning(self, observer_engine):
        oe, db = observer_engine
        with db.session_scope() as s:
            for a in s.query(Agent).all():
                a.heartbeat_last = datetime.utcnow()
                a.status = "idle"
            scout = s.query(Agent).filter_by(name="Scout").first()
            scout.tasks_completed = 2
            scout.tasks_failed = 5
        result = oe.run_fleet_health_check()
        warnings = result["data"]["warning"]
        scout_warning = [w for w in warnings if w["name"] == "Scout"]
        assert len(scout_warning) >= 1
        assert any("failure rate" in issue for issue in scout_warning[0]["issues"])


class TestDailyReport:
    def test_daily_report_empty(self, observer_engine):
        oe, db = observer_engine
        result = oe.aggregate_daily_report()
        assert result["success"] is True
        assert result["data"]["total_tasks"] == 0
        assert result["data"]["total_cost"] == 0.0

    def test_daily_report_with_activity(self, observer_engine):
        oe, db = observer_engine
        with db.session_scope() as s:
            scout = s.query(Agent).filter_by(name="Scout").first()
            scout.tasks_completed = 10
            scout.total_cost_usd = 0.05
        result = oe.aggregate_daily_report()
        assert result["data"]["total_tasks"] == 10
        assert result["data"]["total_cost"] == 0.05
        assert len(result["data"]["agent_details"]) >= 1


class TestAnomalyDetection:
    def test_no_anomalies(self, observer_engine):
        oe, db = observer_engine
        result = oe.detect_anomalies()
        assert result["success"] is True
        assert result["data"]["count"] == 0
        assert result["data"]["severity"] == "info"

    def test_stuck_task(self, observer_engine):
        oe, db = observer_engine
        with db.session_scope() as s:
            agent = s.query(Agent).first()
            task = AgentTask(
                agent_id=agent.id, task_type="test",
                status="running",
                started_at=datetime.utcnow() - timedelta(hours=1),
            )
            s.add(task)
        result = oe.detect_anomalies()
        stuck = [a for a in result["data"]["anomalies"] if a["type"] == "stuck_task"]
        assert len(stuck) >= 1

    def test_silent_agent(self, observer_engine):
        oe, db = observer_engine
        with db.session_scope() as s:
            scout = s.query(Agent).filter_by(name="Scout").first()
            scout.status = "idle"
            scout.heartbeat_last = datetime.utcnow() - timedelta(hours=3)
        result = oe.detect_anomalies()
        silent = [a for a in result["data"]["anomalies"] if a["type"] == "silent_agent"]
        assert len(silent) >= 1

    def test_high_error_rate_anomaly(self, observer_engine):
        oe, db = observer_engine
        with db.session_scope() as s:
            scout = s.query(Agent).filter_by(name="Scout").first()
            scout.tasks_completed = 3
            scout.tasks_failed = 10
        result = oe.detect_anomalies()
        errors = [a for a in result["data"]["anomalies"] if a["type"] == "high_error_rate"]
        assert len(errors) >= 1
        assert result["data"]["severity"] == "critical"
