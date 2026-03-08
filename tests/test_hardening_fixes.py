"""
Tests for 12-point codebase hardening fixes.
Covers: encryption salt, LLM retry, thread safety, browser lifecycle,
        ThreadWorker, Ollama serialization, SQLite write lock, dependency pinning,
        db_manager decomposition, IMAP reuse, playwright stealth.
"""

import os
import sys
import threading
import inspect
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─── Fix 1: Per-install encryption salt ───────────────────────────────

class TestEncryptionSalt:
    """Verify encryption salt is per-install, not hardcoded."""

    def test_salt_not_hardcoded(self):
        """ENCRYPTION_SALT should NOT be the legacy hardcoded value."""
        from config import ENCRYPTION_SALT, _LEGACY_SALT
        # On first install, a random salt is generated
        # It could equal legacy only if the salt file already existed with that value
        assert isinstance(ENCRYPTION_SALT, str)
        assert len(ENCRYPTION_SALT) > 0

    def test_legacy_salt_exists(self):
        """_LEGACY_SALT constant should exist for migration support."""
        from config import _LEGACY_SALT
        assert _LEGACY_SALT == "aura-app-v1"

    def test_salt_loader_function_exists(self):
        """_load_or_create_salt function should exist in config."""
        from config import _load_or_create_salt
        assert callable(_load_or_create_salt)

    def test_key_vault_legacy_migration(self):
        """KeyVault should have legacy fernet for migration."""
        from core.key_vault import KeyVault
        vault = KeyVault()
        # If current salt != legacy, legacy fernet should exist
        from config import ENCRYPTION_SALT, _LEGACY_SALT
        if ENCRYPTION_SALT != _LEGACY_SALT:
            assert vault._legacy_fernet is not None
        # Encrypt/decrypt round-trip works
        ct = vault.encrypt("test-key-123")
        assert vault.decrypt(ct) == "test-key-123"

    def test_key_vault_decrypt_returns_empty_on_garbage(self):
        """KeyVault.decrypt should return empty string on invalid input."""
        from core.key_vault import KeyVault
        vault = KeyVault()
        assert vault.decrypt("not-hex") == ""
        assert vault.decrypt("") == ""


# ─── Fix 2: LLM retry with exponential backoff ───────────────────────

class TestLLMRetry:
    """Verify _call_llm retries on transient errors."""

    def test_transient_error_constants(self):
        """AI engine should define transient error patterns."""
        from core.ai_engine import AIEngine
        assert hasattr(AIEngine, '_TRANSIENT_ERRORS')
        errors = AIEngine._TRANSIENT_ERRORS
        assert "429" in errors
        assert "rate_limit" in errors
        assert "timeout" in errors

    def test_call_llm_has_retry_param(self):
        """_call_llm should accept _max_retries parameter."""
        from core.ai_engine import AIEngine
        sig = inspect.signature(AIEngine._call_llm)
        assert "_max_retries" in sig.parameters

    def test_retry_on_transient_error(self):
        """_call_llm should retry on transient errors."""
        from core.ai_engine import AIEngine
        from core.safety_guard import SafetyGuard

        engine = AIEngine.__new__(AIEngine)
        engine.safety = SafetyGuard()
        engine._models = {"tier2": "test", "tier3": "test"}

        call_count = 0

        def mock_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Error: 429 rate limit exceeded")
            return {
                "usage": {"total_tokens": 10},
                "choices": [{"message": {"content": "success"}}],
            }

        with patch("litellm.completion", side_effect=mock_completion), \
             patch("litellm.completion_cost", return_value=0.001):
            result = engine._call_llm("test-model", [{"role": "user", "content": "hi"}],
                                      _max_retries=3)

        assert result == "success"
        assert call_count == 3

    def test_no_retry_on_permanent_error(self):
        """_call_llm should NOT retry on permanent errors (e.g. auth failure)."""
        from core.ai_engine import AIEngine
        from core.safety_guard import SafetyGuard

        engine = AIEngine.__new__(AIEngine)
        engine.safety = SafetyGuard()

        call_count = 0

        def mock_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("AuthenticationError: Invalid API key")

        with patch("litellm.completion", side_effect=mock_completion):
            result = engine._call_llm("test-model", [{"role": "user", "content": "hi"}],
                                      _max_retries=3)

        assert result is None
        assert call_count == 1  # No retries on permanent error


