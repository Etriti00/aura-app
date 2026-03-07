"""
Tests for core/command_history.py — logging, querying, tree building,
agent context, statistics, and pruning.
"""

import pytest
from datetime import datetime, timedelta
from database.schema import CommandLog, Agent
from tests.conftest import get_agent_id_by_name


class TestCommandLogging:
    def test_log_user_command(self, command_history):
        engine, db = command_history
        result = engine.log_user_command(source="chat", text="Show stats")
        assert result["success"] is True
        assert result["data"]["id"] > 0
        assert result["data"]["correlation_id"] is not None

    def test_log_user_command_with_sender(self, command_history):
        engine, db = command_history
        result = engine.log_user_command(
            source="telegram", text="Start campaign",
            sender_id="12345", display_name="John",
        )
        assert result["success"] is True
        # Verify persisted data
        cmd = engine.get_command(result["data"]["id"])
        assert cmd["data"]["source"] == "telegram"
        assert cmd["data"]["source_sender_id"] == "12345"
        assert cmd["data"]["source_display_name"] == "John"

    def test_log_agent_action_as_child(self, command_history):
        engine, db = command_history
        agent_id = get_agent_id_by_name(db, "Scout")
        root = engine.log_user_command(source="chat", text="Scrape leads")
        root_id = root["data"]["id"]
        child = engine.log_agent_action(
            parent_command_id=root_id,
            agent_id=agent_id,
            command_type="task_dispatched",
            parameters={"task_type": "scrape_leads"},
            status="completed",
        )
        assert child["success"] is True
        assert child["data"]["parent_command_id"] == root_id

    def test_correlation_id_inherited(self, command_history):
        engine, db = command_history
        agent_id = get_agent_id_by_name(db, "Scout")
        root = engine.log_user_command(source="chat", text="Test")
        corr_id = root["data"]["correlation_id"]
        child = engine.log_agent_action(
            parent_command_id=root["data"]["id"],
            agent_id=agent_id,
            command_type="task_dispatched",
        )
        assert child["data"]["correlation_id"] == corr_id

    def test_log_command_all_fields(self, command_history):
        engine, db = command_history
        agent_id = get_agent_id_by_name(db, "Commander")
        result = engine.log_command(
            source="discord",
            command_type="escalation",
            command_text="Escalate ticket",
            actor_type="agent",
            agent_id=agent_id,
            intent="escalate_ticket",
            parameters={"ticket_id": 1},
            result={"escalated_to": "Commander"},
            status="completed",
            cost_usd=0.05,
            tokens_used=500,
            source_sender_id="discord_user_1",
        )
        assert result["success"] is True
        cmd = engine.get_command(result["data"]["id"])
        assert cmd["data"]["source"] == "discord"
        assert cmd["data"]["command_type"] == "escalation"
        assert cmd["data"]["agent_name"] == "Commander"
        assert cmd["data"]["cost_usd"] == 0.05
        assert cmd["data"]["tokens_used"] == 500

    def test_log_command_generates_unique_correlation_ids(self, command_history):
        engine, db = command_history
        r1 = engine.log_user_command(source="chat", text="Command 1")
        r2 = engine.log_user_command(source="chat", text="Command 2")
        assert r1["data"]["correlation_id"] != r2["data"]["correlation_id"]


