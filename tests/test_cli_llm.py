"""
Tests for core/cli_llm.py — shared CLI subscription transports — and the
ChatGPT (Codex CLI) subscription dispatch in AIEngine.
"""

import os
from unittest.mock import MagicMock, patch

from core import cli_llm


def _fake_which(name, *args, **kwargs):
    return f"C:\\fake\\{name}.cmd"


class TestSplitMessages:
    def test_system_and_user_split(self):
        system, prompt = cli_llm._split_messages([
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hello"},
        ])
        assert system == "be brief"
        assert prompt == "hello"

    def test_multiple_messages_joined(self):
        system, prompt = cli_llm._split_messages([
            {"role": "system", "content": "a"},
            {"role": "user", "content": "b"},
            {"role": "assistant", "content": "c"},
            {"role": "user", "content": "d"},
        ])
        assert system == "a"
        assert prompt == "b\n\nc\n\nd"

    def test_no_system(self):
        system, prompt = cli_llm._split_messages([{"role": "user", "content": "x"}])
        assert system == ""
        assert prompt == "x"


class TestClaudeModelMap:
    def test_known_models_mapped(self):
        assert cli_llm.CLAUDE_CLI_MODEL_MAP["anthropic/claude-haiku-4-5"] == "haiku"
        assert cli_llm.CLAUDE_CLI_MODEL_MAP["claude-sonnet-4-6"] == "sonnet"


class TestCallCodexCli:
    def _fake_run_writes_output(self, text):
        def fake_run(cmd, **kwargs):
            idx = cmd.index("--output-last-message")
            with open(cmd[idx + 1], "w", encoding="utf-8") as f:
                f.write(text)
            m = MagicMock()
            m.returncode = 0
            m.stdout = ""
            m.stderr = ""
            return m
        return fake_run

    def test_success_reads_output_file(self):
        fake = self._fake_run_writes_output("codex says hi")
        with patch.object(cli_llm.shutil, "which", side_effect=_fake_which), \
             patch.object(cli_llm.subprocess, "run", side_effect=fake):
            out = cli_llm.call_codex_cli(
                [{"role": "user", "content": "hi"}], "openai/gpt-4.1"
            )
        assert out == "codex says hi"

    def test_strips_openai_prefix(self):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            idx = cmd.index("--output-last-message")
            with open(cmd[idx + 1], "w", encoding="utf-8") as f:
                f.write("ok")
            m = MagicMock(); m.returncode = 0; m.stdout = ""; m.stderr = ""
            return m

        with patch.object(cli_llm.shutil, "which", side_effect=_fake_which), \
             patch.object(cli_llm.subprocess, "run", side_effect=fake_run):
            cli_llm.call_codex_cli([{"role": "user", "content": "x"}], "openai/gpt-4.1")
        cmd = captured["cmd"]
        assert cmd[cmd.index("--model") + 1] == "gpt-4.1"

    def test_stdout_fallback_when_file_empty(self):
        def fake_run(cmd, **kwargs):
            m = MagicMock(); m.returncode = 0
            m.stdout = "from stdout"; m.stderr = ""
            return m

        with patch.object(cli_llm.shutil, "which", side_effect=_fake_which), \
             patch.object(cli_llm.subprocess, "run", side_effect=fake_run):
            out = cli_llm.call_codex_cli([{"role": "user", "content": "x"}], "gpt-4o")
        assert out == "from stdout"

    def test_missing_cli_returns_none(self):
        with patch.object(cli_llm.shutil, "which", side_effect=_fake_which), \
             patch.object(cli_llm.subprocess, "run", side_effect=FileNotFoundError):
            out = cli_llm.call_codex_cli([{"role": "user", "content": "x"}], "gpt-4o")
        assert out is None

    def test_nonzero_exit_returns_none(self):
        def fake_run(cmd, **kwargs):
            m = MagicMock(); m.returncode = 1
            m.stdout = ""; m.stderr = "not logged in"
            return m

        with patch.object(cli_llm.shutil, "which", side_effect=_fake_which), \
             patch.object(cli_llm.subprocess, "run", side_effect=fake_run):
            out = cli_llm.call_codex_cli([{"role": "user", "content": "x"}], "gpt-4o")
        assert out is None

    def test_temp_file_cleaned_up(self):
        paths = {}

        def fake_run(cmd, **kwargs):
            idx = cmd.index("--output-last-message")
            paths["out"] = cmd[idx + 1]
            with open(cmd[idx + 1], "w", encoding="utf-8") as f:
                f.write("ok")
            m = MagicMock(); m.returncode = 0; m.stdout = ""; m.stderr = ""
            return m

        with patch.object(cli_llm.shutil, "which", side_effect=_fake_which), \
             patch.object(cli_llm.subprocess, "run", side_effect=fake_run):
            cli_llm.call_codex_cli([{"role": "user", "content": "x"}], "gpt-4o")
        assert not os.path.exists(paths["out"])


