"""
Tests for database/schema.py — all ORM models, relationships, defaults, and constraints.
"""

import pytest
from datetime import datetime
from database.schema import (
    Base, Campaign, Lead, Skill, Settings, FollowUpSequence, FollowUpStep,
    FollowUpSend, SuppressionEntry, EnrichmentData, ApiUsageLog, RagMemory,
    CrmSyncLog, ChannelDraft, BudgetConfig, GatewayConfig, AuthorizedUser,
    Agent, AgentTask, AgentMessage, AgentMemoryLog,
    AgentTicket, TicketComment, TicketDependency,
    TrendsData, TrendsAlert,
)


class TestCampaignModel:
    def test_create_campaign(self, db):
        with db.session_scope() as s:
            c = Campaign(name="Test Campaign")
            s.add(c)
            s.flush()
            assert c.id is not None
            assert c.name == "Test Campaign"
            assert c.status == "draft"
            assert c.total_leads == 0
            assert c.ab_split_ratio == 0.5

    def test_campaign_defaults(self, db):
        with db.session_scope() as s:
            c = Campaign(name="Defaults")
            s.add(c)
            s.flush()
            assert c.search_query == ""
            assert c.target_city == ""
            assert c.target_niche == ""
            assert c.qualified_leads == 0
            assert c.emails_sent == 0
            assert c.replies == 0
            assert c.total_token_cost == 0.0

    def test_campaign_lead_relationship(self, db):
        with db.session_scope() as s:
            c = Campaign(name="With Leads")
            s.add(c)
            s.flush()
            lead = Lead(campaign_id=c.id, business_name="Acme Corp")
            s.add(lead)
            s.flush()
            assert len(c.leads) == 1
            assert c.leads[0].business_name == "Acme Corp"

    def test_campaign_cascade_delete(self, db):
        with db.session_scope() as s:
            c = Campaign(name="Cascade Test")
            s.add(c)
            s.flush()
            s.add(Lead(campaign_id=c.id, business_name="Will be deleted"))
            s.flush()
            s.delete(c)
            s.flush()
            assert s.query(Lead).count() == 0


class TestLeadModel:
    def test_create_lead(self, db):
        with db.session_scope() as s:
            c = Campaign(name="Parent")
            s.add(c)
            s.flush()
            lead = Lead(campaign_id=c.id, business_name="Test Biz", email="test@example.com")
            s.add(lead)
            s.flush()
            assert lead.id is not None
            assert lead.status == "new"
            assert lead.has_website is False

    def test_lead_defaults(self, db):
        with db.session_scope() as s:
            c = Campaign(name="P")
            s.add(c)
            s.flush()
            lead = Lead(campaign_id=c.id)
            s.add(lead)
            s.flush()
            assert lead.business_name == ""
            assert lead.website_score == 0
            assert lead.tier2_cost_usd == 0.0
            assert lead.tier3_cost_usd == 0.0
            assert lead.ab_variant is None
            assert lead.timezone_offset is None


class TestSkillModel:
    def test_create_skill(self, db):
        with db.session_scope() as s:
            skill = Skill(name="Test Skill", tone="casual", is_builtin=False)
            s.add(skill)
            s.flush()
            assert skill.id is not None
            assert skill.temperature == 0.7
            assert skill.max_tokens == 1024
            assert skill.preferred_tier == "tier3"


class TestSettingsModel:
    def test_settings_defaults(self, db):
        with db.session_scope() as s:
            settings = Settings(id=1)
            s.add(settings)
            s.flush()
            assert settings.theme == "light"
            assert settings.first_run_complete is False
            assert settings.tier2_model == "gemini/gemini-3.5-flash"
            assert settings.tier3_model == "anthropic/claude-sonnet-5"
            assert settings.email_delivery_method == "resend"
            assert settings.enrichment_enabled is True
            assert settings.suppression_enabled is True
            assert settings.rag_enabled is False
            assert settings.gateway_enabled is False
            assert settings.agent_system_enabled is False
            assert settings.trends_enabled is True


class TestAgentModel:
    def test_create_agent(self, db):
        with db.session_scope() as s:
            a = Agent(name="TestAgent", role="worker", identity_emoji="🧪")
            s.add(a)
            s.flush()
            assert a.id is not None
            assert a.status == "idle"
            assert a.model_tier == "haiku"
            assert a.rank == 3
            assert a.tasks_completed == 0
            assert a.tasks_failed == 0
            assert a.total_cost_usd == 0.0

    def test_agent_hierarchy_self_reference(self, db):
        with db.session_scope() as s:
            commander = Agent(name="Boss", role="orchestrator", rank=1)
            s.add(commander)
            s.flush()
            worker = Agent(name="Worker", role="worker", rank=3, reports_to_id=commander.id)
            s.add(worker)
            s.flush()
            assert worker.reports_to.name == "Boss"
            assert worker.reports_to_id == commander.id


