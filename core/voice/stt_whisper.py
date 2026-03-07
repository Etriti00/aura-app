"""
Aura — Whisper STT Provider
Speech-to-text using faster-whisper (local) or OpenAI Whisper API.
"""

import io
import tempfile

from utils.logger import get_logger

logger = get_logger("stt_whisper")

# Try local faster-whisper first
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.info("faster-whisper not installed — local STT unavailable")

# OpenAI API fallback
try:
    from openai import OpenAI
    OPENAI_STT_AVAILABLE = True
except ImportError:
    OPENAI_STT_AVAILABLE = False


class WhisperSTT:
    """Speech-to-text using local faster-whisper or OpenAI Whisper API."""

    def __init__(self, mode: str = "local", api_key: str = "",
                 model_size: str = "base"):
        self._mode = mode  # "local" or "api"
        self._local_model = None
        self._openai_client = None

        if mode == "local" and FASTER_WHISPER_AVAILABLE:
            try:
                self._local_model = WhisperModel(
                    model_size, device="cpu", compute_type="int8"
                )
                logger.info(f"Whisper local model loaded: {model_size}")
            except Exception as e:
                logger.warning(f"Failed to load local Whisper model: {e}")

        if mode == "api" and api_key and OPENAI_STT_AVAILABLE:
            try:
                self._openai_client = OpenAI(api_key=api_key)
            except Exception as e:
                logger.warning(f"Failed to init OpenAI STT client: {e}")

    @property
    def is_available(self) -> bool:
        if self._mode == "local":
            return self._local_model is not None
        return self._openai_client is not None

    def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes to text."""
        if self._mode == "local":
            return self._transcribe_local(audio_bytes)
        return self._transcribe_api(audio_bytes)

    def _transcribe_local(self, audio_bytes: bytes) -> str:
        """Transcribe using local faster-whisper."""
        if not self._local_model:
            return ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                f.flush()
                segments, _ = self._local_model.transcribe(f.name, beam_size=5)
                text_parts = [segment.text for segment in segments]
                return " ".join(text_parts).strip()
        except Exception as e:
            logger.error(f"Local Whisper transcribe failed: {e}")
            return ""

    def _transcribe_api(self, audio_bytes: bytes) -> str:
        """Transcribe using OpenAI Whisper API."""
        if not self._openai_client:
            return ""
        try:
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "audio.wav"
            transcript = self._openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
            return transcript.text.strip()
        except Exception as e:
            logger.error(f"OpenAI Whisper transcribe failed: {e}")
            return ""

    def transcribe_stream(self, audio_chunk: bytes):
        """Transcribe a streaming audio chunk (for real-time use)."""
        # For real-time: accumulate chunks and transcribe when VAD detects silence
        # This is a simplified version — full implementation uses VAD
        text = self.transcribe(audio_chunk)
        return text if text else None
