"""
Aura — Database Schema (SQLAlchemy ORM Models)
Core tables: campaigns, leads, skills, settings,
follow_up_sequences, follow_up_steps, follow_up_sends,
suppression_list, enrichment_data, plus agent/ticket/trends tables
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey,
    create_engine, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    search_query = Column(String(500), default="")
    target_city = Column(String(255), default="")
    target_niche = Column(String(255), default="")
    scrape_sources = Column(String(500), default='["duckduckgo"]')  # JSON list
    status = Column(String(50), default="draft", index=True)  # draft/active/paused/completed
    total_leads = Column(Integer, default=0)
    qualified_leads = Column(Integer, default=0)
    emails_sent = Column(Integer, default=0)
    replies = Column(Integer, default=0)
    total_token_cost = Column(Float, default=0.0)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ─── Expansion columns ─────────────────────────────────────────────
    ab_skill_b_id = Column(Integer, ForeignKey("skills.id"), nullable=True)
    ab_split_ratio = Column(Float, default=0.5)
    sequence_id = Column(Integer, ForeignKey("follow_up_sequences.id"), nullable=True)

    # Relationships
    leads = relationship("Lead", back_populates="campaign", cascade="all, delete-orphan")
    skill = relationship("Skill", back_populates="campaigns", foreign_keys=[skill_id])
    skill_b = relationship("Skill", foreign_keys=[ab_skill_b_id])
    sequence = relationship("FollowUpSequence",
                             foreign_keys=[sequence_id])

    def __repr__(self):
        return f"<Campaign(id={self.id}, name='{self.name}', status='{self.status}')>"


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    business_name = Column(String(500), default="")
    category = Column(String(255), default="")
    address = Column(String(500), default="")
    city = Column(String(255), default="")
    country = Column(String(100), default="")
    phone = Column(String(50), default="")
    email = Column(String(255), default="", index=True)
    source_url = Column(String(1000), default="")
    source_platform = Column(String(50), default="")  # duckduckgo/google_maps/yelp
    has_website = Column(Boolean, default=False)
    website_url = Column(String(1000), default="")
    website_issues = Column(Text, default="")
    website_score = Column(Integer, default=0)  # 0–100
    status = Column(String(50), default="new", index=True)
    disqualify_reason = Column(String(500), default="")
    tier2_tokens_used = Column(Integer, default=0)
    tier2_cost_usd = Column(Float, default=0.0)
    tier3_tokens_used = Column(Integer, default=0)
    tier3_cost_usd = Column(Float, default=0.0)
    email_subject = Column(String(500), default="")
    email_body = Column(Text, default="")
    email_sent_at = Column(DateTime, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ─── Expansion columns ─────────────────────────────────────────────
    ab_variant = Column(String(2), nullable=True)          # "A" or "B"
    timezone_offset = Column(Integer, nullable=True)       # UTC offset in hours
    scheduled_send_at = Column(DateTime, nullable=True)
    lifecycle_state = Column(String(50), default="new", index=True)   # rich state machine (Phase 2)

    # Relationships
    campaign = relationship("Campaign", back_populates="leads")
    enrichment = relationship("EnrichmentData", back_populates="lead", uselist=False)
    follow_up_sends = relationship("FollowUpSend", back_populates="lead")

    def __repr__(self):
        return f"<Lead(id={self.id}, name='{self.business_name}', status='{self.status}')>"


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    system_prompt = Column(Text, default="")
    tone = Column(String(50), default="professional")
    example_output = Column(Text, default="")
    preferred_tier = Column(String(20), default="tier3")
    preferred_model = Column(String(100), default="")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=1024)
    is_default = Column(Boolean, default=False)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ─── Enhanced fields (Claude Agent SDK-inspired) ─────────────────
    description = Column(Text, default="")              # Detailed description (up to 1024 chars)
    instructions = Column(Text, default="")             # Step-by-step markdown instructions
    input_schema = Column(Text, default="{}")           # JSON schema for expected inputs
    output_schema = Column(Text, default="{}")          # JSON schema for expected outputs
    examples = Column(Text, default="[]")               # JSON array of example usages
    category = Column(String(50), default="general")    # prospecting|qualification|outreach|analysis|enrichment|research|conversation|management
    version = Column(String(20), default="1.0")         # Semantic version
    capabilities = Column(Text, default="[]")           # JSON list of capability strings
    tags = Column(Text, default="[]")                   # JSON list of searchable tags

    # Relationships
    campaigns = relationship("Campaign", back_populates="skill", foreign_keys="Campaign.skill_id")

    def __repr__(self):
        return f"<Skill(id={self.id}, name='{self.name}', builtin={self.is_builtin})>"


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Encrypted API keys (stored as hex strings)
    anthropic_key_enc = Column(String(500), default="")
    openai_key_enc = Column(String(500), default="")
    gemini_key_enc = Column(String(500), default="")
    openrouter_key_enc = Column(String(500), default="")
    resend_key_enc = Column(String(500), default="")

    # Subscription auth tokens (encrypted)
    anthropic_sub_token_enc = Column(String(2000), default="")   # Claude setup-token
    openai_sub_token_enc = Column(String(2000), default="")      # ChatGPT OAuth access token
    openai_sub_refresh_enc = Column(String(2000), default="")    # ChatGPT OAuth refresh token

    # Auth mode per provider: "api" | "subscription" | "none"
    anthropic_auth_mode = Column(String(20), default="none")
    openai_auth_mode = Column(String(20), default="none")

    smtp_password_enc = Column(String(500), default="")

    # AI model defaults
    tier2_model = Column(String(100), default="gemini/gemini-2.0-flash")
    tier3_model = Column(String(100), default="anthropic/claude-sonnet-4-6")

    # Email delivery
    email_delivery_method = Column(String(20), default="resend")  # "smtp" or "resend"
    smtp_host = Column(String(255), default="")
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String(255), default="")
    sender_name = Column(String(255), default="")
    sender_email = Column(String(255), default="")
    sender_company = Column(String(255), default="")

    # Scraper config
    scraper_enabled_sources = Column(String(500), default='["duckduckgo", "google_maps", "yelp"]')

    # App state
    theme = Column(String(20), default="light")
    first_run_complete = Column(Boolean, default=False)

    # Daily email tracking
    emails_sent_today = Column(Integer, default=0)
    emails_counter_date = Column(String(10), default="")  # YYYY-MM-DD

    # ─── Expansion: IMAP settings ──────────────────────────────────────
    imap_host = Column(String(255), default="")
    imap_port = Column(Integer, default=993)
    imap_username = Column(String(255), default="")
    imap_password_enc = Column(String(500), default="")
    imap_use_ssl = Column(Boolean, default=True)

    # ─── Expansion: Feature toggles ────────────────────────────────────
    send_schedule_enabled = Column(Boolean, default=False)
    ab_test_enabled = Column(Boolean, default=False)
    enrichment_enabled = Column(Boolean, default=True)
    suppression_enabled = Column(Boolean, default=True)

    # ─── Expansion: Chat model ─────────────────────────────────────────
    chat_model = Column(String(100), default="anthropic/claude-sonnet-4-6")

    # ─── Expansion: Apollo & Hunter API keys ─────────────────────────
    apollo_key_enc = Column(String(500), default="")
    hunter_key_enc = Column(String(500), default="")

    # ─── Expansion: CRM API keys ─────────────────────────────────────
    hubspot_key_enc = Column(String(500), default="")
    pipedrive_key_enc = Column(String(500), default="")

    # ─── Expansion: RAG Memory ───────────────────────────────────────
    rag_enabled = Column(Boolean, default=False)
    rag_similarity_threshold = Column(Float, default=0.75)

    # ─── Expansion: 4-Tier Router ────────────────────────────────────
    routing_use_local_first = Column(Boolean, default=True)
    routing_haiku_model = Column(String(100), default="anthropic/claude-haiku-4-5")

    # ─── Expansion: Cross-Channel ────────────────────────────────────
    cross_channel_enabled = Column(Boolean, default=False)

    # ─── Expansion: CRM Syncing ──────────────────────────────────────
    crm_platform = Column(String(50), nullable=True)     # "hubspot" or "pipedrive"

    # ─── Expansion: Inbox Triage ─────────────────────────────────────
    inbox_triage_enabled = Column(Boolean, default=False)
    inbox_triage_schedule = Column(String(10), default="08:00")

    # ─── Expansion: Cost Pacing ───────────────────────────────────────
    pacing_enabled = Column(Boolean, default=False)
    pacing_eco_mode = Column(Boolean, default=True)

    # ─── Expansion: Gateway ───────────────────────────────────────────
    gateway_enabled = Column(Boolean, default=False)

    # ─── Expansion: Multi-Agent System ─────────────────────────────────
    agent_system_enabled = Column(Boolean, default=False)
    observer_alert_threshold = Column(Integer, default=80)
    canary_agent_id = Column(Integer, nullable=True)
    fleet_description = Column(Text, default="")

    # ─── Expansion: Google Trends ──────────────────────────────────────
    trends_enabled = Column(Boolean, default=True)
    trends_check_interval_hours = Column(Integer, default=6)
    trends_default_region = Column(String(50), default="US")
    trends_auto_alert = Column(Boolean, default=True)

    # ─── Expansion: Autonomy & Advanced Engines ────────────────────────
    autonomy_level = Column(String(50), default="supervised")
    reflection_enabled = Column(Boolean, default=True)
    self_improvement_enabled = Column(Boolean, default=True)
    knowledge_graph_enabled = Column(Boolean, default=True)
    conversation_engine_enabled = Column(Boolean, default=True)

    # ─── Expansion: Research APIs ────────────────────────────────────
    apify_key_enc = Column(String(500), default="")
    firecrawl_key_enc = Column(String(500), default="")
    tavily_key_enc = Column(String(500), default="")
    research_auto_enabled = Column(Boolean, default=True)
    research_deep_threshold = Column(Integer, default=7)

    # ─── Expansion: Voice Calls ──────────────────────────────────────
    twilio_account_sid_enc = Column(String(500), default="")
    twilio_auth_token_enc = Column(String(500), default="")
    twilio_phone_number = Column(String(20), default="")
    elevenlabs_key_enc = Column(String(500), default="")
    elevenlabs_voice_id = Column(String(100), default="")
    voice_call_enabled = Column(Boolean, default=False)
    voice_tts_provider = Column(String(20), default="elevenlabs")
    voice_stt_provider = Column(String(20), default="whisper_local")
    voice_max_call_duration_s = Column(Integer, default=300)
    piper_model_path = Column(String(500), default="")

    def __repr__(self):
        return f"<Settings(id={self.id}, theme='{self.theme}')>"


# ═══════════════════════════════════════════════════════════════════════════════
# Expansion Tables
# ═══════════════════════════════════════════════════════════════════════════════

class FollowUpSequence(Base):
    __tablename__ = "follow_up_sequences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    campaign = relationship("Campaign",
                            foreign_keys=[campaign_id])
    steps = relationship("FollowUpStep", back_populates="sequence",
                         cascade="all, delete-orphan",
                         order_by="FollowUpStep.step_number")

    def __repr__(self):
        return f"<FollowUpSequence(id={self.id}, name='{self.name}')>"


class FollowUpStep(Base):
    __tablename__ = "follow_up_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sequence_id = Column(Integer, ForeignKey("follow_up_sequences.id"), nullable=False)
    step_number = Column(Integer, nullable=False)  # 1, 2, 3 …
    delay_days = Column(Integer, default=3)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=True)
    subject_prefix = Column(String(255), default="Re: ")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    sequence = relationship("FollowUpSequence", back_populates="steps")
    skill = relationship("Skill")

    def __repr__(self):
        return f"<FollowUpStep(id={self.id}, seq={self.sequence_id}, step={self.step_number})>"


class FollowUpSend(Base):
    __tablename__ = "follow_up_sends"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    step_id = Column(Integer, ForeignKey("follow_up_steps.id"), nullable=False)
    sent_at = Column(DateTime, nullable=True)
    scheduled_for = Column(DateTime, nullable=True)
    status = Column(String(20), default="scheduled", index=True)  # scheduled/sent/skipped/failed

    # Relationships
    lead = relationship("Lead", back_populates="follow_up_sends")
    step = relationship("FollowUpStep")

    def __repr__(self):
        return f"<FollowUpSend(id={self.id}, lead={self.lead_id}, status='{self.status}')>"


class SuppressionEntry(Base):
    __tablename__ = "suppression_list"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=True)
    domain = Column(String(255), nullable=True)
    reason = Column(String(500), default="manual")
    added_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SuppressionEntry(id={self.id}, email='{self.email}', domain='{self.domain}')>"


class EnrichmentData(Base):
    __tablename__ = "enrichment_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), unique=True, nullable=False)
    google_maps_rating = Column(Float, nullable=True)
    google_maps_review_count = Column(Integer, nullable=True)
    domain_age_years = Column(Float, nullable=True)
    has_facebook = Column(Boolean, default=False)
    has_instagram = Column(Boolean, default=False)
    has_linkedin = Column(Boolean, default=False)
    website_screenshot_path = Column(String(1000), nullable=True)
    enriched_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    lead = relationship("Lead", back_populates="enrichment")

    def __repr__(self):
        return f"<EnrichmentData(id={self.id}, lead_id={self.lead_id})>"


# ═══════════════════════════════════════════════════════════════════════════════
# Advanced Feature Tables
# ═══════════════════════════════════════════════════════════════════════════════

class ApiUsageLog(Base):
    __tablename__ = "api_usage_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service = Column(String(50), nullable=False)        # "apollo", "hunter", "anthropic", "openai", "gemini"
    endpoint = Column(String(255), default="")
    tokens_used = Column(Integer, nullable=True)
    credits_used = Column(Float, nullable=True)
    cost_usd = Column(Float, default=0.0)
    response_code = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)

    def __repr__(self):
        return f"<ApiUsageLog(id={self.id}, service='{self.service}', cost=${self.cost_usd})>"


class RagMemory(Base):
    __tablename__ = "rag_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    content_type = Column(String(50), nullable=False)   # "sent_email", "reply", "successful_template"
    content_text = Column(Text, default="")
    embedding = Column(Text, default="")                # JSON-serialized float list
    reply_received = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<RagMemory(id={self.id}, type='{self.content_type}', replied={self.reply_received})>"


class CrmSyncLog(Base):
    __tablename__ = "crm_sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    crm_platform = Column(String(50), nullable=False)   # "hubspot", "pipedrive"
    crm_record_id = Column(String(255), default="")
    sync_status = Column(String(20), default="pending")  # "synced", "failed", "pending"
    synced_at = Column(DateTime, nullable=True)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CrmSyncLog(id={self.id}, platform='{self.crm_platform}', status='{self.sync_status}')>"


class ChannelDraft(Base):
    __tablename__ = "channel_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    channel = Column(String(50), nullable=False)        # "email", "linkedin", "twitter"
    subject = Column(String(500), nullable=True)
    body = Column(Text, default="")
    status = Column(String(20), default="draft")        # "draft", "approved", "sent", "failed"
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    lead = relationship("Lead")

    def __repr__(self):
        return f"<ChannelDraft(id={self.id}, channel='{self.channel}', status='{self.status}')>"


class BudgetConfig(Base):
    __tablename__ = "budget_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    budget_usd = Column(Float, default=0.0)
    time_window_hours = Column(Float, default=24.0)
    started_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    spent_usd = Column(Float, default=0.0)
    status = Column(String(20), default="inactive")   # inactive/active/paused/expired
    eco_mode = Column(Boolean, default=True)
    max_tier = Column(String(20), default="sonnet")
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BudgetConfig(id={self.id}, budget=${self.budget_usd}, status='{self.status}')>"


class GatewayConfig(Base):
    __tablename__ = "gateway_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False)      # "telegram" or "discord"
    bot_token_enc = Column(String(500), default="")
    is_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<GatewayConfig(id={self.id}, platform='{self.platform}', enabled={self.is_enabled})>"


class AuthorizedUser(Base):
    __tablename__ = "authorized_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False)      # "telegram" or "discord"
    platform_user_id = Column(String(255), nullable=False)
    display_name = Column(String(255), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AuthorizedUser(id={self.id}, platform='{self.platform}', user='{self.platform_user_id}')>"


# ═══════════════════════════════════════════════════════════════════════════════
# Multi-Agent System Tables
# ═══════════════════════════════════════════════════════════════════════════════

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)           # orchestrator/worker/canary/observer
    soul = Column(Text, default="")                     # personality and behavioral constraints
    mission = Column(Text, default="")                  # current objective and success criteria
    playbook = Column(Text, default="")                 # SOPs and decision trees
    boundaries = Column(Text, default="")               # hard limits and approval requirements
    identity_emoji = Column(String(10), default="🤖")
    status = Column(String(20), default="idle")         # idle/running/paused/error
    current_task = Column(String(500), nullable=True)
    heartbeat_last = Column(DateTime, nullable=True)
    heartbeat_interval_mins = Column(Integer, default=30)
    boot_script = Column(Text, nullable=True)           # Python snippet on agent restart
    memory_today = Column(Text, nullable=True)          # daily working notes, reset at midnight
    long_term_memory = Column(Text, nullable=True)      # curated cross-session memory
    model_tier = Column(String(20), default="haiku")    # local/ollama/haiku/sonnet
    tasks_completed = Column(Integer, default=0)
    tasks_failed = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ─── Hierarchy fields ─────────────────────────────────
    rank = Column(Integer, default=3)                       # 1=C-Level, 2=Specialist, 3=Worker
    reports_to_id = Column(Integer, ForeignKey("agents.id"), nullable=True)

    # Relationships
    tasks = relationship("AgentTask", back_populates="agent",
                         foreign_keys="AgentTask.agent_id")
    sent_messages = relationship("AgentMessage", back_populates="sender",
                                 foreign_keys="AgentMessage.from_agent_id")
    memory_logs = relationship("AgentMemoryLog", back_populates="agent")
    reports_to = relationship("Agent", remote_side="Agent.id",
                              foreign_keys=[reports_to_id])

    def __repr__(self):
        return f"<Agent(id={self.id}, name='{self.name}', role='{self.role}', status='{self.status}')>"


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    task_type = Column(String(100), nullable=False, index=True)
    task_payload = Column(Text, default="{}")            # JSON
    status = Column(String(20), default="queued", index=True)        # queued/running/completed/failed/delegated
    assigned_by = Column(String(255), default="user")    # orchestrator name or "user"
    delegated_to_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    result = Column(Text, nullable=True)
    error = Column(String(1000), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cost_usd = Column(Float, default=0.0)
    tokens_used = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    context_hash = Column(String(64), nullable=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    agent = relationship("Agent", back_populates="tasks",
                         foreign_keys=[agent_id])
    delegated_to = relationship("Agent", foreign_keys=[delegated_to_agent_id])
    skill = relationship("Skill")

    def __repr__(self):
        return f"<AgentTask(id={self.id}, type='{self.task_type}', status='{self.status}')>"


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    to_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    message_type = Column(String(50), default="info")    # task_delegation/status_report/alert/heartbeat/handoff
    content = Column(Text, default="{}")                  # JSON
    acknowledged = Column(Boolean, default=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime, nullable=True)

    # Relationships
    sender = relationship("Agent", back_populates="sent_messages",
                          foreign_keys=[from_agent_id])
    receiver = relationship("Agent", foreign_keys=[to_agent_id])

    def __repr__(self):
        return f"<AgentMessage(id={self.id}, type='{self.message_type}')>"


class AgentMemoryLog(Base):
    __tablename__ = "agent_memory_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    log_date = Column(String(10), default="")            # YYYY-MM-DD
    content = Column(Text, default="")
    memory_type = Column(String(50), default="daily_notes")  # daily_notes/long_term/heartbeat_report
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    agent = relationship("Agent", back_populates="memory_logs")

    def __repr__(self):
        return f"<AgentMemoryLog(id={self.id}, agent={self.agent_id}, type='{self.memory_type}')>"


# ═══════════════════════════════════════════════════════════════════════════════
# Ticket System Tables
# ═══════════════════════════════════════════════════════════════════════════════

class AgentTicket(Base):
    __tablename__ = "agent_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    priority = Column(String(20), default="medium")          # critical/high/medium/low
    status = Column(String(20), default="backlog", index=True)           # backlog/todo/in_progress/review/done
    assignee_id = Column(Integer, ForeignKey("agents.id"), nullable=True, index=True)
    reporter_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    reporter_type = Column(String(20), default="user")       # "user" or "agent"
    parent_ticket_id = Column(Integer, ForeignKey("agent_tickets.id"), nullable=True)
    due_date = Column(DateTime, nullable=True)
    labels = Column(String(500), default="")                 # comma-separated
    blocked_reason = Column(String(500), nullable=True)
    escalated_to_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    approval_status = Column(String(20), nullable=True)      # pending/approved/denied
    approved_by_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    linked_task_id = Column(Integer, ForeignKey("agent_tasks.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    assignee = relationship("Agent", foreign_keys=[assignee_id])
    reporter = relationship("Agent", foreign_keys=[reporter_id])
    parent_ticket = relationship("AgentTicket", remote_side=[id], backref="sub_tickets")
    escalated_to = relationship("Agent", foreign_keys=[escalated_to_id])
    approved_by = relationship("Agent", foreign_keys=[approved_by_id])
    linked_task = relationship("AgentTask")
    comments = relationship("TicketComment", back_populates="ticket",
                            cascade="all, delete-orphan",
                            order_by="TicketComment.created_at")
    dependencies = relationship("TicketDependency",
                                foreign_keys="TicketDependency.ticket_id",
                                cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AgentTicket(id={self.id}, title='{self.title}', status='{self.status}')>"


class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("agent_tickets.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    author_type = Column(String(20), default="user")         # "user" or "agent"
    content = Column(Text, nullable=False)
    comment_type = Column(String(20), default="comment")     # comment/status_change/escalation/approval
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    ticket = relationship("AgentTicket", back_populates="comments")
    author = relationship("Agent")

    def __repr__(self):
        return f"<TicketComment(id={self.id}, ticket={self.ticket_id})>"


class TicketDependency(Base):
    __tablename__ = "ticket_dependencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("agent_tickets.id"), nullable=False)
    depends_on_id = Column(Integer, ForeignKey("agent_tickets.id"), nullable=False)

    ticket = relationship("AgentTicket", foreign_keys=[ticket_id])
    depends_on = relationship("AgentTicket", foreign_keys=[depends_on_id])

    __table_args__ = (
        UniqueConstraint("ticket_id", "depends_on_id", name="uq_ticket_dependency"),
    )

    def __repr__(self):
        return f"<TicketDependency(id={self.id}, ticket={self.ticket_id}, depends_on={self.depends_on_id})>"


# ═══════════════════════════════════════════════════════════════════════════════
# Command History Tables
# ═══════════════════════════════════════════════════════════════════════════════

class CommandLog(Base):
    __tablename__ = "command_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Command tree
    parent_command_id = Column(Integer, ForeignKey("command_log.id"), nullable=True)
    correlation_id = Column(String(64), nullable=True)

    # Source tracking
    source = Column(String(50), nullable=False, index=True)
    source_sender_id = Column(String(255), nullable=True)
    source_display_name = Column(String(255), nullable=True)

    # Actor
    actor_type = Column(String(20), default="user")
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)

    # Content
    command_type = Column(String(100), nullable=False)
    command_text = Column(Text, default="")
    intent = Column(String(100), nullable=True)
    parameters = Column(Text, default="{}")
    result = Column(Text, nullable=True)
    status = Column(String(20), default="pending")

    # Cost
    cost_usd = Column(Float, default=0.0)
    tokens_used = Column(Integer, default=0)

    # Links
    linked_task_id = Column(Integer, ForeignKey("agent_tasks.id"), nullable=True)
    linked_ticket_id = Column(Integer, ForeignKey("agent_tickets.id"), nullable=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Relationships
    parent_command = relationship("CommandLog", remote_side=[id], backref="child_commands")
    agent = relationship("Agent", foreign_keys=[agent_id])
    linked_task = relationship("AgentTask")
    linked_ticket = relationship("AgentTicket")
    campaign = relationship("Campaign")

    def __repr__(self):
        return f"<CommandLog(id={self.id}, type='{self.command_type}', source='{self.source}', status='{self.status}')>"


# ═══════════════════════════════════════════════════════════════════════════════
# Google Trends Tables
# ═══════════════════════════════════════════════════════════════════════════════

class TrendsData(Base):
    __tablename__ = "trends_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(500), nullable=False)
    region = Column(String(50), default="US")
    timeframe = Column(String(50), default="today 3-m")
    interest_over_time = Column(Text, default="{}")      # JSON
    related_queries = Column(Text, default="{}")         # JSON
    related_topics = Column(Text, default="{}")          # JSON
    rising_breakouts = Column(Text, default="{}")        # JSON
    peak_date = Column(String(20), nullable=True)
    current_score = Column(Integer, default=0)           # 0–100
    trend_direction = Column(String(20), nullable=True)  # rising/falling/stable/breakout
    fetched_at = Column(DateTime, default=datetime.utcnow)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)

    campaign = relationship("Campaign")

    def __repr__(self):
        return f"<TrendsData(id={self.id}, keyword='{self.keyword}', direction='{self.trend_direction}')>"


class TrendsAlert(Base):
    __tablename__ = "trends_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(500), nullable=False)
    alert_type = Column(String(50), default="spike")     # breakout/spike/new_competitor/seasonal
    message = Column(Text, default="")
    triggered_at = Column(DateTime, default=datetime.utcnow)
    acknowledged = Column(Boolean, default=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)

    campaign = relationship("Campaign")

    def __repr__(self):
        return f"<TrendsAlert(id={self.id}, keyword='{self.keyword}', type='{self.alert_type}')>"


# ═══════════════════════════════════════════════════════════════════════════════
# Reflection & Self-Improvement Tables
# ═══════════════════════════════════════════════════════════════════════════════

class AgentReflection(Base):
    __tablename__ = "agent_reflections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("agent_tasks.id"), nullable=False)
    task_type = Column(String(100), nullable=False)
    output_text = Column(Text, default="")
    reflection_text = Column(Text, default="")
    score = Column(Integer, default=5)                # 1-10 quality score
    improvement_notes = Column(Text, default="")
    revision_count = Column(Integer, default=0)
    was_revised = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent")
    task = relationship("AgentTask")

    def __repr__(self):
        return f"<AgentReflection(id={self.id}, agent_id={self.agent_id}, score={self.score})>"


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    metric_type = Column(String(100), nullable=False)    # reply_rate, qualification_accuracy, email_quality_avg
    metric_key = Column(String(255), default="")         # niche, skill_name, campaign_id
    value = Column(Float, default=0.0)
    sample_count = Column(Integer, default=0)
    period = Column(String(20), default="daily")         # daily, weekly, all_time
    period_date = Column(String(10), default="")         # YYYY-MM-DD
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent = relationship("Agent")

    def __repr__(self):
        return f"<PerformanceMetric(id={self.id}, type='{self.metric_type}', value={self.value})>"


class AgentLearnedRule(Base):
    __tablename__ = "agent_learned_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    rule_type = Column(String(50), nullable=False)       # timing, content, targeting, approach
    rule_text = Column(Text, nullable=False)
    confidence = Column(Float, default=0.5)              # 0.0-1.0
    evidence_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    source = Column(String(50), default="auto")          # auto, manual, ab_test
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent = relationship("Agent")

    def __repr__(self):
        return f"<AgentLearnedRule(id={self.id}, type='{self.rule_type}', confidence={self.confidence})>"


# ─── Lead State Transition (audit trail) ──────────────────────────────────────

class LeadStateTransition(Base):
    __tablename__ = "lead_state_transitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    from_state = Column(String(50), nullable=False)
    to_state = Column(String(50), nullable=False)
    triggered_by = Column(String(100), default="system")   # agent name, user, system
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead")
    agent = relationship("Agent")

    def __repr__(self):
        return f"<LeadStateTransition(lead={self.lead_id}, {self.from_state}→{self.to_state})>"


# ─── Knowledge Graph ──────────────────────────────────────────────────────────

class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"
    __table_args__ = (UniqueConstraint("node_type", "node_key", name="uq_node_type_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_type = Column(String(50), nullable=False)    # lead, company, niche, campaign, agent, keyword
    node_key = Column(String(255), nullable=False)     # unique identifier within type
    display_name = Column(String(500), default="")
    properties_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<KnowledgeNode({self.node_type}:{self.node_key})>"


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_node_id = Column(Integer, ForeignKey("knowledge_nodes.id"), nullable=False)
    to_node_id = Column(Integer, ForeignKey("knowledge_nodes.id"), nullable=False)
    edge_type = Column(String(50), nullable=False)     # contacted_by, replied_to, converted_by, competitor_of, similar_to, belongs_to
    weight = Column(Float, default=1.0)
    properties_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    from_node = relationship("KnowledgeNode", foreign_keys=[from_node_id])
    to_node = relationship("KnowledgeNode", foreign_keys=[to_node_id])

    def __repr__(self):
        return f"<KnowledgeEdge({self.from_node_id}→{self.to_node_id}, type='{self.edge_type}')>"


# ─── Conversation Thread ──────────────────────────────────────────────────────

class ConversationThread(Base):
    __tablename__ = "conversation_threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    thread_status = Column(String(50), default="active")        # active, paused, closed, re_engage
    messages_json = Column(Text, default="[]")                   # JSON array of messages
    reply_intent = Column(String(50), nullable=True)             # interested, objection, not_now, question, unsubscribe
    objection_type = Column(String(50), nullable=True)           # price, timing, need, authority, competitor, other
    re_engage_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)
    last_activity = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead")
    campaign = relationship("Campaign")

    def __repr__(self):
        return f"<ConversationThread(lead={self.lead_id}, status='{self.thread_status}', msgs={self.message_count})>"


# ─── Strategic Goals & Milestones ─────────────────────────────────────────────

class StrategicGoal(Base):
    __tablename__ = "strategic_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    goal_text = Column(String(500), nullable=False)
    target_metric = Column(String(100), default="conversions")  # conversions, meetings, replies
    target_value = Column(Integer, default=10)
    budget_usd = Column(Float, nullable=True)
    niche = Column(String(255), default="")
    city = Column(String(255), default="")
    status = Column(String(50), default="planning")  # planning, active, paused, completed, failed
    progress_pct = Column(Float, default=0.0)
    estimated_contacts_needed = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    actual_cost = Column(Float, default=0.0)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    campaign = relationship("Campaign")
    milestones = relationship("GoalMilestone", back_populates="goal")

    def __repr__(self):
        return f"<StrategicGoal(id={self.id}, '{self.goal_text[:30]}', status='{self.status}')>"


class GoalMilestone(Base):
    __tablename__ = "goal_milestones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    goal_id = Column(Integer, ForeignKey("strategic_goals.id"), nullable=False)
    phase = Column(Integer, default=1)
    description = Column(String(500), default="")
    target_value = Column(Integer, default=0)
    actual_value = Column(Integer, default=0)
    status = Column(String(50), default="pending")  # pending, active, completed, failed
    estimated_cost = Column(Float, default=0.0)
    actual_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    goal = relationship("StrategicGoal", back_populates="milestones")

    def __repr__(self):
        return f"<GoalMilestone(goal={self.goal_id}, phase={self.phase}, status='{self.status}')>"


# ─── Pending Approvals (Autonomy) ────────────────────────────────────────────

class PendingApproval(Base):
    __tablename__ = "pending_approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(100), nullable=False)      # send_email, generate_email, skill_revision, etc.
    action_description = Column(String(500), default="")
    action_payload = Column(Text, default="{}")             # JSON
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    status = Column(String(50), default="pending")          # pending, approved, denied, expired
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    agent = relationship("Agent")
    lead = relationship("Lead")

    def __repr__(self):
        return f"<PendingApproval(id={self.id}, type='{self.action_type}', status='{self.status}')>"


# ─── Case System (Lead-as-Case) ──────────────────────────────────────────────

class CaseNote(Base):
    """Timestamped note attached to a lead — the audit log of all agent activity."""
    __tablename__ = "case_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    note_type = Column(String(50), nullable=False)  # observation/outreach/enrichment/qualification/lifecycle/reflection/custom
    content = Column(Text, default="")
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead")
    agent = relationship("Agent")

    def __repr__(self):
        return f"<CaseNote(lead={self.lead_id}, type='{self.note_type}')>"


class CaseMemory(Base):
    """Living summary of a lead's case — re-summarized when notes exceed threshold."""
    __tablename__ = "case_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), unique=True, nullable=False)
    memory_type = Column(String(50), default="summary")  # summary/key_facts/timeline
    content = Column(Text, default="")
    note_count_at_summary = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead = relationship("Lead")

    def __repr__(self):
        return f"<CaseMemory(lead={self.lead_id}, notes_at={self.note_count_at_summary})>"


