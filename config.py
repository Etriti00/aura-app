"""
Aura AI Sales Agent — Global Configuration
All constants, enums, paths, and design tokens live here.
No other file should hardcode these values.
"""

import os
import sys
import enum
from pathlib import Path

# ─── App Identity ──────────────────────────────────────────────────────────────
APP_NAME = "Aura"
APP_VERSION = "1.0.0"
APP_TAGLINE = "Your Local AI Sales Agent"
GITHUB_REPO = "Etriti00/aura-app"

# ─── Paths ─────────────────────────────────────────────────────────────────────
def resolve_assets_dir():
    """Robustly find assets in Dev, PyInstaller OneDir, and OneFile modes."""
    # 1. If frozen (EXE)
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
        
        # Check standard PyInstaller 6+ _internal location
        internal_assets = base_dir / "_internal" / "assets"
        if internal_assets.exists():
            return internal_assets
            
        # Check adjacent assets (Aura/assets)
        adjacent_assets = base_dir / "assets"
        if adjacent_assets.exists():
            return adjacent_assets
            
        # Check sys._MEIPASS (OneFile tmp dir)
        if hasattr(sys, '_MEIPASS'):
            meipass_assets = Path(sys._MEIPASS) / "assets"
            if meipass_assets.exists():
                return meipass_assets
                
    # 2. Dev mode (running from source)
    # config.py is in root, so assets is adjacent
    dev_assets = Path(__file__).parent / "assets"
    return dev_assets

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

ASSETS_DIR = resolve_assets_dir()
FONTS_DIR = ASSETS_DIR / "fonts"
ICONS_DIR = ASSETS_DIR / "icons"
THEMES_DIR = ASSETS_DIR / "themes"
DATA_DIR = Path(os.path.expanduser("~")) / ".aura"
DB_PATH = DATA_DIR / "aura.db"
LOG_PATH = DATA_DIR / "aura.log"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─── Encryption ────────────────────────────────────────────────────────────────
import secrets as _secrets

_SALT_FILE = DATA_DIR / ".salt"
_LEGACY_SALT = "aura-app-v1"  # kept for migration from pre-v1.1 installs

