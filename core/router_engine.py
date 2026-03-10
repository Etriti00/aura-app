"""
Aura — 4-Tier LLM Router
Routes AI tasks to the cheapest capable tier:
  local → ollama → haiku → sonnet
Logs all usage to ApiUsageLog for cost tracking.
"""

import json
import time
import re
import threading
from typing import Optional, Dict, Any

from database.db_manager import DatabaseManager
from database.schema import Settings, ApiUsageLog
from core.key_vault import KeyVault
from config import ROUTER_TASK_TIER_MAP, DEFAULT_HAIKU_MODEL, DEFAULT_TIER3_MODEL
from utils.logger import get_logger

logger = get_logger("router_engine")

# ─── Local-tier task handlers ──────────────────────────────────────────
# These never touch an LLM — pure Python string/regex ops.

def _local_format_csv(prompt: str, context: dict) -> str:
    """Format data as CSV — just return the prompt content as-is."""
    return context.get("data", prompt)


def _local_normalize_data(prompt: str, context: dict) -> str:
    """Basic normalization: strip, title-case, etc."""
    text = context.get("data", prompt)
    if isinstance(text, str):
        return text.strip().title()
    return str(text)


def _local_extract_keywords(prompt: str, context: dict) -> str:
    """Extract keywords via simple word-frequency."""
    text = context.get("data", prompt)
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:10]
    return json.dumps([w for w, _ in top])


def _local_regex_validation(prompt: str, context: dict) -> str:
    """Validate data with a regex pattern from context."""
    pattern = context.get("pattern", r".+")
    text = context.get("data", prompt)
    match = bool(re.fullmatch(pattern, text))
    return json.dumps({"valid": match})


def _local_deduplicate(prompt: str, context: dict) -> str:
    """Deduplicate a list."""
    items = context.get("items", [])
    return json.dumps(list(dict.fromkeys(items)))


LOCAL_HANDLERS = {
    "format_csv": _local_format_csv,
    "normalize_data": _local_normalize_data,
    "extract_keywords": _local_extract_keywords,
    "regex_validation": _local_regex_validation,
    "deduplicate": _local_deduplicate,
}