# ─── Token Management (Cached Summaries) ─────────────────────────────────────

class CachedSummary(Base):
    """Pre-computed summaries of long text. Invalidated by source_hash change."""
    __tablename__ = "cached_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(50), nullable=False)  # agent_memory/lead_case/conversation
    source_id = Column(Integer, nullable=False)
    summary_text = Column(Text, default="")
    source_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CachedSummary(type='{self.source_type}', id={self.source_id})>"


# ─── Subagent Tasks ──────────────────────────────────────────────────────────

class SubagentTask(Base):
    """Atomic subtask within a parent AgentTask. Uses cheaper models by default."""
    __tablename__ = "subagent_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_task_id = Column(Integer, ForeignKey("agent_tasks.id"), nullable=False)
    subtask_type = Column(String(100), nullable=False)
    input_json = Column(Text, default="{}")
    output_json = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending/running/completed/failed
    tier = Column(String(20), default="haiku")
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    parent_task = relationship("AgentTask")

    def __repr__(self):
        return f"<SubagentTask(parent={self.parent_task_id}, type='{self.subtask_type}')>"


# ═══════════════════════════════════════════════════════════════════════════════
# Research & Voice Call Tables
# ═══════════════════════════════════════════════════════════════════════════════

class ResearchReport(Base):
    """Pre-outreach intelligence gathered about a lead."""
    __tablename__ = "research_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    depth = Column(String(20), default="quick")              # quick / deep
    status = Column(String(20), default="pending")           # pending / running / completed / failed
    sources_used = Column(Text, default="[]")                # JSON list: ["tavily", "firecrawl", "apify"]
    company_overview = Column(Text, default="")
    services_offered = Column(Text, default="")
    pain_points = Column(Text, default="")
    competitors = Column(Text, default="")
    tech_stack = Column(Text, default="")
    recent_news = Column(Text, default="")
    gaps_opportunities = Column(Text, default="")
    raw_data = Column(Text, default="{}")                    # Full JSON of raw provider responses
    llm_summary = Column(Text, default="")                   # LLM-synthesized summary
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead = relationship("Lead")
    campaign = relationship("Campaign")

    def __repr__(self):
        return f"<ResearchReport(lead={self.lead_id}, depth='{self.depth}', status='{self.status}')>"


class VoiceCall(Base):
    """Voice call record — outbound cold calls and inbound handling."""
    __tablename__ = "voice_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    direction = Column(String(20), default="outbound")       # outbound / inbound
    status = Column(String(20), default="queued")            # queued / ringing / in_progress / completed / failed / no_answer / voicemail
    twilio_call_sid = Column(String(64), nullable=True)
    from_number = Column(String(20), default="")
    to_number = Column(String(20), default="")
    duration_seconds = Column(Integer, default=0)
    recording_path = Column(String(500), nullable=True)
    transcript = Column(Text, default="[]")                  # Speaker-labeled JSON
    call_notes = Column(Text, default="")                    # AI-generated summary
    call_outcome = Column(String(50), nullable=True)         # interested / not_interested / callback / voicemail / no_answer / meeting_booked
    sentiment = Column(String(20), nullable=True)            # positive / neutral / negative
    tts_provider = Column(String(20), nullable=True)
    stt_provider = Column(String(20), nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead")
    agent = relationship("Agent")
    campaign = relationship("Campaign")

    def __repr__(self):
        return f"<VoiceCall(id={self.id}, lead={self.lead_id}, status='{self.status}')>"
