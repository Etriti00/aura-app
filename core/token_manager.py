"""
Aura — Token Manager
Estimates token usage, compacts agent context, caches summaries and responses.
Features 1 (Conversation Compaction) + 3 (Advanced Token Saving).
"""

import hashlib
import json
import time
from collections import OrderedDict
from datetime import datetime, timedelta

from database.db_manager import DatabaseManager
from database.schema import CachedSummary
from config import (
    AGENT_CONTEXT_MAX_TOKENS,
    TOKEN_ESTIMATE_CHARS_PER_TOKEN,
    SUMMARY_CACHE_TTL_HOURS,
    RESPONSE_CACHE_MAX_SIZE,
    RESPONSE_CACHE_TTL_HOURS,
    TASK_CONTEXT_SECTIONS,
)
from utils.logger import get_logger

logger = get_logger("token_manager")

# Try tiktoken for accurate counting, fall back to char estimate
try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(text: str) -> int:
        return len(_ENC.encode(text))
except (ImportError, ValueError):
    _ENC = None

    def _count_tokens(text: str) -> int:
        return max(1, len(text) // TOKEN_ESTIMATE_CHARS_PER_TOKEN)


class TokenManager:
    """Token estimation, context compaction, summary caching, response caching."""

    def __init__(self, db_manager: DatabaseManager, router_engine=None):
        self.db_manager = db_manager
        self.router_engine = router_engine
        # In-memory LRU response cache: {prompt_hash: (result_dict, expiry_ts)}
        self._response_cache: OrderedDict = OrderedDict()

    # ─── Token Estimation ─────────────────────────────────────────────────

    def estimate_tokens(self, text: str) -> int:
        """Count or estimate tokens for a string."""
        if not text:
            return 0
        return _count_tokens(text)

    def budget_remaining(self, used: int,
                         max_tokens: int = AGENT_CONTEXT_MAX_TOKENS) -> int:
        """How many tokens are left in the budget."""
        return max(0, max_tokens - used)

    # ─── Context Compaction ───────────────────────────────────────────────

    def compact_context(self, context_parts: dict, task_type: str,
                        max_tokens: int = AGENT_CONTEXT_MAX_TOKENS) -> dict:
        """
        Drop or truncate context sections to stay within max_tokens.

        Strategy:
          1. Filter to only sections relevant for this task_type.
          2. If under budget, return as-is.
          3. Progressively trim memory, history, and case_context.
          4. As last resort, summarize long_term_memory via LLM.
        """
        # Step 1: Filter to relevant sections
        allowed = TASK_CONTEXT_SECTIONS.get(
            task_type, TASK_CONTEXT_SECTIONS["_default"]
        )
        filtered = {k: v for k, v in context_parts.items() if k in allowed}

        # Step 2: Check budget
        total = sum(self.estimate_tokens(v) for v in filtered.values())
        if total <= max_tokens:
            return filtered

        # Step 3: Progressive trimming
        # Trim memory_today to last 500 chars
        if "memory_today" in filtered and len(filtered["memory_today"]) > 500:
            filtered["memory_today"] = filtered["memory_today"][-500:]
            total = sum(self.estimate_tokens(v) for v in filtered.values())
            if total <= max_tokens:
                return filtered

        # Trim long_term_memory to last 1000 chars
        if "long_term_memory" in filtered and len(filtered["long_term_memory"]) > 1000:
            filtered["long_term_memory"] = filtered["long_term_memory"][-1000:]
            total = sum(self.estimate_tokens(v) for v in filtered.values())
            if total <= max_tokens:
                return filtered

        # Trim history to last 5 entries (split by newline, keep last 5)
        if "history" in filtered:
            lines = filtered["history"].split("\n")
            if len(lines) > 6:  # header + 5 entries
                filtered["history"] = lines[0] + "\n" + "\n".join(lines[-5:])
            total = sum(self.estimate_tokens(v) for v in filtered.values())
            if total <= max_tokens:
                return filtered

        # Trim case_context to half
        if "case_context" in filtered:
            ctx = filtered["case_context"]
            half = len(ctx) // 2
            filtered["case_context"] = ctx[:half] + "\n[...truncated]"
            total = sum(self.estimate_tokens(v) for v in filtered.values())
            if total <= max_tokens:
                return filtered

        # Step 4: Summarize long_term_memory via LLM as last resort
        if "long_term_memory" in filtered and self.router_engine:
            try:
                summary = self.summarize_text(
                    filtered["long_term_memory"], max_tokens=300
                )
                filtered["long_term_memory"] = f"LONG_TERM_MEMORY (summary): {summary}"
            except Exception as e:
                logger.debug(f"LLM summarization failed during compaction: {e}")
                # Hard truncate as final fallback
                filtered["long_term_memory"] = filtered["long_term_memory"][:400]

        return filtered

    # ─── Prompt Hashing ───────────────────────────────────────────────────

    def hash_prompt(self, prompt: str) -> str:
        """SHA-256 hash of a prompt string for dedup / context_hash column."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    # ─── Response Cache (In-Memory LRU) ───────────────────────────────────

    def get_cached_response(self, prompt_hash: str) -> dict | None:
        """Check in-memory response cache. Returns cached result or None."""
        if prompt_hash not in self._response_cache:
            return None

        result, expiry_ts = self._response_cache[prompt_hash]
        if time.time() > expiry_ts:
            # Expired — remove and return miss
            del self._response_cache[prompt_hash]
            return None

        # Move to end (most recently used)
        self._response_cache.move_to_end(prompt_hash)
        return result

    def cache_response(self, prompt_hash: str, result: dict):
        """Store result in LRU response cache with TTL."""
        expiry = time.time() + (RESPONSE_CACHE_TTL_HOURS * 3600)
        self._response_cache[prompt_hash] = (result, expiry)
        self._response_cache.move_to_end(prompt_hash)

        # Evict oldest if over max size
        while len(self._response_cache) > RESPONSE_CACHE_MAX_SIZE:
            self._response_cache.popitem(last=False)

    # ─── Summary Cache (DB-backed) ────────────────────────────────────────

    def get_or_create_summary(self, source_type: str, source_id: int,
                              source_text: str,
                              max_summary_tokens: int = 400) -> str:
        """
        Return a cached summary if source text hasn't changed.
        Otherwise summarize via haiku and store in cached_summaries table.
        """
        if not source_text or not source_text.strip():
            return ""

        source_hash = hashlib.md5(source_text.encode("utf-8")).hexdigest()

        try:
            with self.db_manager.session_scope() as session:
                cached = (
                    session.query(CachedSummary)
                    .filter_by(source_type=source_type, source_id=source_id)
                    .first()
                )

                ttl_cutoff = datetime.utcnow() - timedelta(
                    hours=SUMMARY_CACHE_TTL_HOURS
                )

                if (cached and cached.source_hash == source_hash
                        and cached.updated_at > ttl_cutoff):
                    return cached.summary_text

                # Generate new summary
                summary = self.summarize_text(
                    source_text, max_tokens=max_summary_tokens
                )

                if cached:
                    cached.summary_text = summary
                    cached.source_hash = source_hash
                    cached.updated_at = datetime.utcnow()
                else:
                    session.add(CachedSummary(
                        source_type=source_type,
                        source_id=source_id,
                        summary_text=summary,
                        source_hash=source_hash,
                    ))

                return summary
        except Exception as e:
            logger.error(f"Summary cache error: {e}")
            # Fallback: truncate
            max_chars = max_summary_tokens * TOKEN_ESTIMATE_CHARS_PER_TOKEN
            return source_text[:max_chars]

    def summarize_text(self, text: str, max_tokens: int = 400) -> str:
        """
        Use a cheap LLM call (haiku via router) to summarize text.
        Falls back to hard truncation if router not available.
        """
        if not self.router_engine:
            max_chars = max_tokens * TOKEN_ESTIMATE_CHARS_PER_TOKEN
            return text[:max_chars]

        prompt = (
            "Summarize the following text concisely, preserving key facts, "
            "names, dates, and decisions. Output only the summary, no preamble.\n\n"
            f"{text[:8000]}"
        )

        try:
            result = self.router_engine.route(
                "summarize_for_cache", prompt,
                context={"max_tokens": max_tokens, "temperature": 0.2},
            )
            if result.get("success"):
                return result["data"]
        except Exception as e:
            logger.debug(f"LLM summarization failed: {e}")

        # Fallback: truncate
        max_chars = max_tokens * TOKEN_ESTIMATE_CHARS_PER_TOKEN
        return text[:max_chars]