def _load_or_create_salt() -> str:
    """Load existing salt or generate a new one on first run."""
    if _SALT_FILE.exists():
        return _SALT_FILE.read_text(encoding="utf-8").strip()
    salt = _secrets.token_hex(32)
    _SALT_FILE.write_text(salt, encoding="utf-8")
    # Restrict file permissions (owner-only read/write)
    try:
        import stat
        os.chmod(_SALT_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except (OSError, AttributeError):
        pass  # Windows may not support chmod the same way
    return salt

ENCRYPTION_SALT = _load_or_create_salt()

# ─── Color Palette (Cupertino Light) ───────────────────────────────────────────
class Colors:
    BG_PRIMARY = "#F5F5F7"
    BG_SURFACE = "#FFFFFF"
    ACCENT = "#007AFF"
    ACCENT_HOVER = "#0066CC"
    SUCCESS = "#34C759"
    WARNING = "#FF9500"
    DANGER = "#FF3B30"
    TEXT_PRIMARY = "#1D1D1F"
    TEXT_SECONDARY = "#86868B"
    BORDER = "#E5E5EA"

# ─── Dark Mode Palette ────────────────────────────────────────────────────────
class DarkColors:
    BG_PRIMARY = "#1C1C1E"
    BG_SURFACE = "#2C2C2E"
    ACCENT = "#0A84FF"
    ACCENT_HOVER = "#409CFF"
    SUCCESS = "#30D158"
    WARNING = "#FF9F0A"
    DANGER = "#FF453A"
    TEXT_PRIMARY = "#F5F5F7"
    TEXT_SECONDARY = "#98989D"
    BORDER = "#38383A"

# ─── Geometry ──────────────────────────────────────────────────────────────────
class Geometry:
    CARD_RADIUS = 12
    BUTTON_RADIUS = 8
    BADGE_RADIUS = 6
    PADDING = 16
    SIDEBAR_WIDTH = 220
    TOPBAR_HEIGHT = 56
    WINDOW_MIN = (1024, 680)
    WINDOW_DEFAULT = (1280, 800)

# ─── Shadows ───────────────────────────────────────────────────────────────────
class Shadows:
    CARD = "0px 4px 12px rgba(0, 0, 0, 0.05)"
    MODAL = "0px 8px 32px rgba(0, 0, 0, 0.12)"
    TOAST = "0px 4px 16px rgba(0, 0, 0, 0.10)"

# ─── Autonomy ──────────────────────────────────────────────────────────────────
class AutonomyLevel(str, enum.Enum):
    OBSERVER = "observer"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"
    FULL_TRUST = "full_trust"

AUTONOMY_REQUIRES_APPROVAL = {
    "observer": ["all"],
    "supervised": ["send_email", "generate_email", "crm_sync", "skill_revision", "make_call"],
    "autonomous": ["skill_revision", "self_improvement", "make_call"],
    "full_trust": ["make_call"],
}

# ─── Enums ─────────────────────────────────────────────────────────────────────
class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"

class LeadStatus(str, enum.Enum):
    NEW = "new"
    QUALIFYING = "qualifying"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    EMAIL_DRAFTED = "email_drafted"
    SCHEDULED = "scheduled"
    EMAIL_SENT = "emailed"
    REPLIED = "replied"
    CONVERTED = "converted"

class LeadLifecycleStatus(str, enum.Enum):
    NEW = "new"
    RESEARCHED = "researched"
    QUALIFYING = "qualifying"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    EMAIL_DRAFTED = "email_drafted"
    SCHEDULED = "scheduled"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    OBJECTION_RAISED = "objection_raised"
    OBJECTION_HANDLED = "objection_handled"
    MEETING_SCHEDULED = "meeting_scheduled"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATING = "negotiating"
    RE_ENGAGE_SCHEDULED = "re_engage_scheduled"
    REPLIED = "replied"
    CONVERTED = "converted"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"

LEAD_STATE_TRANSITIONS = {
    "new": ["researched", "qualifying", "disqualified"],
    "researched": ["qualifying", "disqualified"],
    "qualifying": ["qualified", "disqualified"],
    "qualified": ["email_drafted", "contacted", "disqualified"],
    "email_drafted": ["scheduled", "contacted"],
    "scheduled": ["contacted"],
    "contacted": ["interested", "objection_raised", "re_engage_scheduled", "closed_lost", "replied"],
    "replied": ["interested", "objection_raised", "re_engage_scheduled", "closed_lost"],
    "interested": ["meeting_scheduled", "proposal_sent", "objection_raised"],
    "objection_raised": ["objection_handled", "closed_lost", "re_engage_scheduled"],
    "objection_handled": ["interested", "meeting_scheduled", "closed_lost"],
    "meeting_scheduled": ["proposal_sent", "negotiating", "closed_lost"],
    "proposal_sent": ["negotiating", "closed_won", "closed_lost"],
    "negotiating": ["closed_won", "closed_lost"],
    "re_engage_scheduled": ["contacted", "closed_lost"],
    "closed_lost": ["re_engage_scheduled"],
}

LEAD_TERMINAL_STATES = {"closed_won", "disqualified"}

# ─── AI Engine Defaults ───────────────────────────────────────────────────────
DEFAULT_TIER2_MODEL = "gemini/gemini-2.0-flash"
DEFAULT_TIER3_MODEL = "anthropic/claude-sonnet-4-6"

# ─── Scraper Safety Settings ───────────────────────────────────────────────────
# Human jitter delays (seconds)
JITTER_MIN = 2.0
JITTER_MAX = 6.0

# Reading simulation — longer pause every N requests
READING_PAUSE_EVERY = 15
READING_PAUSE_MIN = 8.0
READING_PAUSE_MAX = 18.0

# Break simulation — extended pause every N requests
BREAK_PAUSE_EVERY = 50
BREAK_PAUSE_MIN = 30.0
BREAK_PAUSE_MAX = 90.0

# Kill switch — triggers after N consecutive failures (403/429/CAPTCHA)
KILL_SWITCH_CONSECUTIVE_FAILS = 5
KILL_SWITCH_COOLDOWN_SECONDS = 1800  # 30 minutes

# Available scraper sources (legacy — use LEAD_SOURCES for new code)
SCRAPER_SOURCES = ["duckduckgo", "google_maps", "yelp"]

# ─── Unified Lead Sources ────────────────────────────────────────────────────
LEAD_SOURCES = {
    "scraper": ["duckduckgo", "google_maps", "yelp"],
    "api": ["apollo", "hunter_io", "hubspot"],
    "import": ["linkedin_csv", "csv_batch"],
}

# Flat list of all source identifiers
ALL_LEAD_SOURCES = (
    LEAD_SOURCES["scraper"] + LEAD_SOURCES["api"] + LEAD_SOURCES["import"]
)

# Human-readable labels for UI display
LEAD_SOURCE_LABELS = {
    "duckduckgo": "DuckDuckGo",
    "google_maps": "Google Maps",
    "yelp": "Yelp",
    "apollo": "Apollo.io",
    "hunter_io": "Hunter.io",
    "hubspot": "HubSpot",
    "linkedin_csv": "LinkedIn (CSV)",
    "csv_batch": "Batch CSV",
}

# API key settings field for each API source (must exist on Settings model)
LEAD_SOURCE_API_KEY_FIELD = {
    "apollo": "apollo_key_enc",
    "hunter_io": "hunter_key_enc",
    "hubspot": "hubspot_key_enc",
}

# Minimum results from a source before trying the next fallback
SCRAPER_MIN_RESULTS_THRESHOLD = 5

# Browser fingerprint rotation — realistic User-Agent strings
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
]

