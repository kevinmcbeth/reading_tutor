"""Mock Whisper service — returns deterministic transcription without GPU."""

import asyncio


async def transcribe_async(
    audio_bytes: bytes, target_word: str | None = None
) -> dict:
    await asyncio.sleep(0.01)
    transcript = target_word or "hello"
    return {
        "transcript": transcript,
        "alternatives": [
            {"text": transcript, "probability": 0.85},
            {"text": "help", "probability": 0.10},
            {"text": "held", "probability": 0.05},
        ],
        "confidence": 0.85,
    }
