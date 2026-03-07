"""Tests for TokenManager — token estimation, context compaction, response & summary caching."""

import time
import pytest
from core.token_manager import TokenManager, _count_tokens
from database.schema import CachedSummary


# ─── Token Estimation ──────────────────────────────────────────────────────

class TestTokenEstimation:

    def test_estimate_returns_int(self, token_manager):
        tm, _ = token_manager
        result = tm.estimate_tokens("Hello world")
        assert isinstance(result, int)
        assert result > 0

    def test_empty_string_returns_zero(self, token_manager):
        tm, _ = token_manager
        assert tm.estimate_tokens("") == 0

    def test_none_returns_zero(self, token_manager):
        tm, _ = token_manager
        assert tm.estimate_tokens(None) == 0

    def test_long_text_proportional(self, token_manager):
        tm, _ = token_manager
        short = tm.estimate_tokens("Hello")
        long_text = tm.estimate_tokens("Hello " * 1000)
        assert long_text > short * 10

    def test_budget_remaining(self, token_manager):
        tm, _ = token_manager
        assert tm.budget_remaining(3000, max_tokens=8000) == 5000
        assert tm.budget_remaining(9000, max_tokens=8000) == 0


# ─── Context Compaction ────────────────────────────────────────────────────

class TestCompactContext:

    def test_fits_budget_unchanged(self, token_manager):
        tm, _ = token_manager
        parts = {
            "soul": "SOUL: Be helpful",
            "payload": "TASK: test\nPAYLOAD: {}",
        }
        result = tm.compact_context(parts, "generate_email", max_tokens=5000)
        assert result == parts

    def test_filters_by_task_type(self, token_manager):
        tm, _ = token_manager
        parts = {
            "soul": "SOUL: Be helpful",
            "mission": "MISSION: Long mission text " * 100,
            "playbook": "PLAYBOOK: Detailed playbook " * 100,
            "boundaries": "BOUNDARIES: Strict rules " * 100,
            "skill": "SKILL: email writer",
            "payload": "TASK: generate_email\nPAYLOAD: {}",
        }
        result = tm.compact_context(parts, "generate_email", max_tokens=5000)
        # generate_email only needs soul, skill, memory_today, case_context, payload
        assert "soul" in result
        assert "skill" in result
        assert "payload" in result
        assert "mission" not in result
        assert "playbook" not in result
        assert "boundaries" not in result

    def test_trims_memory_when_over_budget(self, token_manager):
        tm, _ = token_manager
        long_memory = "LONG_TERM_MEMORY: " + "x" * 4000
        parts = {
            "soul": "SOUL: Be helpful",
            "long_term_memory": long_memory,
            "payload": "TASK: research\nPAYLOAD: {}",
        }
        result = tm.compact_context(parts, "research", max_tokens=500)
        assert "long_term_memory" in result
        assert len(result["long_term_memory"]) < len(long_memory)

    def test_trims_history_entries(self, token_manager):
        tm, _ = token_manager
        history_lines = ["RECENT_COMMAND_HISTORY:"] + [
            f"Entry {i} with detailed task info " * 5 for i in range(20)
        ]
        # Large context to force compaction
        parts = {
            "soul": "SOUL: " + "Be a great agent. " * 50,
            "mission": "MISSION: " + "Help users effectively. " * 50,
            "skill": "SKILL: " + "Expert email writer persona. " * 50,
            "long_term_memory": "LONG_TERM_MEMORY: " + "Learned important things. " * 200,
            "memory_today": "TODAY_NOTES: " + "Did stuff today. " * 100,
            "history": "\n".join(history_lines),
            "payload": "TASK: test\nPAYLOAD: {}",
        }
        result = tm.compact_context(parts, "_default", max_tokens=500)
        if "history" in result:
            lines = result["history"].split("\n")
            assert len(lines) <= 7  # header + 5 entries max

    def test_default_sections_for_unknown_task(self, token_manager):
        tm, _ = token_manager
        parts = {
            "soul": "x",
            "mission": "x",
            "skill": "x",
            "payload": "TASK: x\nPAYLOAD: {}",
        }
        result = tm.compact_context(parts, "unknown_task_type", max_tokens=5000)
        assert "soul" in result
        assert "mission" in result