# Tier 1 Doorman — aggregator keywords to auto-discard
AGGREGATOR_KEYWORDS = [
    "yelp", "tripadvisor", "wikipedia", "facebook", "instagram", "twitter",
    "linkedin", "yellowpages", "bbb", "glassdoor", "indeed", "craigslist",
    "angieslist", "angi", "thumbtack", "houzz", "zillow", "realtor.com",
    "nextdoor", "mapquest", "foursquare", "trustpilot", "google.com/maps",
]

# ─── Email Delivery ───────────────────────────────────────────────────────────
MAX_DAILY_EMAILS = 100
DAILY_EMAIL_WARNING_THRESHOLD = 80

# ─── Timer Intervals (milliseconds) ───────────────────────────────────────────
FOLLOWUP_CHECK_INTERVAL_MS = 30 * 60 * 1000   # 30 minutes
REPLY_CHECK_INTERVAL_MS = 2 * 60 * 60 * 1000   # 2 hours
SCHEDULE_CHECK_INTERVAL_MS = 5 * 60 * 1000     # 5 minutes

# ─── Chat Panel ────────────────────────────────────────────────────────────────
CHAT_PANEL_WIDTH = 400

# ─── Typography ────────────────────────────────────────────────────────────────
FONT_FAMILY = "Inter"
FONT_WEIGHT_REGULAR = 400
FONT_WEIGHT_SEMIBOLD = 600
FONT_MONO = "JetBrains Mono"

# ─── API Rate Limits ──────────────────────────────────────────────────────────
APOLLO_RATE_PER_MINUTE = 50
APOLLO_RATE_PER_HOUR = 200
HUNTER_RATE_PER_MINUTE = 15
HUBSPOT_RATE_PER_MINUTE = 600     # HubSpot private apps allow 100 requests/10s = 600/min
HUBSPOT_RATE_PER_HOUR = 4000
API_BACKOFF_STEPS = [5, 15, 60]   # seconds — exponential backoff on 429

