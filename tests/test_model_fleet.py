"""Tests for the model fleet registry and the two-step model verifier."""

import os
from unittest.mock import MagicMock, patch

from core import model_fleet
from core.model_verifier import ModelVerifier


class TestFleetRegistry:
    def test_every_provider_well_formed(self):
        for name, p in model_fleet.PROVIDERS.items():
            assert p["label"]
            assert isinstance(p["models"], list) and p["models"]
            if name != "ollama":
                assert p["env"] and p["key_field"]

    def test_flagship_models_present(self):
        models = model_fleet.all_models()
        for expected in (
            "anthropic/claude-fable-5", "openai/gpt-5.5",
            "xai/grok-4.5", "zai/glm-5.2", "moonshot/kimi-k2.7",
            "dashscope/qwen3-max", "minimax/minimax-m3",
            "nvidia_nim/nvidia/nemotron-3-ultra-550b",
        ):
            assert expected in models, expected

    def test_provider_for_model(self):
        assert model_fleet.provider_for_model("xai/grok-4.5") == "xai"
        assert model_fleet.provider_for_model("moonshot/kimi-k2.6") == "moonshot"
        assert model_fleet.provider_for_model("claude-sonnet-5") == "anthropic"
        assert model_fleet.provider_for_model("ollama/llama3.1") == "ollama"
        assert model_fleet.provider_for_model("") is None

    def test_custom_models_json_and_csv(self):
        s = MagicMock()
        s.custom_models = '["acme/model-x", "acme/model-y"]'
        assert model_fleet.custom_models(s) == ["acme/model-x", "acme/model-y"]
        s.custom_models = "acme/model-x, acme/model-y"
        assert model_fleet.custom_models(s) == ["acme/model-x", "acme/model-y"]
        s.custom_models = ""
        assert model_fleet.custom_models(s) == []

    def test_all_models_merges_custom(self):
        s = MagicMock()
        s.custom_models = '["acme/model-x"]'
        models = model_fleet.all_models(s)
        assert "acme/model-x" in models
        assert models.count("acme/model-x") == 1

    def test_extended_env_injection(self):
        s = MagicMock()
        s.xai_key_enc = "enc"
        for f in ("zai_key_enc", "moonshot_key_enc", "dashscope_key_enc",
                  "minimax_key_enc", "nvidia_nim_key_enc"):
            setattr(s, f, "")
        vault = MagicMock()
        vault.decrypt.return_value = "xai-secret"
        os.environ.pop("XAI_API_KEY", None)
        model_fleet.inject_extended_provider_env(s, vault)
        assert os.environ.get("XAI_API_KEY") == "xai-secret"
        os.environ.pop("XAI_API_KEY", None)


class TestModelVerifier:
    def _verifier(self, settings=None):
        v = ModelVerifier(None, None)
        v._get_settings = lambda: settings
        return v

    def test_empty_model_id(self):
        result = self._verifier().verify("")
        assert not result["success"] and result["error"]

    def test_missing_key_fails_step_one(self):
        os.environ.pop("XAI_API_KEY", None)
        result = self._verifier().verify("xai/grok-4.5")
        assert not result["auth_ok"]
        assert "No API key configured" in result["error"]

    def test_ollama_skips_credential_gate(self):
        v = self._verifier()
        with patch.object(v, "_call", return_value=("OK", None)):
            result = v.verify("ollama/llama3.1")
        assert result["success"] and result["auth_ok"] and result["roundtrip_ok"]

    def test_roundtrip_empty_response_fails_step_two(self):
        v = self._verifier()
        with patch.object(v, "_call", return_value=("", None)):
            result = v.verify("ollama/llama3.1")
        assert result["auth_ok"] and not result["roundtrip_ok"]

    def test_auth_error_fails_step_one(self):
        v = self._verifier()
        with patch.object(v, "_call", return_value=(None, "401 Unauthorized")):
            result = v.verify("ollama/llama3.1")
        assert not result["auth_ok"]
        assert "Authentication failed" in result["error"]

    def test_subscription_mode_passes_gate(self):
        settings = MagicMock()
        settings.anthropic_auth_mode = "subscription"
        v = self._verifier(settings)
        with patch.object(v, "_call", return_value=("OK", None)):
            result = v.verify("anthropic/claude-sonnet-5")
        assert result["success"]