<p align="center">
  <img src="assets/icons/aura_icon.png" alt="Aura Logo" width="120" height="120">
</p>

<h1 align="center">Aura</h1>
<p align="center">
  <strong>Your Local AI Sales Agent</strong><br>
  Autonomous lead generation, outreach, and deal closing — running entirely on your desktop.
</p>

<p align="center">
  <a href="https://github.com/Etriti00/aura-app/stargazers"><img src="https://img.shields.io/github/stars/Etriti00/aura-app?style=for-the-badge&color=4E5BF2" alt="Stars"></a>
  <a href="https://github.com/Etriti00/aura-app/issues"><img src="https://img.shields.io/github/issues/Etriti00/aura-app?style=for-the-badge" alt="Issues"></a>
  <a href="https://github.com/Etriti00/aura-app/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Etriti00/aura-app?style=for-the-badge" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform">
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> ·
  <a href="#-features">Features</a> ·
  <a href="#%EF%B8%8F-architecture">Architecture</a> ·
  <a href="DOCUMENTATION.md">Technical Docs</a> ·
  <a href="USER_MANUAL.md">User Manual</a>
</p>

---

## What is Aura?

Aura is a **desktop AI sales agent** that automates the entire B2B lead generation pipeline — from finding prospects to closing deals. It runs locally on your machine with a fleet of 20 specialized AI agents that handle prospecting, research, outreach, follow-ups, invoicing, and even voice calls.

Unlike cloud SaaS tools, Aura keeps your data local (SQLite), your API keys encrypted (machine-bound AES), and gives you full control over autonomy levels — from observer mode to full autopilot.

### The Pipeline

```
Find leads → Enrich & qualify → Deep research → Draft personalized emails
    → Send sequences → Detect replies → Classify intent → Handle objections
        → Follow up → Close deal    (or)    → Voice call as last resort
```

Every step is automated. Every step is configurable. Every step requires your approval until you say otherwise.

---

## Quick Start

### Install the CLI

```bash
# Install from source (recommended)
git clone https://github.com/Etriti00/aura-app.git
cd aura-app
pip install .

# Or install in editable/dev mode
pip install -e .

# Install the browser engine (needed for web scraping)
playwright install chromium
```

After installation, the `aura` command is available globally:

```bash
$ aura status
Aura v2.1.0 — System Status
───────────────────────────────
  Campaigns          0
  Leads              0
  Agents             20

$ aura help
$ aura hunt "plumber" --city "Austin TX"
$ aura                    # starts interactive REPL
```

### Install the Desktop App (GUI)

```bash
# Option A: Download pre-built executable
# → https://github.com/Etriti00/aura-app/releases
#   Windows: Aura.exe  |  macOS: Aura.app  |  Linux: ./Aura

# Option B: Install from source with GUI
git clone https://github.com/Etriti00/aura-app.git
cd aura-app
pip install ".[gui]"
playwright install chromium
aura-gui
```

### Cross-Platform Notes

| Platform | CLI Install | GUI Install | Build |
|----------|-------------|-------------|-------|
| **Windows** | `pip install .` → `aura` | `pip install ".[gui]"` → `aura-gui` | `pyinstaller aura.spec` → `dist\Aura\Aura.exe` |
| **macOS** | `pip install .` → `aura` | `pip install ".[gui]"` → `aura-gui` | `pyinstaller aura.spec` → `dist/Aura.app` |
| **Linux** | `pip install .` → `aura` | `pip install ".[gui]"` → `aura-gui` | `pyinstaller aura.spec` → `dist/Aura/Aura` |

**Prerequisites**: Python 3.10+ and Git.

### First Launch

On first launch, configure at least one AI API key:

```bash
# CLI
aura config-api-keys

# GUI
# The Setup Wizard opens automatically on first run
```

1. **AI Provider Key** — Anthropic (Claude), OpenAI, or Google (Gemini)
2. **Sender Identity** — `aura config-set sender_name "Your Name"`
3. **Email Delivery** — `aura config-smtp`