# ─── Prompt Hashing ────────────────────────────────────────────────────────

class TestHashPrompt:

    def test_deterministic(self, token_manager):
        tm, _ = token_manager
        h1 = tm.hash_prompt("test prompt")
        h2 = tm.hash_prompt("test prompt")
        assert h1 == h2

    def test_different_prompts_different_hashes(self, token_manager):
        tm, _ = token_manager
        h1 = tm.hash_prompt("prompt A")
        h2 = tm.hash_prompt("prompt B")
        assert h1 != h2

    def test_returns_hex_string(self, token_manager):
        tm, _ = token_manager
        h = tm.hash_prompt("test")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex


# ─── Response Cache ────────────────────────────────────────────────────────

class TestResponseCache:

    def test_cache_miss(self, token_manager):
        tm, _ = token_manager
        assert tm.get_cached_response("nonexistent_hash") is None

    def test_cache_hit(self, token_manager):
        tm, _ = token_manager
        result = {"success": True, "data": "cached result"}
        tm.cache_response("hash123", result)
        cached = tm.get_cached_response("hash123")
        assert cached is not None
        assert cached["data"] == "cached result"

    def test_cache_different_keys(self, token_manager):
        tm, _ = token_manager
        tm.cache_response("hashA", {"data": "A"})
        tm.cache_response("hashB", {"data": "B"})
        assert tm.get_cached_response("hashA")["data"] == "A"
        assert tm.get_cached_response("hashB")["data"] == "B"

    def test_lru_eviction(self, db):
        from config import RESPONSE_CACHE_MAX_SIZE
        tm = TokenManager(db)
        # Fill cache to max + 1
        for i in range(RESPONSE_CACHE_MAX_SIZE + 10):
            tm.cache_response(f"hash_{i}", {"data": f"result_{i}"})
        # Oldest entries should be evicted
        assert len(tm._response_cache) <= RESPONSE_CACHE_MAX_SIZE

    def test_expired_entry_returns_none(self, db):
        tm = TokenManager(db)
        # Manually insert an expired entry
        tm._response_cache["expired"] = ({"data": "old"}, time.time() - 1)
        assert tm.get_cached_response("expired") is None


# ─── Summary Cache (DB-backed) ────────────────────────────────────────────

class TestSummaryCache:

    def test_no_router_returns_truncated(self, token_manager):
        tm, db = token_manager
        text = "A" * 2000
        result = tm.get_or_create_summary("agent_memory", 1, text, max_summary_tokens=100)
        assert len(result) <= 500  # 100 * 4 chars/token

    def test_empty_text_returns_empty(self, token_manager):
        tm, _ = token_manager
        assert tm.get_or_create_summary("agent_memory", 1, "") == ""
        assert tm.get_or_create_summary("agent_memory", 1, "   ") == ""

    def test_creates_db_row(self, token_manager):
        tm, db = token_manager
        tm.get_or_create_summary("agent_memory", 99, "Some content to summarize")
        with db.session_scope() as session:
            cached = session.query(CachedSummary).filter_by(
                source_type="agent_memory", source_id=99
            ).first()
            assert cached is not None
            assert cached.source_hash != ""

    def test_returns_cached_on_same_hash(self, token_manager):
        tm, db = token_manager
        text = "Same text content"
        r1 = tm.get_or_create_summary("lead_case", 1, text)
        r2 = tm.get_or_create_summary("lead_case", 1, text)
        assert r1 == r2

    def test_invalidates_on_changed_text(self, token_manager):
        tm, db = token_manager
        r1 = tm.get_or_create_summary("lead_case", 50, "Version 1 of the text")
        r2 = tm.get_or_create_summary("lead_case", 50, "Version 2 completely different")
        # Both should return something (truncated fallback), but different
        assert r1 != r2


# ─── Summarize Text ───────────────────────────────────────────────────────

class TestSummarizeText:

    def test_no_router_truncates(self, token_manager):
        tm, _ = token_manager
        text = "Hello world " * 500
        result = tm.summarize_text(text, max_tokens=50)
        assert len(result) <= 200  # 50 * 4

    def test_short_text_passthrough(self, token_manager):
        tm, _ = token_manager
        result = tm.summarize_text("Short text", max_tokens=100)
        assert result == "Short text"
