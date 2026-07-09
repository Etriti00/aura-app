"""
Aura — Model Verifier
Two step validation used before a model is trusted anywhere in the app,
and required before a per-agent model assignment is finalized:

  Step 1 (authenticate): confirm credentials exist for the model's provider
          and that the provider accepts them (a minimal one token call).
  Step 2 (round trip):  send a real test prompt and require a non empty
          response from the model.

Both steps honor subscription auth — Claude, ChatGPT, and Gemini CLI modes
route through core.cli_llm instead of LiteLLM.
"""

import os
import time
from typing import Optional

from core.model_fleet import PROVIDERS, provider_for_model
from utils.logger import get_logger

logger = get_logger("model_verifier")

_TEST_PROMPT = "Reply with exactly the word OK and nothing else."


class ModelVerifier:
    """Validates that a model authenticates and can serve a round trip."""

    def __init__(self, db_manager=None, key_vault=None):
        self.db_manager = db_manager
        self.key_vault = key_vault

    # ─── public API ────────────────────────────────────────────────

    def verify(self, model_id: str) -> dict:
        """
        Run the two step verification for a model ID.

        Returns:
            {
                "success": bool,        # both steps passed
                "auth_ok": bool,        # step 1
                "roundtrip_ok": bool,   # step 2
                "latency_ms": int,
                "response": str,
                "error": str | None,
            }
        """
        result = {
            "success": False, "auth_ok": False, "roundtrip_ok": False,
            "latency_ms": 0, "response": "", "error": None,
        }
        if not model_id or not str(model_id).strip():
            result["error"] = "No model ID provided"
            return result
        model_id = str(model_id).strip()

        settings = self._get_settings()

        # ── Step 1: credentials present + provider accepts them ──
        auth_error = self._check_credentials(model_id, settings)
        if auth_error:
            result["error"] = auth_error
            return result

        start = time.monotonic()
        text, err = self._call(model_id, settings, _TEST_PROMPT, max_tokens=8)
        elapsed = int((time.monotonic() - start) * 1000)
        result["latency_ms"] = elapsed

        if err and self._is_auth_error(err):
            result["error"] = f"Authentication failed: {err}"
            return result
        result["auth_ok"] = True

        # ── Step 2: the round trip must produce output ──
        if err:
            result["error"] = f"Model call failed: {err}"
            return result
        if not text or not text.strip():
            result["error"] = "Model returned an empty response"
            return result

        result["roundtrip_ok"] = True
        result["response"] = text.strip()[:200]
        result["success"] = True
        logger.info(f"Model verified: {model_id} ({elapsed}ms)")
        return result

    # ─── internals ─────────────────────────────────────────────────

    def _get_settings(self):
        if not self.db_manager:
            return None
        try:
            return self.db_manager.get_settings()
        except Exception:
            return None

    def _subscription_mode(self, model_id: str, settings) -> bool:
        if settings is None:
            return False
        from core.cli_llm import try_subscription_route  # noqa: F401
        provider = provider_for_model(model_id)
        mode_field = {
            "anthropic": "anthropic_auth_mode",
            "openai": "openai_auth_mode",
            "gemini": "gemini_auth_mode",
        }.get(provider)
        return bool(
            mode_field
            and getattr(settings, mode_field, "none") == "subscription"
        )

    def _check_credentials(self, model_id: str, settings) -> Optional[str]:
        provider = provider_for_model(model_id)
        if provider is None:
            return None  # unknown prefix — let LiteLLM decide at call time
        if provider == "ollama":
            return None  # local, no key required
        if self._subscription_mode(model_id, settings):
            return None  # CLI subscription covers this provider
        info = PROVIDERS[provider]
        env_present = bool(os.environ.get(info["env"], ""))
        stored = bool(
            settings is not None
            and getattr(settings, info["key_field"], "")
        )
        if not env_present and not stored:
            return (
                f"No API key configured for {info['label']}. "
                f"Add it in Settings > API Keys."
            )
        # Make sure a stored key is exported for the call
        if stored and not env_present and self.key_vault:
            try:
                key = self.key_vault.decrypt(getattr(settings, info["key_field"]))
                if key:
                    os.environ[info["env"]] = key
            except Exception as e:
                return f"Stored key could not be decrypted: {e}"
        return None

    def _call(self, model_id: str, settings, prompt: str,
              max_tokens: int = 8) -> tuple:
        """Make one call; returns (text, error)."""
        messages = [{"role": "user", "content": prompt}]

        # Subscription CLI routing first
        try:
            from core.cli_llm import try_subscription_route
            handled, text = try_subscription_route(settings, model_id, messages)
            if handled:
                if text:
                    return text, None
                return None, "provider CLI call failed (is it installed and logged in?)"
        except Exception as e:
            return None, str(e)

        try:
            import litellm
            litellm.set_verbose = False
            litellm.drop_params = True
            kwargs = dict(
                model=model_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0,
            )
            if model_id.startswith("ollama"):
                kwargs["api_base"] = "http://localhost:11434"
            response = litellm.completion(**kwargs)
            text = response["choices"][0]["message"]["content"]
            return (text or ""), None
        except Exception as e:
            return None, str(e)

    @staticmethod
    def _is_auth_error(error: str) -> bool:
        needles = ("401", "403", "authentication", "unauthorized",
                   "invalid api key", "api key", "permission")
        low = (error or "").lower()
        return any(n in low for n in needles)