> All API keys are encrypted with machine-bound AES-256. They never leave your device.

---

## Features

### Lead Discovery & Enrichment
- **Multi-source scraping** — DuckDuckGo, Google Maps, Yelp
- **API integrations** — Apollo.io, Hunter.io, HubSpot CRM
- **CSV imports** — LinkedIn Sales Navigator exports, batch files
- **Auto-enrichment** — Email finder, phone lookup, website analysis
- **AI qualification** — Automatic lead scoring with LLM-powered assessment

### Deep Research
- **Multi-provider intelligence** — Tavily, Firecrawl, Apify
- **LLM synthesis** — Generates company overview, pain points, tech stack, gaps & opportunities
- **Auto-depth selection** — Quick research for low-score leads, deep dive for high-potential

### Outreach Automation
- **Research-powered emails** — Drafts reference actual company data, competitor gaps, and pain points
- **Multi-step sequences** — Automated follow-up cadences with customizable delays
- **Reply detection** — IMAP polling classifies intent (interested, objection, not interested, question, unsubscribe)
- **Conversation engine** — Multi-turn thread management with objection handling
- **A/B testing** — Compare subject lines and email variants

### AI Agent Fleet
- **20 specialized agents** — Prospector, Qualifier, Closer, Researcher, Accountant, Caller, and more
- **Rank-based hierarchy** — Commander (C-Level) → Specialists → Workers
- **Task routing** — 25+ task types automatically dispatched to the right specialist
- **Ticket system** — Kanban board with escalation, dependencies, and due dates
- **Self-improvement** — Agents learn from performance metrics and reflection scores

### Voice Calling (Last Resort)
- **Twilio integration** — WebSocket media streams for real-time audio
- **TTS cascade** — ElevenLabs → OpenAI → Piper (local fallback)
- **STT** — Whisper (local or API)
- **Auto-trigger** — Detects stalled leads (3+ failed emails or 7+ days silent)
- **Always requires approval** — Even at full-trust autonomy level

### Security & Reliability
- **Per-install encryption salt** — Unique random salt per installation (auto-migrates from legacy)
- **Key migration** — Automatic re-encryption of legacy ciphertext to new per-install salt
- **LLM retry with backoff** — Exponential backoff on transient errors (429, 503, timeouts)
- **Thread-safe database** — Serialized writes prevent SQLite locking errors
- **Thread-safe delivery counter** — Atomic daily send limit with `threading.Lock`
- **Browser lifecycle management** — Context-managed Playwright with batch mode and stealth for bulk operations
- **IMAP connection pooling** — Persistent connections with automatic stale detection and reconnect
- **Resource cleanup on error** — SMTP and IMAP connections always closed via `try/finally`
- **HTML injection prevention** — Email body escaped before HTML embedding
- **Database indexes** — 15 indexes on frequently queried columns for faster lookups
- **Graceful shutdown** — `closeEvent` stops all timers, fleet, gateways, and batch browser on exit
- **GPU-aware scheduling** — Ollama calls serialized via semaphore for single-GPU machines
- **Thread-safe safety guard** — All mutable counters protected by locks

### Autonomy & Control
- **4 autonomy levels** — Observer, Supervised, Autonomous, Full Trust
- **Approval queue** — Review and approve/deny any action before execution
- **Budget controls** — Daily spend limits with automatic tier downgrade
- **Rate limiting** — Per-provider API queues prevent throttling

### Integrations
- **Telegram bot** — Control Aura from Telegram with natural language commands
- **Discord bot** — Same capabilities via Discord server
- **Command palette** — `Ctrl+K` fuzzy search across all 14 pages
- **Cross-page navigation** — Deep links between pages with context passing

### Analytics & Intelligence
- **Dashboard** — Real-time campaign stats, funnel visualization, conversion rates
- **Trends** — Google Trends integration for market intelligence
- **Budget tracking** — Per-model cost breakdown, daily/monthly projections
- **Command history** — Full audit trail with tree visualization