# ─── 4-Tier LLM Router ──────────────────────────────────────────────────────
DEFAULT_HAIKU_MODEL = "anthropic/claude-haiku-4-5"
ROUTER_TASK_TIER_MAP = {
    # Tier 0 — Local Python (free)
    "format_csv": "local",
    "normalize_data": "local",
    "extract_keywords": "local",
    "regex_validation": "local",
    "deduplicate": "local",
    # Tier 1 — Local Ollama (free, requires Ollama running)
    "parse_html": "ollama",
    "extract_structured_data": "ollama",
    "classify_business_type": "ollama",
    "summarize_webpage": "ollama",
    "format_lead_data": "ollama",
    # Tier 2 — Haiku (fast, cheap ~$0.001/task)
    "navigate_webpage": "haiku",
    "parse_api_response": "haiku",
    "qualify_lead_basic": "haiku",
    "score_website": "haiku",
    "read_blog_content": "haiku",
    # Tier 3 — Sonnet (powerful, reserved for decisions)
    "qualify_lead_complex": "sonnet",
    "generate_email": "sonnet",
    "analyze_performance": "sonnet",
    "orchestrate_command": "sonnet",
    "rag_style_matching": "sonnet",
    # Agent system
    "agent_heartbeat": "local",
    "agent_triage": "haiku",
    "agent_self_check": "ollama",
    # Google Trends
    "trend_analysis": "haiku",
    "trend_opportunity": "sonnet",
    # Token / Subagent system internals
    "summarize_for_cache": "haiku",
    "summarize_case": "haiku",
    "extract_lead_insights": "haiku",
    "draft_email": "haiku",
    "review_tone": "haiku",
    "check_website": "haiku",
    "assess_fit": "haiku",
    "score_lead": "haiku",
    # Research system
    "synthesize_research": "sonnet",
    "classify_research_depth": "haiku",
    # Voice call system
    "voice_conversation": "sonnet",
    "voice_call_notes": "haiku",
    "voice_call_classify": "haiku",
}

# ─── RAG Memory ──────────────────────────────────────────────────────────────
RAG_MAX_EXAMPLES = 3
RAG_SIMILARITY_THRESHOLD = 0.75

# ─── Vector RAG (Advanced) ──────────────────────────────────────────────────
VECTOR_RAG_MODEL = "all-MiniLM-L6-v2"
VECTOR_RAG_COLLECTIONS = ["emails", "interactions", "knowledge", "agent_learnings"]
VECTOR_RAG_MAX_RESULTS = 5
VECTOR_RAG_SIMILARITY_THRESHOLD = 0.65
CHROMADB_PERSIST_DIR = DATA_DIR / "chromadb"

# ─── Conversation Engine ────────────────────────────────────────────────────
CONVERSATION_RE_ENGAGE_DEFAULT_DAYS = 14
CONVERSATION_MAX_THREAD_MESSAGES = 20
REPLY_INTENT_TYPES = ["interested", "objection", "not_now", "question", "unsubscribe"]
OBJECTION_TYPES = ["price", "timing", "need", "authority", "competitor", "other"]

# ─── Cross-Channel ──────────────────────────────────────────────────────────
SUPPORTED_CHANNELS = ["email", "linkedin", "twitter"]

# ─── CRM Syncing ────────────────────────────────────────────────────────────
SUPPORTED_CRMS = ["hubspot", "pipedrive"]

# ─── Inbox Triage ───────────────────────────────────────────────────────────
TRIAGE_CHECK_INTERVAL_MS = 30 * 60 * 1000   # 30 minutes

# ─── Cost Pacing ────────────────────────────────────────────────────────────
PACING_CHECK_INTERVAL_MS = 60 * 1000  # 1 minute
PACING_MIN_BUDGET_USD = 0.50          # Minimum viable budget
TIER_COST_PER_1K_TOKENS = {
    "local": 0.0,
    "ollama": 0.0,
    "haiku": 0.0005,   # $0.50/1M tokens
    "sonnet": 0.006,   # $6/1M tokens
}
ECO_MODE_FALLBACK_CHAIN = ["sonnet", "haiku", "ollama", "local"]

# ─── Gateway ────────────────────────────────────────────────────────────────
GATEWAY_PLATFORMS = ["telegram", "discord"]
GATEWAY_POLL_INTERVAL_S = 1.0  # Telegram polling interval
GATEWAY_MAX_MESSAGE_LENGTH = 4096

# ─── Ticket System ────────────────────────────────────────────────────────────
TICKET_STATUSES = ["backlog", "todo", "in_progress", "review", "done"]
TICKET_PRIORITIES = ["critical", "high", "medium", "low"]
TICKET_PRIORITY_COLORS = {
    "critical": "#EF4444",
    "high":     "#F59E0B",
    "medium":   "#4E5BF2",
    "low":      "#6B7280",
}
AGENT_RANKS = {1: "C-Level", 2: "Specialist Lead", 3: "Worker"}
ESCALATION_CHECK_INTERVAL_MS = 5 * 60 * 1000   # 5 minutes
TICKET_DUE_WARNING_HOURS = 4

