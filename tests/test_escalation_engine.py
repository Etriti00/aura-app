"""
Tests for core/escalation_engine.py — blocked ticket detection, escalation chain,
ticket request flow, auto-evaluate, approval/denial, supervisor chain.
"""

import pytest
from datetime import datetime
from database.schema import Agent, AgentTicket, AgentMessage
from tests.conftest import get_agent_id_by_name


class TestCheckAndEscalate:
    def test_escalates_blocked_ticket(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        t = te.create_ticket(
            title="Blocked task", assignee_id=scout_id, priority="high"
        )
        ticket_id = t["data"]["id"]
        te.move_ticket(ticket_id, "in_progress")
        te.update_ticket(ticket_id, blocked_reason="Need API access")

        result = ee.check_and_escalate()
        assert result["success"] is True
        assert result["count"] == 1
        assert result["escalated"][0]["from_agent"] == "Scout"
        assert result["escalated"][0]["to_agent"] == "Triage Lead"

    def test_does_not_escalate_already_escalated(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        triage_id = get_agent_id_by_name(db, "Triage Lead")
        t = te.create_ticket(title="Already escalated", assignee_id=scout_id)
        ticket_id = t["data"]["id"]
        te.move_ticket(ticket_id, "in_progress")
        te.update_ticket(ticket_id, blocked_reason="Stuck", escalated_to_id=triage_id)

        result = ee.check_and_escalate()
        assert result["count"] == 0

    def test_does_not_escalate_without_assignee(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        t = te.create_ticket(title="No assignee")
        te.move_ticket(t["data"]["id"], "in_progress")
        te.update_ticket(t["data"]["id"], blocked_reason="Stuck")
        result = ee.check_and_escalate()
        assert result["count"] == 0

    def test_does_not_escalate_non_in_progress(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        t = te.create_ticket(title="Not in progress", assignee_id=scout_id)
        te.update_ticket(t["data"]["id"], blocked_reason="Stuck")
        result = ee.check_and_escalate()
        assert result["count"] == 0

    def test_escalation_creates_comment(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        t = te.create_ticket(title="Comment test", assignee_id=scout_id)
        ticket_id = t["data"]["id"]
        te.move_ticket(ticket_id, "in_progress")
        te.update_ticket(ticket_id, blocked_reason="Need help")
        ee.check_and_escalate()

        comments = te.get_comments(ticket_id)
        escalation_comments = [
            c for c in comments["data"] if c["comment_type"] == "escalation"
        ]
        assert len(escalation_comments) >= 1

    def test_escalation_creates_agent_message(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        triage_id = get_agent_id_by_name(db, "Triage Lead")
        t = te.create_ticket(title="Message test", assignee_id=scout_id)
        ticket_id = t["data"]["id"]
        te.move_ticket(ticket_id, "in_progress")
        te.update_ticket(ticket_id, blocked_reason="Blocked")
        ee.check_and_escalate()

        with db.session_scope() as s:
            msgs = s.query(AgentMessage).filter_by(
                to_agent_id=triage_id, message_type="escalation"
            ).all()
            assert len(msgs) >= 1

    def test_escalation_reassigns_ticket(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        triage_id = get_agent_id_by_name(db, "Triage Lead")
        t = te.create_ticket(title="Reassign", assignee_id=scout_id)
        ticket_id = t["data"]["id"]
        te.move_ticket(ticket_id, "in_progress")
        te.update_ticket(ticket_id, blocked_reason="Stuck")
        ee.check_and_escalate()

        ticket = te.get_ticket(ticket_id)
        assert ticket["data"]["assignee_id"] == triage_id
        assert ticket["data"]["escalated_to_id"] == triage_id


class TestManualEscalation:
    def test_escalate_ticket(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        commander_id = get_agent_id_by_name(db, "Commander")
        t = te.create_ticket(title="Manual escalate", assignee_id=scout_id)
        result = ee.escalate_ticket(
            t["data"]["id"], scout_id, commander_id, "Need Commander help"
        )
        assert result["success"] is True

    def test_escalate_nonexistent_ticket(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        result = ee.escalate_ticket(99999, 1, 2, "reason")
        assert result["success"] is False


class TestTicketRequestFlow:
    def test_auto_approved_self_assignment(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        result = ee.process_ticket_request(scout_id, {
            "title": "My own task",
            "assignee_id": scout_id,
            "priority": "medium",
        })
        assert result["success"] is True
        assert result["data"]["approval_status"] == "approved"

    def test_auto_approved_sub_ticket_own_assignment(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        parent = te.create_ticket(title="Parent", assignee_id=scout_id)
        result = ee.process_ticket_request(scout_id, {
            "title": "Sub-task",
            "parent_ticket_id": parent["data"]["id"],
            "priority": "medium",
        })
        assert result["success"] is True
        assert result["data"]["approval_status"] == "approved"

    def test_auto_approved_low_priority_unassigned(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        result = ee.process_ticket_request(scout_id, {
            "title": "Low priority note",
            "priority": "low",
        })
        assert result["success"] is True
        assert result["data"]["approval_status"] == "approved"

    def test_critical_needs_approval(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        result = ee.process_ticket_request(scout_id, {
            "title": "Critical issue",
            "priority": "critical",
        })
        assert result["success"] is True
        assert result["data"]["approval_status"] == "pending"

    def test_pending_notifies_commander(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        commander_id = get_agent_id_by_name(db, "Commander")
        ee.process_ticket_request(scout_id, {
            "title": "Needs approval",
            "priority": "high",
        })
        with db.session_scope() as s:
            msgs = s.query(AgentMessage).filter_by(
                to_agent_id=commander_id, message_type="ticket_request"
            ).all()
            assert len(msgs) >= 1


class TestApproveAndDeny:
    def test_approve_pending_ticket(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        commander_id = get_agent_id_by_name(db, "Commander")
        t = ee.process_ticket_request(scout_id, {
            "title": "Approve me", "priority": "high",
        })
        ticket_id = t["data"]["id"]
        result = ee.approve_ticket_request(ticket_id, commander_id)
        assert result["success"] is True

        ticket = te.get_ticket(ticket_id)
        assert ticket["data"]["approval_status"] == "approved"
        assert ticket["data"]["approved_by_id"] == commander_id

    def test_deny_pending_ticket(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        commander_id = get_agent_id_by_name(db, "Commander")
        t = ee.process_ticket_request(scout_id, {
            "title": "Deny me", "priority": "high",
        })
        ticket_id = t["data"]["id"]
        result = ee.deny_ticket_request(ticket_id, commander_id, "Not needed")
        assert result["success"] is True

        ticket = te.get_ticket(ticket_id)
        assert ticket["data"]["approval_status"] == "denied"
        assert ticket["data"]["status"] == "done"

    def test_approve_non_pending_fails(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        t = te.create_ticket(title="Not pending")
        commander_id = get_agent_id_by_name(db, "Commander")
        result = ee.approve_ticket_request(t["data"]["id"], commander_id)
        assert result["success"] is False

    def test_deny_non_pending_fails(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        t = te.create_ticket(title="Not pending")
        commander_id = get_agent_id_by_name(db, "Commander")
        result = ee.deny_ticket_request(t["data"]["id"], commander_id)
        assert result["success"] is False


class TestAutoEvaluate:
    def test_critical_always_needs_approval(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        result = ee.auto_evaluate_ticket_request(scout_id, {"priority": "critical"})
        assert result["auto_approved"] is False

    def test_self_assignment_auto_approved(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        result = ee.auto_evaluate_ticket_request(
            scout_id, {"assignee_id": scout_id, "priority": "medium"}
        )
        assert result["auto_approved"] is True

    def test_low_unassigned_auto_approved(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        result = ee.auto_evaluate_ticket_request(
            scout_id, {"priority": "low"}
        )
        assert result["auto_approved"] is True

    def test_high_priority_needs_approval(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        result = ee.auto_evaluate_ticket_request(
            scout_id, {"priority": "high"}
        )
        assert result["auto_approved"] is False


class TestSupervisorChain:
    def test_scout_chain(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        chain = ee.get_supervisor_chain(scout_id)
        names = [c["name"] for c in chain]
        assert names == ["Scout", "Triage Lead", "Commander"]

    def test_commander_chain(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        commander_id = get_agent_id_by_name(db, "Commander")
        chain = ee.get_supervisor_chain(commander_id)
        assert len(chain) == 1
        assert chain[0]["name"] == "Commander"

    def test_trend_spotter_chain(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        ts_id = get_agent_id_by_name(db, "Trend Spotter")
        chain = ee.get_supervisor_chain(ts_id)
        names = [c["name"] for c in chain]
        assert names == ["Trend Spotter", "Analyst", "Commander"]

    def test_nonexistent_agent_chain(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        chain = ee.get_supervisor_chain(99999)
        assert chain == []


class TestPendingRequests:
    def test_get_pending_requests(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        ee.process_ticket_request(scout_id, {
            "title": "Pending 1", "priority": "high",
        })
        ee.process_ticket_request(scout_id, {
            "title": "Pending 2", "priority": "critical",
        })
        result = ee.get_pending_requests()
        assert result["success"] is True
        assert len(result["data"]) == 2

    def test_approved_not_in_pending(self, escalation_engine):
        ee, te, ae, db = escalation_engine
        scout_id = get_agent_id_by_name(db, "Scout")
        commander_id = get_agent_id_by_name(db, "Commander")
        t = ee.process_ticket_request(scout_id, {
            "title": "Will approve", "priority": "high",
        })
        ee.approve_ticket_request(t["data"]["id"], commander_id)
        result = ee.get_pending_requests()
        assert len(result["data"]) == 0
