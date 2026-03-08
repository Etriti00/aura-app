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

    conn.commit()
    conn.close()
