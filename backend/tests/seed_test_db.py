"""Seed the test database with sample data. Idempotent — truncates on re-run."""

import asyncio
import json
import os
import struct
import sys
import zlib
from datetime import datetime, timedelta
from pathlib import Path

# Ensure backend is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("ENV_FILE", str(Path(__file__).parent.parent / ".env.test"))

import asyncpg

from config import settings
from database import SCHEMA


def _minimal_png() -> bytes:
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = zlib.compress(b"\x00\xff\x00\x00")
    idat = _chunk(b"IDAT", raw)
    iend = _chunk(b"IEND", b"")
    return header + ihdr + idat + iend


def _minimal_wav() -> bytes:
    sample_rate = 16000
    num_samples = 1600  # 100ms
    data = b"\x00\x00" * num_samples
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


TRUNCATE_SQL = """
TRUNCATE session_words, sessions, generation_logs, generation_jobs,
         story_words, story_sentences, stories, children, families
CASCADE;
"""


async def seed():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        # Create schema
        await conn.execute(SCHEMA)

        # Truncate for idempotency
        await conn.execute(TRUNCATE_SQL)

        # --- Families ---
        from auth import hash_password

        f1 = await conn.fetchval(
            "INSERT INTO families (username, password_hash, display_name) "
            "VALUES ($1, $2, $3) RETURNING id",
            "testfamily1", hash_password("password123"), "Test Family One",
        )
        f2 = await conn.fetchval(
            "INSERT INTO families (username, password_hash, display_name) "
            "VALUES ($1, $2, $3) RETURNING id",
            "testfamily2", hash_password("password123"), "Test Family Two",
        )

        # --- Children ---
        c1 = await conn.fetchval(
            "INSERT INTO children (family_id, name, avatar) VALUES ($1, $2, $3) RETURNING id",
            f1, "Alice", "fox",
        )
        c2 = await conn.fetchval(
            "INSERT INTO children (family_id, name, avatar) VALUES ($1, $2, $3) RETURNING id",
            f1, "Bob", "owl",
        )
        c3 = await conn.fetchval(
            "INSERT INTO children (family_id, name, avatar) VALUES ($1, $2, $3) RETURNING id",
            f2, "Charlie", "bear",
        )

        # --- Stories (2 ready) ---
        fixture_path = Path(__file__).parent / "fixtures" / "mock_story.json"
        story_data = json.loads(fixture_path.read_text())

        data_dir = settings.data_path
        png_bytes = _minimal_png()
        wav_bytes = _minimal_wav()

        for story_num in range(1, 3):
            uuid = f"test-story-{story_num}"
            story_id = await conn.fetchval(
                "INSERT INTO stories (family_id, uuid, title, topic, difficulty, theme, style, status) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, 'ready') RETURNING id",
                f1, uuid, f"Test Story {story_num}", "animals", "easy", None, "cartoon",
            )

            # Create job record
            await conn.execute(
                "INSERT INTO generation_jobs (story_id, status, progress_pct, completed_at) "
                "VALUES ($1, 'completed', 100, $2)",
                story_id, datetime.utcnow(),
            )

            images_dir = data_dir / "stories" / uuid / "images"
            audio_dir = data_dir / "stories" / uuid / "audio"
            images_dir.mkdir(parents=True, exist_ok=True)
            audio_dir.mkdir(parents=True, exist_ok=True)

            for idx, sent in enumerate(story_data["sentences"]):
                text = sent["text"]
                challenge_indices = sent.get("challenge_words", [])

                img_path = str(images_dir / f"sentence_{idx}.png")
                Path(img_path).write_bytes(png_bytes)

                sent_audio_path = str(audio_dir / f"sentence_{idx}.wav")
                Path(sent_audio_path).write_bytes(wav_bytes)

                sentence_id = await conn.fetchval(
                    "INSERT INTO story_sentences (story_id, idx, text, image_prompt, image_path, has_image) "
                    "VALUES ($1, $2, $3, $4, $5, TRUE) RETURNING id",
                    story_id, idx, text, f"A cartoon illustration of: {text}", img_path,
                )

                words = text.split()
                for w_idx, word in enumerate(words):
                    is_challenge = w_idx in challenge_indices
                    word_audio_path = str(audio_dir / f"word_{sentence_id}_{w_idx}.wav")
                    Path(word_audio_path).write_bytes(wav_bytes)

                    await conn.execute(
                        "INSERT INTO story_words (sentence_id, idx, text, audio_path, has_audio, is_challenge_word) "
                        "VALUES ($1, $2, $3, $4, TRUE, $5)",
                        sentence_id, w_idx, word, word_audio_path, is_challenge,
                    )

        # --- Completed session for child 1, story 1 ---
        # Get story 1 info
        story1 = await conn.fetchrow("SELECT id FROM stories ORDER BY id LIMIT 1")
        story1_words = await conn.fetch(
            """SELECT sw.id FROM story_words sw
               JOIN story_sentences ss ON sw.sentence_id = ss.id
               WHERE ss.story_id = $1
               ORDER BY ss.idx, sw.idx""",
            story1["id"],
        )

        session_id = await conn.fetchval(
            "INSERT INTO sessions (child_id, story_id, attempt_number, score, total_words, completed_at) "
            "VALUES ($1, $2, 1, $3, $4, $5) RETURNING id",
            c1, story1["id"], len(story1_words), len(story1_words),
            datetime.utcnow() - timedelta(hours=1),
        )

        for w in story1_words:
            await conn.execute(
                "INSERT INTO session_words (session_id, word_id, attempts, correct) "
                "VALUES ($1, $2, 1, TRUE)",
                session_id, w["id"],
            )

        print(f"Seeded: 2 families, 3 children, 2 stories, 1 session")
        print(f"  Family 1: id={f1}, username=testfamily1, children: Alice(id={c1}), Bob(id={c2})")
        print(f"  Family 2: id={f2}, username=testfamily2, children: Charlie(id={c3})")
        print(f"  Data dir: {data_dir}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