class TestAgentTicketModel:
    def test_create_ticket(self, db_with_agents):
        with db_with_agents.session_scope() as s:
            t = AgentTicket(title="Test ticket", priority="high", status="backlog")
            s.add(t)
            s.flush()
            assert t.id is not None
            assert t.priority == "high"
            assert t.status == "backlog"
            assert t.reporter_type == "user"
            assert t.completed_at is None

    def test_ticket_defaults(self, db):
        with db.session_scope() as s:
            t = AgentTicket(title="Defaults test")
            s.add(t)
            s.flush()
            assert t.priority == "medium"
            assert t.status == "backlog"
            assert t.description == ""
            assert t.labels == ""
            assert t.blocked_reason is None
            assert t.approval_status is None

    def test_ticket_assignee_relationship(self, db_with_agents):
        with db_with_agents.session_scope() as s:
            agent = s.query(Agent).filter_by(name="Scout").first()
            t = AgentTicket(title="Assigned", assignee_id=agent.id)
            s.add(t)
            s.flush()
            assert t.assignee.name == "Scout"

    def test_ticket_sub_tickets(self, db):
        with db.session_scope() as s:
            parent = AgentTicket(title="Parent ticket")
            s.add(parent)
            s.flush()
            child = AgentTicket(title="Child ticket", parent_ticket_id=parent.id)
            s.add(child)
            s.flush()
            assert len(parent.sub_tickets) == 1
            assert parent.sub_tickets[0].title == "Child ticket"

    def test_ticket_comments_relationship(self, db):
        with db.session_scope() as s:
            t = AgentTicket(title="With comments")
            s.add(t)
            s.flush()
            c1 = TicketComment(ticket_id=t.id, content="First comment")
            c2 = TicketComment(ticket_id=t.id, content="Second comment")
            s.add_all([c1, c2])
            s.flush()
            assert len(t.comments) == 2

    def test_ticket_cascade_delete_comments(self, db):
        with db.session_scope() as s:
            t = AgentTicket(title="Delete me")
            s.add(t)
            s.flush()
            s.add(TicketComment(ticket_id=t.id, content="Will die"))
            s.flush()
            s.delete(t)
            s.flush()
            assert s.query(TicketComment).count() == 0


class TestTicketDependencyModel:
    def test_create_dependency(self, db):
        with db.session_scope() as s:
            t1 = AgentTicket(title="Ticket A")
            t2 = AgentTicket(title="Ticket B")
            s.add_all([t1, t2])
            s.flush()
            dep = TicketDependency(ticket_id=t1.id, depends_on_id=t2.id)
            s.add(dep)
            s.flush()
            assert dep.id is not None
            assert dep.ticket.title == "Ticket A"
            assert dep.depends_on.title == "Ticket B"

    def test_unique_constraint(self, db):
        from sqlalchemy.exc import IntegrityError

        # Create tickets and first dependency, capture IDs
        with db.session_scope() as s:
            t1 = AgentTicket(title="A")
            t2 = AgentTicket(title="B")
            s.add_all([t1, t2])
            s.flush()
            tid1, tid2 = t1.id, t2.id
            s.add(TicketDependency(ticket_id=tid1, depends_on_id=tid2))
            s.flush()

        # Second add of same dep should violate UniqueConstraint
        with pytest.raises(IntegrityError):
            with db.session_scope() as s:
                s.add(TicketDependency(ticket_id=tid1, depends_on_id=tid2))
                s.flush()  # Force constraint check within session


class TestAgentTaskModel:
    def test_create_task(self, db_with_agents):
        with db_with_agents.session_scope() as s:
            agent = s.query(Agent).first()
            task = AgentTask(
                agent_id=agent.id, task_type="scrape_leads",
                task_payload='{"query": "test"}', status="queued",
            )
            s.add(task)
            s.flush()
            assert task.id is not None
            assert task.status == "queued"
            assert task.cost_usd == 0.0


class TestAgentMessageModel:
    def test_create_message(self, db_with_agents):
        with db_with_agents.session_scope() as s:
            agents = s.query(Agent).limit(2).all()
            msg = AgentMessage(
                from_agent_id=agents[0].id,
                to_agent_id=agents[1].id,
                message_type="info",
                content='{"hello": "world"}',
            )
            s.add(msg)
            s.flush()
            assert msg.id is not None
            assert msg.acknowledged is False


class TestTrendsModels:
    def test_create_trends_data(self, db):
        with db.session_scope() as s:
            td = TrendsData(keyword="python", region="US", current_score=75)
            s.add(td)
            s.flush()
            assert td.id is not None
            assert td.timeframe == "today 3-m"

    def test_create_trends_alert(self, db):
        with db.session_scope() as s:
            ta = TrendsAlert(keyword="react", alert_type="breakout", message="React is trending!")
            s.add(ta)
            s.flush()
            assert ta.acknowledged is False


class TestFollowUpModels:
    def test_sequence_with_steps(self, db):
        with db.session_scope() as s:
            c = Campaign(name="FU Test")
            s.add(c)
            s.flush()
            seq = FollowUpSequence(campaign_id=c.id, name="3-Step Follow-up")
            s.add(seq)
            s.flush()
            s.add(FollowUpStep(sequence_id=seq.id, step_number=1, delay_days=3))
            s.add(FollowUpStep(sequence_id=seq.id, step_number=2, delay_days=7))
            s.flush()
            assert len(seq.steps) == 2
            assert seq.steps[0].step_number == 1


class TestSuppressionModel:
    def test_create_entry(self, db):
        with db.session_scope() as s:
            entry = SuppressionEntry(email="spam@test.com", reason="bounce")
            s.add(entry)
            s.flush()
            assert entry.id is not None


class TestBudgetConfigModel:
    def test_defaults(self, db):
        with db.session_scope() as s:
            bc = BudgetConfig()
            s.add(bc)
            s.flush()
            assert bc.budget_usd == 0.0
            assert bc.status == "inactive"
            assert bc.eco_mode is True


class TestGatewayModels:
    def test_gateway_config(self, db):
        with db.session_scope() as s:
            gc = GatewayConfig(platform="telegram", is_enabled=True)
            s.add(gc)
            s.flush()
            assert gc.platform == "telegram"

    def test_authorized_user(self, db):
        with db.session_scope() as s:
            au = AuthorizedUser(platform="discord", platform_user_id="123456")
            s.add(au)
            s.flush()
            assert au.is_active is True
