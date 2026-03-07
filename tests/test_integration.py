"""
Integration tests — end-to-end scenarios that exercise multiple engines working
together, verifying the full ticket lifecycle, escalation chains, sprint workflows,
and dashboard stat propagation.
"""

import pytest
from datetime import datetime, timedelta
from database.schema import Agent, AgentTicket, AgentMessage
from tests.conftest import get_agent_id_by_name


@pytest.fixture
def full_stack(db_with_agents):
    """All engines wired together."""
    from core.ticket_engine import TicketEngine
    from core.escalation_engine import EscalationEngine
    from core.ticket_scheduler import TicketScheduler
    from core.agent_engine import AgentEngine
    from core.fleet_orchestrator import FleetOrchestrator
    from core.observer_engine import ObserverEngine
    from core.key_vault import KeyVault

    db = db_with_agents
    kv = KeyVault()
    te = TicketEngine(db)
    ae = AgentEngine(db, kv)
    ee = EscalationEngine(db, te, ae)
    ts = TicketScheduler(db, te, ae)
    ae.escalation_engine = ee
    fo = FleetOrchestrator(db, ae)
    oe = ObserverEngine(db, ae)
    return {
        "db": db, "te": te, "ae": ae, "ee": ee, "ts": ts, "fo": fo, "oe": oe,
    }


class TestFullTicketLifecycle:
    def test_create_move_comment_complete(self, full_stack):
        """Create → assign → move through pipeline → add comments → complete."""
        te = full_stack["te"]
        db = full_stack["db"]
        scout_id = get_agent_id_by_name(db, "Scout")

        # Create
        result = te.create_ticket(
            title="Full lifecycle ticket",
            description="Test end-to-end",
            priority="high",
            assignee_id=scout_id,
        )
        assert result["success"]
        tid = result["data"]["id"]

        # Move through pipeline
        for status in ["todo", "in_progress", "review", "done"]:
            move = te.move_ticket(tid, status)
            assert move["success"], f"Failed to move to {status}"

        # Add comments
        te.add_comment(tid, "Started working on this")
        te.add_comment(tid, "Done!", author_type="agent")

        # Verify final state
        ticket = te.get_ticket(tid)
        assert ticket["data"]["status"] == "done"
        assert ticket["data"]["completed_at"] is not None
        # 4 status change comments + 2 manual comments = 6
        assert len(ticket["data"]["comments"]) == 6

    def test_sub_ticket_workflow(self, full_stack):
        """Parent ticket with sub-tickets, track completion."""
        te = full_stack["te"]
        parent = te.create_ticket(title="Epic: New Feature")
        pid = parent["data"]["id"]

        sub1 = te.create_ticket(title="Sub: Design", parent_ticket_id=pid)
        sub2 = te.create_ticket(title="Sub: Implement", parent_ticket_id=pid)
        sub3 = te.create_ticket(title="Sub: Test", parent_ticket_id=pid)

        # Complete sub-tasks
        te.move_ticket(sub1["data"]["id"], "done")
        te.move_ticket(sub2["data"]["id"], "done")

        # Verify parent tracks sub count
        parent_detail = te.get_ticket(pid)
        assert parent_detail["data"]["sub_ticket_count"] == 3
        assert len(parent_detail["data"]["sub_tickets"]) == 3


class TestEscalationChainIntegration:
    def test_blocked_ticket_full_escalation_flow(self, full_stack):
        """Ticket gets blocked → auto-escalated → supervisor resolves."""
        te = full_stack["te"]
        ee = full_stack["ee"]
        db = full_stack["db"]

        scout_id = get_agent_id_by_name(db, "Scout")
        triage_id = get_agent_id_by_name(db, "Triage Lead")

        # Scout creates ticket, starts work, gets blocked
        t = te.create_ticket(
            title="API Integration", assignee_id=scout_id, priority="high"
        )
        tid = t["data"]["id"]
        te.move_ticket(tid, "in_progress")
        te.update_ticket(tid, blocked_reason="Need API credentials")

        # Escalation engine detects and escalates
        result = ee.check_and_escalate()
        assert result["count"] == 1
        assert result["escalated"][0]["to_agent"] == "Triage Lead"

        # Verify ticket is now assigned to Triage Lead
        ticket = te.get_ticket(tid)
        assert ticket["data"]["assignee_id"] == triage_id
        assert ticket["data"]["escalated_to_id"] == triage_id

        # Triage Lead resolves it
        te.update_ticket(tid, blocked_reason=None)
        te.move_ticket(tid, "review")
        te.move_ticket(tid, "done")

        final = te.get_ticket(tid)
        assert final["data"]["status"] == "done"


class TestAgentTicketRequestIntegration:
    def test_agent_request_approve_deny(self, full_stack):
        """Agent requests ticket → Commander approves → Agent requests another → denied."""
        ee = full_stack["ee"]
        te = full_stack["te"]
        db = full_stack["db"]

        scout_id = get_agent_id_by_name(db, "Scout")
        commander_id = get_agent_id_by_name(db, "Commander")

        # Request 1: approved
        t1 = ee.process_ticket_request(scout_id, {
            "title": "Need a new scraping tool",
            "priority": "high",
        })
        assert t1["success"]
        assert t1["data"]["approval_status"] == "pending"

        approve = ee.approve_ticket_request(t1["data"]["id"], commander_id)
        assert approve["success"]

        # Request 2: denied
        t2 = ee.process_ticket_request(scout_id, {
            "title": "Want unlimited budget",
            "priority": "critical",
        })
        deny = ee.deny_ticket_request(t2["data"]["id"], commander_id, "Not approved")
        assert deny["success"]

        # Verify states
        ticket1 = te.get_ticket(t1["data"]["id"])
        assert ticket1["data"]["approval_status"] == "approved"
        ticket2 = te.get_ticket(t2["data"]["id"])
        assert ticket2["data"]["approval_status"] == "denied"
        assert ticket2["data"]["status"] == "done"  # Denied tickets are closed


