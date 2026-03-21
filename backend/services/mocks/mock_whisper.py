"""Mock Whisper service — returns deterministic transcription without GPU."""

import asyncio


async def transcribe_async(
    audio_bytes: bytes, target_word: str | None = None
) -> dict:
    await asyncio.sleep(0.01)
    transcript = target_word or "hello"
    return {
        "transcript": transcript,
        "alternatives": [transcript],
        "confidence": 0.95,
    }