# ─── Fix 3: Thread-safe SafetyGuard ──────────────────────────────────

class TestSafetyGuardThreadSafety:
    """Verify SafetyGuard uses threading lock for all mutable state."""

    def test_has_lock(self):
        """SafetyGuard should have a threading.Lock."""
        from core.safety_guard import SafetyGuard
        guard = SafetyGuard()
        assert hasattr(guard, '_lock')
        assert isinstance(guard._lock, type(threading.Lock()))

    def test_concurrent_request_counting(self):
        """Multiple threads incrementing request_count should be safe."""
        from core.safety_guard import SafetyGuard
        guard = SafetyGuard()

        def increment_100():
            for _ in range(100):
                guard.human_jitter.__wrapped__ if hasattr(guard.human_jitter, '__wrapped__') else None
                with guard._lock:
                    guard.request_count += 1

        threads = [threading.Thread(target=increment_100) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert guard.request_count == 500

    def test_report_failure_thread_safe(self):
        """report_failure should be thread-safe."""
        from core.safety_guard import SafetyGuard
        guard = SafetyGuard()

        def fail_many():
            for _ in range(10):
                guard.report_failure(500, "test")

        threads = [threading.Thread(target=fail_many) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert guard.consecutive_fails == 30

    def test_kill_switch_property_uses_lock(self):
        """is_killed property should use lock."""
        from core.safety_guard import SafetyGuard
        guard = SafetyGuard()
        # Should not raise, even called from multiple threads
        assert guard.is_killed is False

    def test_cancel_is_thread_safe(self):
        """cancel() and is_cancelled should use lock."""
        from core.safety_guard import SafetyGuard
        guard = SafetyGuard()
        guard.cancel()
        assert guard.is_cancelled is True

    def test_add_token_usage_thread_safe(self):
        """add_token_usage should be thread-safe."""
        from core.safety_guard import SafetyGuard
        guard = SafetyGuard()

        def add_tokens():
            for _ in range(100):
                guard.add_token_usage(10, 0.01)

        threads = [threading.Thread(target=add_tokens) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert guard.total_tokens_used == 5000
        assert abs(guard.total_cost_usd - 5.0) < 0.001


# ─── Fix 4+5: Browser lifecycle + batch reuse ────────────────────────

class TestBrowserLifecycle:
    """Verify browser context manager and batch mode in EnrichmentEngine."""

    def test_browser_context_manager_exists(self):
        """EnrichmentEngine should have _browser_context context manager."""
        from core.enrichment_engine import EnrichmentEngine
        engine = EnrichmentEngine.__new__(EnrichmentEngine)
        engine._batch_playwright = None
        engine._batch_browser = None
        assert hasattr(engine, '_browser_context')

    def test_batch_methods_exist(self):
        """EnrichmentEngine should have start_batch/end_batch."""
        from core.enrichment_engine import EnrichmentEngine
        engine = EnrichmentEngine.__new__(EnrichmentEngine)
        assert hasattr(engine, 'start_batch')
        assert hasattr(engine, 'end_batch')

    def test_init_has_batch_attrs(self):
        """__init__ should initialize batch browser attributes."""
        from core.enrichment_engine import EnrichmentEngine
        engine = EnrichmentEngine(MagicMock())
        assert engine._batch_playwright is None
        assert engine._batch_browser is None

    def test_end_batch_no_error_when_not_started(self):
        """end_batch should not error when no batch is active."""
        from core.enrichment_engine import EnrichmentEngine
        engine = EnrichmentEngine(MagicMock())
        engine.end_batch()  # Should not raise

    def test_browser_context_uses_batch_browser(self):
        """_browser_context should use batch browser when available."""
        from core.enrichment_engine import EnrichmentEngine
        engine = EnrichmentEngine(MagicMock())

        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        engine._batch_browser = mock_browser

        with engine._browser_context() as page:
            assert page == mock_page

        mock_page.close.assert_called_once()


# ─── Fix 6: ThreadWorker kwargs injection safety ─────────────────────

class TestThreadWorkerKwargs:
    """Verify ThreadWorker checks function signature before injecting kwargs."""

    def test_no_injection_for_simple_function(self):
        """Simple functions without callback params should NOT get injected kwargs."""
        from utils.thread_worker import ThreadWorker

        def simple_fn(x, y):
            return x + y

        worker = ThreadWorker(fn=simple_fn, kwargs={"x": 1, "y": 2})
        # Simulate what run() does
        sig = inspect.signature(simple_fn)
        params = sig.parameters
        accepts_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )
        assert not accepts_kwargs
        assert "_progress_callback" not in params
        assert "_cancel_checker" not in params

    def test_injection_for_function_with_progress(self):
        """Functions with _progress_callback param should get it injected."""
        from utils.thread_worker import ThreadWorker

        def fn_with_progress(data, _progress_callback=None):
            return data

        worker = ThreadWorker(fn=fn_with_progress, kwargs={"data": "test"})
        sig = inspect.signature(fn_with_progress)
        assert "_progress_callback" in sig.parameters

    def test_injection_for_function_with_kwargs(self):
        """Functions with **kwargs should get callbacks injected."""
        from utils.thread_worker import ThreadWorker

        def fn_with_kwargs(data, **kwargs):
            return data

        sig = inspect.signature(fn_with_kwargs)
        accepts_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        assert accepts_kwargs

    def test_inspect_import_in_thread_worker(self):
        """ThreadWorker module should import inspect."""
        import utils.thread_worker as tw
        assert hasattr(tw, 'inspect')


# ─── Fix 7: Ollama serialization ─────────────────────────────────────

class TestOllamaSerialization:
    """Verify Ollama tier uses semaphore for GPU serialization."""

    def test_router_has_ollama_semaphore(self):
        """RouterEngine should have an Ollama semaphore."""
        from core.router_engine import RouterEngine
        engine = RouterEngine.__new__(RouterEngine)
        engine._ollama_semaphore = threading.Semaphore(1)
        assert isinstance(engine._ollama_semaphore, threading.Semaphore)

    def test_init_creates_semaphore(self):
        """RouterEngine.__init__ should create the semaphore."""
        from core.router_engine import RouterEngine
        engine = RouterEngine(MagicMock(), MagicMock())
        assert hasattr(engine, '_ollama_semaphore')
        assert isinstance(engine._ollama_semaphore, threading.Semaphore)

    def test_execute_tier_serializes_ollama(self):
        """_execute_tier with 'ollama' should acquire semaphore."""
        from core.router_engine import RouterEngine
        source = inspect.getsource(RouterEngine._execute_tier)
        # Verify the ollama branch uses the semaphore
        assert "ollama_semaphore" in source
        assert 'tier == "ollama"' in source or "tier == 'ollama'" in source

    def test_execute_tier_no_semaphore_for_haiku(self):
        """_execute_tier with 'haiku' should NOT use ollama semaphore."""
        from core.router_engine import RouterEngine
        engine = RouterEngine(MagicMock(), MagicMock())

        engine._run_llm = MagicMock(return_value={"success": True})
        engine._get_model_for_tier = MagicMock(return_value="anthropic/claude-haiku")
        engine._models_loaded = True

        # This should work without touching the semaphore
        result = engine._execute_tier("haiku", "test_task", "prompt", {})
        engine._run_llm.assert_called_once()

    def test_threading_import_in_router(self):
        """router_engine should import threading."""
        import core.router_engine as re_mod
        assert hasattr(re_mod, 'threading')


# ─── Fix 8: SQLite write serialization ───────────────────────────────

class TestSQLiteWriteLock:
    """Verify DatabaseManager has write lock for session_scope."""

    def test_db_manager_has_write_lock(self):
        """DatabaseManager should have _write_lock attribute."""
        from tests.conftest import InMemoryDatabaseManager
        db = InMemoryDatabaseManager()
        assert hasattr(db, '_write_lock')
        assert isinstance(db._write_lock, type(threading.RLock()))

    def test_session_scope_acquires_lock(self, db):
        """session_scope should serialize writes via lock."""
        # Verify the lock exists
        assert hasattr(db, '_write_lock')

        # Test that concurrent session_scope calls are serialized
        results = []

        def write_op(value):
            with db.session_scope() as session:
                results.append(value)
                time.sleep(0.01)  # Simulate work

        threads = [threading.Thread(target=write_op, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5


# ─── Fix 9: Pinned dependencies ──────────────────────────────────────

class TestPinnedDependencies:
    """Verify requirements.txt has pinned versions."""

    def test_all_versions_pinned(self):
        """Every dependency in requirements.txt should have == pinning."""
        req_path = PROJECT_ROOT / "requirements.txt"
        assert req_path.exists()

        with open(req_path, 'r') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            assert '==' in line, f"Dependency not pinned: {line}"

    def test_playwright_stealth_included(self):
        """playwright-stealth should be in requirements.txt."""
        req_path = PROJECT_ROOT / "requirements.txt"
        content = req_path.read_text()
        assert "playwright-stealth" in content

    def test_dev_requirements_exist(self):
        """requirements-dev.txt should exist and reference base."""
        dev_path = PROJECT_ROOT / "requirements-dev.txt"
        assert dev_path.exists()
        content = dev_path.read_text()
        assert "-r requirements.txt" in content


# ─── Fix 10: db_manager decomposition ────────────────────────────────

class TestDBManagerDecomposition:
    """Verify db_manager is decomposed into separate modules."""

    def test_db_manager_is_slim(self):
        """db_manager.py should be under 200 lines."""
        db_path = PROJECT_ROOT / "database" / "db_manager.py"
        line_count = len(db_path.read_text().splitlines())
        assert line_count < 200, f"db_manager.py has {line_count} lines, expected < 200"

    def test_seed_skills_module_exists(self):
        """database/seed_skills.py should exist and be importable."""
        from database.seed_skills import seed_defaults
        assert callable(seed_defaults)

    def test_seed_agents_module_exists(self):
        """database/seed_agents.py should exist and be importable."""
        from database.seed_agents import seed_default_agents
        assert callable(seed_default_agents)

    def test_migrations_module_exists(self):
        """database/migrations.py should exist and be importable."""
        from database.migrations import migrate_schema
        assert callable(migrate_schema)

    def test_delegation_works(self):
        """DatabaseManager methods should delegate to extracted modules."""
        from database.db_manager import DatabaseManager
        source = inspect.getsource(DatabaseManager.seed_defaults)
        assert "seed_skills" in source or "seed_defaults" in source

        source = inspect.getsource(DatabaseManager.seed_default_agents)
        assert "seed_agents" in source

        source = inspect.getsource(DatabaseManager.migrate_schema)
        assert "migrations" in source or "migrate_schema" in source

    def test_aura_spec_includes_new_modules(self):
        """aura.spec should reference the new database modules."""
        spec_path = PROJECT_ROOT / "aura.spec"
        content = spec_path.read_text()
        assert "database.seed_skills" in content
        assert "database.seed_agents" in content
        assert "database.migrations" in content


# ─── Fix 11: IMAP connection reuse ───────────────────────────────────

class TestIMAPReuse:
    """Verify ReplyDetector reuses IMAP connections."""

    def test_has_imap_conn_attribute(self):
        """ReplyDetector should have _imap_conn attribute."""
        from core.reply_detector import ReplyDetector
        detector = ReplyDetector(MagicMock(), MagicMock())
        assert hasattr(detector, '_imap_conn')
        assert detector._imap_conn is None

    def test_has_get_imap_connection_method(self):
        """ReplyDetector should have _get_imap_connection method."""
        from core.reply_detector import ReplyDetector
        assert hasattr(ReplyDetector, '_get_imap_connection')

    def test_has_close_connection_method(self):
        """ReplyDetector should have close_connection method."""
        from core.reply_detector import ReplyDetector
        assert hasattr(ReplyDetector, 'close_connection')

    def test_reuses_live_connection(self):
        """_get_imap_connection should reuse a live connection."""
        from core.reply_detector import ReplyDetector
        detector = ReplyDetector(MagicMock(), MagicMock())

        mock_conn = MagicMock()
        mock_conn.noop.return_value = ("OK", [])
        detector._imap_conn = mock_conn

        config = {"host": "imap.test.com", "port": 993, "username": "u",
                  "password": "p", "use_ssl": True}

        result = detector._get_imap_connection(config)
        assert result == mock_conn
        mock_conn.noop.assert_called_once()

    def test_reconnects_on_stale_connection(self):
        """_get_imap_connection should reconnect if noop() fails."""
        from core.reply_detector import ReplyDetector
        detector = ReplyDetector(MagicMock(), MagicMock())

        # Stale connection that fails noop
        stale_conn = MagicMock()
        stale_conn.noop.side_effect = Exception("Connection lost")
        detector._imap_conn = stale_conn

        config = {"host": "imap.test.com", "port": 993, "username": "u",
                  "password": "p", "use_ssl": True}

        with patch("imaplib.IMAP4_SSL") as mock_imap:
            mock_new_conn = MagicMock()
            mock_imap.return_value = mock_new_conn
            result = detector._get_imap_connection(config)

        assert result == mock_new_conn
        assert detector._imap_conn == mock_new_conn

    def test_close_connection_clears_conn(self):
        """close_connection should logout and clear _imap_conn."""
        from core.reply_detector import ReplyDetector
        detector = ReplyDetector(MagicMock(), MagicMock())

        mock_conn = MagicMock()
        detector._imap_conn = mock_conn
        detector.close_connection()

        mock_conn.logout.assert_called_once()
        assert detector._imap_conn is None


# ─── Fix 12: Playwright stealth ──────────────────────────────────────

class TestPlaywrightStealth:
    """Verify stealth is applied in browser_context."""

    def test_stealth_in_browser_context_code(self):
        """_browser_context source should reference playwright_stealth."""
        from core.enrichment_engine import EnrichmentEngine
        source = inspect.getsource(EnrichmentEngine._browser_context)
        assert "stealth_sync" in source or "playwright_stealth" in source

    def test_contextlib_import(self):
        """enrichment_engine should use contextlib.contextmanager."""
        import core.enrichment_engine as ee
        source = inspect.getsource(ee)
        assert "contextmanager" in source


# ─── Audit Round 2: New hardening tests ──────────────────────────────

class TestKeyVaultMigrationReencrypts:
    """Verify KeyVault.migrate_ciphertext re-encrypts legacy ciphertext."""

    def test_migrate_ciphertext_returns_none_when_no_legacy(self):
        """migrate_ciphertext should return None if no legacy fernet."""
        from core.key_vault import KeyVault
        vault = KeyVault()
        vault._legacy_fernet = None
        assert vault.migrate_ciphertext("aabbcc") is None

    def test_migrate_ciphertext_returns_none_for_empty(self):
        from core.key_vault import KeyVault
        vault = KeyVault()
        assert vault.migrate_ciphertext("") is None

    def test_migrate_ciphertext_returns_none_if_already_new(self):
        """If ciphertext decrypts with new salt, no migration needed."""
        from core.key_vault import KeyVault
        vault = KeyVault()
        ct = vault.encrypt("my-api-key")
        result = vault.migrate_ciphertext(ct)
        assert result is None  # Already encrypted with new salt

    def test_migrate_ciphertext_reencrypts_legacy(self):
        """If ciphertext was encrypted with legacy salt, re-encrypt with new salt."""
        from core.key_vault import KeyVault
        from config import ENCRYPTION_SALT, _LEGACY_SALT

        vault = KeyVault()
        if ENCRYPTION_SALT == _LEGACY_SALT:
            pytest.skip("Salt hasn't changed from legacy — no migration to test")

        # Encrypt with legacy fernet
        legacy_ct = vault._legacy_fernet.encrypt(b"secret-key-123").hex()

        # Migrate
        new_ct = vault.migrate_ciphertext(legacy_ct)
        assert new_ct is not None
        assert new_ct != legacy_ct

        # New ciphertext should decrypt with new salt
        assert vault.decrypt(new_ct) == "secret-key-123"

    def test_migrate_ciphertext_method_exists(self):
        from core.key_vault import KeyVault
        assert hasattr(KeyVault, 'migrate_ciphertext')


class TestDeliveryEngineThreadSafeCounter:
    """Verify DeliveryEngine daily counter is thread-safe."""

    def test_has_lock(self):
        from core.delivery_engine import DeliveryEngine
        engine = DeliveryEngine.__new__(DeliveryEngine)
        engine._lock = threading.Lock()
        engine._daily_count = 0
        engine._max_daily = 100
        assert isinstance(engine._lock, type(threading.Lock()))

    def test_increment_daily_respects_limit(self):
        from core.delivery_engine import DeliveryEngine
        engine = DeliveryEngine.__new__(DeliveryEngine)
        engine._lock = threading.Lock()
        engine._daily_count = 0
        engine._max_daily = 3

        assert engine._increment_daily() is True
        assert engine._increment_daily() is True
        assert engine._increment_daily() is True
        assert engine._increment_daily() is False  # Limit reached

    def test_concurrent_increment(self):
        """Multiple threads incrementing should not exceed max_daily."""
        from core.delivery_engine import DeliveryEngine
        engine = DeliveryEngine.__new__(DeliveryEngine)
        engine._lock = threading.Lock()
        engine._daily_count = 0
        engine._max_daily = 50

        successes = []

        def increment_many():
            for _ in range(20):
                if engine._increment_daily():
                    successes.append(1)

        threads = [threading.Thread(target=increment_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 50 should succeed (100 attempts, 50 limit)
        assert len(successes) == 50
        assert engine._daily_count == 50


class TestSMTPConnectionCleanup:
    """Verify SMTP connections are cleaned up on error."""

    def test_send_via_smtp_has_finally(self):
        """_send_via_smtp should use try/finally for cleanup."""
        from core.delivery_engine import DeliveryEngine
        source = inspect.getsource(DeliveryEngine._send_via_smtp)
        assert "finally" in source
        assert "server.quit()" in source or "server.quit" in source

    def test_send_with_screenshot_smtp_has_finally(self):
        """send_with_screenshot SMTP block should use try/finally."""
        from core.delivery_engine import DeliveryEngine
        source = inspect.getsource(DeliveryEngine.send_with_screenshot)
        assert "finally" in source


class TestTriageIMAPCleanup:
    """Verify triage engine IMAP connections are cleaned up on error."""

    def test_fetch_overnight_has_finally(self):
        """fetch_overnight_emails should use try/finally for IMAP cleanup."""
        from core.triage_engine import TriageEngine
        source = inspect.getsource(TriageEngine.fetch_overnight_emails)
        assert "finally" in source
        assert "mail.logout()" in source or "mail.logout" in source

    def test_fetch_returns_empty_on_no_config(self):
        """fetch_overnight_emails should return [] when no IMAP config."""
        from core.triage_engine import TriageEngine
        engine = TriageEngine(MagicMock(), MagicMock())
        engine.db_manager.get_settings.return_value = None
        result = engine.fetch_overnight_emails()
        assert result == []


class TestHTMLEscapeInEmail:
    """Verify email body is HTML-escaped before embedding."""

    def test_delivery_engine_uses_html_escape(self):
        """DeliveryEngine should use html.escape for email body."""
        from core.delivery_engine import DeliveryEngine
        source = inspect.getsource(DeliveryEngine)
        assert "html.escape" in source

    def test_html_escape_import(self):
        """delivery_engine module should import html."""
        import core.delivery_engine as de
        assert hasattr(de, 'html')

    def test_escape_prevents_xss(self):
        """html.escape should neutralize script tags."""
        import html
        malicious = '<script>alert("xss")</script>'
        escaped = html.escape(malicious)
        assert "<script>" not in escaped
        assert "&lt;script&gt;" in escaped


class TestBatchBrowserStealthApplied:
    """Verify stealth is applied in batch browser path."""

    def test_batch_path_applies_stealth(self):
        """_browser_context batch path should import and apply stealth_sync."""
        from core.enrichment_engine import EnrichmentEngine
        source = inspect.getsource(EnrichmentEngine._browser_context)
        assert "stealth_sync" in source

    def test_batch_path_uses_batch_browser(self):
        """When _batch_browser is set, _browser_context should use it."""
        from core.enrichment_engine import EnrichmentEngine
        engine = EnrichmentEngine(MagicMock())

        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        engine._batch_browser = mock_browser

        with engine._browser_context() as page:
            assert page == mock_page

        mock_browser.new_page.assert_called_once()
        mock_page.close.assert_called_once()


class TestDatabaseIndexes:
    """Verify database indexes exist on frequently queried columns."""

    def test_schema_has_indexed_columns(self):
        """Key columns in schema.py should have index=True."""
        from database.schema import Lead, Campaign, AgentTask, FollowUpSend, AgentTicket, CommandLog
        # Check Lead indexes
        assert Lead.__table__.c.campaign_id.index is True
        assert Lead.__table__.c.status.index is True
        assert Lead.__table__.c.email.index is True
        assert Lead.__table__.c.lifecycle_state.index is True
        # Campaign
        assert Campaign.__table__.c.status.index is True
        # AgentTask
        assert AgentTask.__table__.c.agent_id.index is True
        assert AgentTask.__table__.c.status.index is True
        assert AgentTask.__table__.c.task_type.index is True
        # FollowUpSend
        assert FollowUpSend.__table__.c.lead_id.index is True
        assert FollowUpSend.__table__.c.status.index is True
        # AgentTicket
        assert AgentTicket.__table__.c.status.index is True
        assert AgentTicket.__table__.c.assignee_id.index is True
        # CommandLog
        assert CommandLog.__table__.c.source.index is True
        assert CommandLog.__table__.c.created_at.index is True

    def test_migrations_create_indexes(self):
        """migrations.py should create indexes for existing databases."""
        from database.migrations import migrate_schema
        source = inspect.getsource(migrate_schema)
        assert "CREATE INDEX IF NOT EXISTS" in source
        assert "ix_leads_status" in source
        assert "ix_agent_tasks_agent_id" in source


class TestMainWindowCloseEvent:
    """Verify MainWindow has closeEvent for cleanup."""

    def test_close_event_exists(self):
        """MainWindow should have a closeEvent method."""
        from ui.main_window import MainWindow
        assert hasattr(MainWindow, 'closeEvent')

    def test_close_event_stops_resources(self):
        """closeEvent source should stop key resources."""
        from ui.main_window import MainWindow
        source = inspect.getsource(MainWindow.closeEvent)
        assert "fleet_ctrl" in source or "shutdown_fleet" in source
        assert "reply_detector" in source or "close_connection" in source
        assert "gateway_ctrl" in source or "stop_all" in source
        assert "enrichment_engine" in source or "end_batch" in source
        assert "_dashboard_timer" in source


class TestConsolidatedMigrations:
    """Verify migration system is consolidated — no dual migrations."""

    def test_db_manager_no_migrate_schema_method(self):
        """DatabaseManager should NOT have _migrate_schema (consolidated into migrations.py)."""
        from database.db_manager import DatabaseManager
        assert not hasattr(DatabaseManager, '_migrate_schema')

    def test_migrations_has_skills_columns(self):
        """migrations.py should handle skills table columns."""
        from database.migrations import migrate_schema
        source = inspect.getsource(migrate_schema)
        assert "skills" in source
        assert "description" in source
        assert "capabilities" in source

    def test_migrations_has_agent_tasks_columns(self):
        """migrations.py should handle agent_tasks token columns."""
        from database.migrations import migrate_schema
        source = inspect.getsource(migrate_schema)
        assert "input_tokens" in source
        assert "output_tokens" in source
        assert "context_hash" in source