---

## CLI Reference

The CLI provides **81 commands** across **17 groups** with full feature parity to the GUI. Run `aura` to start the interactive REPL, or `aura <command>` for one-shot execution.

### REPL Mode

```
$ aura
Aura v2.1.0 — AI Sales Agent
Type /help for commands, or type naturally.

aura> /hunt plumber --city "Austin TX" --limit 20
aura> /qualify 1
aura> /draft 1
aura> /send 1
aura> find me SaaS leads in healthcare    ← natural language works too
```

### Command Groups

| Group | Commands | Description |
|-------|----------|-------------|
| **Pipeline** | `/hunt`, `/qualify`, `/enrich`, `/draft`, `/send`, `/replies`, `/sequence` | Core lead-to-email pipeline |
| **Campaigns** | `/campaigns`, `/campaign-create`, `/campaign-status`, `/campaign-pause`, `/campaign-resume`, `/export-csv`, `/export-pdf` | Campaign management and export |
| **Leads** | `/leads`, `/lead-detail`, `/lead-lifecycle`, `/lead-search`, `/case` | Lead management and case files |
| **Fleet** | `/fleet-status`, `/fleet-boot`, `/fleet-shutdown`, `/agents`, `/agent-assign`, `/goals`, `/goal-create`, `/reflections`, `/knowledge-graph`, `/conversations`, `/ask`, `/improvement` | AI agent fleet operations |
| **Kanban** | `/tickets`, `/ticket-create`, `/ticket-update`, `/ticket-comment`, `/ticket-stats` | Ticket/task management |
| **Skills** | `/skills`, `/skill-detail` | AI skill registry |
| **Research** | `/research`, `/research-report`, `/research-queue` | Lead research intelligence |
| **Voice** | `/call`, `/call-log`, `/call-transcript` | Voice call management |
| **Budget** | `/budget`, `/budget-set`, `/token-usage` | Cost pacing and token tracking |
| **Trends** | `/trends`, `/trends-opportunities`, `/trends-alerts` | Google Trends market intelligence |
| **Autonomy** | `/autonomy-level`, `/autonomy-set`, `/approvals`, `/approve`, `/deny` | Agent autonomy controls |
| **Suppression** | `/suppression-list`, `/suppress`, `/unsuppress` | Email suppression management |
| **Integrations** | `/gateway-status`, `/gateway-connect`, `/gateway-disconnect`, `/crm-sync`, `/gateway-auth` | Telegram, Discord, CRM |
| **History** | `/history`, `/history-detail`, `/history-tree` | Command audit trail |
| **Config** | `/config`, `/config-set`, `/config-api-keys`, `/config-smtp` | Settings management |
| **Knowledge** | `/knowledge-add`, `/knowledge-list`, `/knowledge-remove`, `/memory-rules`, `/memory-stats`, `/memory-clear` | Knowledge base & correction memory |
| **System** | `/help`, `/status`, `/version`, `/clear`, `/exit` | System utilities |

### One-Shot Commands

```bash
# Hunt leads
aura hunt "SaaS companies" --city "San Francisco" --limit 100

# Check campaign stats
aura campaign-status 1

# Show system status
aura status

# Get help
aura help pipeline

# Verbose mode (show engine logs)
aura --verbose status
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Interface Layer (GUI or CLI)                 │
│   GUI: PySide6 (14 Pages, Chat Panel, Sidebar)          │
│   CLI: REPL + 81 commands (no PySide6 required)         │
├─────────────────────────────────────────────────────────┤
│                   Controller Layer                       │
│   GUI: 19 QObject controllers with Signal/Slot wiring   │
│   CLI: Direct engine calls (bypasses controllers)       │
├─────────────────────────────────────────────────────────┤
│                   Core Engine Layer                      │
│          50+ specialized engines (business logic)        │
├─────────────────────────────────────────────────────────┤
│                   Database Layer                         │
│       SQLAlchemy ORM  │  SQLite (WAL mode)  │  30+ tables│
├─────────────────────────────────────────────────────────┤
│                   External Services                      │
│  LiteLLM │ Apollo │ Twilio │ Telegram │ Discord │ IMAP   │
└─────────────────────────────────────────────────────────┘
```