# ─── Command History ────────────────────────────────────────────────────────
COMMAND_HISTORY_MAX_RETENTION_DAYS = 90
COMMAND_HISTORY_PAGE_SIZE = 50
COMMAND_HISTORY_AGENT_CONTEXT_LIMIT = 20
COMMAND_HISTORY_SOURCES = ["telegram", "discord", "chat", "system", "scheduled"]
COMMAND_HISTORY_TYPES = [
    "user_command", "intent_parsed", "task_dispatched",
    "task_completed", "task_failed", "delegation",
    "escalation", "system_event",
]

# ─── Reflection Engine ────────────────────────────────────────────────────────
REFLECTION_SCORE_THRESHOLD = 4        # below this triggers revision
REFLECTION_MAX_REVISIONS = 2          # max re-execution attempts
REFLECTION_ENABLED = True             # master toggle

# ─── Self-Improvement Engine ────────────────────────────────────────────────
IMPROVEMENT_CYCLE_INTERVAL_MS = 24 * 60 * 60 * 1000  # daily
IMPROVEMENT_MIN_SAMPLES = 10
IMPROVEMENT_REPLY_RATE_THRESHOLD = 0.05
IMPROVEMENT_QUALITY_THRESHOLD = 5
IMPROVEMENT_AB_TEST_MIN_SIZE = 20

# ─── Strategy Engine ────────────────────────────────────────────────────────
DEFAULT_SCRAPE_TO_QUALIFY_RATE = 0.60
DEFAULT_QUALIFY_TO_EMAIL_RATE = 0.80
DEFAULT_EMAIL_TO_REPLY_RATE = 0.05
DEFAULT_REPLY_TO_MEETING_RATE = 0.30
DEFAULT_MEETING_TO_CONVERSION_RATE = 0.25
STRATEGY_PROGRESS_CHECK_INTERVAL_MS = 30 * 60 * 1000

# ─── Multi-Agent System ──────────────────────────────────────────────────────
AGENT_HEARTBEAT_DEFAULT_MINS = 30
AGENT_HEARTBEAT_CHECK_MS = 60 * 1000          # 1 minute timer tick
AGENT_MAX_DELEGATION_DEPTH = 3
AGENT_MAX_MESSAGES_PER_HOUR = 10
FLEET_MAX_CONCURRENT_TASKS = 10
OBSERVER_CHECK_INTERVAL_MS = 5 * 60 * 1000    # 5 minutes
SELF_IMPROVEMENT_INTERVAL_MS = 24 * 60 * 60 * 1000  # 24 hours
AGENT_ROLES = ["orchestrator", "worker", "canary", "observer"]

# ─── Google Trends ────────────────────────────────────────────────────────────
TRENDS_MAX_KEYWORDS = 5
TRENDS_DEFAULT_TIMEFRAME = "today 3-m"
TRENDS_RATE_LIMIT_BATCH = 5        # sleep after N requests
TRENDS_RATE_LIMIT_SLEEP_MIN = 30   # seconds
TRENDS_RATE_LIMIT_SLEEP_MAX = 60
TRENDS_429_SLEEP = 300             # seconds on 429
TRENDS_CACHE_HOURS = 4
TRENDS_SPIKE_THRESHOLD = 20        # point change triggers alert
TRENDS_OPPORTUNITY_MIN_SCORE = 60
TRENDS_TIMEFRAMES = [
    ("now 1-H", "Last hour"),
    ("now 4-H", "Last 4 hours"),
    ("now 1-d", "Last day"),
    ("now 7-d", "Last 7 days"),
    ("today 1-m", "Last month"),
    ("today 3-m", "Last 3 months"),
    ("today 12-m", "Last year"),
    ("today 5-y", "Last 5 years"),
]

# ─── Token Management ──────────────────────────────────────────────────────
AGENT_CONTEXT_MAX_TOKENS = 8000
TOKEN_ESTIMATE_CHARS_PER_TOKEN = 4
SUMMARY_CACHE_TTL_HOURS = 24
RESPONSE_CACHE_MAX_SIZE = 500
RESPONSE_CACHE_TTL_HOURS = 1