class TestCommandStatusUpdate:
    def test_update_to_completed(self, command_history):
        engine, db = command_history
        root = engine.log_user_command(source="chat", text="Test")
        result = engine.update_command_status(
            root["data"]["id"], "completed",
            result={"output": "done"},
            cost_usd=0.01, tokens_used=100,
        )
        assert result["success"] is True
        assert result["data"]["status"] == "completed"

    def test_update_computes_duration(self, command_history):
        engine, db = command_history
        root = engine.log_user_command(source="chat", text="Test")
        result = engine.update_command_status(root["data"]["id"], "completed")
        assert result["success"] is True
        assert result["data"]["duration_ms"] is not None
        assert result["data"]["duration_ms"] >= 0

    def test_update_to_failed(self, command_history):
        engine, db = command_history
        root = engine.log_user_command(source="chat", text="Test")
        result = engine.update_command_status(
            root["data"]["id"], "failed",
            result={"error": "Something went wrong"},
        )
        assert result["success"] is True
        assert result["data"]["status"] == "failed"

    def test_update_nonexistent(self, command_history):
        engine, db = command_history
        result = engine.update_command_status(99999, "completed")
        assert result["success"] is False

    def test_update_accumulates_cost(self, command_history):
        engine, db = command_history
        root = engine.log_command(
            source="chat", command_type="user_command",
            status="running", cost_usd=0.01,
        )
        cmd_id = root["data"]["id"]
        engine.update_command_status(cmd_id, "completed", cost_usd=0.02)
        cmd = engine.get_command(cmd_id)
        assert cmd["data"]["cost_usd"] == pytest.approx(0.03, abs=0.001)


class TestCommandTree:
    def test_get_tree_single_node(self, command_history):
        engine, db = command_history
        root = engine.log_user_command(source="chat", text="Test")
        tree = engine.get_command_tree(root["data"]["id"])
        assert tree["success"] is True
        assert tree["data"]["id"] == root["data"]["id"]
        assert tree["data"]["children"] == []

    def test_get_tree_with_children(self, command_history):
        engine, db = command_history
        agent_id = get_agent_id_by_name(db, "Scout")
        root = engine.log_user_command(source="chat", text="Complex command")
        root_id = root["data"]["id"]
        engine.log_agent_action(
            parent_command_id=root_id, agent_id=agent_id,
            command_type="task_dispatched",
        )
        engine.log_agent_action(
            parent_command_id=root_id, agent_id=agent_id,
            command_type="task_completed",
        )
        tree = engine.get_command_tree(root_id)
        assert tree["success"] is True
        assert len(tree["data"]["children"]) == 2

    def test_get_tree_nested_3_levels(self, command_history):
        engine, db = command_history
        agent_id = get_agent_id_by_name(db, "Scout")
        root = engine.log_user_command(source="chat", text="Pipeline")
        root_id = root["data"]["id"]
        child = engine.log_agent_action(
            parent_command_id=root_id,
            agent_id=agent_id, command_type="task_dispatched",
        )
        child_id = child["data"]["id"]
        engine.log_agent_action(
            parent_command_id=child_id,
            agent_id=agent_id, command_type="delegation",
        )
        tree = engine.get_command_tree(root_id)
        assert len(tree["data"]["children"]) == 1
        assert len(tree["data"]["children"][0]["children"]) == 1

    def test_get_tree_nonexistent(self, command_history):
        engine, db = command_history
        tree = engine.get_command_tree(99999)
        assert tree["success"] is False