### Project Structure

```
aura-app/
├── main.py                  # GUI entry point
├── cli.py                   # CLI entry point (81 commands, REPL)
├── config.py                # All constants, paths, design tokens
├── aura.spec                # PyInstaller build configuration (cross-platform)
├── pyproject.toml           # Python packaging (pip install -e .)
├── requirements.txt         # Full dependencies (GUI + CLI)
├── requirements-cli.txt     # CLI-only dependencies (no PySide6)
│
├── core/                    # 50+ business logic engines
│   ├── ai_engine.py         # LLM orchestration (generate, qualify, classify)
│   ├── agent_engine.py      # Agent task execution with context building
│   ├── fleet_orchestrator.py # Multi-agent dispatch and coordination
│   ├── orchestrator_engine.py # Natural language command → action mapping
│   ├── scraper_engine.py    # Multi-source web scraping
│   ├── delivery_engine.py   # Email delivery (Resend + SMTP)
│   ├── research_engine.py   # Multi-provider research orchestration
│   ├── voice_call_engine.py # Twilio WebSocket voice calling
│   ├── router_engine.py     # 4-tier LLM routing (local→ollama→haiku→sonnet)
│   ├── rag_engine.py        # TF-IDF + optional ChromaDB retrieval
│   ├── voice/               # TTS (ElevenLabs, OpenAI, Piper) + STT (Whisper)
│   ├── gateway_adapters/    # Telegram + Discord bot adapters
│   ├── enrichment_layers/   # DNS, Ollama, free APIs, deep crawl enrichment
│   └── ...                  # 40+ more engines
│
├── controllers/             # 19 signal-based UI controllers
│   ├── hunter_controller.py
│   ├── outreach_controller.py
│   ├── fleet_controller.py
│   ├── autonomy_controller.py
│   └── ...
│
├── ui/
│   ├── main_window.py       # Application shell + engine wiring
│   ├── setup_wizard.py      # First-run configuration
│   ├── pages/               # 14 full-page views
│   │   ├── dashboard.py     # Campaign analytics
│   │   ├── hunter.py        # Lead discovery
│   │   ├── forge.py         # AI persona management
│   │   ├── outreach.py      # Email campaigns
│   │   ├── fleet.py         # Agent monitoring
│   │   ├── kanban.py        # Task board
│   │   ├── research.py      # Research reports
│   │   ├── calls.py         # Voice call management
│   │   └── ...              # 6 more pages
│   └── components/          # Reusable widgets
│       ├── sidebar.py
│       ├── chat_panel.py
│       ├── command_palette.py
│       └── ...
│
├── database/
│   ├── schema.py            # 50+ SQLAlchemy models
│   ├── db_manager.py        # Session factory, WAL mode, thread-safe writes
│   ├── migrations.py        # ALTER TABLE migrations for backward compat
│   ├── seed_agents.py       # 20 agent definitions + hierarchy setup
│   └── seed_skills.py       # Built-in skill & settings seeding
│
├── assets/
│   ├── themes/              # QSS stylesheets (dark + light)
│   ├── icons/               # Application icon
│   └── templates/           # CSV import templates
│
├── scripts/                 # Build scripts (cross-platform, macOS icon, Linux installer)
│   ├── build.py             # Cross-platform build automation
│   ├── build_icns.sh        # macOS icon generation
│   └── linux/               # Linux desktop entry + installer
│
└── tests/                   # 1250+ tests across 50+ files
    ├── conftest.py          # Fixtures (in-memory DB, QApp)
    └── test_*.py            # Comprehensive coverage
```

### Key Technologies

