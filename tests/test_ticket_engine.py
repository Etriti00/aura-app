"""
Tests for core/ticket_engine.py — CRUD, status transitions, comments,
dependencies, hierarchy enforcement, due dates, statistics.
"""

import pytest
from datetime import datetime, timedelta
from database.schema import Agent, AgentTicket, TicketComment
from tests.conftest import get_agent_id_by_name


class TestTicketCreate:
    def test_create_basic_ticket(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Test ticket")
        assert result["success"] is True
        assert result["data"]["title"] == "Test ticket"
        assert result["data"]["priority"] == "medium"
        assert result["data"]["status"] == "backlog"

    def test_create_ticket_with_all_fields(self, ticket_engine):
        te, db = ticket_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        due = datetime.utcnow() + timedelta(days=1)
        result = te.create_ticket(
            title="Full ticket",
            description="Detailed description",
            priority="critical",
            assignee_id=agent_id,
            reporter_type="agent",
            due_date=due,
            labels="bug,urgent",
        )
        assert result["success"] is True
        data = result["data"]
        assert data["priority"] == "critical"
        assert data["description"] == "Detailed description"
        assert data["assignee_name"] == "Scout"
        assert data["labels"] == "bug,urgent"
        assert data["due_date"] is not None

    def test_create_ticket_invalid_priority_defaults(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Bad priority", priority="super_critical")
        assert result["success"] is True
        assert result["data"]["priority"] == "medium"

    def test_create_sub_ticket(self, ticket_engine):
        te, db = ticket_engine
        parent = te.create_ticket(title="Parent")
        assert parent["success"] is True
        child = te.create_ticket(
            title="Child", parent_ticket_id=parent["data"]["id"]
        )
        assert child["success"] is True
        assert child["data"]["parent_ticket_id"] == parent["data"]["id"]

    def test_create_ticket_with_approval_status(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Pending", approval_status="pending")
        assert result["success"] is True
        assert result["data"]["approval_status"] == "pending"


class TestTicketUpdate:
    def test_update_title(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Original")
        ticket_id = result["data"]["id"]
        update = te.update_ticket(ticket_id, title="Updated")
        assert update["success"] is True
        assert update["data"]["title"] == "Updated"

    def test_update_multiple_fields(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Multi")
        ticket_id = result["data"]["id"]
        update = te.update_ticket(
            ticket_id, priority="high", labels="feature", description="New desc"
        )
        assert update["success"] is True
        assert update["data"]["priority"] == "high"
        assert update["data"]["labels"] == "feature"

    def test_update_nonexistent_ticket(self, ticket_engine):
        te, db = ticket_engine
        result = te.update_ticket(99999, title="Nope")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_update_ignores_protected_fields(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Protected")
        ticket_id = result["data"]["id"]
        original_id = result["data"]["id"]
        update = te.update_ticket(ticket_id, id=99999)
        assert update["success"] is True
        assert update["data"]["id"] == original_id


class TestTicketMove:
    def test_move_ticket_valid_status(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Move me")
        ticket_id = result["data"]["id"]
        move = te.move_ticket(ticket_id, "in_progress")
        assert move["success"] is True
        assert move["new_status"] == "in_progress"

    def test_move_ticket_invalid_status(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Bad move")
        move = te.move_ticket(result["data"]["id"], "invalid_status")
        assert move["success"] is False
        assert "Invalid status" in move["error"]

    def test_move_to_done_sets_completed_at(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Complete me")
        ticket_id = result["data"]["id"]
        te.move_ticket(ticket_id, "done")
        ticket = te.get_ticket(ticket_id)
        assert ticket["data"]["completed_at"] is not None

    def test_move_from_done_clears_completed_at(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Reopen me")
        ticket_id = result["data"]["id"]
        te.move_ticket(ticket_id, "done")
        te.move_ticket(ticket_id, "in_progress")
        ticket = te.get_ticket(ticket_id)
        assert ticket["data"]["completed_at"] is None

    def test_move_creates_status_change_comment(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Comment on move")
        ticket_id = result["data"]["id"]
        te.move_ticket(ticket_id, "todo")
        comments = te.get_comments(ticket_id)
        assert comments["success"] is True
        assert len(comments["data"]) >= 1
        assert "status changed" in comments["data"][0]["content"].lower()

    def test_move_clears_blocked_reason(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Blocked")
        ticket_id = result["data"]["id"]
        te.update_ticket(ticket_id, blocked_reason="Waiting on API")
        te.move_ticket(ticket_id, "review")
        ticket = te.get_ticket(ticket_id)
        assert ticket["data"]["blocked_reason"] is None

    def test_move_nonexistent_ticket(self, ticket_engine):
        te, db = ticket_engine
        result = te.move_ticket(99999, "todo")
        assert result["success"] is False


class TestTicketDelete:
    def test_delete_ticket(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Delete me")
        ticket_id = result["data"]["id"]
        delete = te.delete_ticket(ticket_id)
        assert delete["success"] is True
        get = te.get_ticket(ticket_id)
        assert get["success"] is False

    def test_delete_nonexistent(self, ticket_engine):
        te, db = ticket_engine
        result = te.delete_ticket(99999)
        assert result["success"] is False


class TestTicketGet:
    def test_get_ticket_with_comments(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Get me")
        ticket_id = result["data"]["id"]
        te.add_comment(ticket_id, "A comment")
        ticket = te.get_ticket(ticket_id)
        assert ticket["success"] is True
        assert len(ticket["data"]["comments"]) == 1

    def test_get_ticket_with_sub_tickets(self, ticket_engine):
        te, db = ticket_engine
        parent = te.create_ticket(title="Parent")
        te.create_ticket(title="Child 1", parent_ticket_id=parent["data"]["id"])
        te.create_ticket(title="Child 2", parent_ticket_id=parent["data"]["id"])
        result = te.get_ticket(parent["data"]["id"])
        assert len(result["data"]["sub_tickets"]) == 2

    def test_get_all_tickets_no_filter(self, ticket_engine):
        te, db = ticket_engine
        te.create_ticket(title="A")
        te.create_ticket(title="B")
        te.create_ticket(title="C")
        result = te.get_all_tickets()
        assert result["success"] is True
        assert len(result["data"]) == 3

    def test_get_all_tickets_filter_by_status(self, ticket_engine):
        te, db = ticket_engine
        te.create_ticket(title="Backlog 1")
        r = te.create_ticket(title="In Progress 1")
        te.move_ticket(r["data"]["id"], "in_progress")
        result = te.get_all_tickets(status="in_progress")
        assert len(result["data"]) == 1

    def test_get_all_tickets_filter_by_priority(self, ticket_engine):
        te, db = ticket_engine
        te.create_ticket(title="High", priority="high")
        te.create_ticket(title="Low", priority="low")
        result = te.get_all_tickets(priority="high")
        assert len(result["data"]) == 1

    def test_get_all_tickets_filter_by_label(self, ticket_engine):
        te, db = ticket_engine
        te.create_ticket(title="Bug", labels="bug,ui")
        te.create_ticket(title="Feature", labels="feature")
        result = te.get_all_tickets(label="bug")
        assert len(result["data"]) == 1

    def test_get_tickets_by_status(self, ticket_engine):
        te, db = ticket_engine
        te.create_ticket(title="A")
        r = te.create_ticket(title="B")
        te.move_ticket(r["data"]["id"], "in_progress")
        result = te.get_tickets_by_status()
        assert result["success"] is True
        assert "backlog" in result["data"]
        assert "in_progress" in result["data"]
        assert "done" in result["data"]
        assert len(result["data"]["backlog"]) == 1
        assert len(result["data"]["in_progress"]) == 1


class TestComments:
    def test_add_comment(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Comment test")
        ticket_id = result["data"]["id"]
        comment = te.add_comment(ticket_id, "Hello world")
        assert comment["success"] is True
        assert comment["data"]["content"] == "Hello world"
        assert comment["data"]["author_type"] == "user"

    def test_add_comment_with_author(self, ticket_engine):
        te, db = ticket_engine
        agent_id = get_agent_id_by_name(db, "Commander")
        result = te.create_ticket(title="Agent comment")
        comment = te.add_comment(
            result["data"]["id"], "System message",
            author_id=agent_id, author_type="agent", comment_type="escalation"
        )
        assert comment["success"] is True
        assert comment["data"]["author_name"] == "Commander"
        assert comment["data"]["comment_type"] == "escalation"

    def test_add_comment_to_nonexistent_ticket(self, ticket_engine):
        te, db = ticket_engine
        result = te.add_comment(99999, "No ticket")
        assert result["success"] is False

    def test_get_comments_ordered(self, ticket_engine):
        te, db = ticket_engine
        result = te.create_ticket(title="Ordered comments")
        ticket_id = result["data"]["id"]
        te.add_comment(ticket_id, "First")
        te.add_comment(ticket_id, "Second")
        te.add_comment(ticket_id, "Third")
        comments = te.get_comments(ticket_id)
        assert len(comments["data"]) == 3
        assert comments["data"][0]["content"] == "First"
        assert comments["data"][2]["content"] == "Third"


class TestDependencies:
    def test_add_dependency(self, ticket_engine):
        te, db = ticket_engine
        a = te.create_ticket(title="A")
        b = te.create_ticket(title="B")
        result = te.add_dependency(a["data"]["id"], b["data"]["id"])
        assert result["success"] is True

    def test_self_dependency_rejected(self, ticket_engine):
        te, db = ticket_engine
        a = te.create_ticket(title="Self")
        result = te.add_dependency(a["data"]["id"], a["data"]["id"])
        assert result["success"] is False
        assert "itself" in result["error"].lower()

    def test_duplicate_dependency_rejected(self, ticket_engine):
        te, db = ticket_engine
        a = te.create_ticket(title="A")
        b = te.create_ticket(title="B")
        te.add_dependency(a["data"]["id"], b["data"]["id"])
        result = te.add_dependency(a["data"]["id"], b["data"]["id"])
        assert result["success"] is False

    def test_remove_dependency(self, ticket_engine):
        te, db = ticket_engine
        a = te.create_ticket(title="A")
        b = te.create_ticket(title="B")
        te.add_dependency(a["data"]["id"], b["data"]["id"])
        result = te.remove_dependency(a["data"]["id"], b["data"]["id"])
        assert result["success"] is True

    def test_check_blocked(self, ticket_engine):
        te, db = ticket_engine
        a = te.create_ticket(title="Blocked ticket")
        b = te.create_ticket(title="Blocker")
        te.add_dependency(a["data"]["id"], b["data"]["id"])
        result = te.check_blocked(a["data"]["id"])
        assert result["success"] is True
        assert result["is_blocked"] is True
        assert len(result["blockers"]) == 1

    def test_not_blocked_after_done(self, ticket_engine):
        te, db = ticket_engine
        a = te.create_ticket(title="Waiting")
        b = te.create_ticket(title="Blocker")
        te.add_dependency(a["data"]["id"], b["data"]["id"])
        te.move_ticket(b["data"]["id"], "done")
        result = te.check_blocked(a["data"]["id"])
        assert result["is_blocked"] is False


class TestSubTickets:
    def test_get_sub_tickets(self, ticket_engine):
        te, db = ticket_engine
        parent = te.create_ticket(title="Parent")
        te.create_ticket(title="Sub 1", parent_ticket_id=parent["data"]["id"])
        te.create_ticket(title="Sub 2", parent_ticket_id=parent["data"]["id"])
        result = te.get_sub_tickets(parent["data"]["id"])
        assert result["success"] is True
        assert len(result["data"]) == 2

    def test_sub_ticket_count_in_parent(self, ticket_engine):
        te, db = ticket_engine
        parent = te.create_ticket(title="Parent")
        te.create_ticket(title="Sub", parent_ticket_id=parent["data"]["id"])
        ticket = te.get_ticket(parent["data"]["id"])
        assert ticket["data"]["sub_ticket_count"] == 1


class TestHierarchyEnforcement:
    def test_rank_1_can_do_anything(self, ticket_engine):
        te, db = ticket_engine
        commander_id = get_agent_id_by_name(db, "Commander")
        result = te.can_agent_create_ticket(commander_id)
        assert result["allowed"] is True
        assert result["needs_approval"] is False

    def test_rank_2_can_assign_to_rank_3(self, ticket_engine):
        te, db = ticket_engine
        triage_id = get_agent_id_by_name(db, "Triage Lead")
        scout_id = get_agent_id_by_name(db, "Scout")
        result = te.can_agent_create_ticket(triage_id, scout_id)
        assert result["allowed"] is True
        assert result["needs_approval"] is False

    def test_rank_2_needs_approval_for_peer(self, ticket_engine):
        te, db = ticket_engine
        triage_id = get_agent_id_by_name(db, "Triage Lead")
        result = te.can_agent_create_ticket(triage_id)
        assert result["allowed"] is True
        assert result["needs_approval"] is True

    def test_rank_3_always_needs_approval(self, ticket_engine):
        te, db = ticket_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        result = te.can_agent_create_ticket(scout_id)
        assert result["allowed"] is True
        assert result["needs_approval"] is True

    def test_rank_1_can_move_any_ticket(self, ticket_engine):
        te, db = ticket_engine
        commander_id = get_agent_id_by_name(db, "Commander")
        scout_id = get_agent_id_by_name(db, "Scout")
        t = te.create_ticket(title="Move test", assignee_id=scout_id)
        result = te.can_agent_move_ticket(commander_id, t["data"]["id"])
        assert result["allowed"] is True

    def test_assigned_agent_can_move_own_ticket(self, ticket_engine):
        te, db = ticket_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        t = te.create_ticket(title="Own ticket", assignee_id=scout_id)
        result = te.can_agent_move_ticket(scout_id, t["data"]["id"])
        assert result["allowed"] is True

    def test_rank_2_can_move_direct_report_ticket(self, ticket_engine):
        te, db = ticket_engine
        triage_id = get_agent_id_by_name(db, "Triage Lead")
        scout_id = get_agent_id_by_name(db, "Scout")
        t = te.create_ticket(title="Scout task", assignee_id=scout_id)
        result = te.can_agent_move_ticket(triage_id, t["data"]["id"])
        assert result["allowed"] is True

    def test_rank_3_cannot_move_others_ticket(self, ticket_engine):
        te, db = ticket_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        enricher_id = get_agent_id_by_name(db, "Enricher")
        t = te.create_ticket(title="Not yours", assignee_id=enricher_id)
        result = te.can_agent_move_ticket(scout_id, t["data"]["id"])
        assert result["allowed"] is False

    def test_nonexistent_agent(self, ticket_engine):
        te, db = ticket_engine
        result = te.can_agent_create_ticket(99999)
        assert result["success"] is False


class TestDueDates:
    def test_get_overdue_tickets(self, ticket_engine):
        te, db = ticket_engine
        past = datetime.utcnow() - timedelta(hours=2)
        te.create_ticket(title="Overdue", due_date=past)
        te.create_ticket(title="Not overdue")
        result = te.get_overdue_tickets()
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["title"] == "Overdue"

    def test_done_tickets_not_overdue(self, ticket_engine):
        te, db = ticket_engine
        past = datetime.utcnow() - timedelta(hours=2)
        t = te.create_ticket(title="Done", due_date=past)
        te.move_ticket(t["data"]["id"], "done")
        result = te.get_overdue_tickets()
        assert len(result["data"]) == 0

    def test_get_upcoming_due(self, ticket_engine):
        te, db = ticket_engine
        soon = datetime.utcnow() + timedelta(hours=2)
        far = datetime.utcnow() + timedelta(days=5)
        te.create_ticket(title="Due soon", due_date=soon)
        te.create_ticket(title="Due later", due_date=far)
        result = te.get_upcoming_due(hours=4)
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["title"] == "Due soon"


class TestTicketStats:
    def test_stats_empty(self, ticket_engine):
        te, db = ticket_engine
        result = te.get_ticket_stats()
        assert result["success"] is True
        assert result["data"]["total"] == 0

    def test_stats_counts(self, ticket_engine):
        te, db = ticket_engine
        te.create_ticket(title="A", priority="high")
        te.create_ticket(title="B", priority="low")
        r = te.create_ticket(title="C")
        te.move_ticket(r["data"]["id"], "in_progress")
        result = te.get_ticket_stats()
        data = result["data"]
        assert data["total"] == 3
        assert data["by_status"]["backlog"] == 2
        assert data["by_status"]["in_progress"] == 1
        assert data["by_priority"]["high"] == 1
        assert data["by_priority"]["low"] == 1

    def test_stats_overdue_count(self, ticket_engine):
        te, db = ticket_engine
        past = datetime.utcnow() - timedelta(hours=2)
        te.create_ticket(title="Overdue", due_date=past)
        te.create_ticket(title="Fine")
        result = te.get_ticket_stats()
        assert result["data"]["overdue"] == 1


class TestTicketToDict:
    def test_dict_has_all_fields(self, ticket_engine):
        te, db = ticket_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        result = te.create_ticket(
            title="Full dict",
            description="desc",
            priority="high",
            assignee_id=agent_id,
            labels="test",
        )
        data = result["data"]
        required_fields = [
            "id", "title", "description", "priority", "status",
            "assignee_id", "assignee_name", "assignee_emoji",
            "reporter_id", "reporter_name", "reporter_type",
            "parent_ticket_id", "due_date", "due_date_display",
            "labels", "blocked_reason", "escalated_to_id",
            "approval_status", "approved_by_id", "linked_task_id",
            "created_at", "updated_at", "completed_at", "sub_ticket_count",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