class TestCommandQuery:
    def test_get_history_empty(self, command_history):
        engine, db = command_history
        result = engine.get_history()
        assert result["success"] is True
        assert result["data"]["items"] == []
        assert result["data"]["total"] == 0

    def test_get_history_paginated(self, command_history):
        engine, db = command_history
        for i in range(15):
            engine.log_user_command(source="chat", text=f"Command {i}")
        result = engine.get_history(page=1, page_size=10)
        assert len(result["data"]["items"]) == 10
        assert result["data"]["total"] == 15
        assert result["data"]["pages"] == 2
        # Page 2
        result2 = engine.get_history(page=2, page_size=10)
        assert len(result2["data"]["items"]) == 5

    def test_filter_by_source(self, command_history):
        engine, db = command_history
        engine.log_user_command(source="chat", text="Chat cmd")
        engine.log_user_command(source="telegram", text="TG cmd")
        result = engine.get_history(source="telegram")
        assert len(result["data"]["items"]) == 1
        assert result["data"]["items"][0]["source"] == "telegram"

    def test_filter_by_agent(self, command_history):
        engine, db = command_history
        agent_id = get_agent_id_by_name(db, "Scout")
        root = engine.log_user_command(source="chat", text="Test")
        engine.log_agent_action(
            parent_command_id=root["data"]["id"],
            agent_id=agent_id, command_type="task_dispatched",
        )
        result = engine.get_history(agent_id=agent_id, root_only=False)
        assert len(result["data"]["items"]) == 1

    def test_filter_by_status(self, command_history):
        engine, db = command_history
        root = engine.log_user_command(source="chat", text="Pending")
        engine.update_command_status(root["data"]["id"], "completed")
        engine.log_user_command(source="chat", text="Still pending")
        result = engine.get_history(status="pending")
        assert len(result["data"]["items"]) == 1

    def test_search_text(self, command_history):
        engine, db = command_history
        engine.log_user_command(source="chat", text="Start campaign for dentists in NYC")
        engine.log_user_command(source="chat", text="Show stats")
        result = engine.get_history(search_text="dentists")
        assert len(result["data"]["items"]) == 1

    def test_root_only_filter(self, command_history):
        engine, db = command_history
        agent_id = get_agent_id_by_name(db, "Scout")
        root = engine.log_user_command(source="chat", text="Root")
        engine.log_agent_action(
            parent_command_id=root["data"]["id"],
            agent_id=agent_id, command_type="task_dispatched",
        )
        result = engine.get_history(root_only=True)
        assert len(result["data"]["items"]) == 1

    def test_get_command_single(self, command_history):
        engine, db = command_history
        root = engine.log_user_command(source="chat", text="Single")
        cmd = engine.get_command(root["data"]["id"])
        assert cmd["success"] is True
        assert cmd["data"]["command_text"] == "Single"
        assert cmd["data"]["actor_type"] == "user"

    def test_get_command_nonexistent(self, command_history):
        engine, db = command_history
        cmd = engine.get_command(99999)
        assert cmd["success"] is False

    def test_history_ordered_newest_first(self, command_history):
        engine, db = command_history
        engine.log_user_command(source="chat", text="First")
        engine.log_user_command(source="chat", text="Second")
        result = engine.get_history()
        items = result["data"]["items"]
        assert items[0]["command_text"] == "Second"
        assert items[1]["command_text"] == "First"


class TestAgentContext:
    def test_get_recent_for_agent_context(self, command_history):
        engine, db = command_history
        for i in range(5):
            engine.log_user_command(source="chat", text=f"Command {i}")
        result = engine.get_recent_for_agent_context(limit=3)
        assert result["success"] is True
        assert isinstance(result["data"], str)
        assert len(result["data"]) > 0

    def test_agent_context_contains_commands(self, command_history):
        engine, db = command_history
        engine.log_user_command(source="telegram", text="Check leads")
        result = engine.get_recent_for_agent_context(limit=5)
        assert "Check leads" in result["data"]
        assert "telegram" in result["data"]

    def test_agent_context_empty_returns_empty_string(self, command_history):
        engine, db = command_history
        result = engine.get_recent_for_agent_context(limit=5)
        assert result["success"] is True
        assert result["data"] == ""


class TestStats:
    def test_get_stats_empty(self, command_history):
        engine, db = command_history
        result = engine.get_stats()
        assert result["success"] is True
        assert result["data"]["total"] == 0

    def test_get_stats_with_data(self, command_history):
        engine, db = command_history
        engine.log_user_command(source="chat", text="Test 1")
        engine.log_user_command(source="telegram", text="Test 2")
        result = engine.get_stats()
        assert result["success"] is True
        assert result["data"]["total"] == 2
        assert "chat" in result["data"]["by_source"]
        assert "telegram" in result["data"]["by_source"]

    def test_stats_success_rate(self, command_history):
        engine, db = command_history
        r1 = engine.log_user_command(source="chat", text="Success")
        r2 = engine.log_user_command(source="chat", text="Fail")
        engine.update_command_status(r1["data"]["id"], "completed")
        engine.update_command_status(r2["data"]["id"], "failed")
        result = engine.get_stats()
        assert result["data"]["success_rate"] == 50.0

    def test_stats_today_count(self, command_history):
        engine, db = command_history
        engine.log_user_command(source="chat", text="Today cmd")
        result = engine.get_stats()
        assert result["data"]["today"] >= 1


