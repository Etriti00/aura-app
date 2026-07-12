"""
Tests for per-agent skill assignments and the Commander grant flow.
"""

import json

import pytest

from core.agent_engine import AgentEngine
from database.schema import Agent, AgentMessage, Skill
from database.seed_agents import SKILL_ASSIGNMENTS, seed_default_agents
from database.seed_skills import seed_defaults


@pytest.fixture
def seeded_db(db):
    seed_defaults(db)
    seed_default_agents(db)
    return db


@pytest.fixture
def engine(seeded_db):
    return AgentEngine(seeded_db, key_vault=None)


def _agent(session, name):
    return session.query(Agent).filter_by(name=name).first()


class TestSkillAssignments:
    def test_every_seed_agent_has_an_assignment(self, seeded_db):
        with seeded_db.session_scope() as session:
            for name in SKILL_ASSIGNMENTS:
                agent = _agent(session, name)
                assert agent is not None, name
                assert agent.allowed_skills is not None, name
                assert isinstance(json.loads(agent.allowed_skills), list)

    def test_assignments_reference_real_skills(self, seeded_db):
        """Names in SKILL_ASSIGNMENTS must exist in the seeded library
        (registry skills are seeded separately and are exempt)."""
        registry_names = {
            "Prospector", "Qualifier", "Closer", "Analyst",
            "Enrichment Specialist", "Researcher", "Conversationalist",
            "Fleet Commander", "Research Analyst", "Voice Agent",
        }
        with seeded_db.session_scope() as session:
            seeded = {s.name for s in session.query(Skill).all()}
        for name, skills in SKILL_ASSIGNMENTS.items():
            for skill_name in skills:
                assert (skill_name in seeded
                        or skill_name in registry_names), (
                    f"{name} assigned unknown skill {skill_name}"
                )

    def test_closer_carries_outreach_personas_only(self, seeded_db):
        with seeded_db.session_scope() as session:
            closer = _agent(session, "Closer")
            names = json.loads(closer.allowed_skills)
            assert "The Closer" in names
            assert "Fleet Commander" not in names
            assert "CRM Data Mapper" not in names


class TestSkillMatchingWithAssignments:
    def test_assigned_skill_preferred(self, engine, seeded_db):
        with seeded_db.session_scope() as session:
            qualifier = _agent(session, "Qualifier")
            match = engine._find_matching_skill(
                session, "qualify_lead", {}, agent=qualifier
            )
            assert match is not None
            assert match["name"] in json.loads(qualifier.allowed_skills)

    def test_unrestricted_legacy_agent_matches_globally(self, engine, seeded_db):
        with seeded_db.session_scope() as session:
            agent = Agent(name="Legacy", role="worker", allowed_skills=None)
            session.add(agent)
            session.flush()
            match = engine._find_matching_skill(
                session, "generate_email", {}, agent=agent
            )
            assert match is not None
            # No grant messages for unrestricted agents
            msgs = session.query(AgentMessage).filter_by(
                from_agent_id=agent.id
            ).count()
            assert msgs == 0


class TestCommanderGrantFlow:
    def test_out_of_assignment_match_is_granted(self, engine, seeded_db):
        """An agent with an empty assignment that needs a skill gets it
        granted by the Commander, and both messages are logged."""
        with seeded_db.session_scope() as session:
            postman = _agent(session, "Postman")
            assert json.loads(postman.allowed_skills) == []

            match = engine._find_matching_skill(
                session, "generate_email", {}, agent=postman
            )
            assert match is not None

            granted = json.loads(postman.allowed_skills)
            assert match["name"] in granted

            commander = _agent(session, "Commander")
            request = session.query(AgentMessage).filter_by(
                from_agent_id=postman.id, to_agent_id=commander.id,
                message_type="skill_request",
            ).first()
            grant = session.query(AgentMessage).filter_by(
                from_agent_id=commander.id, to_agent_id=postman.id,
                message_type="skill_granted",
            ).first()
            assert request is not None
            assert grant is not None
            assert json.loads(grant.content)["skill_name"] == match["name"]

    def test_grant_is_idempotent(self, engine, seeded_db):
        with seeded_db.session_scope() as session:
            postman = _agent(session, "Postman")
            engine._grant_skill(session, postman, "Data Summarizer")
            engine._grant_skill(session, postman, "Data Summarizer")
            names = json.loads(postman.allowed_skills)
            assert names.count("Data Summarizer") == 1

    def test_explicit_skill_id_outside_assignment_grants(self, engine, seeded_db):
        with seeded_db.session_scope() as session:
            observer = _agent(session, "Observer")
            skill = session.query(Skill).filter_by(
                name="Executive Report Writer"
            ).first()
            match = engine._find_matching_skill(
                session, "summarize", {"skill_id": skill.id}, agent=observer
            )
            assert match["name"] == "Executive Report Writer"
            assert "Executive Report Writer" in json.loads(
                observer.allowed_skills
            )


class TestSkillLibrary:
    def test_invoice_architect_seeded_for_accountant(self, seeded_db):
        with seeded_db.session_scope() as session:
            skill = session.query(Skill).filter_by(
                name="Invoice Architect"
            ).first()
            assert skill is not None
            assert skill.is_builtin
            accountant = _agent(session, "Accountant")
            assert "Invoice Architect" in json.loads(
                accountant.allowed_skills
            )

    def test_status_exposes_assigned_skills(self, engine, seeded_db):
        with seeded_db.session_scope() as session:
            scout_id = _agent(session, "Scout").id
        status = engine.get_agent_status(scout_id)
        assert status["success"]
        names = [s["name"] for s in status["data"]["skills"]]
        assert names == ["Prospector"]
