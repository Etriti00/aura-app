"""
Aura — CLI LLM Transport
Shared subprocess helpers that route LLM calls through official provider
CLIs when the user authenticates with a subscription instead of an API key:

  - Anthropic  → `claude` (Claude Code CLI, `claude login`)
  - Google     → `gemini` (Gemini CLI, `gemini auth login`)
  - OpenAI     → `codex`  (Codex CLI, `codex login` with a ChatGPT account)

All helpers take a LiteLLM-style message list and model name, return the
response text, or None on any failure (callers fall back / surface errors).
"""

import os
import shutil
import subprocess
import tempfile
from typing import Optional

from utils.logger import get_logger

logger = get_logger("cli_llm")

CLI_TIMEOUT_S = 120


def _resolve_cli(name: str) -> Optional[str]:
    """
    Resolve a CLI name to a launchable path. On Windows, npm installs
    CLIs as .cmd shims which bare subprocess argv[0] lookup cannot find
    (CreateProcess only appends .exe) — shutil.which honours PATHEXT.
    """
    return shutil.which(name)

# Map LiteLLM model names → Claude CLI aliases
CLAUDE_CLI_MODEL_MAP = {
    "anthropic/claude-sonnet-4-6": "sonnet",
    "anthropic/claude-sonnet-4-5": "sonnet",
    "anthropic/claude-haiku-4-5": "haiku",
    "anthropic/claude-opus-4-6": "opus",
    "claude-sonnet-4-6": "sonnet",
    "claude-sonnet-4-5": "sonnet",
    "claude-haiku-4-5": "haiku",
    "claude-opus-4-6": "opus",
}


def _split_messages(messages: list) -> tuple:
    """Split a message list into (system_text, prompt_text)."""
    system_parts, parts = [], []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(content)
        else:
            parts.append(content)
    return "\n\n".join(system_parts), "\n\n".join(parts)


def claude_cli_available() -> bool:
    return shutil.which("claude") is not None


def gemini_cli_available() -> bool:
    return shutil.which("gemini") is not None


def codex_cli_available() -> bool:
    return shutil.which("codex") is not None


def call_claude_cli(messages: list, model: str) -> Optional[str]:
    """Route an LLM call through the Claude Code CLI (subscription mode)."""
    exe = _resolve_cli("claude")
    if not exe:
        logger.error("claude CLI not found — install Claude Code and run 'claude login'")
        return None

    system_text, prompt_text = _split_messages(messages)
    # Prompt goes via stdin: long prompts overflow the ~8K cmd.exe argv
    # limit that npm .cmd shims are subject to on Windows.
    full_prompt = (
        f"[Instructions]\n{system_text}\n\n{prompt_text}" if system_text else prompt_text
    )
    cli_model = CLAUDE_CLI_MODEL_MAP.get(model, "sonnet")

    cmd = [
        exe, "-p",
        "--model", cli_model,
        "--output-format", "text",
        "--no-session-persistence",
    ]

    try:
        logger.debug(f"Claude CLI call: model={cli_model}, prompt_len={len(full_prompt)}")
        result = subprocess.run(
            cmd, input=full_prompt, capture_output=True, text=True,
            timeout=CLI_TIMEOUT_S,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        stderr = result.stderr.strip()
        if stderr:
            logger.error(f"claude CLI error: {stderr}")
        elif result.returncode != 0:
            logger.error(f"claude CLI exited with code {result.returncode}")
        return None
    except FileNotFoundError:
        logger.error("claude CLI not found — install Claude Code and run 'claude login'")
        return None
    except subprocess.TimeoutExpired:
        logger.error(f"claude CLI timed out after {CLI_TIMEOUT_S}s")
        return None
    except Exception as e:
        logger.error(f"claude CLI call failed: {e}")
        return None


def call_gemini_cli(messages: list, model: str) -> Optional[str]:
    """Route an LLM call through the Gemini CLI (subscription mode)."""
    system_text, prompt_text = _split_messages(messages)
    full_prompt = f"[Instructions]\n{system_text}\n\n{prompt_text}" if system_text else prompt_text

    # Strip "gemini/" prefix — the CLI takes bare model names
    cli_model = model.removeprefix("gemini/") if model.startswith("gemini/") else model

    try:
        logger.debug(f"Gemini CLI call: model={cli_model}, prompt_len={len(full_prompt)}")
        exe = _resolve_cli("gemini")
        if not exe:
            raise FileNotFoundError
        result = subprocess.run(
            [exe, "--model", cli_model, "--yolo"],
            input=full_prompt, capture_output=True, text=True,
            timeout=CLI_TIMEOUT_S,
            env={**os.environ, "GOOGLE_API_KEY": "", "GEMINI_API_KEY": ""},
        )
        if result.returncode == 0:
            return result.stdout.strip()
        logger.error(f"gemini CLI error: {result.stderr.strip()}")
        return None
    except FileNotFoundError:
        logger.error("gemini CLI not found — install it and run 'gemini auth login'")
        return None
    except subprocess.TimeoutExpired:
        logger.error(f"gemini CLI timed out after {CLI_TIMEOUT_S}s")
        return None
    except Exception as e:
        logger.error(f"gemini CLI call failed: {e}")
        return None


def call_codex_cli(messages: list, model: str) -> Optional[str]:
    """
    Route an LLM call through the OpenAI Codex CLI (ChatGPT subscription mode).
    Requires `codex` to be installed (npm install -g @openai/codex) and
    authenticated via 'codex login' with a ChatGPT Plus/Pro account.
    """
    system_text, prompt_text = _split_messages(messages)
    full_prompt = f"[Instructions]\n{system_text}\n\n{prompt_text}" if system_text else prompt_text

    # Strip "openai/" prefix — the CLI takes bare model names
    cli_model = model.removeprefix("openai/") if model.startswith("openai/") else model

    # codex exec writes agent chatter to stdout; --output-last-message gives
    # us just the final response text in a file.
    out_path = None
    try:
        fd, out_path = tempfile.mkstemp(prefix="aura_codex_", suffix=".txt")
        os.close(fd)
        exe = _resolve_cli("codex")
        if not exe:
            raise FileNotFoundError
        cmd = [
            exe, "exec",
            "--skip-git-repo-check",
            "--sandbox", "read-only",
            "--color", "never",
            "--model", cli_model,
            "--output-last-message", out_path,
            "-",
        ]
        logger.debug(f"Codex CLI call: model={cli_model}, prompt_len={len(full_prompt)}")
        result = subprocess.run(
            cmd, input=full_prompt, capture_output=True, text=True,
            timeout=CLI_TIMEOUT_S,
        )
        if result.returncode == 0:
            try:
                with open(out_path, encoding="utf-8") as f:
                    text = f.read().strip()
                if text:
                    return text
            except OSError:
                pass
            # Fallback: some codex versions only print to stdout
            if result.stdout.strip():
                return result.stdout.strip()
            logger.error("codex CLI returned no output")
            return None
        stderr = result.stderr.strip()
        logger.error(f"codex CLI error: {stderr or f'exit code {result.returncode}'}")
        return None
    except FileNotFoundError:
        logger.error(
            "codex CLI not found — install with 'npm install -g @openai/codex' "
            "and run 'codex login' (sign in with your ChatGPT account)"
        )
        return None
    except subprocess.TimeoutExpired:
        logger.error(f"codex CLI timed out after {CLI_TIMEOUT_S}s")
        return None
    except Exception as e:
        logger.error(f"codex CLI call failed: {e}")
        return None
    finally:
        if out_path:
            try:
                os.unlink(out_path)
            except OSError:
                pass