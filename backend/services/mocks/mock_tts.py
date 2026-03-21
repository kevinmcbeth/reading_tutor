"""Mock TTS service — writes minimal WAV silence without GPU."""

import asyncio
import struct
from pathlib import Path


def _minimal_wav(duration_ms: int = 100) -> bytes:
    """Generate a silent WAV file."""
    sample_rate = 16000
    num_samples = sample_rate * duration_ms // 1000
    data = b"\x00\x00" * num_samples  # 16-bit silence

    data_size = len(data)
    fmt_chunk = struct.pack("<HHIIHH", 1, 1, sample_rate, sample_rate * 2, 2, 16)

    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", 16)
        + fmt_chunk
        + b"data"
        + struct.pack("<I", data_size)
        + data
    )


async def generate_word_audio_async(word: str, output_path: str) -> bool:
    await asyncio.sleep(0.01)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(_minimal_wav(200))
    return True


async def generate_sentence_audio_async(sentence: str, output_path: str) -> bool:
    await asyncio.sleep(0.01)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(_minimal_wav(1000))
    return True


async def unload_tts_async() -> None:
    await asyncio.sleep(0.01)
