import asyncio
import logging
import tempfile
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel

    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False
    logger.warning(
        "faster-whisper not installed. Speech recognition will be unavailable. "
        "Install with: pip install faster-whisper"
    )

_model: "WhisperModel | None" = None
_semaphore = asyncio.Semaphore(1)


def _get_model() -> "WhisperModel":
    """Lazy-load the Whisper model (singleton)."""
    global _model
    if _model is None:
        if not _WHISPER_AVAILABLE:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Install with: pip install faster-whisper"
            )
        logger.info(
            "Loading Whisper model %s on device %s",
            settings.WHISPER_MODEL,
            settings.WHISPER_DEVICE,
        )
        _model = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type="default",
        )
        logger.info("Whisper model loaded successfully")
    return _model


def transcribe(audio_bytes: bytes, target_word: str | None = None) -> dict:
    """Transcribe audio bytes and return transcript with alternatives.

    Args:
        audio_bytes: Raw audio data (WebM, WAV, etc.)
        target_word: Optional expected word to bias recognition toward.

    Returns:
        dict with keys: transcript, alternatives, confidence
    """
    model = _get_model()

    # Write audio to a temp file since faster-whisper needs a file path
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    try:
        tmp.write(audio_bytes)
        tmp.close()

        kwargs: dict = {
            "language": "en",
            "beam_size": 5,
            "best_of": 3,
            "temperature": [0.0, 0.2, 0.4],
            "word_timestamps": False,
            "vad_filter": True,
        }
        if target_word:
            kwargs["initial_prompt"] = (
                f"The child is reading the word: {target_word}"
            )

        segments, info = model.transcribe(str(tmp_path), **kwargs)

        # Collect all segment texts
        texts: list[str] = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                texts.append(text)

        transcript = " ".join(texts).strip() if texts else ""

        # Build alternatives from individual segments (deduplicated, preserving order)
        seen: set[str] = set()
        alternatives: list[str] = []
        for t in texts:
            low = t.lower()
            if low not in seen:
                seen.add(low)
                alternatives.append(t)

        # Use the language probability as a confidence proxy
        confidence = round(info.language_probability, 4) if info else 0.0

        return {
            "transcript": transcript,
            "alternatives": alternatives,
            "confidence": confidence,
        }
    finally:
        tmp_path.unlink(missing_ok=True)


async def transcribe_async(
    audio_bytes: bytes, target_word: str | None = None
) -> dict:
    """Async wrapper for transcribe that offloads to a thread with GPU semaphore."""
    async with _semaphore:
        return await asyncio.to_thread(transcribe, audio_bytes, target_word)