class TestSprintWorkflowIntegration:
    def test_create_sprint_track_progress(self, full_stack):
        """Create sprint → assign tickets → complete some → check progress."""
        te = full_stack["te"]
        ts = full_stack["ts"]

        t1 = te.create_ticket(title="Sprint Task 1", priority="high")
        t2 = te.create_ticket(title="Sprint Task 2", priority="medium")
        t3 = te.create_ticket(title="Sprint Task 3", priority="low")

        start = datetime.utcnow()
        end = start + timedelta(days=14)
        ids = [t1["data"]["id"], t2["data"]["id"], t3["data"]["id"]]
        sprint = ts.create_sprint("Q1 Sprint", start, end, ids)
        assert sprint["success"]
        assert sprint["ticket_count"] == 3

        # Complete one task
        te.move_ticket(t1["data"]["id"], "done")
        te.move_ticket(t2["data"]["id"], "in_progress")

        progress = ts.get_sprint_progress("Q1 Sprint")
        assert progress["total"] == 3
        assert progress["done"] == 1
        assert progress["in_progress"] == 1
        assert progress["progress_pct"] == 33


class TestDueDateNotificationIntegration:
    def test_overdue_sends_messages(self, full_stack):
        """Overdue ticket triggers notification to assignee."""
        te = full_stack["te"]
        ts = full_stack["ts"]
        db = full_stack["db"]

        scout_id = get_agent_id_by_name(db, "Scout")
        past = datetime.utcnow() - timedelta(hours=2)
        te.create_ticket(title="Late task", due_date=past, assignee_id=scout_id)

        # Check due dates
        result = ts.check_due_dates()
        assert result["overdue_count"] == 1

        # Send notifications
        notif = ts.send_due_date_notifications(result["notifications"])
        assert notif["sent"] == 1

        # Verify message was sent to Scout
        with db.session_scope() as s:
            msgs = s.query(AgentMessage).filter_by(to_agent_id=scout_id).all()
            overdue_msgs = [m for m in msgs if m.message_type == "ticket_overdue"]
            assert len(overdue_msgs) >= 1


class TestDependencyBlockingIntegration:
    def test_dependency_blocks_and_unblocks(self, full_stack):
        """Ticket A depends on B → A is blocked → B completes → A unblocked."""
        te = full_stack["te"]

        a = te.create_ticket(title="Waiting ticket")
        b = te.create_ticket(title="Prerequisite")
        te.add_dependency(a["data"]["id"], b["data"]["id"])

        # A should be blocked
        blocked = te.check_blocked(a["data"]["id"])
        assert blocked["is_blocked"] is True
        assert blocked["blockers"][0]["title"] == "Prerequisite"

        # Complete B
        te.move_ticket(b["data"]["id"], "done")

        # A should no longer be blocked
        blocked = te.check_blocked(a["data"]["id"])
        assert blocked["is_blocked"] is False


class TestStatsIntegration:
    def test_stats_reflect_full_board_state(self, full_stack):
        """Stats accurately count tickets across all statuses."""
        te = full_stack["te"]

        # Create tickets in various states
        te.create_ticket(title="Backlog 1")
        te.create_ticket(title="Backlog 2", priority="critical")
        t3 = te.create_ticket(title="In Progress")
        te.move_ticket(t3["data"]["id"], "in_progress")
        t4 = te.create_ticket(title="Done", due_date=datetime.utcnow() - timedelta(hours=1))
        te.move_ticket(t4["data"]["id"], "done")
        te.create_ticket(
            title="Overdue",
            due_date=datetime.utcnow() - timedelta(hours=1),
            priority="high",
        )

        stats = te.get_ticket_stats()
        assert stats["data"]["total"] == 5
        assert stats["data"]["by_status"]["backlog"] == 3  # 2 new + 1 overdue
        assert stats["data"]["by_status"]["in_progress"] == 1
        assert stats["data"]["by_status"]["done"] == 1
        assert stats["data"]["overdue"] == 1  # Only the not-done overdue
        assert stats["data"]["by_priority"]["critical"] == 1
        assert stats["data"]["by_priority"]["high"] == 1


class TestFleetWithTicketsIntegration:
    def test_fleet_boot_then_ticket_ops(self, full_stack):
        """Fleet boots → agents create tickets → verify everything works."""
        fo = full_stack["fo"]
        te = full_stack["te"]
        ee = full_stack["ee"]
        db = full_stack["db"]

        # Boot the fleet
        boot = fo.boot_fleet()
        assert boot["data"]["booted"] == 19

        # Commander creates a ticket
        commander_id = get_agent_id_by_name(db, "Commander")
        t = te.create_ticket(
            title="Fleet-created ticket",
            reporter_id=commander_id,
            reporter_type="agent",
        )
        assert t["success"]

        # Fleet health check should still be OK
        oe = full_stack["oe"]
        health = oe.run_fleet_health_check()
        assert health["data"]["health_pct"] == 100
