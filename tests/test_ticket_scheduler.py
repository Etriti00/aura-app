"""
Tests for core/ticket_scheduler.py — due-date checks, notifications,
sprint planning, sprint progress, timeline.
"""

import pytest
from datetime import datetime, timedelta
from database.schema import Agent, AgentTicket, AgentMessage
from tests.conftest import get_agent_id_by_name


class TestCheckDueDates:
    def test_detects_overdue(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        scout_id = get_agent_id_by_name(db, "Scout")
        past = datetime.utcnow() - timedelta(hours=2)
        te.create_ticket(title="Overdue", due_date=past, assignee_id=scout_id)
        result = ts.check_due_dates()
        assert result["success"] is True
        assert result["overdue_count"] == 1
        assert result["overdue"][0]["title"] == "Overdue"
        assert result["overdue"][0]["hours_overdue"] > 0

    def test_detects_upcoming(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        soon = datetime.utcnow() + timedelta(hours=2)
        te.create_ticket(title="Due soon", due_date=soon)
        result = ts.check_due_dates(warning_hours=4)
        assert result["upcoming_count"] == 1
        assert result["upcoming"][0]["title"] == "Due soon"

    def test_ignores_done_tickets(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        past = datetime.utcnow() - timedelta(hours=2)
        t = te.create_ticket(title="Done", due_date=past)
        te.move_ticket(t["data"]["id"], "done")
        result = ts.check_due_dates()
        assert result["overdue_count"] == 0

    def test_ignores_far_future(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        far = datetime.utcnow() + timedelta(days=30)
        te.create_ticket(title="Far future", due_date=far)
        result = ts.check_due_dates(warning_hours=4)
        assert result["upcoming_count"] == 0

    def test_notifications_generated(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        scout_id = get_agent_id_by_name(db, "Scout")
        past = datetime.utcnow() - timedelta(hours=1)
        soon = datetime.utcnow() + timedelta(hours=2)
        te.create_ticket(title="Overdue", due_date=past, assignee_id=scout_id)
        te.create_ticket(title="Soon", due_date=soon, assignee_id=scout_id)
        result = ts.check_due_dates(warning_hours=4)
        assert len(result["notifications"]) == 2
        types = [n["type"] for n in result["notifications"]]
        assert "overdue" in types
        assert "upcoming" in types

    def test_no_due_date_ignored(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        te.create_ticket(title="No due date")
        result = ts.check_due_dates()
        assert result["overdue_count"] == 0
        assert result["upcoming_count"] == 0


class TestSendDueDateNotifications:
    def test_sends_messages(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        scout_id = get_agent_id_by_name(db, "Scout")
        notifications = [
            {"type": "overdue", "ticket_id": 1, "title": "Late!", "assignee_id": scout_id},
        ]
        result = ts.send_due_date_notifications(notifications)
        assert result["success"] is True
        assert result["sent"] == 1

        with db.session_scope() as s:
            msgs = s.query(AgentMessage).filter_by(
                to_agent_id=scout_id
            ).all()
            assert len(msgs) >= 1

    def test_skips_unassigned(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        notifications = [
            {"type": "overdue", "ticket_id": 1, "title": "No assignee", "assignee_id": None},
        ]
        result = ts.send_due_date_notifications(notifications)
        assert result["success"] is True
        assert result["sent"] == 0

    def test_no_agent_engine(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        ts.agent_engine = None
        result = ts.send_due_date_notifications([{"type": "overdue", "ticket_id": 1, "title": "X", "assignee_id": 1}])
        assert result["success"] is False


class TestCreateSprint:
    def test_create_sprint(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        t1 = te.create_ticket(title="Sprint task 1")
        t2 = te.create_ticket(title="Sprint task 2")
        start = datetime.utcnow()
        end = start + timedelta(days=14)
        result = ts.create_sprint(
            "Sprint 1", start, end, [t1["data"]["id"], t2["data"]["id"]]
        )
        assert result["success"] is True
        assert result["ticket_count"] == 2
        assert result["sprint_name"] == "Sprint 1"

    def test_sprint_sets_labels(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        t = te.create_ticket(title="Sprint labelled")
        start = datetime.utcnow()
        end = start + timedelta(days=7)
        ts.create_sprint("Alpha", start, end, [t["data"]["id"]])
        ticket = te.get_ticket(t["data"]["id"])
        assert "sprint:Alpha" in ticket["data"]["labels"]

    def test_sprint_sets_due_date(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        t = te.create_ticket(title="Sprint due")
        start = datetime.utcnow()
        end = start + timedelta(days=7)
        ts.create_sprint("Beta", start, end, [t["data"]["id"]])
        ticket = te.get_ticket(t["data"]["id"])
        assert ticket["data"]["due_date"] is not None

    def test_sprint_adds_comment(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        t = te.create_ticket(title="Sprint comment")
        start = datetime.utcnow()
        end = start + timedelta(days=7)
        ts.create_sprint("Gamma", start, end, [t["data"]["id"]])
        comments = te.get_comments(t["data"]["id"])
        sprint_comments = [c for c in comments["data"] if "sprint" in c["content"].lower()]
        assert len(sprint_comments) >= 1


class TestGetSprintProgress:
    def test_sprint_progress(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        t1 = te.create_ticket(title="Done task")
        t2 = te.create_ticket(title="In progress")
        t3 = te.create_ticket(title="Todo")
        start = datetime.utcnow()
        end = start + timedelta(days=14)
        ts.create_sprint("Progress", start, end, [t1["data"]["id"], t2["data"]["id"], t3["data"]["id"]])
        te.move_ticket(t1["data"]["id"], "done")
        te.move_ticket(t2["data"]["id"], "in_progress")

        result = ts.get_sprint_progress("Progress")
        assert result["success"] is True
        assert result["total"] == 3
        assert result["done"] == 1
        assert result["in_progress"] == 1
        assert result["remaining"] == 2
        assert result["progress_pct"] == 33  # 1/3 ≈ 33%

    def test_nonexistent_sprint(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        result = ts.get_sprint_progress("NonExistent")
        assert result["success"] is True
        assert result["total"] == 0


class TestGetTimeline:
    def test_timeline_groups_by_date(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        tomorrow = datetime.utcnow() + timedelta(days=1)
        day_after = datetime.utcnow() + timedelta(days=2)
        te.create_ticket(title="Tomorrow 1", due_date=tomorrow)
        te.create_ticket(title="Tomorrow 2", due_date=tomorrow)
        te.create_ticket(title="Day after", due_date=day_after)
        result = ts.get_timeline(days_ahead=7)
        assert result["success"] is True
        assert len(result["dates"]) == 2

    def test_timeline_excludes_done(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        tomorrow = datetime.utcnow() + timedelta(days=1)
        t = te.create_ticket(title="Done", due_date=tomorrow)
        te.move_ticket(t["data"]["id"], "done")
        result = ts.get_timeline(days_ahead=7)
        assert len(result["dates"]) == 0

    def test_timeline_excludes_far_dates(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        far = datetime.utcnow() + timedelta(days=30)
        te.create_ticket(title="Far away", due_date=far)
        result = ts.get_timeline(days_ahead=14)
        assert len(result["dates"]) == 0

    def test_empty_timeline(self, ticket_scheduler):
        ts, te, ae, db = ticket_scheduler
        result = ts.get_timeline()
        assert result["success"] is True
        assert result["dates"] == {}