class TestPrune:
    def test_prune_old_entries(self, command_history):
        engine, db = command_history
        # Create an old entry
        with db.session_scope() as session:
            old = CommandLog(
                source="chat", command_type="user_command",
                command_text="Old entry", actor_type="user",
                status="completed",
                created_at=datetime.utcnow() - timedelta(days=100),
            )
            session.add(old)
        result = engine.prune_old_entries(days=90)
        assert result["success"] is True
        assert result["deleted"] >= 1

    def test_prune_keeps_recent(self, command_history):
        engine, db = command_history
        engine.log_user_command(source="chat", text="Recent")
        result = engine.prune_old_entries(days=90)
        assert result["success"] is True
        assert result["deleted"] == 0

    def test_prune_with_tree(self, command_history):
        engine, db = command_history
        # Create old root + old child
        with db.session_scope() as session:
            old_time = datetime.utcnow() - timedelta(days=100)
            root = CommandLog(
                source="chat", command_type="user_command",
                command_text="Old root", actor_type="user",
                status="completed", created_at=old_time,
                correlation_id="old-test-id",
            )
            session.add(root)
            session.flush()
            child = CommandLog(
                source="system", command_type="task_dispatched",
                actor_type="agent", status="completed",
                parent_command_id=root.id, created_at=old_time,
                correlation_id="old-test-id",
            )
            session.add(child)
        result = engine.prune_old_entries(days=90)
        assert result["deleted"] >= 2


class TestCommandHistoryController:
    """Test the controller signal-based interface."""

    def test_controller_refresh_history(self, command_history, qapp):
        engine, db = command_history
        from controllers.command_history_controller import CommandHistoryController
        ctrl = CommandHistoryController(db, engine)

        received = []
        ctrl.history_ready.connect(lambda d: received.append(d))
        ctrl.refresh_history()
        assert len(received) == 1
        assert "items" in received[0]
        assert "total" in received[0]

    def test_controller_get_command_tree(self, command_history, qapp):
        engine, db = command_history
        from controllers.command_history_controller import CommandHistoryController
        ctrl = CommandHistoryController(db, engine)

        root = engine.log_user_command(source="chat", text="Test tree")

        received = []
        ctrl.command_tree_ready.connect(lambda d: received.append(d))
        ctrl.get_command_tree(root["data"]["id"])
        assert len(received) == 1
        assert received[0]["id"] == root["data"]["id"]

    def test_controller_error_on_bad_tree(self, command_history, qapp):
        engine, db = command_history
        from controllers.command_history_controller import CommandHistoryController
        ctrl = CommandHistoryController(db, engine)

        errors = []
        ctrl.error.connect(lambda msg: errors.append(msg))
        ctrl.get_command_tree(99999)
        assert len(errors) == 1

    def test_controller_refresh_stats(self, command_history, qapp):
        engine, db = command_history
        from controllers.command_history_controller import CommandHistoryController
        ctrl = CommandHistoryController(db, engine)

        engine.log_user_command(source="chat", text="Stats test")

        received = []
        ctrl.stats_ready.connect(lambda d: received.append(d))
        ctrl.refresh_stats()
        assert len(received) == 1
        assert received[0]["total"] >= 1

    def test_controller_prune(self, command_history, qapp):
        engine, db = command_history
        from controllers.command_history_controller import CommandHistoryController
        ctrl = CommandHistoryController(db, engine)

        received = []
        ctrl.prune_complete.connect(lambda n: received.append(n))
        ctrl.prune_history(days=90)
        assert len(received) == 1
        assert received[0] == 0  # nothing old to prune

    def test_controller_get_agents_list(self, command_history, qapp):
        engine, db = command_history
        from controllers.command_history_controller import CommandHistoryController
        ctrl = CommandHistoryController(db, engine)
        agents = ctrl.get_agents_list()
        assert len(agents) == 19
        assert all("id" in a and "name" in a for a in agents)
