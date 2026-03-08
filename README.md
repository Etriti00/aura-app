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
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform">
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

Aura is a **desktop AI sales agent** that automates the entire B2B lead generation pipeline — from finding prospects to closing deals. It runs locally on your machine with a fleet of 19 specialized AI agents that handle prospecting, research, outreach, follow-ups, and even voice calls.

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

### Option A: Download the Executable (Recommended)

1. Go to [Releases](https://github.com/Etriti00/aura-app/releases)
2. Download `Aura-v1.1.0-win64.zip`
3. Extract and run `Aura.exe`
4. Complete the setup wizard (enter at least one AI API key)

### Option B: Run from Source

**Prerequisites**: Python 3.11+ and Git

```bash
# Clone the repository
git clone https://github.com/Etriti00/aura-app.git
cd aura-app

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser (needed for web scraping)
playwright install chromium

# Launch
python main.py
```

### First Launch

On first launch, the **Setup Wizard** walks you through:

1. **AI Provider Key** — At least one of: Anthropic (Claude), OpenAI, or Google (Gemini)
2. **Sender Identity** — Your name, email, and company
3. **Email Delivery** — Resend API key or SMTP credentials

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
- **19 specialized agents** — Prospector, Qualifier, Closer, Researcher, Caller, and more
- **Rank-based hierarchy** — Commander (C-Level) → Specialists → Workers
- **Task routing** — 20 task types automatically dispatched to the right specialist
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
- **LLM retry with backoff** — Exponential backoff on transient errors (429, 503, timeouts)
- **Thread-safe database** — Serialized writes prevent SQLite locking errors
- **Browser lifecycle management** — Context-managed Playwright with batch mode for bulk operations
- **IMAP connection pooling** — Persistent connections with automatic stale detection and reconnect
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

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    UI Layer (PySide6)                     │
│   14 Pages  │  10 Components  │  Chat Panel  │  Sidebar  │
├─────────────────────────────────────────────────────────┤
│                   Controller Layer                       │
│       19 QObject controllers with Signal/Slot wiring     │
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
├── main.py                  # Entry point
├── config.py                # All constants, paths, design tokens
├── aura.spec                # PyInstaller build configuration
├── requirements.txt         # Python dependencies
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
│   ├── schema.py            # 30+ SQLAlchemy models
│   ├── db_manager.py        # Session factory, WAL mode, thread-safe writes
│   ├── migrations.py        # ALTER TABLE migrations for backward compat
│   ├── seed_agents.py       # 19 agent definitions + hierarchy setup
│   └── seed_skills.py       # Built-in skill & settings seeding
│
├── assets/
│   ├── themes/              # QSS stylesheets (dark + light)
│   ├── icons/               # Application icon
│   └── templates/           # CSV import templates
│
└── tests/                   # 935 tests across 40+ files
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
| Packaging | PyInstaller (OneDir) |

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

```bash
# Activate virtual environment
venv\Scripts\activate

# Build the executable
pyinstaller aura.spec --noconfirm

# Output: dist/Aura/Aura.exe
```

The build bundles all assets, themes, fonts, and dependencies into a self-contained directory at `dist/Aura/`.

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

**Current status**: 935 tests across 40+ files — 100% passing.

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

- Full B2B lead generation pipeline with 19 AI agents
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
  <sub>Aura v1.1.0</sub>
</p>
