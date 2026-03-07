"""
Tests for the Autonomy Controller — permission checks, level management,
approval queue, approve/deny flow.
"""

import pytest

from database.schema import PendingApproval, Settings
from config import AutonomyLevel


# ─── Schema Tests ──────────────────────────────────────────────


class TestSchema:

    def test_pending_approval_creation(self, autonomy_controller):
        ctrl, db = autonomy_controller
        with db.session_scope() as s:
            a = PendingApproval(
                action_type="send_email",
                action_description="Send cold email to Lead 42",
            )
            s.add(a)
            s.flush()
            assert a.id is not None
            assert a.status == "pending"


# ─── Permission Checking ──────────────────────────────────────


class TestPermissionChecking:

    def test_observer_blocks_everything(self, autonomy_controller):
        ctrl, db = autonomy_controller
        result = ctrl.check_permission("send_email", autonomy_level="observer")
        assert result["success"] is True
        assert result["data"]["allowed"] is False
        assert result["data"]["needs_approval"] is True

    def test_supervised_blocks_send_email(self, autonomy_controller):
        ctrl, db = autonomy_controller
        result = ctrl.check_permission("send_email", autonomy_level="supervised")
        assert result["data"]["allowed"] is False
        assert result["data"]["needs_approval"] is True

    def test_supervised_allows_scrape(self, autonomy_controller):
        ctrl, db = autonomy_controller
        result = ctrl.check_permission("scrape_leads", autonomy_level="supervised")
        assert result["data"]["allowed"] is True
        assert result["data"]["needs_approval"] is False

    def test_autonomous_allows_email(self, autonomy_controller):
        ctrl, db = autonomy_controller
        result = ctrl.check_permission("send_email", autonomy_level="autonomous")
        assert result["data"]["allowed"] is True

    def test_autonomous_blocks_skill_revision(self, autonomy_controller):
        ctrl, db = autonomy_controller
        result = ctrl.check_permission("skill_revision", autonomy_level="autonomous")
        assert result["data"]["allowed"] is False

    def test_full_trust_allows_all(self, autonomy_controller):
        ctrl, db = autonomy_controller
        result = ctrl.check_permission("send_email", autonomy_level="full_trust")
        assert result["data"]["allowed"] is True
        result2 = ctrl.check_permission("skill_revision", autonomy_level="full_trust")
        assert result2["data"]["allowed"] is True


# ─── Level Management ─────────────────────────────────────────


class TestLevelManagement:

    def test_get_default_level(self, autonomy_controller):
        ctrl, db = autonomy_controller
        result = ctrl.get_autonomy_level()
        assert result["success"] is True
        assert result["data"]["level"] == "supervised"

    def test_set_level(self, autonomy_controller):
        ctrl, db = autonomy_controller
        result = ctrl.set_autonomy_level("autonomous")
        assert result["success"] is True
        assert result["data"]["level"] == "autonomous"

        # Verify persisted
        check = ctrl.get_autonomy_level()
        assert check["data"]["level"] == "autonomous"

        # Reset
        ctrl.set_autonomy_level("supervised")

    def test_set_invalid_level(self, autonomy_controller):
        ctrl, db = autonomy_controller
        result = ctrl.set_autonomy_level("mega_trust")
        assert result["success"] is False
        assert "Invalid level" in result["error"]


# ─── Approval Queue ───────────────────────────────────────────


class TestApprovalQueue:

    def test_queue_for_approval(self, autonomy_controller):
        ctrl, db = autonomy_controller
        result = ctrl.queue_for_approval(
            "send_email", description="Cold email to Joe's Plumbing",
            payload={"lead_id": 42, "subject": "Hello!"},
        )
        assert result["success"] is True
        assert "approval_id" in result["data"]

    def test_get_pending_approvals(self, autonomy_controller):
        ctrl, db = autonomy_controller
        ctrl.queue_for_approval("generate_email", description="Test 1")
        ctrl.queue_for_approval("send_email", description="Test 2")

        result = ctrl.get_pending_approvals()
        assert result["success"] is True
        assert len(result["data"]) >= 2

    def test_approve_action(self, autonomy_controller):
        ctrl, db = autonomy_controller
        q = ctrl.queue_for_approval("send_email", description="Approve me")
        approval_id = q["data"]["approval_id"]

        result = ctrl.approve_action(approval_id)
        assert result["success"] is True
        assert result["data"]["status"] == "approved"

    def test_deny_action(self, autonomy_controller):
        ctrl, db = autonomy_controller
        q = ctrl.queue_for_approval("skill_revision", description="Deny me")
        approval_id = q["data"]["approval_id"]

        result = ctrl.deny_action(approval_id)
        assert result["success"] is True
        assert result["data"]["status"] == "denied"

    def test_cannot_resolve_twice(self, autonomy_controller):
        ctrl, db = autonomy_controller
        q = ctrl.queue_for_approval("send_email", description="Double resolve")
        approval_id = q["data"]["approval_id"]

        ctrl.approve_action(approval_id)
        result = ctrl.approve_action(approval_id)
        assert result["success"] is False
        assert "already" in result["error"]

    def test_nonexistent_approval(self, autonomy_controller):
        ctrl, db = autonomy_controller
        result = ctrl.approve_action(99999)
        assert result["success"] is False
