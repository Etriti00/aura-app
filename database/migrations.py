"""
Aura — Schema Migrations
Extracted from db_manager.py to reduce file size.
Contains ALTER TABLE migrations for backward compatibility.
"""

import sqlite3


def migrate_schema(db_path):
    """Add new columns to existing tables for backward compatibility.
    Safe to call multiple times - uses ALTER TABLE ADD COLUMN with try/except."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    def _add_col(table, column, col_type, default):
        try:
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Settings: API integration keys
    _add_col("settings", "apollo_key_enc", "TEXT", "''")
    _add_col("settings", "hunter_key_enc", "TEXT", "''")
    _add_col("settings", "hubspot_key_enc", "TEXT", "''")
    _add_col("settings", "pipedrive_key_enc", "TEXT", "''")

    # Settings: RAG
    _add_col("settings", "rag_enabled", "INTEGER", "0")
    _add_col("settings", "rag_similarity_threshold", "REAL", "0.75")

    # Settings: Router
    _add_col("settings", "routing_use_local_first", "INTEGER", "1")
    _add_col("settings", "routing_haiku_model", "TEXT", "'anthropic/claude-haiku-4-5'")

    # Settings: Cross-channel
    _add_col("settings", "cross_channel_enabled", "INTEGER", "0")

    # Settings: CRM
    _add_col("settings", "crm_platform", "TEXT", "NULL")

    # Settings: Triage
    _add_col("settings", "inbox_triage_enabled", "INTEGER", "0")
    _add_col("settings", "inbox_triage_schedule", "TEXT", "'08:00'")

    # Settings: Pacing
    _add_col("settings", "pacing_enabled", "INTEGER", "0")
    _add_col("settings", "pacing_eco_mode", "INTEGER", "1")

    # Settings: Gateway
    _add_col("settings", "gateway_enabled", "INTEGER", "0")

    # Settings: OpenRouter
    _add_col("settings", "openrouter_key_enc", "TEXT", "''")

    # Settings: Subscription auth tokens
    _add_col("settings", "anthropic_sub_token_enc", "TEXT", "''")
    _add_col("settings", "openai_sub_token_enc", "TEXT", "''")
    _add_col("settings", "openai_sub_refresh_enc", "TEXT", "''")

    # Settings: Multi-Agent System
    _add_col("settings", "agent_system_enabled", "INTEGER", "0")
    _add_col("settings", "observer_alert_threshold", "INTEGER", "80")
    _add_col("settings", "canary_agent_id", "INTEGER", "NULL")
    _add_col("settings", "fleet_description", "TEXT", "''")

    # Settings: Google Trends
    _add_col("settings", "trends_enabled", "INTEGER", "1")
    _add_col("settings", "trends_check_interval_hours", "INTEGER", "6")
    _add_col("settings", "trends_default_region", "TEXT", "'US'")
    _add_col("settings", "trends_auto_alert", "INTEGER", "1")

    # AgentTask: skill tracking
    _add_col("agent_tasks", "skill_id", "INTEGER", "NULL")

    # Settings: Auth mode per provider (api/subscription/none)
    _add_col("settings", "anthropic_auth_mode", "TEXT", "'none'")
    _add_col("settings", "openai_auth_mode", "TEXT", "'none'")

    # Agent hierarchy
    _add_col("agents", "rank", "INTEGER", "3")
    _add_col("agents", "reports_to_id", "INTEGER", "NULL")

    # Lead: lifecycle state (Phase 2)
    _add_col("leads", "lifecycle_state", "TEXT", "'new'")

    # Settings: Autonomy & Advanced Engines (Phase 8)
    _add_col("settings", "autonomy_level", "TEXT", "'supervised'")
    _add_col("settings", "reflection_enabled", "INTEGER", "1")
    _add_col("settings", "self_improvement_enabled", "INTEGER", "0")
    _add_col("settings", "knowledge_graph_enabled", "INTEGER", "0")
    _add_col("settings", "conversation_engine_enabled", "INTEGER", "0")

    # Settings: Research API keys & config
    _add_col("settings", "apify_key_enc", "TEXT", "''")
    _add_col("settings", "firecrawl_key_enc", "TEXT", "''")
    _add_col("settings", "tavily_key_enc", "TEXT", "''")
    _add_col("settings", "research_auto_enabled", "INTEGER", "1")
    _add_col("settings", "research_deep_threshold", "INTEGER", "7")

    # Settings: Voice / Twilio / TTS / STT
    _add_col("settings", "twilio_account_sid_enc", "TEXT", "''")
    _add_col("settings", "twilio_auth_token_enc", "TEXT", "''")
    _add_col("settings", "twilio_phone_number", "TEXT", "''")
    _add_col("settings", "elevenlabs_key_enc", "TEXT", "''")
    _add_col("settings", "elevenlabs_voice_id", "TEXT", "''")
    _add_col("settings", "voice_call_enabled", "INTEGER", "0")
    _add_col("settings", "voice_tts_provider", "TEXT", "'elevenlabs'")
    _add_col("settings", "voice_stt_provider", "TEXT", "'whisper_local'")
    _add_col("settings", "voice_max_call_duration_s", "INTEGER", "300")
    _add_col("settings", "piper_model_path", "TEXT", "''")

    # ─── Skills table: enhanced fields (Claude Agent SDK-inspired) ──────
    _add_col("skills", "description", "TEXT", "''")
    _add_col("skills", "instructions", "TEXT", "''")
    _add_col("skills", "input_schema", "TEXT", "'{}'")
    _add_col("skills", "output_schema", "TEXT", "'{}'")
    _add_col("skills", "examples", "TEXT", "'[]'")
    _add_col("skills", "category", "VARCHAR(50)", "'general'")
    _add_col("skills", "version", "VARCHAR(20)", "'1.0'")
    _add_col("skills", "capabilities", "TEXT", "'[]'")
    _add_col("skills", "tags", "TEXT", "'[]'")

    # ─── AgentTask: token tracking + dedup ─────────────────────────────
    _add_col("agent_tasks", "input_tokens", "INTEGER", "0")
    _add_col("agent_tasks", "output_tokens", "INTEGER", "0")
    _add_col("agent_tasks", "context_hash", "TEXT", "NULL")

    # ─── v2.0: Lead completeness ────────────────────────────────────
    _add_col("leads", "data_completeness_score", "REAL", "0.0")

    # ─── v2.0: EnrichmentData — Layer 0 (DNS/WHOIS/SSL) ─────────────
    _add_col("enrichment_data", "whois_registrar", "TEXT", "NULL")
    _add_col("enrichment_data", "mx_records_valid", "INTEGER", "NULL")
    _add_col("enrichment_data", "has_ssl", "INTEGER", "NULL")
    _add_col("enrichment_data", "is_mobile_responsive", "INTEGER", "NULL")
    _add_col("enrichment_data", "tech_stack", "TEXT", "''")
    _add_col("enrichment_data", "social_links", "TEXT", "''")

    # ─── v2.0: EnrichmentData — Layer 1 (Ollama extraction) ─────────
    _add_col("enrichment_data", "decision_maker_name", "TEXT", "NULL")
    _add_col("enrichment_data", "decision_maker_title", "TEXT", "NULL")
    _add_col("enrichment_data", "company_description", "TEXT", "''")
    _add_col("enrichment_data", "pain_points", "TEXT", "''")
    _add_col("enrichment_data", "icp_fit_score", "INTEGER", "NULL")

    # ─── v2.0: EnrichmentData — Layer 2 (Free APIs) ─────────────────
    _add_col("enrichment_data", "gmaps_phone", "TEXT", "NULL")
    _add_col("enrichment_data", "gmaps_category", "TEXT", "NULL")
    _add_col("enrichment_data", "gmaps_hours", "TEXT", "''")
    _add_col("enrichment_data", "company_size_estimate", "TEXT", "NULL")
    _add_col("enrichment_data", "industry_tag", "TEXT", "NULL")
    _add_col("enrichment_data", "linkedin_url", "TEXT", "NULL")

    # ─── v2.0: EnrichmentData — Layer 4 (Deep crawl) ────────────────
    _add_col("enrichment_data", "email_source", "TEXT", "NULL")
    _add_col("enrichment_data", "data_sources", "TEXT", "'[]'")
    _add_col("enrichment_data", "deep_crawl_summary", "TEXT", "''")

    # ─── v2.0: Settings — Business / Invoice ─────────────────────────
    _add_col("settings", "company_legal_name", "TEXT", "''")
    _add_col("settings", "company_address", "TEXT", "''")
    _add_col("settings", "company_tax_id", "TEXT", "''")
    _add_col("settings", "company_iban", "TEXT", "''")
    _add_col("settings", "company_swift", "TEXT", "''")
    _add_col("settings", "company_bank_name", "TEXT", "''")
    _add_col("settings", "invoice_prefix", "TEXT", "'INV-'")
    _add_col("settings", "invoice_next_number", "INTEGER", "1")
    _add_col("settings", "invoice_currency", "TEXT", "'EUR'")
    _add_col("settings", "payment_terms_days", "INTEGER", "30")
    _add_col("settings", "invoice_notes", "TEXT", "''")
    _add_col("settings", "company_logo_path", "TEXT", "''")
    _add_col("settings", "company_email", "TEXT", "''")
    _add_col("settings", "company_phone", "TEXT", "''")
    _add_col("settings", "company_website", "TEXT", "''")
    _add_col("settings", "telegram_owner_chat_id", "TEXT", "''")

    # ─── v2.0: Invoice approval lifecycle fields ──────────────────────
    _add_col("invoices", "approval_requested_at", "DATETIME", "NULL")
    _add_col("invoices", "approval_call_count", "INTEGER", "0")
    _add_col("invoices", "approved_at", "DATETIME", "NULL")
    _add_col("invoices", "sent_at", "DATETIME", "NULL")
    _add_col("invoices", "paid_at", "DATETIME", "NULL")

    # ─── v2.0: Enrichment daily counters (persisted) ──────────────────
    _add_col("settings", "enrichment_gmaps_count", "INTEGER", "0")
    _add_col("settings", "enrichment_gmaps_date", "TEXT", "''")
    _add_col("settings", "enrichment_clearbit_count", "INTEGER", "0")
    _add_col("settings", "enrichment_clearbit_date", "TEXT", "''")
    _add_col("settings", "gmaps_api_key_enc", "TEXT", "''")

    # ─── v2.0: CREATE TABLE IF NOT EXISTS for new models ──────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL,
            description TEXT DEFAULT '',
            base_price REAL DEFAULT 0.0,
            max_price REAL DEFAULT 0.0,
            unit VARCHAR(50) DEFAULT 'project',
            category VARCHAR(100) DEFAULT 'general',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number VARCHAR(50) UNIQUE NOT NULL,
            lead_id INTEGER REFERENCES leads(id),
            campaign_id INTEGER REFERENCES campaigns(id),
            client_name VARCHAR(255) DEFAULT '',
            client_email VARCHAR(255) DEFAULT '',
            client_address TEXT DEFAULT '',
            subtotal REAL DEFAULT 0.0,
            tax_rate REAL DEFAULT 0.0,
            tax_amount REAL DEFAULT 0.0,
            total REAL DEFAULT 0.0,
            currency VARCHAR(10) DEFAULT 'EUR',
            status VARCHAR(30) DEFAULT 'draft',
            approval_status VARCHAR(30) DEFAULT 'pending',
            due_date TIMESTAMP,
            pdf_path VARCHAR(500),
            pricing_rationale TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL REFERENCES invoices(id),
            service_id INTEGER REFERENCES services(id),
            description VARCHAR(500) DEFAULT '',
            quantity REAL DEFAULT 1.0,
            unit_price REAL DEFAULT 0.0,
            total REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS finance_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER REFERENCES leads(id),
            invoice_id INTEGER REFERENCES invoices(id),
            note_type VARCHAR(50) DEFAULT 'general',
            content TEXT DEFAULT '',
            created_by VARCHAR(100) DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS discord_server_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id VARCHAR(30) UNIQUE NOT NULL,
            guild_name VARCHAR(255) DEFAULT '',
            channel_dashboard VARCHAR(30),
            channel_leads VARCHAR(30),
            channel_outreach VARCHAR(30),
            channel_fleet VARCHAR(30),
            channel_approvals VARCHAR(30),
            channel_invoices VARCHAR(30),
            channel_logs VARCHAR(30),
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── Indexes for frequently queried columns ──────────────────────
    indexes = [
        ("ix_leads_campaign_id", "leads", "campaign_id"),
        ("ix_leads_status", "leads", "status"),
        ("ix_leads_email", "leads", "email"),
        ("ix_leads_lifecycle_state", "leads", "lifecycle_state"),
        ("ix_campaigns_status", "campaigns", "status"),
        ("ix_agent_tasks_agent_id", "agent_tasks", "agent_id"),
        ("ix_agent_tasks_status", "agent_tasks", "status"),
        ("ix_agent_tasks_task_type", "agent_tasks", "task_type"),
        ("ix_follow_up_sends_lead_id", "follow_up_sends", "lead_id"),
        ("ix_follow_up_sends_status", "follow_up_sends", "status"),
        ("ix_agent_tickets_status", "agent_tickets", "status"),
        ("ix_agent_tickets_assignee_id", "agent_tickets", "assignee_id"),
        ("ix_crm_sync_log_lead_id", "crm_sync_log", "lead_id"),
        ("ix_command_log_source", "command_log", "source"),
        ("ix_command_log_created_at", "command_log", "created_at"),
        # v2.0 indexes
        ("ix_invoices_lead_id", "invoices", "lead_id"),
        ("ix_invoices_status", "invoices", "status"),
        ("ix_invoices_approval_status", "invoices", "approval_status"),
        ("ix_invoice_line_items_invoice_id", "invoice_line_items", "invoice_id"),
        ("ix_finance_notes_lead_id", "finance_notes", "lead_id"),
        ("ix_finance_notes_invoice_id", "finance_notes", "invoice_id"),
        ("ix_discord_server_configs_guild_id", "discord_server_configs", "guild_id"),
        ("ix_leads_data_completeness", "leads", "data_completeness_score"),
    ]
    for idx_name, table, column in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
        except sqlite3.OperationalError:
            pass  # Table may not exist yet

    conn.commit()
    conn.close()
