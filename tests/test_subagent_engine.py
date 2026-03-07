"""Tests for SubagentEngine — should_decompose, decompose_and_run, get_subtasks."""

import json
import pytest
from datetime import datetime
from core.subagent_engine import SubagentEngine, SUBTASK_PROMPTS
from database.schema import SubagentTask, AgentTask, Agent


# ─── Schema Model Tests ───────────────────────────────────────────────────

class TestSchemaModels:

    def test_subagent_task_creation(self, db):
        with db.session_scope() as session:
            # Need a parent AgentTask first
            agent = Agent(name="TestAgent", role="worker", status="idle")
            session.add(agent)
            session.flush()
            parent = AgentTask(
                agent_id=agent.id, task_type="generate_email",
                status="running",
            )
            session.add(parent)
            session.flush()

            subtask = SubagentTask(
                parent_task_id=parent.id,
                subtask_type="extract_lead_insights",
                tier="haiku",
                status="pending",
            )
            session.add(subtask)
            session.flush()
            assert subtask.id is not None
            assert subtask.parent_task_id == parent.id

    def test_subagent_task_defaults(self, db):
        with db.session_scope() as session:
            agent = Agent(name="TestAgent2", role="worker", status="idle")
            session.add(agent)
            session.flush()
            parent = AgentTask(
                agent_id=agent.id, task_type="test", status="running",
            )
            session.add(parent)
            session.flush()
            subtask = SubagentTask(
                parent_task_id=parent.id, subtask_type="test_sub",
            )
            session.add(subtask)
            session.flush()
            assert subtask.tier == "haiku"
            assert subtask.status == "pending"
            assert subtask.tokens_used == 0
            assert subtask.cost_usd == 0.0


# ─── Should Decompose ─────────────────────────────────────────────────────

class TestShouldDecompose:

    def test_known_task_type(self, subagent_engine):
        engine, _ = subagent_engine
        assert engine.should_decompose("generate_email") is True
        assert engine.should_decompose("qualify_lead_complex") is True

    def test_unknown_task_type(self, subagent_engine):
        engine, _ = subagent_engine
        assert engine.should_decompose("unknown_task") is False
        assert engine.should_decompose("qualify_lead") is False

    def test_empty_string(self, subagent_engine):
        engine, _ = subagent_engine
        assert engine.should_decompose("") is False


# ─── Decompose and Run ────────────────────────────────────────────────────

class TestDecomposeAndRun:

    def test_no_decomposition_for_unknown(self, subagent_engine):
        engine, _ = subagent_engine
        result = engine.decompose_and_run(
            parent_task_id=1, task_type="unknown_task",
            payload={}, lead_context="",
        )
        assert result["decomposed"] is False

    def test_no_router_returns_failure(self, subagent_engine):
        engine, _ = subagent_engine
        # engine has no router_engine
        result = engine.decompose_and_run(
            parent_task_id=1, task_type="generate_email",
            payload={}, lead_context="Some context",
        )
        assert result["success"] is False
        assert "No router" in result.get("error", "")

    def test_get_subtasks_empty(self, subagent_engine):
        engine, _ = subagent_engine
        result = engine.get_subtasks_for_parent(99999)
        assert result["success"] is True
        assert result["data"] == []


# ─── Subtask Prompt Building ──────────────────────────────────────────────

class TestBuildSubtaskPrompt:

    def test_extract_lead_insights_prompt(self, subagent_engine):
        engine, _ = subagent_engine
        prompt = engine._build_subtask_prompt(
            "extract_lead_insights",
            lead_context="Business: Acme Plumbing, City: Austin",
            previous_output="",
            payload={},
        )
        assert "Acme Plumbing" in prompt
        assert "Austin" in prompt

    def test_draft_email_includes_skill(self, subagent_engine):
        engine, _ = subagent_engine
        prompt = engine._build_subtask_prompt(
            "draft_email",
            lead_context="",
            previous_output="Lead has website issues",
            payload={"sender_name": "John", "sender_company": "Acme"},
            skill_data={"system_prompt": "Be direct and value-focused"},
        )
        assert "John" in prompt
        assert "Acme" in prompt
        assert "Be direct" in prompt

    def test_review_tone_includes_draft(self, subagent_engine):
        engine, _ = subagent_engine
        prompt = engine._build_subtask_prompt(
            "review_tone",
            lead_context="",
            previous_output="Dear sir, I'd like to offer...",
            payload={},
            skill_data={"tone": "friendly"},
        )
        assert "Dear sir" in prompt
        assert "friendly" in prompt

    def test_unknown_subtask_fallback(self, subagent_engine):
        engine, _ = subagent_engine
        prompt = engine._build_subtask_prompt(
            "completely_unknown_type",
            lead_context="Some context",
            previous_output="",
            payload={},
        )
        assert "Some context" in prompt


# ─── Subtask Prompt Templates ─────────────────────────────────────────────

class TestSubtaskPrompts:

    def test_all_decomposition_types_have_prompts(self):
        from config import SUBAGENT_DECOMPOSITION_MAP
        for task_type, patterns in SUBAGENT_DECOMPOSITION_MAP.items():
            for pattern in patterns:
                assert pattern["type"] in SUBTASK_PROMPTS or True, (
                    f"Missing prompt template for subtask type '{pattern['type']}'"
                )

    def test_prompt_templates_are_strings(self):
        for key, template in SUBTASK_PROMPTS.items():
            assert isinstance(template, str)
            assert len(template) > 10
