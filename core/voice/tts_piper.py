"""
Aura — Piper TTS Provider
Local/offline text-to-speech using Piper (no API key required).
"""

import subprocess
import shutil

from utils.logger import get_logger

logger = get_logger("tts_piper")


class PiperTTS:
    """Local text-to-speech using Piper subprocess."""

    def __init__(self, model_path: str = ""):
        self._model_path = model_path
        self._piper_bin = shutil.which("piper") or shutil.which("piper-tts")

    @property
    def is_available(self) -> bool:
        return bool(self._piper_bin and self._model_path)

    def synthesize(self, text: str) -> bytes:
        """Convert text to speech using local Piper, return WAV bytes."""
        if not self.is_available:
            return b""
        try:
            proc = subprocess.run(
                [
                    self._piper_bin,
                    "--model", self._model_path,
                    "--output-raw",
                ],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if proc.returncode == 0:
                return proc.stdout
            logger.warning(f"Piper returned code {proc.returncode}: {proc.stderr.decode()[:200]}")
            return b""
        except subprocess.TimeoutExpired:
            logger.error("Piper TTS timed out")
            return b""
        except Exception as e:
            logger.error(f"Piper TTS failed: {e}")
            return b""

    def synthesize_pcm(self, text: str, sample_rate: int = 8000) -> bytes:
        """Generate raw PCM audio (16-bit signed, mono)."""
        if not self.is_available:
            return b""
        try:
            proc = subprocess.run(
                [
                    self._piper_bin,
                    "--model", self._model_path,
                    "--output-raw",
                    "--output_sample_rate", str(sample_rate),
                ],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if proc.returncode == 0:
                return proc.stdout
            return b""
        except Exception as e:
            logger.error(f"Piper PCM TTS failed: {e}")
            return b""
