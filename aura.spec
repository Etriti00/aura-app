# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all
import os

_SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
_ICON_PATH = os.path.join(_SPEC_DIR, 'assets', 'icons', 'aura_icon.ico')

datas = [('assets', 'assets')]

# Bundle qtawesome fonts
try:
    import qtawesome
    _qta_dir = os.path.dirname(qtawesome.__file__)
    datas += [(os.path.join(_qta_dir, 'fonts'), 'qtawesome/fonts')]
except ImportError:
    pass
binaries = []
hiddenimports = [
    'qtawesome',
    'qtawesome.iconic_font',
    'litellm',
    'playwright',
    'playwright_stealth',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'sqlalchemy',
    'sqlalchemy.orm',
    'sqlite3',
    'config',
    # Core engines
    'core.ai_engine',
    'core.scraper_engine',
    'core.delivery_engine',
    'core.sequence_engine',
    'core.reply_detector',
    'core.enrichment_engine',
    'core.ab_engine',
    'core.suppression_engine',
    'core.scheduler_engine',
    'core.batch_importer',
    'core.report_engine',
    'core.analyst_engine',
    'core.orchestrator_engine',
    'core.api_queue',
    'core.apollo_engine',
    'core.hunter_engine',
    'core.router_engine',
    'core.rag_engine',
    'core.channel_engine',
    'core.crm_engine',
    'core.triage_engine',
    'core.pacing_engine',
    'core.gateway_engine',
    'core.token_manager',
    'core.case_engine',
    'core.subagent_engine',
    'core.gateway_adapters',
    'core.gateway_adapters.base_adapter',
    'core.gateway_adapters.telegram_adapter',
    'core.gateway_adapters.discord_adapter',
    # Controllers
    'controllers.hunter_controller',
    'controllers.dashboard_controller',
    'controllers.forge_controller',
    'controllers.outreach_controller',
    'controllers.settings_controller',
    'controllers.sequence_controller',
    'controllers.reply_controller',
    'controllers.chat_controller',
    'controllers.enrichment_api_controller',
    'controllers.budget_controller',
    'controllers.gateway_controller',
    # UI
    'ui.main_window',
    'ui.setup_wizard',
    'ui.pages.dashboard',
    'ui.pages.hunter',
    'ui.pages.forge',
    'ui.pages.outreach',
    'ui.pages.settings',
    'ui.pages.suppression',
    'ui.pages.budget',
    'ui.pages.integrations',
    'ui.components.glass_card',
    'ui.components.modern_button',
    'ui.components.sidebar',
    'ui.components.chat_panel',
    'ui.components.toast_notification',
    'ui.components.masked_input',
    'ui.components.empty_state',
    # Database
    'database.db_manager',
    'database.schema',
    'database.seed_skills',
    'database.seed_agents',
    'database.migrations',
    # Utils
    'utils.logger',
    'core.key_vault',
    'utils.thread_worker',
    'utils.paths',
    # Missing modules
    'core.agent_engine',
    'core.fleet_orchestrator',
    'core.observer_engine',
    'core.subscription_auth',
    'core.trends_engine',
    'controllers.fleet_controller',
    'controllers.trends_controller',
    'ui.pages.fleet',
    'ui.pages.trends',
    'core.ticket_engine',
    'core.escalation_engine',
    'core.ticket_scheduler',
    'controllers.kanban_controller',
    'ui.pages.kanban',
    'core.command_history',
    'controllers.command_history_controller',
    'ui.pages.history',
    # Advanced engines (Phases 1-8)
    'core.reflection_engine',
    'core.lead_lifecycle_engine',
    'core.knowledge_graph_engine',
    'core.conversation_engine',
    'core.self_improvement_engine',
    'core.strategy_engine',
    'controllers.autonomy_controller',
    # Research system
    'core.research_providers',
    'core.research_providers.tavily_provider',
    'core.research_providers.firecrawl_provider',
    'core.research_providers.apify_provider',
    'core.research_engine',
    'controllers.research_controller',
    'ui.pages.research',
    # Voice call system
    'core.voice',
    'core.voice.tts_elevenlabs',
    'core.voice.tts_openai',
    'core.voice.tts_piper',
    'core.voice.stt_whisper',
    'core.voice_call_engine',
    'controllers.voice_controller',
    'ui.pages.calls',
]

# Collect all playwright dependencies
tmp_ret = collect_all('playwright')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Collect litellm dependencies
tmp_ret = collect_all('litellm')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Aura',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_ICON_PATH,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Aura',
)
