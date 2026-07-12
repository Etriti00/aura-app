"""
Aura — Model Fleet Registry
Single source of truth for every LLM provider and model Aura can drive.

Each provider entry carries the LiteLLM route prefix implicitly in its model
IDs, the environment variable LiteLLM expects, and the encrypted settings
column where Aura stores the key. UIs, key injection, and the model verifier
all read from this registry, so adding a provider is a one-entry change.

Custom models: users may register any extra model IDs (comma separated) in
settings.custom_models — they are merged into every picker and are routable
as long as the matching provider key or subscription is configured.
"""

import json
from typing import Optional

from utils.logger import get_logger

logger = get_logger("model_fleet")

PROVIDERS = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "env": "ANTHROPIC_API_KEY",
        "key_field": "anthropic_key_enc",
        "models": [
            "anthropic/claude-fable-5",
            "anthropic/claude-opus-4-8",
            "anthropic/claude-sonnet-5",
            "anthropic/claude-sonnet-4-6",
            "anthropic/claude-haiku-4-5",
        ],
    },
    "openai": {
        "label": "OpenAI (GPT)",
        "env": "OPENAI_API_KEY",
        "key_field": "openai_key_enc",
        "models": [
            "openai/gpt-5.6-sol",
            "openai/gpt-5.6-terra",
            "openai/gpt-5.6-luna",
            "openai/gpt-5.5",
            "openai/gpt-5.2",
            "openai/gpt-4.1",
            "openai/gpt-4.1-mini",
            "openai/o4-mini",
        ],
    },
    "gemini": {
        "label": "Google (Gemini)",
        "env": "GEMINI_API_KEY",
        "key_field": "gemini_key_enc",
        "models": [
            "gemini/gemini-3.5-flash",
            "gemini/gemini-3-flash",
            "gemini/gemini-3.1-flash-lite",
        ],
    },
    "meta": {
        "label": "Meta (Muse Spark)",
        "env": "META_API_KEY",
        "key_field": "meta_key_enc",
        "models": [
            "meta/muse-spark-1.1",
        ],
    },
    "xai": {
        "label": "xAI (Grok)",
        "env": "XAI_API_KEY",
        "key_field": "xai_key_enc",
        "models": [
            "xai/grok-4.5",
            "xai/grok-4.3",
        ],
    },
    "zai": {
        "label": "Z.ai (GLM)",
        "env": "ZAI_API_KEY",
        "key_field": "zai_key_enc",
        "models": [
            "zai/glm-5.2",
            "zai/glm-5.1",
        ],
    },
    "moonshot": {
        "label": "Moonshot (Kimi)",
        "env": "MOONSHOT_API_KEY",
        "key_field": "moonshot_key_enc",
        "models": [
            "moonshot/kimi-k2.7",
            "moonshot/kimi-k2.6",
        ],
    },
    "dashscope": {
        "label": "Alibaba (Qwen)",
        "env": "DASHSCOPE_API_KEY",
        "key_field": "dashscope_key_enc",
        "models": [
            "dashscope/qwen3-max",
            "dashscope/qwen3.6-plus",
        ],
    },
    "minimax": {
        "label": "MiniMax",
        "env": "MINIMAX_API_KEY",
        "key_field": "minimax_key_enc",
        "models": [
            "minimax/minimax-m3",
            "minimax/minimax-m2.5",
        ],
    },
    "nvidia_nim": {
        "label": "NVIDIA NIM (Nemotron)",
        "env": "NVIDIA_NIM_API_KEY",
        "key_field": "nvidia_nim_key_enc",
        "models": [
            "nvidia_nim/nvidia/nemotron-3-ultra-550b",
        ],
    },
    "openrouter": {
        "label": "OpenRouter (any model, one key)",
        "env": "OPENROUTER_API_KEY",
        "key_field": "openrouter_key_enc",
        "models": [
            "openrouter/openai/gpt-5.6-sol",
            "openrouter/meta/muse-spark-1.1",
            "openrouter/x-ai/grok-4.5",
            "openrouter/z-ai/glm-5.2",
            "openrouter/z-ai/glm-5.1",
            "openrouter/moonshotai/kimi-k2.7",
            "openrouter/moonshotai/kimi-k2.6",
            "openrouter/qwen/qwen3-max",
            "openrouter/minimax/minimax-m3",
            "openrouter/nvidia/nemotron-3-ultra",
            "openrouter/openai/gpt-5.5",
            "openrouter/auto",
        ],
    },
    "ollama": {
        "label": "Ollama (local, free)",
        "env": None,
        "key_field": None,
        "models": [
            "ollama/llama3.1",
            "ollama/llama3",
            "ollama/mistral",
            "ollama/qwen2",
            "ollama/gemma2",
            "ollama/phi3",
        ],
    },
}

# Providers added by the fleet registry (beyond Aura's original big three +
# openrouter) — used by env injection so legacy paths stay untouched.
EXTENDED_PROVIDERS = ("meta", "xai", "zai", "moonshot", "dashscope", "minimax", "nvidia_nim")


def custom_models(settings) -> list:
    """Parse the user's custom model list from settings.custom_models."""
    raw = getattr(settings, "custom_models", None) if settings else None
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(m).strip() for m in parsed if str(m).strip()]
    except (ValueError, TypeError):
        pass
    # Fall back to comma separated plain text
    return [m.strip() for m in str(raw).split(",") if m.strip()]


def all_models(settings=None) -> list:
    """Every model in the fleet, providers in registry order, then custom."""
    models = []
    for provider in PROVIDERS.values():
        models.extend(provider["models"])
    for m in custom_models(settings):
        if m not in models:
            models.append(m)
    return models


def provider_for_model(model_id: str) -> Optional[str]:
    """Resolve the provider key for a model ID via its route prefix."""
    if not model_id:
        return None
    prefix = model_id.split("/", 1)[0]
    if prefix in PROVIDERS:
        return prefix
    if model_id.startswith(("claude", "gpt")):
        return "anthropic" if model_id.startswith("claude") else "openai"
    if model_id.startswith("gemini-"):
        return "gemini"
    return None


def inject_extended_provider_env(settings, key_vault) -> None:
    """
    Decrypt and export API keys for the extended provider fleet so LiteLLM
    can route to them. The original providers (anthropic/openai/gemini/
    openrouter) keep their existing auth-mode-aware injection paths.
    """
    import os

    if not settings or not key_vault:
        return
    for name in EXTENDED_PROVIDERS:
        provider = PROVIDERS[name]
        enc = getattr(settings, provider["key_field"], "") or ""
        if not enc:
            continue
        try:
            key = key_vault.decrypt(enc)
            if key:
                os.environ[provider["env"]] = key
        except Exception as e:
            logger.warning(f"Key injection failed for {name}: {e}")