| Component | Technology |
|-----------|-----------|
| Desktop Framework | PySide6 (Qt 6) |
| Database | SQLAlchemy + SQLite (WAL mode) |
| LLM Routing | LiteLLM (Anthropic, OpenAI, Google, Ollama) |
| Email Delivery | Resend API + SMTP fallback |
| Web Scraping | Playwright + BeautifulSoup |
| Voice Calls | Twilio + WebSocket media streams |
| TTS | ElevenLabs, OpenAI, Piper (local) |
| STT | Whisper (local via faster-whisper, or API) |
| Encryption | AES-256 via `cryptography` (machine-bound, per-install salt) |
| CLI | 81 commands, REPL, natural language fallback |
| Packaging | PyInstaller (OneDir), cross-platform (Win/macOS/Linux) |

---

## Configuration

All configuration lives in `config.py`. Key settings you may want to adjust:

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_DAILY_EMAILS` | 100 | Daily outbound email limit |
| `FOLLOWUP_CHECK_INTERVAL_MS` | 1,800,000 | Follow-up sequence check interval (30 min) |
| `REPLY_CHECK_INTERVAL_MS` | 7,200,000 | IMAP reply check interval (2 hours) |
| `ESCALATION_CHECK_INTERVAL_MS` | 300,000 | Ticket escalation check (5 min) |
| `AGENT_CONTEXT_MAX_TOKENS` | 8,000 | Max context tokens per agent task |
| `CALLER_FAILED_EMAIL_THRESHOLD` | 3 | Failed emails before voice call eligibility |
| `CALLER_STALLED_DAYS` | 7 | Days silent before stalled-lead detection |

Runtime settings (API keys, toggles, sender identity) are configured in the **Settings** page within the app.

---

## Building from Source

### Windows

```bash
venv\Scripts\activate
pyinstaller aura.spec --noconfirm
# Output: dist/Aura/Aura.exe
```

### macOS

```bash
source venv/bin/activate
# Generate .icns icon (optional, requires iconutil)
bash scripts/build_icns.sh
# Build
pyinstaller aura.spec --noconfirm
# Output: dist/Aura.app
```

### Linux

```bash
source venv/bin/activate
pyinstaller aura.spec --noconfirm
# Output: dist/Aura/Aura

# Optional: System-wide install
sudo bash scripts/linux/install.sh
```

### Cross-Platform Build Script

```bash
python scripts/build.py
```

The build bundles all assets, themes, fonts, and dependencies into a self-contained directory.

---

## Testing

```bash
# Run full test suite
venv\Scripts\python.exe -m pytest tests/ -v --tb=long

# Run a specific test file
venv\Scripts\python.exe -m pytest tests/test_agent_engine.py -v

# Run tests matching a pattern
venv\Scripts\python.exe -m pytest tests/ -k "test_stalled" -v
```

**Current status**: 1250+ tests across 50+ files — 100% passing.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Technical Documentation](DOCUMENTATION.md) | Architecture deep-dive, engine reference, database schema, security model |
| [User Manual](USER_MANUAL.md) | Page-by-page walkthrough, feature toggles, keyboard shortcuts, troubleshooting |

---

## Supported AI Providers

Aura works with any combination of these LLM providers:

| Provider | Models | Use Case |
|----------|--------|----------|
| **Anthropic** | Claude Haiku, Sonnet | Primary (recommended) |
| **OpenAI** | GPT-4o, GPT-4o-mini | Alternative |
| **Google** | Gemini Pro, Flash | Alternative |
| **Ollama** | Any local model | Privacy-first, free tier |

The **4-tier router** automatically selects the optimal model based on task complexity and budget:

```
Tier 1 (Local)  →  Tier 2 (Haiku/Flash)  →  Tier 3 (Sonnet/GPT-4o)  →  Tier 4 (Opus)
   Free              ~$0.001/task              ~$0.01/task               ~$0.10/task
