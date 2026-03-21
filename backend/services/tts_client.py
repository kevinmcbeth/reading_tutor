"""HTTP client for remote TTS microservice (F5-TTS on EKS GPU)."""

import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


async def generate_word_audio(word: str) -> bytes | None:
    """Generate audio for a single word via remote TTS service. Returns WAV bytes."""
    return await _request_tts(word, "word")


async def generate_sentence_audio(sentence: str) -> bytes | None:
    """Generate audio for a sentence via remote TTS service. Returns WAV bytes."""
    return await _request_tts(sentence, "sentence")


async def _request_tts(text: str, audio_type: str) -> bytes | None:
    """Send a TTS request to the remote service."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            resp = await client.post(
                f"{settings.TTS_URL}/generate",
                json={"text": text, "type": audio_type},
            )
            resp.raise_for_status()
            return resp.content
    except httpx.HTTPError as exc:
        logger.error("Remote TTS request failed for '%s': %s", text, exc)
        return None
    except Exception as exc:
        logger.error("Remote TTS unexpected error for '%s': %s", text, exc)
        return None