class TestCallClaudeCli:
    def test_unknown_model_defaults_to_sonnet(self):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            m = MagicMock(); m.returncode = 0; m.stdout = "hi"; m.stderr = ""
            return m

        with patch.object(cli_llm.shutil, "which", side_effect=_fake_which), \
             patch.object(cli_llm.subprocess, "run", side_effect=fake_run):
            out = cli_llm.call_claude_cli(
                [{"role": "user", "content": "x"}], "anthropic/some-future-model"
            )
        assert out == "hi"
        cmd = captured["cmd"]
        assert cmd[cmd.index("--model") + 1] == "sonnet"

    def test_prompt_delivered_via_stdin(self):
        """Prompts go via stdin — argv overflows the Windows cmd.exe limit."""
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["input"] = kwargs.get("input")
            m = MagicMock(); m.returncode = 0; m.stdout = "hi"; m.stderr = ""
            return m

        with patch.object(cli_llm.shutil, "which", side_effect=_fake_which), \
             patch.object(cli_llm.subprocess, "run", side_effect=fake_run):
            cli_llm.call_claude_cli(
                [{"role": "system", "content": "sys"},
                 {"role": "user", "content": "x"}],
                "anthropic/claude-haiku-4-5",
            )
        assert "[Instructions]\nsys" in captured["input"]
        assert "x" in captured["input"]
        # No prompt text in argv
        assert all("sys" != part and "x" != part for part in captured["cmd"])


class TestAIEngineCodexDispatch:
    def _engine(self):
        from core.ai_engine import AIEngine
        from core.safety_guard import SafetyGuard
        engine = AIEngine.__new__(AIEngine)
        engine.safety = SafetyGuard()
        return engine

    def test_codex_mode_routes_openai_models_to_cli(self):
        from core.ai_engine import AIEngine
        engine = self._engine()
        engine._openai_sub_mode = True
        with patch.object(AIEngine, "_call_codex_cli", return_value="routed") as cli, \
             patch("litellm.completion") as lc:
            out = engine._call_llm("openai/gpt-4.1", [{"role": "user", "content": "x"}])
        assert out == "routed"
        cli.assert_called_once()
        lc.assert_not_called()

    def test_codex_mode_matches_bare_gpt_names(self):
        from core.ai_engine import AIEngine
        engine = self._engine()
        engine._openai_sub_mode = True
        with patch.object(AIEngine, "_call_codex_cli", return_value="routed"):
            out = engine._call_llm("gpt-4o", [{"role": "user", "content": "x"}])
        assert out == "routed"

    def test_default_flags_off(self):
        engine = self._engine()
        assert engine._openai_sub_mode is False
        assert engine._claude_sub_mode is False
        assert engine._gemini_sub_mode is False

    def test_configure_sets_codex_flag(self):
        from core.ai_engine import AIEngine
        engine = AIEngine()
        engine.configure({}, {}, sub_tokens={"openai_sub_cli": True})
        assert engine._openai_sub_mode is True
        engine.configure({}, {}, sub_tokens={})
        assert engine._openai_sub_mode is False

    def test_configure_never_uses_oauth_token_as_api_key(self):
        """ChatGPT OAuth tokens are not valid API keys and must not reach env."""
        from core.ai_engine import AIEngine
        os.environ.pop("OPENAI_API_KEY", None)
        engine = AIEngine()
        engine.configure({}, {}, sub_tokens={"openai_sub": "oauth-token-xyz"})
        assert os.environ.get("OPENAI_API_KEY") != "oauth-token-xyz"