"""Mock ComfyUI client — writes a minimal valid PNG without GPU."""

import asyncio
import struct
import zlib
from pathlib import Path


def _minimal_png() -> bytes:
    """Generate a 1x1 red pixel PNG."""

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = zlib.compress(b"\x00\xff\x00\x00")  # filter byte + RGB
    idat = _chunk(b"IDAT", raw)
    iend = _chunk(b"IEND", b"")
    return header + ihdr + idat + iend


async def generate_image(
    prompt: str,
    negative_prompt: str,
    output_path: str,
    width: int = 1024,
    height: int = 768,
) -> bool:
    await asyncio.sleep(0.02)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(_minimal_png())
    return True
