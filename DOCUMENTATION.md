# Aura — Technical Documentation

> **Version**: 2.5.0
> **Stack**: Python 3.14 | PySide6 | SQLAlchemy | SQLite | LiteLLM
> **Platform**: Windows | macOS | Linux (packaged via PyInstaller)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Structure](#2-project-structure)
3. [Database Layer](#3-database-layer)
4. [Core Engines](#4-core-engines)
5. [Controllers](#5-controllers)
6. [UI Layer](#6-ui-layer)
7. [Multi-Agent System](#7-multi-agent-system)
8. [Ticket / Kanban System](#8-ticket--kanban-system)
9. [Command History System](#9-command-history-system)
10. [Advanced AI Engines](#10-advanced-ai-engines)
11. [LLM Router & Cost Pacing](#11-llm-router--cost-pacing)
12. [External Integrations](#12-external-integrations)
13. [Security & Encryption](#13-security--encryption)
14. [Configuration Reference](#14-configuration-reference)
15. [Build & Deployment](#15-build--deployment)
16. [Testing](#16-testing)
17. [Theming & Design System](#17-theming--design-system)

---

## 1. Architecture Overview

Aura is a desktop lead-generation and outreach automation platform built with a layered MVC architecture:

```
┌─────────────────────────────────────────────────────┐
│                   UI Layer (PySide6)                 │
│  Pages (14) │ Components (9) │ Chat Panel │ Sidebar  │
├─────────────────────────────────────────────────────┤
│                  Controller Layer                    │
│  20 QObject controllers with Signal/Slot wiring      │
├─────────────────────────────────────────────────────┤
│                  Core Engine Layer                    │
│  50+ specialized engines (business logic)            │
├─────────────────────────────────────────────────────┤
│                  Database Layer                       │
│  SQLAlchemy ORM │ SQLite (WAL mode) │ 50+ tables     │
├─────────────────────────────────────────────────────┤
│                  External Services                    │
│  LiteLLM │ Apollo │ Twilio │ Telegram │ Discord │ IMAP│
└─────────────────────────────────────────────────────┘
```

**Key Design Principles:**
- **Signal-driven UI**: All controllers inherit `QObject`, emit signals consumed by UI pages
- **Background threading**: Long operations run in `ThreadWorker` (QThread) to keep the UI responsive
- **Engine composition**: Engines are injected into each other (e.g., AIEngine receives RouterEngine)
- **Result pattern**: All engine methods return `{"success": bool, "data": ..., "error": "..."}`
- **QSS-only styling**: No inline `setStyleSheet()` — all visual design is managed via QSS objectNames
- **Hardware-bound encryption**: API keys encrypted with Fernet derived from machine hardware ID

---

## 2. Project Structure

```
AuraApp/
├── main.py                    # Application entry point
├── config.py                  # Global constants, enums, paths, design tokens
├── aura.spec                  # PyInstaller build specification
│
├── database/
│   ├── schema.py              # 50+ SQLAlchemy ORM models
│   └── db_manager.py          # DB init, migrations, seeding (18 skills, 20 agents)
│
├── core/                      # 50+ business logic engines
│   ├── ai_engine.py           # Universal LiteLLM adapter (2-tier routing)
│   ├── model_fleet.py         # Provider + model registry (10 providers, custom IDs)
│   ├── model_verifier.py      # Two-step model validation (auth + live round trip)
│   ├── router_engine.py       # 4-tier LLM router (local → ollama → haiku → sonnet)
│   ├── scraper_engine.py      # Multi-source web scraper (DDG → GMaps → Yelp)
│   ├── agent_engine.py        # Agent lifecycle, task execution, delegation
│   ├── fleet_orchestrator.py  # Multi-agent coordination, dispatch, canary testing
│   ├── ticket_engine.py       # Ticket CRUD, status transitions, hierarchy
│   ├── escalation_engine.py   # Blocked-ticket detection, rank-based escalation
│   ├── command_history.py     # Unified activity log with tree traversal
│   ├── gateway_engine.py      # External messaging gateway (Telegram/Discord)
│   ├── orchestrator_engine.py # Natural language command interpreter
│   ├── pacing_engine.py       # Budget cruise-control for LLM costs
│   ├── research_engine.py     # Multi-provider lead research orchestration
│   ├── voice_call_engine.py   # Twilio WebSocket voice calling
│   ├── case_engine.py         # Per-lead case files and living summaries
│   ├── token_manager.py       # Token estimation, context compaction, response caching
│   ├── subagent_engine.py     # Task decomposition into subtasks
│   ├── reflection_engine.py   # Post-action critique and scoring
│   ├── lead_lifecycle_engine.py # 19-state lead lifecycle FSM
│   ├── knowledge_graph_engine.py # Entity-relationship graph
│   ├── conversation_engine.py # Multi-turn thread management
│   ├── self_improvement_engine.py # Performance monitoring and learning
│   ├── strategy_engine.py     # Goal-oriented backward planning
│   ├── skill_registry.py      # 18 built-in skill definitions
│   ├── navigation_service.py  # Cross-page navigation with context
│   ├── hubspot_engine.py      # HubSpot CRM search and enrichment
│   ├── linkedin_engine.py     # LinkedIn CSV import
│   ├── observer_engine.py     # Fleet health monitoring
│   ├── response_formatter.py  # Multi-platform output (Telegram/Discord/Chat/CLI)
│   ├── enrichment_scoring.py  # Weighted completeness scoring
│   ├── excel_export_engine.py # Professional .xlsx exports with charts
│   ├── pricing_engine.py      # Service CRUD, invoice gen, PDF, revenue
│   ├── invoice_approval_engine.py # Approval flow with rank-based escalation
│   ├── ... (15+ more)
│   ├── voice/                 # TTS (ElevenLabs, OpenAI, Piper) + STT (Whisper)
│   ├── enrichment_layers/     # DNS/WHOIS, Ollama, free APIs, deep crawl
│   ├── research_providers/    # Tavily, Firecrawl, Apify research providers
│   └── gateway_adapters/      # Telegram & Discord bot adapters + server mode
│
├── controllers/               # 20 signal-based UI controllers
│   ├── dashboard_controller.py
│   ├── hunter_controller.py
│   ├── forge_controller.py
│   ├── outreach_controller.py
│   ├── fleet_controller.py
│   ├── kanban_controller.py
│   ├── command_history_controller.py
│   ├── ... (8 more)
│
├── ui/
│   ├── main_window.py         # App shell, page stack, controller wiring
│   ├── pages/                 # 14 page views
│   │   ├── dashboard.py       # Campaign overview and analytics
│   │   ├── hunter.py          # Lead scraping and discovery
│   │   ├── forge.py           # AI skill/persona management
│   │   ├── outreach.py        # Email generation and multi-channel
│   │   ├── fleet.py           # Multi-agent fleet management
│   │   ├── kanban.py          # Ticket/task Kanban board
│   │   ├── history.py         # Command history and activity log
│   │   ├── trends.py          # Google Trends intelligence
│   │   ├── budget.py          # Cost pacing and budget monitoring
│   │   ├── integrations.py    # Telegram/Discord connections
│   │   ├── settings.py        # 6-tab layout: API Keys, AI, Email, Features, Business, Appearance
│   │   ├── suppression.py     # Email/domain suppression list
│   │   ├── research.py        # Multi-source lead research and reports
│   │   └── calls.py           # Voice call system and call logs
│   └── components/            # 9 reusable UI components
│       ├── sidebar.py         # Navigation rail (14 pages)
│       ├── chat_panel.py      # Slide-in chat interface
│       ├── glass_card.py      # Glassmorphism containers + StatCards
│       ├── modern_button.py   # Styled buttons with loading state
│       ├── empty_state.py     # Empty data placeholders
│       ├── masked_input.py    # Secure API key input with reveal
│       ├── toast_notification.py # Auto-dismiss corner notifications
│       └── command_palette.py # Ctrl+K fuzzy search across pages and actions
│
├── assets/
│   ├── themes/
│   │   ├── neon_dark.qss      # Dark theme (~2000 lines)
│   │   └── neon_light.qss     # Light theme (~2000 lines)
│   ├── fonts/                 # Inter font family
│   └── icons/
│
├── utils/
│   ├── logger.py              # Rotating file logger (5MB, 3 backups)
│   └── thread_worker.py       # QThread wrapper with signals
│
└── tests/                     # 1,362 tests across 55 files
    ├── conftest.py            # InMemoryDatabaseManager, shared fixtures
    ├── test_scraper.py
    ├── test_ai_engine.py
    ├── test_ticket_engine.py
    ├── test_command_history.py
    ├── test_voice_call_engine.py
    ├── test_research_engine.py
    ├── test_integration_gaps.py
    ├── test_enrichment_layers.py
    ├── test_excel_export_engine.py
    ├── test_pricing_engine.py
    ├── test_discord_server.py
    ├── test_telegram_commands.py
    ├── test_settings_controller.py
    ├── test_integration_v2.py
    └── ... (30+ more)
```

---

## 3. Database Layer

### 3.1 DatabaseManager

**Location**: `database/db_manager.py`

SQLite with WAL mode for concurrent read/write. Uses `session_scope()` context manager for transactional safety:

```python
with self.db_manager.session_scope() as session:
    lead = session.query(Lead).filter_by(id=lead_id).first()
    lead.status = "qualified"
    # auto-commits on exit
```

**Initialization sequence** (called from `main.py`):
1. `init_db()` — Create all tables from SQLAlchemy metadata
2. `migrate_schema()` — Idempotent ALTER TABLE migrations (safe to re-run)
3. `seed_defaults()` — Insert singleton Settings + 18 built-in Skills
4. `seed_default_agents()` — Insert 19 agents with full personas + hierarchy

### 3.2 Schema Models (39 tables)

| Category | Models | Purpose |
|----------|--------|---------|
| **Lead Gen** | Campaign, Lead, Skill, Settings | Core outreach pipeline |
| **Sequences** | FollowUpSequence, FollowUpStep, FollowUpSend | Multi-step follow-ups |
| **Enrichment** | EnrichmentData, SuppressionEntry | Lead enrichment + blacklist |
| **Analytics** | ApiUsageLog, RagMemory, CrmSyncLog | Cost tracking, RAG, CRM sync |
| **Multi-Channel** | ChannelDraft | Email/LinkedIn/Twitter drafts |
| **Budget** | BudgetConfig | Pacing and tier management |
| **Gateway** | GatewayConfig, AuthorizedUser | Telegram/Discord config |
| **Agents** | Agent, AgentTask, AgentMessage, AgentMemoryLog | Multi-agent system |
| **Tickets** | AgentTicket, TicketComment, TicketDependency | Kanban/ticket system |
| **History** | CommandLog | Unified activity log |
| **Trends** | TrendsData, TrendsAlert | Google Trends analytics |
| **Advanced AI** | AgentReflection, PerformanceMetric, AgentLearnedRule, LeadStateTransition, KnowledgeNode, KnowledgeEdge, ConversationThread, StrategicGoal, GoalMilestone, PendingApproval | Phases 1-8 AI engines |
| **Case/Token** | CaseNote, CaseMemory, CachedSummary, SubagentTask | Case files, token management, subagent decomposition |
| **Research** | ResearchReport | Multi-source lead research synthesis |
| **Voice** | VoiceCall | Twilio voice calling and transcripts |

### 3.3 Key Relationships

```
Campaign ──1:N──> Lead
Campaign ──M:1──> Skill (primary + A/B variant)
Lead ──1:1──> EnrichmentData
Lead ──1:N──> ChannelDraft
Lead ──1:N──> FollowUpSend
Lead ──1:1──> ResearchReport
Lead ──1:N──> CaseNote
Lead ──1:N──> VoiceCall
Lead ──1:N──> ConversationThread
Lead ──1:N──> LeadStateTransition

Agent ──1:N──> AgentTask
Agent ──M:1──> Agent (reports_to hierarchy)
Agent ──1:N──> AgentMessage
Agent ──1:N──> AgentTicket (as assignee/reporter)

AgentTicket ──1:N──> TicketComment
AgentTicket ──M:N──> AgentTicket (dependencies via TicketDependency)
AgentTicket ──1:N──> AgentTicket (parent/sub-tickets)

CommandLog ──1:N──> CommandLog (parent/child tree via parent_command_id)
```

---

## 4. Core Engines

### 4.1 Lead Generation Pipeline

| Engine | File | Purpose |
|--------|------|---------|
| **ScraperEngine** | `scraper_engine.py` | Multi-source scraper: DuckDuckGo → Google Maps → Yelp fallback. Includes Tier 1 "Doorman" filter (pure Python, no AI cost). Human-like jitter via SafetyGuard. |
| **EnrichmentEngine** | `enrichment_engine.py` | Waterfall enrichment: local checks → Apollo → Hunter. Google Maps presence, WHOIS domain age, social media checks, website screenshots via Playwright. |
| **AIEngine** | `ai_engine.py` | Universal LiteLLM adapter. Tier 2 (cheap model) for qualification with auto-escalation for borderline scores (4-6). Tier 3 (premium) for email generation. |
| **SafetyGuard** | `safety_guard.py` | Human-like request pacing with random jitter (2-6s), reading pauses every 15 requests, break pauses every 50. Kill switch after 5 consecutive failures (30-min cooldown). |

**Pipeline flow:**
```
Scrape → Tier 1 Filter → Save → Enrich → Qualify (AI Tier 2) → Generate Email (AI Tier 3) → Send
```

### 4.2 Email Delivery & Follow-ups

| Engine | File | Purpose |
|--------|------|---------|
| **DeliveryEngine** | `delivery_engine.py` | Resend (primary) → SMTP (fallback). Daily limit enforcement, inline screenshot embedding, RAG storage of sent emails. |
| **SequenceEngine** | `sequence_engine.py` | Multi-step follow-up sequences with configurable delay_days between steps. Context-aware prompts include all prior sends. |
| **SchedulerEngine** | `scheduler_engine.py` | Timezone-aware scheduling. Detects lead timezone from city, calculates optimal send time (9am local). |
| **ReplyDetector** | `reply_detector.py` | IMAP inbox scanning for replies. Subject-line matching, lead status updates, follow-up cancellation, RAG storage. |
| **TriageEngine** | `triage_engine.py` | Morning inbox triage: categorize (reply/bounce/unsubscribe/other), generate executive summary, auto-draft warm replies, process unsubscribes. |

### 4.3 Intelligence & Analysis

| Engine | File | Purpose |
|--------|------|---------|
| **RAGEngine** | `rag_engine.py` | Local RAG for email style mimicry. TF-IDF embeddings (Ollama fallback to local). Cosine similarity matching. Replied emails weighted higher. |
| **ABEngine** | `ab_engine.py` | A/B testing for skill variants. Deterministic assignment (lead_id modulo). Minimum 20 sends for confidence. Winner determination. |
| **AnalystEngine** | `analyst_engine.py` | AI-powered performance analysis using real campaign data. Never fabricates numbers. |
| **TrendsEngine** | `trends_engine.py` | Google Trends via pytrends. Interest over time, related queries, geographic distribution, spike detection, rising niche discovery. Cached with TTL. |
| **ReportEngine** | `report_engine.py` | Campaign reports: PDF (ReportLab) and CSV exports. Stats tables, lead lists, summary views. |

### 4.4 External Integrations

| Engine | File | Purpose |
|--------|------|---------|
| **ApolloEngine** | `apollo_engine.py` | Apollo.io people search and enrichment. All requests via APIQueue. |
| **HunterEngine** | `hunter_engine.py` | Hunter.io email finding and verification. All requests via APIQueue. |
| **CRMEngine** | `crm_engine.py` | HubSpot + Pipedrive CRM sync. Contact/deal creation, status mapping, sync logging. |
| **APIQueue** | `api_queue.py` | Rate-limit-aware HTTP request queue. Per-service rate limiting, exponential backoff, usage logging. |
| **GatewayEngine** | `gateway_engine.py` | Central gateway for Telegram/Discord. Authorization gate, intent routing via orchestrator, platform-aware response formatting. |
| **ChannelEngine** | `channel_engine.py` | Multi-channel draft generation: email + LinkedIn + Twitter. Router-aware LLM calls. |

### 4.5 System Engines

| Engine | File | Purpose |
|--------|------|---------|
| **RouterEngine** | `router_engine.py` | 4-tier LLM router: local Python → Ollama → Haiku → Sonnet. Task-based routing with tier fallback. Pacing-aware. |
| **PacingEngine** | `pacing_engine.py` | Budget cruise-control. Tier governor, eco-mode fallback chain, burn-rate tracking, projected runway. |
| **KeyVault** | `key_vault.py` | Hardware-bound Fernet encryption derived from machine hardware ID. Encrypt/decrypt/mask API keys. |
| **OrchestratorEngine** | `orchestrator_engine.py` | Natural language command interpreter. AI-powered intent parsing with confidence scoring. Executes routed intents. Rolling 20-message history. |
| **SuppressionEngine** | `suppression_engine.py` | Global email/domain blacklist with in-memory set cache (10-min TTL). CSV bulk import. |
| **BatchImporter** | `batch_importer.py` | CSV-based batch campaign creation. Validates required columns, resolves skill names, inter-campaign jitter. |

---

## 5. Controllers

All controllers inherit `QObject` and use Qt's Signal/Slot system for UI communication. Long operations use `ThreadWorker` for background execution.

| Controller | File | Signals | Purpose |
|------------|------|---------|---------|
| **DashboardController** | `dashboard_controller.py` | stats_ready | Aggregate campaign/lead/API stats |
| **HunterController** | `hunter_controller.py` | lead_found, scrape_progress, scrape_finished, kill_switch_activated | Scraping pipeline orchestration |
| **ForgeController** | `forge_controller.py` | skills_changed, skill_saved, skill_error | Skill CRUD + JSON import/export |
| **OutreachController** | `outreach_controller.py` | email_generated, email_sent, batch_progress, all_channels_drafted | Email generation + delivery + scheduling |
| **FleetController** | `fleet_controller.py` | fleet_status_ready, health_check_ready, agent_status_ready, dispatch_result | Fleet boot/shutdown, health monitoring, task dispatch |
| **KanbanController** | `kanban_controller.py` | board_ready, ticket_created/moved/updated/deleted, due_date_alerts, sprint_created | Ticket CRUD + board operations |
| **CommandHistoryController** | `command_history_controller.py` | history_ready, command_tree_ready, stats_ready, prune_complete | History query, filter, tree view, prune |
| **ChatController** | `chat_controller.py` | response_ready, thinking, progress | AI chat via OrchestratorEngine |
| **BudgetController** | `budget_controller.py` | status_updated, tier_downgraded, budget_warning, budget_expired | Budget pacing lifecycle + monitoring |
| **TrendsController** | `trends_controller.py` | interest_ready, related_ready, opportunities_ready, alerts_ready | Google Trends queries + alerts |
| **SettingsController** | `settings_controller.py` | settings_saved, theme_changed, auth_mode_changed | API keys, models, SMTP, theme, toggles |
| **GatewayController** | `gateway_controller.py` | message_received, connection_status, notification_sent | Platform adapter lifecycle |
| **EnrichmentApiController** | `enrichment_api_controller.py` | lead_enriched, search_progress, rate_limited | Apollo/Hunter API operations |
| **SequenceController** | `sequence_controller.py` | followup_sent, batch_complete | 30-min timer for follow-up sends |
| **ReplyController** | `reply_controller.py` | reply_detected, triage_complete | 2-hr reply check + daily triage |
| **ResearchController** | `research_controller.py` | research_started, research_completed, research_failed, queue_updated, reports_ready | Multi-source research orchestration |
| **VoiceController** | `voice_controller.py` | call_started, call_ended, call_failed, transcript_update, server_status | Twilio voice calling integration |
| **AutonomyController** | `autonomy_controller.py` | approval_queued, approval_approved, approval_denied, autonomy_level_changed | Approval queue and autonomy governance |

### Timer-Based Background Operations

| Controller | Timer | Interval | Action |
|------------|-------|----------|--------|
| FleetController | Heartbeat | 1 min | Agent heartbeat check |
| FleetController | Observer | 5 min | Fleet health monitoring |
| FleetController | Escalation | 5 min | Blocked ticket escalation |
| BudgetController | Pacing | 1 min | Budget burn-rate check |
| SequenceController | Follow-up | 30 min | Due follow-up processing |
| ReplyController | Reply check | 2 hr | IMAP inbox scan |
| ReplyController | Triage schedule | 1 min | Daily triage time check |
| OutreachController | Schedule drain | 5 min | Scheduled email send |
| FleetController | Caller check | 5 min | Stalled lead detection for voice calls |

---

## 6. UI Layer

### 6.1 Main Window Layout

```
┌──────────┬──────────────────────────────────┬──────────┐
│          │  Top Bar (56px)  [💬 Chat Toggle] │          │
│          ├──────────────────────────────────┤          │
│ Sidebar  │                                  │  Chat    │
│ (220px)  │      Page Stack (14 pages)       │  Panel   │
│          │                                  │ (400px)  │
│ 14 nav   │                                  │ (hidden  │
│ buttons  │                                  │  default)│
│          ├──────────────────────────────────┤          │
│          │  Status Bar (32px)               │          │
└──────────┴──────────────────────────────────┴──────────┘
```

### 6.2 Pages (14)

| Index | Page | File | Purpose |
|-------|------|------|---------|
| 0 | Dashboard | `dashboard.py` | Campaign overview: stat cards, pipeline funnel, A/B results, fleet health, trends, ticket pipeline |
| 1 | Hunter | `hunter.py` | Lead scraping: search form, real-time results table, batch CSV import, Apollo search |
| 2 | Forge | `forge.py` | AI persona management: skill list + editor, A/B stats, RAG memory management |
| 3 | Outreach | `outreach.py` | Email workflow (5 tabs): Compose, Sequences, Replies, Scheduled, Channels |
| 4 | Fleet | `fleet.py` | Agent fleet: stat grid, agent cards with detail dialogs, observer panel |
| 5 | Kanban | `kanban.py` | 5-column Kanban board: Backlog → To Do → In Progress → Review → Done |
| 6 | History | `history.py` | Command history: filter bar, expandable command trees, pagination, detail dialog |
| 7 | Trends | `trends.py` | Google Trends: keyword analysis, related queries, opportunity discovery, alerts |
| 8 | Budget | `budget.py` | Cost pacing: budget config, pre-flight check, real-time burn-rate monitor |
| 9 | Integrations | `integrations.py` | Platform connections (Telegram/Discord), access control, notification prefs |
| 10 | Settings | `settings.py` | API keys, auth modes, model selection, SMTP/IMAP, theme, feature toggles |
| 11 | Suppression | `suppression.py` | Email/domain suppression list management + CSV import |
| 12 | Research | `research.py` | Multi-source lead research, provider badges, queue, report viewer |
| 13 | Calls | `calls.py` | Voice call system: active calls, call log, transcript viewer |

### 6.3 Components (9)

| Component | File | Purpose |
|-----------|------|---------|
| **Sidebar** | `sidebar.py` | Navigation rail with 14 buttons, active state via QSS property |
| **ChatPanel** | `chat_panel.py` | Slide-in chat: message bubbles, typing indicator, confirmation cards, inline editors, progress widgets |
| **GlassCard** | `glass_card.py` | Glassmorphism container + StatCard with accent variants (blue/green/purple/orange/red/cyan/pink) |
| **ModernButton** | `modern_button.py` | Styled button with primary/secondary/danger/ghost variants and loading state |
| **EmptyState** | `empty_state.py` | Empty data placeholder with icon, title, subtitle, optional action button |
| **MaskedInput** | `masked_input.py` | Secure API key field with reveal/hide toggle |
| **ToastNotification** | `toast_notification.py` | Auto-dismiss corner notifications (success/error/warning/info), stackable |
| **CommandPalette** | `command_palette.py` | Ctrl+K fuzzy search across pages, actions, and commands |

---

## 7. Multi-Agent System

### 7.1 Agent Hierarchy (20 Agents)

```
Commander (rank 1, orchestrator)
├── Scheduler (rank 2, orchestrator)
├── Triage Lead (rank 2, orchestrator)
│   ├── Scout (rank 3, worker)
│   ├── Enricher (rank 3, worker)
│   ├── Qualifier (rank 3, worker)
│   ├── Closer (rank 3, worker)
│   ├── Postman (rank 3, worker)
│   └── Tracker (rank 3, worker)
├── Analyst (rank 2, worker)
│   └── Trend Spotter (rank 3, worker)
├── Forger (rank 2, worker)
├── Archivist (rank 3, worker)
├── Syncer (rank 3, worker)
├── Suppressor (rank 3, worker)
├── Reporter (rank 3, worker)
├── Accountant (rank 3, worker)
├── Caller (rank 3, worker)
├── Observer (rank 2, observer)
│   └── Canary (rank 3, canary)
```

### 7.2 Agent Lifecycle

Each agent has:
- **Soul**: Personality description (e.g., "Elite intelligence operative with a gift for uncovering hidden leads")
- **Mission**: Objectives (e.g., "Discover high-potential business prospects using multi-source scraping")
- **Playbook**: Step-by-step SOPs (numbered procedures)
- **Boundaries**: Hard constraints (e.g., "Never scrape personal social media accounts")
- **Model Tier**: LLM tier assignment (local/ollama/haiku/sonnet)
- **Status**: idle → running → paused → error

### 7.3 Task Dispatch Flow

```
User command → OrchestratorEngine.parse_intent()
  → FleetOrchestrator.dispatch(task_type, payload)
    → Find best agent (specialty map + availability)
    → AgentEngine.run_task(agent_id, task_type, payload)
      → Match skill (payload → name → map → default)
      → Build context (agent persona + history + skill + RAG)
      → RouterEngine.route(task_type, prompt)
      → Log to CommandHistory
      → Return result
```

### 7.4 Delegation & Escalation

- **Delegation depth limit**: Max 3 levels to prevent infinite loops
- **Skill delegation**: If no matching skill, delegate to Forger agent to create one
- **Escalation**: Blocked tickets escalate up the `reports_to` chain to Commander
- **Auto-approve rules**: Sub-tickets, self-assignments, and low-priority tickets auto-approve; others require Commander approval

---

## 8. Ticket / Kanban System

### 8.1 Ticket Lifecycle

```
backlog → todo → in_progress → review → done
                     ↑
                  blocked (special state)
```

### 8.2 Components

- **TicketEngine**: CRUD, status transitions, hierarchy enforcement, dependencies, comments
- **EscalationEngine**: Blocked ticket detection, rank-based escalation chain, Commander approval flow
- **TicketScheduler**: Due-date monitoring, sprint planning (labeled ticket groups), timeline queries
- **KanbanController**: Signal-based bridge to Kanban UI

### 8.3 Features

- Parent/child sub-tickets
- Ticket dependencies (blocking relationships)
- Priority levels: critical, high, medium, low
- Assignee + reporter tracking
- Due dates with warning alerts (4-hour threshold)
- Sprint planning (date-range + ticket assignment)
- Threaded comments (user + agent authors)
- Approval flow for agent-created tickets

---

## 9. Command History System

### 9.1 Architecture

Every user command from any channel (Telegram, Discord, in-app chat) is logged as a root `CommandLog` entry. Agent actions are logged as children, forming a tree:

```
[user_command] "Start a campaign for plumbers in Austin"
├── [intent_parsed] intent=start_campaign, confidence=0.92
├── [task_dispatched] Scout → scrape leads
│   └── [task_completed] 47 leads found
├── [task_dispatched] Qualifier → qualify leads
│   └── [task_completed] 23 qualified
└── [completed] Campaign created
```

### 9.2 Key Design

- **Tree structure**: `parent_command_id` (self-referential FK) forms parent-child trees
- **Correlation ID**: UUID grouping allows O(1) retrieval of entire command chain
- **Agent context injection**: `get_recent_for_agent_context()` provides condensed history for agent prompts
- **Automatic pruning**: Entries older than 90 days can be pruned

### 9.3 Integration Hooks

- **GatewayEngine**: Logs inbound commands before processing, updates status on completion/failure
- **AgentEngine**: Logs task dispatch/completion/failure as child commands
- **FleetOrchestrator**: Passes command IDs through dispatch chain

---

## 10. Advanced AI Engines

Phases 1-8 introduced 7 new core engines and 1 controller that add self-learning, lifecycle management, knowledge graphs, conversation handling, strategic planning, and autonomy control to the platform.

### 10.1 Reflection Engine

**Location**: `core/reflection_engine.py`
**Schema**: `AgentReflection`, `PerformanceMetric`, `AgentLearnedRule`

Post-action critique loop that evaluates agent outputs and drives iterative improvement. After an agent completes a task, the Reflection Engine scores the output on a 1-10 scale using the `REFLECTION_PROMPT` template routed through the LLM router. If the score falls below the revision threshold (default: 4), the engine triggers a revision cycle where the agent re-executes the task with critique feedback injected into the prompt. Reflection results are persisted as `AgentReflection` records for longitudinal performance tracking.

### 10.2 Lead Lifecycle Engine

**Location**: `core/lead_lifecycle_engine.py`
**Schema**: `LeadStateTransition`

A 19-state finite state machine that replaces the flat `LeadStatus` enum with a rich lifecycle model. The full state graph:

```
NEW → RESEARCHED → QUALIFYING → QUALIFIED → EMAIL_DRAFTED → SCHEDULED → CONTACTED
  → INTERESTED → OBJECTION_RAISED → OBJECTION_HANDLED → MEETING_SCHEDULED
  → PROPOSAL_SENT → NEGOTIATING → RE_ENGAGE_SCHEDULED → REPLIED
  → CONVERTED → CLOSED_WON → CLOSED_LOST
```

**Terminal states**: `closed_won`, `disqualified`

Each state transition supports three callback hooks:
- `on_enter` — Fires when a lead enters a state (e.g., trigger enrichment on entering RESEARCHED)
- `on_exit` — Fires when a lead leaves a state (e.g., log duration in QUALIFYING)
- `on_transition` — Fires on the transition edge itself (e.g., record the transition in audit trail)

All transitions are recorded in the `LeadStateTransition` table, providing a complete audit trail with timestamps, source state, target state, and the actor (user or agent) that triggered the change.

### 10.3 Advanced RAG Engine

**Location**: `core/rag_engine.py` (extended)

Multi-layer retrieval-augmented generation engine with TF-IDF as the primary local fallback and optional ChromaDB + sentence-transformers for high-fidelity vector search. Organizes knowledge into 4 collections:

| Collection | Purpose |
|------------|---------|
| `emails` | Sent email drafts and their outcomes (replies, opens) |
| `interactions` | Lead interaction history (calls, meetings, replies) |
| `knowledge` | Domain knowledge, SOPs, and reference material |
| `agent_learnings` | Learned rules and success patterns from agents |

Key methods:
- `store()` — Persist a document into a collection with metadata
- `query()` — Semantic search across one or more collections
- `store_interaction()` — Record a lead interaction with context
- `store_agent_learning()` — Persist an agent-discovered rule or pattern
- `extract_success_factors()` — Analyze high-performing emails to identify winning patterns
- `track_rag_feedback()` — Record whether a RAG-suggested example led to a positive outcome, enabling relevance tuning over time

### 10.4 Knowledge Graph Engine

**Location**: `core/knowledge_graph_engine.py`
**Schema**: `KnowledgeNode`, `KnowledgeEdge`

Entity-relationship graph engine that maps the connections between leads, companies, niches, campaigns, agents, and keywords. Nodes and edges are stored relationally and queried for pattern discovery.

**Node types**: `lead`, `company`, `niche`, `campaign`, `agent`, `keyword`

**Edge types**: `contacted_by`, `replied_to`, `competitor_of`, `similar_to`, `belongs_to`

Key capabilities:
- **Social proof discovery** — Find leads connected to companies that already replied positively, enabling warm introduction angles
- **Niche insights** — Aggregate conversion rates and engagement patterns by niche to identify the most responsive verticals
- **Competitor analysis** — Map competitor relationships between companies to avoid conflicting outreach and identify displacement opportunities

### 10.5 Conversation Engine

**Location**: `core/conversation_engine.py`
**Schema**: `ConversationThread`

Multi-turn email thread management engine that tracks ongoing conversations beyond simple reply detection. Classifies reply intent into one of 5 categories:

| Intent | Description |
|--------|-------------|
| `interested` | Lead expresses positive interest or asks for more info |
| `objection` | Lead raises a concern or pushback |
| `not_now` | Lead defers but does not reject outright |
| `question` | Lead asks a clarifying question |
| `unsubscribe` | Lead requests removal from outreach |

For objection intents, the engine generates suggested responses tailored to the specific objection type (price, timing, competitor, authority). For `not_now` intents, it schedules re-engagement at an appropriate future date. All messages within a thread are tracked in the `ConversationThread` table with full context preservation.

### 10.6 Self-Improvement Engine

**Location**: `core/self_improvement_engine.py`
**Schema**: Uses `PerformanceMetric`, `AgentLearnedRule`

Performance monitoring and continuous improvement engine. Analyzes agent output quality over time, detects underperformers, and extracts learned rules that can be injected into agent prompts.

Key operations:
- **Performance monitoring** — Track success rates, quality scores, and cost efficiency per agent
- **Underperformer detection** — Flag agents whose rolling metrics fall below fleet averages
- **Learned rule extraction** — Analyze high-performing outputs to distill reusable rules (e.g., "Emails mentioning a specific pain point get 3x more replies")
- `run_improvement_cycle()` — Daily orchestration method that runs the full pipeline: collect metrics, detect underperformers, extract rules, and update agent prompts

### 10.7 Strategy Engine

**Location**: `core/strategy_engine.py`
**Schema**: `StrategicGoal`, `GoalMilestone`

Goal-oriented planning engine that works backward from a revenue or conversion target to calculate the required activity volume at each pipeline stage.

**Backward calculation chain**:
```
Target Revenue → Deals Needed → Meetings Required → Replies Required
  → Emails to Send → Leads to Qualify → Contacts to Scrape
```

Each goal is broken into 5 phase milestones with estimated completion dates. The engine provides:
- **Phase tracking** — Progress monitoring across 5 sequential milestones
- **Cost estimation** — Projected AI and API spend to reach the goal based on historical per-unit costs
- **Feasibility analysis** — Whether the goal is achievable within the given timeframe and budget constraints

### 10.8 Autonomy Controller

**Location**: `controllers/autonomy_controller.py`
**Schema**: `PendingApproval`, `autonomy_level` column on `Settings`

QObject-based controller that governs what actions the AI agent fleet can execute without human approval. Implements 4 autonomy levels:

| Level | Name | Blocked Actions | Use Case |
|-------|------|-----------------|----------|
| 0 | OBSERVER | All actions | Monitoring only, no execution |
| 1 | SUPERVISED | `send_email`, `generate_email`, `crm_sync`, `skill_revision`, `make_call` | AI can research and qualify, but humans approve outreach and calls |
| 2 | AUTONOMOUS | `skill_revision`, `self_improvement`, `make_call` | AI handles full pipeline except modifying its own skills and making calls |
| 3 | FULL_TRUST | `make_call` | AI operates without restrictions except voice calls always require approval |

When an agent attempts a blocked action, the request is queued as a `PendingApproval` record. The approval queue is accessible through the UI, where users can:
- **Approve** — Execute the pending action
- **Deny** — Reject and discard the pending action

The current autonomy level is persisted in the `autonomy_level` column on the `Settings` table and can be changed from the Settings page.

### 10.9 Token Manager

**Location**: `core/token_manager.py`
**Schema**: `CachedSummary`

Token estimation and context budget management. Uses tiktoken when available, falling back to character/4 estimation. Provides three key capabilities:

- **Token estimation** — Accurate token counting for prompts and responses
- **Context compaction** — Task-aware section filtering via `TASK_CONTEXT_SECTIONS` mapping, reducing token usage by 40-60%
- **Response caching** — In-memory LRU cache keyed by context hash. Summary cache persisted in `CachedSummary` table for cross-session reuse

### 10.10 Case Engine

**Location**: `core/case_engine.py`
**Schema**: `CaseNote`, `CaseMemory`

Per-lead case file system that builds comprehensive context from 8 data sources. Each lead accumulates timestamped `CaseNote` entries and a living `CaseMemory` summary.

- `build_case_context()` — Assembles lead info + enrichment + notes + conversation + lifecycle + follow-ups + research
- Auto-summarizes via haiku when notes exceed `CASE_MEMORY_SUMMARIZE_THRESHOLD` (default: 10)
- Integrated into 7 systems: agent_engine, outreach_controller, lead_lifecycle_engine, reflection_engine, conversation_engine, self_improvement_engine, fleet_controller

### 10.11 Subagent Engine

**Location**: `core/subagent_engine.py`
**Schema**: `SubagentTask`

Task decomposition engine that breaks complex tasks into parallel subtasks using predefined decomposition patterns:

| Parent Task | Subtasks |
|-------------|----------|
| `generate_email` | extract_insights → draft → review_tone |
| `qualify_lead_complex` | check_website → assess_fit → score_lead |
| `research_company` | scrape_website → analyze_competitors → identify_gaps |

### 10.12 Research System

**Location**: `core/research_engine.py`, `core/research_providers/`
**Schema**: `ResearchReport`

Multi-source research orchestration with LLM synthesis. Three provider adapters:

| Provider | File | Capability |
|----------|------|-----------|
| **Tavily** | `tavily_provider.py` | Web search and summarization |
| **Firecrawl** | `firecrawl_provider.py` | Website scraping and content extraction |
| **Apify** | `apify_provider.py` | Advanced web automation |

Reports include: company overview, pain points, gaps & opportunities, services offered, tech stack, and competitor analysis. Auto-triggered after qualification with depth based on score vs `RESEARCH_DEEP_THRESHOLD`.

### 10.13 Voice Call System

**Location**: `core/voice_call_engine.py`, `core/voice/`
**Schema**: `VoiceCall`

Last-resort voice outreach via Twilio WebSocket Media Streams:

**TTS Cascade** (text-to-speech):
1. ElevenLabs (`core/voice/tts_elevenlabs.py`) — Premium voice synthesis
2. OpenAI TTS (`core/voice/tts_openai.py`) — Mid-tier fallback
3. Piper (`core/voice/tts_piper.py`) — Free local fallback

**STT** (speech-to-text): Whisper (`core/voice/stt_whisper.py`) — Local via faster-whisper or API via OpenAI

**Caller Agent**: Rank 3 worker that detects stalled leads (3+ failed emails or interested-but-silent 7+ days). Voice calls **always require approval** at every autonomy level.

### 10.14 Skill Registry

**Location**: `core/skill_registry.py`

18 built-in skills across 5 categories. Each skill defines: description, instructions, input/output schema, examples, capabilities, and tags.

- `find_best_skill_for_task()` — Capability overlap + category match scoring
- `build_skill_context()` — Structured prompt injection for agent tasks

### 10.15 Navigation Service

**Location**: `core/navigation_service.py`

Cross-page navigation with context passing. Named methods (`go_to_hunter()`, `go_to_outreach(campaign_id)`, etc.) and an action registry for command palette integration. All 14 pages implement `receive_context(context: dict)`.

---

## 11. LLM Router & Cost Pacing

### 11.1 4-Tier Router

| Tier | Engine | Cost/1K tokens | Tasks |
|------|--------|-----------------|-------|
| 0 - Local | Python functions | $0.00 | format_csv, normalize_data, regex_validation |
| 1 - Ollama | Local LLM | $0.00 | parse_html, classify_business, format_lead |
| 2 - Haiku | Claude Haiku | $0.0005 | qualify_lead, score_website, navigate_page |
| 3 - Sonnet | Claude Sonnet | $0.006 | generate_email, analyze_performance, RAG matching |

**Fallback chain**: If a tier fails, it falls back to the next higher tier. 429 rate limits trigger automatic escalation.

### 11.2 Budget Pacing

The PacingEngine acts as a "cruise control" for LLM spend:

- **Tier Governor**: Dynamically restricts the maximum tier based on burn rate
- **Eco-Mode**: Fallback chain downgrades tasks to cheaper tiers when budget is tight
- **Pre-flight Check**: Mathematical feasibility check before activation
- **Real-time Monitoring**: Tracks budget_usd, spent_usd, burn_rate, projected runway
- **Alerts**: Warnings at 50%, 80%, 95% thresholds; auto-expire on exhaustion

---

## 12. External Integrations

### 12.1 Messaging Platforms

- **Telegram**: Via `python-telegram-bot` library. Bot token stored encrypted. Adapter pattern.
- **Discord**: Via `discord.py` library. Bot token stored encrypted. Adapter pattern.
- **Authorization**: Per-platform user whitelist (`AuthorizedUser` table). Only authorized users can send commands.

### 12.2 APIs

| Service | Engine | Purpose |
|---------|--------|---------|
| Apollo.io | ApolloEngine | People/company search, lead enrichment |
| Hunter.io | HunterEngine | Email finding and verification |
| HubSpot | CRMEngine | Contact creation, deal pipeline sync |
| Pipedrive | CRMEngine | Person/deal creation and sync |
| Resend | DeliveryEngine | Primary email delivery |
| Google Trends | TrendsEngine | Trend analysis via pytrends |
| HubSpot | HubSpotEngine | CRM search, contact/company enrichment |
| LinkedIn | LinkedInEngine | CSV import (Sales Navigator exports) |

All external API calls are routed through `APIQueue` for rate limiting, exponential backoff, and usage logging.

### 12.3 SMTP/IMAP

- **SMTP**: Fallback email delivery when Resend unavailable
- **IMAP**: Inbox scanning for reply detection and morning triage

### 12.4 Voice Providers

| Service | Engine | Purpose |
|---------|--------|---------|
| Twilio | VoiceCallEngine | Call initiation, WebSocket media streams |
| ElevenLabs | ElevenLabsTTS | Premium text-to-speech |
| OpenAI TTS | OpenAITTS | Mid-tier text-to-speech fallback |
| Piper | PiperTTS | Free local text-to-speech |
| OpenAI Whisper | WhisperSTT | Speech-to-text (local or API) |

### 12.5 Research Providers

| Service | Engine | Purpose |
|---------|--------|---------|
| Tavily | TavilyProvider | Web search and summarization |
| Firecrawl | FirecrawlProvider | Website scraping and content extraction |
| Apify | ApifyProvider | Advanced web automation |

---

## 13. Security & Encryption

### 13.1 KeyVault

- **Encryption**: Fernet symmetric encryption (AES-128-CBC)
- **Key derivation**: PBKDF2 from machine hardware ID (`py-machineid`) + configurable salt
- **Stored encrypted**: All API keys, bot tokens, SMTP/IMAP passwords, subscription tokens
- **Masking**: Display format `sk-proj-****6789` (first chars + masked + last 4 chars)

### 13.2 Authorization

- **Gateway auth**: Per-platform user whitelist checked before processing any inbound message
- **Soft-delete**: Users are deactivated (not deleted) for audit trail

### 13.3 Data Safety

- **SQLite WAL mode**: Concurrent read/write without locking
- **Session scope**: Transactional context manager with auto-rollback on exception
- **Suppression list**: Global email/domain blacklist prevents sending to opted-out contacts
- **Kill switch**: Automatic scraper shutdown after 5 consecutive failures (30-min cooldown)

---

## 14. Configuration Reference

### 14.1 Paths

| Constant | Value | Purpose |
|----------|-------|---------|
| `DATA_DIR` | `~/.aura` | User data directory |
| `DB_PATH` | `~/.aura/aura.db` | SQLite database |
| `LOG_PATH` | `~/.aura/aura.log` | Rotating log file |
| `ASSETS_DIR` | (resolved) | Bundled assets (themes, fonts, icons) |

### 14.2 Timer Intervals

| Constant | Value | Purpose |
|----------|-------|---------|
| `AGENT_HEARTBEAT_CHECK_MS` | 60,000 (1 min) | Agent heartbeat polling |
| `OBSERVER_CHECK_INTERVAL_MS` | 300,000 (5 min) | Fleet health check |
| `ESCALATION_CHECK_INTERVAL_MS` | 300,000 (5 min) | Blocked ticket escalation |
| `PACING_CHECK_INTERVAL_MS` | 60,000 (1 min) | Budget burn-rate check |
| `FOLLOWUP_CHECK_INTERVAL_MS` | 1,800,000 (30 min) | Follow-up email processing |
| `REPLY_CHECK_INTERVAL_MS` | 7,200,000 (2 hr) | IMAP inbox scan |
| `SCHEDULE_CHECK_INTERVAL_MS` | 300,000 (5 min) | Scheduled email drain |
| `CALLER_CHECK_INTERVAL_MS` | 300,000 (5 min) | Stalled lead detection for voice calls |
| `DASHBOARD_REFRESH_INTERVAL_MS` | 60,000 (1 min) | Dashboard auto-refresh |

### 14.3 Limits

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_DAILY_EMAILS` | 100 | Daily send cap |
| `AGENT_MAX_DELEGATION_DEPTH` | 3 | Max delegation chain depth |
| `FLEET_MAX_CONCURRENT_TASKS` | 10 | Concurrent fleet tasks |
| `RAG_MAX_EXAMPLES` | 3 | Max RAG context examples |
| `TRENDS_MAX_KEYWORDS` | 5 | Max keywords per trends query |
| `COMMAND_HISTORY_MAX_RETENTION_DAYS` | 90 | History pruning threshold |
| `COMMAND_HISTORY_PAGE_SIZE` | 50 | History pagination size |
| `AGENT_CONTEXT_MAX_TOKENS` | 8,000 | Max context tokens per agent task |
| `CASE_NOTE_MAX_RECENT` | 20 | Max recent case notes in context |
| `CASE_MEMORY_SUMMARIZE_THRESHOLD` | 10 | Notes before auto-summarization |
| `CALLER_FAILED_EMAIL_THRESHOLD` | 3 | Failed emails before voice call eligible |
| `CALLER_STALLED_DAYS` | 7 | Days silent before stalled detection |
| `VOICE_MAX_CALL_DURATION_S` | 300 | Max call duration (5 min) |

### 14.4 AI Models (Defaults)

| Setting | Default | Purpose |
|---------|---------|---------|
| `DEFAULT_TIER2_MODEL` | `gemini/gemini-2.0-flash` | Qualification (cheap) |
| `DEFAULT_TIER3_MODEL` | `anthropic/claude-sonnet-4-6` | Email generation (premium) |
| `DEFAULT_HAIKU_MODEL` | `anthropic/claude-haiku-4-5` | Mid-tier tasks |

---

## 15. Build & Deployment

### 15.1 Development Setup

```bash
# Create virtual environment
python -m venv venv

# Install dependencies
venv/Scripts/pip install PySide6 sqlalchemy litellm cryptography py-machineid
venv/Scripts/pip install httpx beautifulsoup4 pytrends reportlab resend
venv/Scripts/pip install python-telegram-bot discord.py playwright

# Install browser for screenshots
venv/Scripts/playwright install chromium

# Run application
venv/Scripts/python main.py
```

### 15.2 Build Executable

```bash
venv/Scripts/pyinstaller aura.spec --noconfirm
# Output: dist/Aura/Aura.exe
```

The spec file bundles:
- 140+ hidden imports (all engines, controllers, UI modules)
- Assets directory (themes, fonts, icons)
- Playwright + LiteLLM dependencies

### 15.3 First Run

On first launch, if `settings.first_run_complete` is False, a SetupWizard modal guides the user through initial API key configuration.

---

## 16. Testing

### 16.1 Infrastructure

- **Framework**: pytest
- **Database**: `InMemoryDatabaseManager` (SQLite `:memory:`)
- **Fixtures** (`tests/conftest.py`):
  - `db` — Bare in-memory database
  - `db_with_agents` — Database with 20 seeded agents
  - `ticket_engine` — TicketEngine instance
  - `command_history` — CommandHistoryEngine instance
  - `qapp` — Session-scoped QCoreApplication for signal testing

### 16.2 Test Suite

| File | Tests | Coverage |
|------|-------|----------|
| `test_scraper.py` | Scraper filtering, deduplication, Tier 1 checks |
| `test_ai_engine.py` | Qualification, email generation, router integration |
| `test_delivery.py` | Email delivery, daily limits, SMTP fallback |
| `test_enrichment.py` | Waterfall enrichment, screenshot caching |
| `test_key_vault.py` | Encrypt/decrypt, masking, hardware binding |
| `test_schema.py` | Model creation, relationships, constraints |
| `test_ticket_engine.py` | CRUD, status transitions, dependencies, hierarchy |
| `test_escalation_engine.py` | Blocked detection, escalation chain, approval flow |
| `test_kanban_controller.py` | Board refresh, CRUD signals, due dates, sprints |
| `test_command_history.py` | Logging, trees, queries, stats, pruning, controller |
| `test_enrichment_layers.py` | DNS/WHOIS, Ollama, free APIs, deep crawl layers |
| `test_excel_export_engine.py` | .xlsx generation, multi-sheet, styling |
| `test_pricing_engine.py` | Service CRUD, invoice gen, PDF, approval flow, revenue |
| `test_discord_server.py` | Channel management, event routing, config persistence |
| `test_telegram_commands.py` | Command routing, arg parsing, inline keyboards |
| `test_settings_controller.py` | Business fields get/save, toggles, regression |
| `test_integration_v2.py` | Cross-engine integration for v2.0 features |
| ... | ... | ... |
| **Total** | **1,362 tests** | **100% passing** |

### 16.3 Running Tests

```bash
venv/Scripts/python.exe -m pytest tests/ -v --tb=long
```

---

## 17. Theming & Design System

### 17.1 Design Language

Framer/Apple Premium Minimalist. Two theme files:
- `assets/themes/neon_dark.qss` (~2000 lines)
- `assets/themes/neon_light.qss` (~2000 lines)

### 17.2 Dark Theme Tokens

| Token | Value |
|-------|-------|
| Background | `#09090F` |
| Sidebar | `#0C0C17` |
| Surface | `rgba(255,255,255,0.025)` |
| Border | `rgba(255,255,255,0.07)` |
| Text | `#FFFFFF` |
| Muted | `rgba(255,255,255,0.45)` |
| Accent | `#4E5BF2` (electric indigo) |
| Success | `#22C55E` |
| Warning | `#F59E0B` |
| Danger | `#EF4444` |

### 17.3 Light Theme Tokens

| Token | Value |
|-------|-------|
| Background | `#F5F5F7` (Apple gray) |
| Surface | `#FFFFFF` |
| Border | `#E8E8ED` |
| Text | `#1D1D1F` |
| Secondary | `#6E6E73` |
| Muted | `#AEAEB2` |
| Accent | `#4E5BF2` |
| Success | `#34C759` |
| Warning | `#FF9500` |

### 17.4 QSS ObjectName System

All styling is applied via `setObjectName()` in Python code and targeted in QSS files. Key objectNames:

**Layout**: `glassCard`, `statCard`, `statValue`, `statLabel`, `sectionHeader`

**Buttons**: `primaryButton`, `secondaryButton`, `dangerButton`, `exportButton`, `chipButton`

**Chat**: `chatPanel`, `chatBubbleUser`, `chatBubbleAI`, `typingIndicator`, `confirmCard`

**Kanban**: `ticketCard`, `ticketCardOverdue`, `kanbanColumn`, `kanbanColumnHeader`, `priorityDotCritical/High/Medium/Low`

**History**: `historyFilterBar`, `historyCommandRow`, `historyChildRow`, `historySourceBadgeTelegram/Discord/Chat/System`, `historyStatusCompleted/Failed/Running/Pending`

**Navigation**: `sidebarButton` (with `active` property), `logoText`, `navSectionLabel`, `versionLabel`

**Feedback**: `toastSuccess/Error/Warning/Info`, `badgeSuccess/Warning/Danger/Info`, `emptyState`

**Research**: `researchPage`, `researchConfigPanel`, `researchQueue`, `researchReportCard`

**Voice/Calls**: `callsPage`, `callConfigPanel`, `callLogTable`, `activeCallCard`, `callTranscriptPanel`

**Command Palette**: `commandPalette`, `commandPaletteInput`, `commandPaletteItem`, `crossNavButton`

---

*Document generated from codebase analysis. Last updated: 2026-03-07.*