class RouterEngine:
    """
    4-tier LLM router: local → ollama → haiku → sonnet.
    Selects the cheapest capable tier for each task type and falls
    back to the next tier if the selected one is unavailable.
    """

    TIER_ORDER = ["local", "ollama", "haiku", "sonnet"]

    # Tier cost ranking for pacing comparisons (higher = more expensive)
    TIER_RANK = {"local": 0, "ollama": 0, "haiku": 1, "sonnet": 2}

    def __init__(self, db_manager: DatabaseManager, key_vault: KeyVault):
        self.db_manager = db_manager
        self.key_vault = key_vault
        self.pacing_engine = None  # Set externally for cost-aware routing
        self.on_rate_limit_callback = None  # Set externally for UI rate-limit alerts

        # Model identifiers — loaded from Settings on first call
        self._haiku_model = DEFAULT_HAIKU_MODEL
        self._sonnet_model = DEFAULT_TIER3_MODEL
        self._ollama_model = "ollama/llama3"  # local Ollama server
        self._models_loaded = False

        # Serialize Ollama calls — single GPU can only handle one inference at a time
        self._ollama_semaphore = threading.Semaphore(1)

    # ─── Configuration ─────────────────────────────────────────────

    def _load_models(self):
        """Load model selections from Settings (lazy, once)."""
        if self._models_loaded:
            return
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    if settings.routing_haiku_model:
                        self._haiku_model = settings.routing_haiku_model
                    if settings.tier2_model and not settings.routing_haiku_model:
                        self._haiku_model = settings.tier2_model
                    if settings.tier3_model:
                        self._sonnet_model = settings.tier3_model
        except Exception as e:
            logger.warning(f"Could not load router models from settings: {e}")
        self._models_loaded = True

    def _get_model_for_tier(self, tier: str) -> Optional[str]:
        """Return the LiteLLM model identifier for a tier."""
        self._load_models()
        return {
            "ollama": self._ollama_model,
            "haiku": self._haiku_model,
            "sonnet": self._sonnet_model,
        }.get(tier)

    def _tier_available(self, tier: str) -> bool:
        """Check whether a tier is reachable, respecting auth_mode per provider."""
        if tier == "local":
            return True
        if tier == "ollama":
            try:
                import httpx
                r = httpx.get("http://localhost:11434/api/tags", timeout=2)
                return r.status_code == 200
            except Exception:
                return False
        # Cloud tiers — respect auth_mode (api/subscription/none)
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if not settings:
                    return False

                anthropic_mode = getattr(settings, "anthropic_auth_mode", "none")
                openai_mode = getattr(settings, "openai_auth_mode", "none")

                def _has_anthropic():
                    if anthropic_mode == "api":
                        return bool(settings.anthropic_key_enc)
                    if anthropic_mode == "subscription":
                        return bool(getattr(settings, "anthropic_sub_token_enc", ""))
                    return False

                def _has_openai():
                    if openai_mode == "api":
                        return bool(settings.openai_key_enc)
                    if openai_mode == "subscription":
                        return bool(getattr(settings, "openai_sub_token_enc", ""))
                    return False

                if tier == "haiku":
                    return _has_anthropic()
                if tier == "sonnet":
                    return (
                        _has_anthropic()
                        or bool(settings.gemini_key_enc)
                        or _has_openai()
                        or bool(getattr(settings, "openrouter_key_enc", ""))
                    )
        except Exception:
            return False
        return False

    # ─── Core routing ──────────────────────────────────────────────

    def route(self, task_type: str, prompt: str, context: dict = None,
              tier_override: str = None) -> dict:
        """
        Route a task to the cheapest capable tier.

        Returns:
            {
                "success": bool,
                "data": str (response text),
                "model_used": str,
                "tokens": int,
                "cost_usd": float,
                "tier": str,
                "error": str | None,
            }
        """
        context = context or {}
        target_tier = tier_override or ROUTER_TASK_TIER_MAP.get(task_type, "sonnet")

        # ── Pacing constraint: limit tiers to budget-allowed maximum ──
        if self.pacing_engine and self.pacing_engine.is_active():
            max_tier = self.pacing_engine.get_allowed_max_tier()
            max_rank = self.TIER_RANK.get(max_tier, 2)
            target_rank = self.TIER_RANK.get(target_tier, 2)
            if target_rank > max_rank:
                logger.info(
                    f"Pacing: downgrading '{task_type}' from {target_tier} → {max_tier}"
                )
                target_tier = max_tier

        # Build fallback chain from target tier upward
        start_idx = self.TIER_ORDER.index(target_tier) if target_tier in self.TIER_ORDER else 3
        fallback_chain = self.TIER_ORDER[start_idx:]

        # If pacing active, remove tiers above the allowed maximum
        if self.pacing_engine and self.pacing_engine.is_active():
            max_tier = self.pacing_engine.get_allowed_max_tier()
            max_rank = self.TIER_RANK.get(max_tier, 2)
            fallback_chain = [
                t for t in fallback_chain
                if self.TIER_RANK.get(t, 2) <= max_rank
            ]
            if not fallback_chain:
                fallback_chain = ["local"]

        for tier in fallback_chain:
            if not self._tier_available(tier):
                logger.debug(f"Tier '{tier}' unavailable for task '{task_type}', trying next")
                continue

            result = self._execute_tier(tier, task_type, prompt, context)
            if result["success"]:
                self._log_usage(tier, task_type, result)
                return result
            # If this tier failed, try the next
            logger.warning(f"Tier '{tier}' failed for '{task_type}': {result.get('error')}")

        return {
            "success": False,
            "data": "",
            "model_used": "",
            "tokens": 0,
            "cost_usd": 0.0,
            "tier": target_tier,
            "error": "All tiers exhausted — no model available",
        }

    def _execute_tier(self, tier: str, task_type: str, prompt: str, context: dict) -> dict:
        """Execute a task on a specific tier.
        Ollama tier is serialized via semaphore (single GPU)."""
        if tier == "local":
            return self._run_local(task_type, prompt, context)
        elif tier == "ollama":
            with self._ollama_semaphore:
                model = self._get_model_for_tier(tier)
                return self._run_llm(model, tier, prompt, context, task_type=task_type)
        else:
            model = self._get_model_for_tier(tier)
            return self._run_llm(model, tier, prompt, context, task_type=task_type)

    def _run_local(self, task_type: str, prompt: str, context: dict) -> dict:
        """Run a local (pure-Python) handler."""
        handler = LOCAL_HANDLERS.get(task_type)
        if not handler:
            return {
                "success": False, "data": "", "model_used": "local",
                "tokens": 0, "cost_usd": 0.0, "tier": "local",
                "error": f"No local handler for '{task_type}'",
            }
        try:
            result_text = handler(prompt, context)
            return {
                "success": True, "data": result_text, "model_used": "local",
                "tokens": 0, "cost_usd": 0.0, "tier": "local", "error": None,
            }
        except Exception as e:
            return {
                "success": False, "data": "", "model_used": "local",
                "tokens": 0, "cost_usd": 0.0, "tier": "local",
                "error": str(e),
            }

    def _run_llm(self, model: str, tier: str, prompt: str, context: dict,
                 task_type: str = "") -> dict:
        """Call LiteLLM with the given model."""
        if not model:
            return {
                "success": False, "data": "", "model_used": model or "",
                "tokens": 0, "cost_usd": 0.0, "tier": tier,
                "error": f"No model configured for tier '{tier}'",
            }

        # Inject API keys into environment
        self._inject_keys()

        try:
            import litellm
            litellm.set_verbose = False

            messages = [{"role": "user", "content": prompt}]
            if context.get("system"):
                messages.insert(0, {"role": "system", "content": context["system"]})

            temperature = context.get("temperature", 0.7)
            # Use task-specific output token budget, then context override, then default
            from config import TASK_OUTPUT_TOKENS
            default_budget = TASK_OUTPUT_TOKENS.get(task_type, TASK_OUTPUT_TOKENS["_default"])
            max_tokens = context.get("max_tokens", default_budget)

            response = litellm.completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            usage = response.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            cost = litellm.completion_cost(completion_response=response) or 0.0
            content = response["choices"][0]["message"]["content"].strip()

            return {
                "success": True,
                "data": content,
                "model_used": model,
                "tokens": total_tokens,
                "cost_usd": cost,
                "tier": tier,
                "error": None,
            }
        except Exception as e:
            error_str = str(e)
            logger.error(f"LLM call failed (model={model}, tier={tier}): {error_str}")
            # Detect rate limit — notify UI so user can switch auth mode
            if "429" in error_str or "rate_limit" in error_str.lower():
                if self.on_rate_limit_callback:
                    try:
                        self.on_rate_limit_callback(tier, error_str)
                    except Exception:
                        pass
            return {
                "success": False, "data": "", "model_used": model,
                "tokens": 0, "cost_usd": 0.0, "tier": tier,
                "error": error_str,
            }

    def _inject_keys(self):
        """Set API keys as env vars for LiteLLM, respecting auth_mode per provider.
        No fallback between api/subscription — mutual exclusivity enforced."""
        import os
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if not settings:
                    return

                # Gemini (API-key only, no subscription mode)
                if settings.gemini_key_enc:
                    os.environ["GEMINI_API_KEY"] = self.key_vault.decrypt(settings.gemini_key_enc)

                # Anthropic — strict auth mode
                anthropic_mode = getattr(settings, "anthropic_auth_mode", "none")
                if anthropic_mode == "api" and settings.anthropic_key_enc:
                    os.environ["ANTHROPIC_API_KEY"] = self.key_vault.decrypt(settings.anthropic_key_enc)
                elif anthropic_mode == "subscription" and getattr(settings, "anthropic_sub_token_enc", ""):
                    os.environ["ANTHROPIC_API_KEY"] = self.key_vault.decrypt(settings.anthropic_sub_token_enc)

                # OpenAI — strict auth mode
                openai_mode = getattr(settings, "openai_auth_mode", "none")
                if openai_mode == "api" and settings.openai_key_enc:
                    os.environ["OPENAI_API_KEY"] = self.key_vault.decrypt(settings.openai_key_enc)
                elif openai_mode == "subscription" and getattr(settings, "openai_sub_token_enc", ""):
                    os.environ["OPENAI_API_KEY"] = self.key_vault.decrypt(settings.openai_sub_token_enc)

                # OpenRouter (API-key only)
                if getattr(settings, "openrouter_key_enc", ""):
                    os.environ["OPENROUTER_API_KEY"] = self.key_vault.decrypt(settings.openrouter_key_enc)
        except Exception as e:
            logger.warning(f"Failed to inject API keys: {e}")

    # ─── Usage logging ─────────────────────────────────────────────

    def _log_usage(self, tier: str, task_type: str, result: dict):
        """Log API usage to the ApiUsageLog table."""
        try:
            with self.db_manager.session_scope() as session:
                log = ApiUsageLog(
                    service=f"router_{tier}",
                    endpoint=task_type,
                    tokens_used=result.get("tokens", 0),
                    cost_usd=result.get("cost_usd", 0.0),
                    response_code=200 if result.get("success") else 500,
                )
                session.add(log)
        except Exception as e:
            logger.warning(f"Failed to log router usage: {e}")

    # ─── Cost analytics ────────────────────────────────────────────

    def estimate_cost(self, task_type: str, estimated_tokens: int = 500) -> dict:
        """Pre-call cost preview for a task type."""
        tier = ROUTER_TASK_TIER_MAP.get(task_type, "sonnet")
        # Rough per-token costs (input+output blended)
        cost_per_token = {
            "local": 0.0,
            "ollama": 0.0,
            "haiku": 0.0000005,   # ~$0.50/1M tokens
            "sonnet": 0.000006,   # ~$6/1M tokens
        }
        est = estimated_tokens * cost_per_token.get(tier, 0.000006)
        return {"tier": tier, "estimated_cost_usd": round(est, 6), "estimated_tokens": estimated_tokens}

    def get_monthly_spend(self) -> dict:
        """Aggregate current month's spend from ApiUsageLog."""
        from sqlalchemy import func, extract
        from datetime import datetime

        now = datetime.utcnow()
        try:
            with self.db_manager.session_scope() as session:
                rows = (
                    session.query(
                        ApiUsageLog.service,
                        func.count(ApiUsageLog.id).label("calls"),
                        func.sum(ApiUsageLog.tokens_used).label("tokens"),
                        func.sum(ApiUsageLog.cost_usd).label("cost"),
                    )
                    .filter(
                        extract("year", ApiUsageLog.timestamp) == now.year,
                        extract("month", ApiUsageLog.timestamp) == now.month,
                    )
                    .group_by(ApiUsageLog.service)
                    .all()
                )

                breakdown = {}
                total_cost = 0.0
                total_calls = 0
                total_tokens = 0

                for service, calls, tokens, cost in rows:
                    calls = calls or 0
                    tokens = tokens or 0
                    cost = cost or 0.0
                    breakdown[service] = {
                        "calls": calls,
                        "tokens": tokens,
                        "cost_usd": round(cost, 4),
                    }
                    total_cost += cost
                    total_calls += calls
                    total_tokens += tokens

                return {
                    "breakdown": breakdown,
                    "total_cost_usd": round(total_cost, 4),
                    "total_calls": total_calls,
                    "total_tokens": total_tokens,
                    "month": now.strftime("%Y-%m"),
                }
        except Exception as e:
            logger.error(f"Failed to get monthly spend: {e}")
            return {"breakdown": {}, "total_cost_usd": 0.0, "total_calls": 0, "total_tokens": 0, "month": ""}
