"""
Aura — ElevenLabs TTS Provider
Primary text-to-speech — best quality, streaming support.
"""

from utils.logger import get_logger

logger = get_logger("tts_elevenlabs")

try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import stream as elevenlabs_stream
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    logger.info("elevenlabs not installed — ElevenLabs TTS unavailable")


class ElevenLabsTTS:
    """ElevenLabs text-to-speech with streaming support."""

    def __init__(self, api_key: str = "", voice_id: str = ""):
        self._api_key = api_key
        self._voice_id = voice_id or "21m00Tcm4TlvDq8ikWAM"  # Default: Rachel
        self._client = None
        if api_key and ELEVENLABS_AVAILABLE:
            try:
                self._client = ElevenLabs(api_key=api_key)
            except Exception as e:
                logger.warning(f"Failed to init ElevenLabs client: {e}")

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def synthesize(self, text: str) -> bytes:
        """Convert text to speech, return audio bytes (mp3)."""
        if not self.is_available:
            return b""
        try:
            audio = self._client.generate(
                text=text,
                voice=self._voice_id,
                model="eleven_turbo_v2_5",
            )
            # audio is a generator — collect all chunks
            chunks = []
            for chunk in audio:
                if isinstance(chunk, bytes):
                    chunks.append(chunk)
            return b"".join(chunks)
        except Exception as e:
            logger.error(f"ElevenLabs synthesize failed: {e}")
            return b""

    def synthesize_stream(self, text: str):
        """Stream text-to-speech, yielding audio chunks."""
        if not self.is_available:
            return
        try:
            audio = self._client.generate(
                text=text,
                voice=self._voice_id,
                model="eleven_turbo_v2_5",
                stream=True,
            )
            for chunk in audio:
                if isinstance(chunk, bytes):
                    yield chunk
        except Exception as e:
            logger.error(f"ElevenLabs stream failed: {e}")

    def synthesize_pcm(self, text: str, sample_rate: int = 8000) -> bytes:
        """Generate PCM audio for Twilio (mulaw 8kHz)."""
        if not self.is_available:
            return b""
        try:
            audio = self._client.generate(
                text=text,
                voice=self._voice_id,
                model="eleven_turbo_v2_5",
                output_format=f"ulaw_{sample_rate}",
            )
            chunks = []
            for chunk in audio:
                if isinstance(chunk, bytes):
                    chunks.append(chunk)
            return b"".join(chunks)
        except Exception as e:
            logger.error(f"ElevenLabs PCM synthesize failed: {e}")
            return b""
