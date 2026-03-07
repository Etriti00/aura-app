"""
Aura — OpenAI TTS Provider
Secondary text-to-speech via OpenAI's TTS API.
"""

from utils.logger import get_logger

logger = get_logger("tts_openai")

try:
    from openai import OpenAI
    OPENAI_TTS_AVAILABLE = True
except ImportError:
    OPENAI_TTS_AVAILABLE = False
    logger.info("openai not installed — OpenAI TTS unavailable")


class OpenAITTS:
    """OpenAI text-to-speech with multiple voice options."""

    VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    def __init__(self, api_key: str = "", voice: str = "nova"):
        self._api_key = api_key
        self._voice = voice if voice in self.VOICES else "nova"
        self._client = None
        if api_key and OPENAI_TTS_AVAILABLE:
            try:
                self._client = OpenAI(api_key=api_key)
            except Exception as e:
                logger.warning(f"Failed to init OpenAI client: {e}")

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def synthesize(self, text: str) -> bytes:
        """Convert text to speech, return audio bytes (mp3)."""
        if not self.is_available:
            return b""
        try:
            response = self._client.audio.speech.create(
                model="tts-1",
                voice=self._voice,
                input=text,
                response_format="mp3",
            )
            return response.content
        except Exception as e:
            logger.error(f"OpenAI TTS synthesize failed: {e}")
            return b""

    def synthesize_pcm(self, text: str, sample_rate: int = 8000) -> bytes:
        """Generate PCM audio for Twilio."""
        if not self.is_available:
            return b""
        try:
            response = self._client.audio.speech.create(
                model="tts-1",
                voice=self._voice,
                input=text,
                response_format="pcm",
            )
            return response.content
        except Exception as e:
            logger.error(f"OpenAI TTS PCM synthesize failed: {e}")
            return b""