```

Budget pacing automatically downgrades tiers when daily spend approaches limits.

---

## Contributing

Contributions are welcome. To get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Run the test suite (`pytest tests/ -v`)
5. Commit (`git commit -m "Add your feature"`)
6. Push (`git push origin feature/your-feature`)
7. Open a Pull Request

Please ensure all tests pass before submitting.

---

## Changelog

### v2.1.0 — Intelligence & Audit Hardening

- **Correction Memory Engine** — Detects user corrections ("no, I meant X") and learns rules that persist across conversations. Agents automatically inject learned rules into their context
- **Knowledge Base Engine** — Store and retrieve business knowledge entries (products, competitors, pricing, processes). New Settings tab for managing entries with search
- **Per-Agent Auto-Memory** — Each agent automatically stores and retrieves learned behaviors in per-agent memory logs, injected into agent context during task execution
- **Knowledge CLI commands** — `/knowledge-add`, `/knowledge-list`, `/knowledge-remove`, `/memory-rules`, `/memory-stats`, `/memory-clear`
- **Audit fixes** — Fixed CLI `/enrich` crash (int→dict), removed dead gateway response method, fixed Settings docstring (6→7 tabs)
- **Config cleanup** — Removed dead `Colors`, `DarkColors`, `Shadows` classes, dead `FONT_*` typography constants, and duplicate `IMPROVEMENT_CYCLE_INTERVAL_MS`
- **Missing PyInstaller imports** — Added `skill_registry`, `hubspot_engine`, `linkedin_engine`, `icons`, `command_palette` to `aura.spec`
- **Version**: 2.0.0 → 2.1.0 across `config.py`, `pyproject.toml`, `aura.spec`
- **Tests**: 1200 → 1250+ tests (50+ new tests across 3 new test files)

### v2.0.0 — Enterprise Features + Settings Overhaul

- **Multi-platform response formatting** — ResponseFormatter renders agent output for Telegram (HTML), Discord (Markdown), Chat (rich text), and CLI (plain text)
- **4-layer enrichment pipeline** — DNS/WHOIS (Layer 0), Ollama local LLM (Layer 1), free APIs (Layer 2), deep web crawl (Layer 4) with weighted completeness scoring
- **Excel export engine** — Professional .xlsx exports with multiple sheets (summary, leads, agents, timeline), auto-column-width, styled headers, and charts
- **Pricing + invoice system** — Service CRUD, invoice generation (PDF via ReportLab or text fallback), approval flow with rank-based escalation, revenue summaries. New Accountant agent (20th agent)
- **Discord server mode** — Auto-create notification channels (#leads, #campaigns, #fleet, #alerts, #reports), event→channel routing with embeds, config persistence
- **Telegram command system** — 12 slash commands (/status, /hunt, /leads, /agents, /draft, /send, /campaigns, /budget, /approve, /deny, /help, /settings) with inline keyboards
- **Business & Invoicing settings** — New Settings tab with company info, banking details, and invoice configuration (16 fields for agent context and invoice generation)
- **Tabbed Settings page** — Restructured from single scroll into 7 sub-tabs: API Keys, AI Config, Email & Delivery, Features, Business & Invoicing, Knowledge Base, Appearance
- **Schema expansion** — 5 new models (Service, Invoice, InvoiceLineItem, FinanceNote, DiscordServerConfig), expanded Lead/EnrichmentData/Settings
- **Tests**: 959 → 1200 tests (241 new tests across 8 new test files)

### v1.3.0 — Advanced CLI + Cross-Platform

- **Advanced CLI**: Complete rewrite of `cli.py` — 75 commands across 16 groups with full GUI parity
- **Easy install**: `pip install .` → `aura` command available globally (CLI-only, no PySide6 required)
- **GUI as optional**: `pip install ".[gui]"` → includes PySide6 for desktop app
- **Clean output**: Zero noise by default — no warnings, no INFO logs. Use `--verbose` for debug output
- **REPL mode**: Interactive `aura>` prompt with `/help` system, fuzzy command matching, ANSI formatting
- **Natural language**: Type plain English in the REPL — orchestrator parses intent and executes
- **One-shot mode**: `aura hunt "plumber" --city "Austin TX"` runs a single command and exits
- **Full engine init**: CLI initializes all 50+ engines (mirrors `main_window.py` exactly)
- **Cross-platform**: Platform-aware `aura.spec` (Windows .exe, macOS .app bundle, Linux executable)
- **macOS icon**: `scripts/build_icns.sh` generates `.icns` from PNG
- **Linux installer**: `scripts/linux/install.sh` + `.desktop` file for system-wide install
- **Build script**: `scripts/build.py` cross-platform build automation
- **CI/CD**: GitHub Actions matrix build for Windows, macOS, and Linux
- **PySide6-optional**: `navigation_service.py` and `thread_worker.py` work without Qt

### v1.2.0 — Audit Round 2: Deep Hardening

- **Key migration**: `KeyVault.migrate_ciphertext()` re-encrypts legacy-salt keys with new per-install salt on startup
- **Batch browser wiring**: Hunter controller now calls `start_batch()`/`end_batch()` around enrichment loops
- **Stealth in batch path**: `playwright_stealth` applied to batch browser pages (not just single-page mode)
- **Thread-safe delivery**: `DeliveryEngine` daily counter uses `threading.Lock` with atomic `_increment_daily()`
- **SMTP leak fix**: All SMTP connections wrapped in `try/finally` with `server.quit()`
- **HTML escape**: Email body HTML-escaped before embedding to prevent XSS injection
- **IMAP leak fix**: Triage engine IMAP connections wrapped in `try/finally` with `mail.logout()`
- **Database indexes**: 15 indexes on frequently queried columns (leads, agent_tasks, tickets, command_log)
- **Graceful shutdown**: `MainWindow.closeEvent()` stops timers, fleet, IMAP, gateways, batch browser, voice engine
- **Consolidated migrations**: Removed dual migration system — all column migrations now in `database/migrations.py`
- **Tests**: 935 → 959 tests (24 new audit round 2 hardening tests)

### v1.1.0 — Hardening & Reliability

- **Security**: Per-install random encryption salt replaces hardcoded salt; automatic key migration from v1.0
- **LLM resilience**: Exponential backoff retry (up to 3 attempts) on transient LLM errors (429, 503, timeouts)
- **Thread safety**: Database writes serialized via `threading.RLock`; safety guard counters protected by locks
- **Browser management**: Context-managed Playwright lifecycle with batch mode for bulk enrichment
- **IMAP pooling**: Persistent IMAP connections with keepalive checks and stale connection recovery
- **GPU scheduling**: Ollama calls serialized via semaphore to prevent GPU contention
- **Codebase refactor**: Extracted `db_manager.py` (1400+ lines) into `migrations.py`, `seed_agents.py`, `seed_skills.py`
- **Dev tooling**: Added `requirements-dev.txt` for test/lint dependencies
- **Tests**: 853 → 935 tests (added `test_hardening_fixes.py` with 82 new tests)

### v1.0.0 — Initial Release

- Full B2B lead generation pipeline with 20 AI agents
- Multi-source lead discovery, deep research, outreach automation
- Voice calling, ticket system, 4-tier LLM routing, autonomy controls

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

## Acknowledgments

- [PySide6](https://doc.qt.io/qtforpython-6/) — Desktop UI framework
- [LiteLLM](https://github.com/BerriAI/litellm) — Universal LLM API proxy
- [SQLAlchemy](https://www.sqlalchemy.org/) — Python SQL toolkit
- [Playwright](https://playwright.dev/) — Browser automation
- [Twilio](https://www.twilio.com/) — Voice calling infrastructure

---

<p align="center">
  Built with <a href="https://www.python.org/">Python</a> and a fleet of AI agents.<br>
  <sub>Aura v2.1.0</sub>
</p>