# Per-task output token budgets (max_tokens for LLM response generation)
TASK_OUTPUT_TOKENS = {
    "generate_email":       1500,
    "write_followup":       1500,
    "synthesize_research":  2000,
    "orchestrate_command":  1500,
    "qualify_lead":         512,
    "qualify_lead_complex": 768,
    "enrich_lead":          512,
    "summarize":            600,
    "classify_reply":       256,
    "handle_objection":     1200,
    "research":             2000,
    "agent_triage":         512,
    "_default":             1024,
}

# Per-task context section selection (only include what the task needs)
TASK_CONTEXT_SECTIONS = {
    "generate_email":       ["soul", "skill", "memory_today", "case_context", "payload"],
    "qualify_lead":         ["soul", "mission", "skill", "case_context", "payload"],
    "qualify_lead_complex": ["soul", "mission", "skill", "playbook", "case_context", "payload"],
    "write_followup":       ["soul", "skill", "memory_today", "case_context", "payload"],
    "research":             ["soul", "mission", "skill", "long_term_memory", "payload"],
    "enrich_lead":          ["soul", "skill", "payload"],
    "summarize":            ["soul", "payload"],
    "_default":             ["soul", "mission", "skill", "playbook", "boundaries",
                             "long_term_memory", "memory_today", "history",
                             "case_context", "payload"],
}

# ─── Subagent System ──────────────────────────────────────────────────────
SUBAGENT_MAX_SUBTASKS = 5
SUBAGENT_DEFAULT_TIER = "haiku"
SUBAGENT_DECOMPOSITION_MAP = {
    "generate_email": [
        {"type": "extract_lead_insights", "tier": "haiku", "max_tokens": 512},
        {"type": "draft_email",           "tier": "haiku", "max_tokens": 768},
        {"type": "review_tone",           "tier": "haiku", "max_tokens": 768},
    ],
    "qualify_lead_complex": [
        {"type": "check_website",  "tier": "haiku"},
        {"type": "assess_fit",     "tier": "haiku"},
        {"type": "score_lead",     "tier": "haiku"},
    ],
}

# ─── Case System ──────────────────────────────────────────────────────────
CASE_NOTE_MAX_RECENT = 20
CASE_MEMORY_SUMMARIZE_THRESHOLD = 10
CASE_CONTEXT_MAX_TOKENS = 2000

# ─── Research Engine ──────────────────────────────────────────────────────
RESEARCH_QUICK_TIMEOUT_S = 30
RESEARCH_DEEP_TIMEOUT_S = 120
TAVILY_RATE_PER_MINUTE = 20
FIRECRAWL_RATE_PER_MINUTE = 10
APIFY_RATE_PER_MINUTE = 5
RESEARCH_DEPTHS = ["quick", "deep"]
RESEARCH_STATUSES = ["pending", "running", "completed", "failed"]

# ─── Voice Call Engine ────────────────────────────────────────────────────
VOICE_WS_PORT = 5080
VOICE_MAX_CALL_DURATION_S = 300
VOICE_SILENCE_THRESHOLD_MS = 700
VOICE_SAMPLE_RATE = 8000
CALL_CHECK_INTERVAL_MS = 10_000
VOICE_TTS_PROVIDERS = ["elevenlabs", "openai", "piper"]
VOICE_STT_PROVIDERS = ["whisper_local", "whisper_api"]
VOICE_CALL_STATUSES = [
    "queued", "ringing", "in_progress", "completed",
    "failed", "no_answer", "voicemail",
]
VOICE_CALL_OUTCOMES = [
    "interested", "not_interested", "callback",
    "voicemail", "no_answer", "meeting_booked",
]

# ─── Caller Agent (Last-Resort Voice) ────────────────────────────────────
CALLER_CHECK_INTERVAL_MS = 300_000       # 5 minutes
CALLER_FAILED_EMAIL_THRESHOLD = 3        # 3+ failed/bounced emails → eligible for call
CALLER_STALLED_DAYS = 7                  # Interested but silent 7+ days → eligible
