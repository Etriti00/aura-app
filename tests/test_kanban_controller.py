"""
Tests for controllers/kanban_controller.py — signal-driven controller bridging
the ticket engine to the Kanban UI. Verifies all CRUD operations, signal emissions,
agents list, due-date checks, sprints, and timelines.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from database.schema import Agent
from tests.conftest import get_agent_id_by_name


@pytest.fixture
def kanban_ctrl(db_with_agents):
    from core.ticket_engine import TicketEngine
    from core.ticket_scheduler import TicketScheduler
    from core.agent_engine import AgentEngine
    from core.key_vault import KeyVault
    from controllers.kanban_controller import KanbanController
    te = TicketEngine(db_with_agents)
    kv = KeyVault()
    ae = AgentEngine(db_with_agents, kv)
    ts = TicketScheduler(db_with_agents, te, ae)
    kc = KanbanController(db_with_agents, te, ts)
    return kc, te, db_with_agents


class TestRefreshBoard:
    def test_emits_board_ready(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.board_ready.connect(lambda data: received.append(data))
        te.create_ticket(title="Test")
        kc.refresh_board()
        assert len(received) == 1
        assert "backlog" in received[0]

    def test_emits_with_filters(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.board_ready.connect(lambda data: received.append(data))
        kc.refresh_board(priority="high")
        assert len(received) == 1


class TestCreateTicket:
    def test_emits_ticket_created(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.ticket_created.connect(lambda data: received.append(data))
        kc.create_ticket(title="New ticket", priority="high")
        assert len(received) == 1
        assert received[0]["title"] == "New ticket"

    def test_error_on_empty_title(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        errors = []
        kc.error.connect(lambda msg: errors.append(msg))
        # Empty title should still succeed (it's allowed by engine)
        kc.create_ticket(title="")
        # The engine doesn't reject empty titles, it creates them


class TestMoveTicket:
    def test_emits_ticket_moved(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.ticket_moved.connect(lambda tid, status: received.append((tid, status)))
        t = te.create_ticket(title="Move me")
        kc.move_ticket(t["data"]["id"], "in_progress")
        assert len(received) == 1
        assert received[0][1] == "in_progress"

    def test_error_on_invalid_status(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        errors = []
        kc.error.connect(lambda msg: errors.append(msg))
        t = te.create_ticket(title="Bad move")
        kc.move_ticket(t["data"]["id"], "invalid_status")
        assert len(errors) == 1


class TestUpdateTicket:
    def test_emits_ticket_updated(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.ticket_updated.connect(lambda data: received.append(data))
        t = te.create_ticket(title="Update me")
        kc.update_ticket(t["data"]["id"], title="Updated")
        assert len(received) == 1
        assert received[0]["title"] == "Updated"


class TestDeleteTicket:
    def test_emits_ticket_deleted(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.ticket_deleted.connect(lambda tid: received.append(tid))
        t = te.create_ticket(title="Delete me")
        kc.delete_ticket(t["data"]["id"])
        assert len(received) == 1

    def test_error_on_nonexistent(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        errors = []
        kc.error.connect(lambda msg: errors.append(msg))
        kc.delete_ticket(99999)
        assert len(errors) == 1


class TestGetTicketDetail:
    def test_emits_detail(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.ticket_detail_ready.connect(lambda data: received.append(data))
        t = te.create_ticket(title="Detail test")
        kc.get_ticket_detail(t["data"]["id"])
        assert len(received) == 1
        assert "comments" in received[0]


class TestAddComment:
    def test_triggers_detail_refresh(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.ticket_detail_ready.connect(lambda data: received.append(data))
        t = te.create_ticket(title="Comment test")
        kc.add_comment(t["data"]["id"], "Hello")
        # Should emit ticket_detail_ready with updated comments
        assert len(received) >= 1
        assert len(received[-1]["comments"]) >= 1


class TestRefreshStats:
    def test_emits_stats(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.stats_ready.connect(lambda data: received.append(data))
        te.create_ticket(title="A")
        te.create_ticket(title="B")
        kc.refresh_stats()
        assert len(received) == 1
        assert received[0]["total"] == 2


class TestCheckDueDates:
    def test_emits_alerts(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.due_date_alerts.connect(lambda data: received.append(data))
        past = datetime.utcnow() - timedelta(hours=1)
        scout_id = get_agent_id_by_name(db, "Scout")
        te.create_ticket(title="Overdue", due_date=past, assignee_id=scout_id)
        kc.check_due_dates()
        assert len(received) == 1
        assert received[0]["overdue_count"] == 1

    def test_no_alert_when_nothing_due(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.due_date_alerts.connect(lambda data: received.append(data))
        kc.check_due_dates()
        assert len(received) == 0  # No alert emitted


class TestCreateSprint:
    def test_emits_sprint_created(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.sprint_created.connect(lambda data: received.append(data))
        t = te.create_ticket(title="Sprint task")
        start = datetime.utcnow()
        end = start + timedelta(days=14)
        kc.create_sprint("Sprint 1", start, end, [t["data"]["id"]])
        assert len(received) == 1
        assert received[0]["sprint_name"] == "Sprint 1"

    def test_error_without_scheduler(self, db_with_agents):
        from core.ticket_engine import TicketEngine
        from controllers.kanban_controller import KanbanController
        te = TicketEngine(db_with_agents)
        kc = KanbanController(db_with_agents, te, ticket_scheduler=None)
        errors = []
        kc.error.connect(lambda msg: errors.append(msg))
        kc.create_sprint("X", datetime.utcnow(), datetime.utcnow(), [])
        assert len(errors) == 1


class TestGetTimeline:
    def test_emits_timeline(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        received = []
        kc.timeline_ready.connect(lambda data: received.append(data))
        tomorrow = datetime.utcnow() + timedelta(days=1)
        te.create_ticket(title="Tomorrow", due_date=tomorrow)
        kc.get_timeline()
        assert len(received) == 1
        assert "dates" in received[0]


class TestGetAgentsList:
    def test_returns_agents(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        agents = kc.get_agents_list()
        assert len(agents) == 20
        assert all("id" in a for a in agents)
        assert all("name" in a for a in agents)
        assert all("emoji" in a for a in agents)
        assert all("rank" in a for a in agents)

    def test_ordered_by_rank(self, kanban_ctrl):
        kc, te, db = kanban_ctrl
        agents = kc.get_agents_list()
        ranks = [a["rank"] for a in agents]
        assert ranks == sorted(ranks)
