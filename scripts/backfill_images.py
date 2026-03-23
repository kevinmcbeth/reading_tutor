#!/usr/bin/env python3
"""Backfill missing images for stories that should have them.

Handles both 'ready' stories missing images and 'text_generated' stories
that need images + audio to become ready.

Usage:
    python scripts/backfill_images.py              # All levels, all stories
    python scripts/backfill_images.py --levels A B  # Specific levels
    python scripts/backfill_images.py --dry-run     # Preview
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Use worktree backend (has the fixed _normalize_image_prompts)
WORKTREE_BACKEND = str(Path(__file__).resolve().parent.parent / "backend")
sys.path.insert(0, WORKTREE_BACKEND)

# Write data to production dir, not the worktree
import os
os.environ.setdefault("DATA_DIR", "/opt/reading-tutor/backend/data")

from config import settings
from database import init_db, close_db, get_pool
from services import comfyui_client, tts_service


def _normalize_image_prompts(raw, num_sentences):
    """Normalize LLM image prompt responses into a consistent list of dicts."""
    if isinstance(raw, dict):
        if "prompts" in raw:
            raw = raw["prompts"]
        elif "image_prompt" in raw:
            raw = [raw]
        else:
            raw = list(raw.values()) if raw else []

    if not isinstance(raw, list):
        return []

    normalized = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            if "sentence_index" not in item:
                item["sentence_index"] = i
            normalized.append(item)
        elif isinstance(item, str):
            normalized.append({
                "sentence_index": i,
                "image_prompt": item,
                "negative_prompt": "",
            })
        elif isinstance(item, list):
            normalized.append({
                "sentence_index": i,
                "image_prompt": item[0] if len(item) > 0 else "",
                "negative_prompt": item[1] if len(item) > 1 else "",
            })
    return normalized


async def backfill_story_images(pool, story_row, level_row, is_local):
    """Generate missing images for a single story."""
    story_id = story_row["id"]
    story_uuid = story_row["uuid"]
    title = story_row["title"]
    style = story_row["style"] or "cartoon"
    image_support = level_row.get("image_support", "heavy")

    sentence_records = [
        dict(r) for r in await pool.fetch(
            "SELECT * FROM story_sentences WHERE story_id = $1 ORDER BY idx", story_id
        )
    ]
    if not sentence_records:
        print(f"    SKIP: no sentences")
        return False

    # Check which sentences need image prompts
    missing_prompts = [sr for sr in sentence_records if not sr.get("image_prompt")]

    if missing_prompts:
        try:
            from services import ollama_client
            story_text = " ".join(sr["text"] for sr in sentence_records)
            raw = await ollama_client.generate_fp_image_prompts(
                story_text,
                style,
                [{"text": sr["text"]} for sr in sentence_records],
                image_support or "heavy",
            )
            image_prompts = _normalize_image_prompts(raw, len(sentence_records))

            saved = 0
            for ip in image_prompts:
                s_idx = ip.get("sentence_index", 0)
                if s_idx < len(sentence_records) and not sentence_records[s_idx].get("image_prompt"):
                    sid = sentence_records[s_idx]["id"]
                    await pool.execute(
                        "UPDATE story_sentences SET image_prompt = $1, negative_prompt = $2 "
                        "WHERE id = $3",
                        ip.get("image_prompt", ""),
                        ip.get("negative_prompt", ""),
                        sid,
                    )
                    saved += 1
            print(f"    Image prompts: {saved} new")

            if is_local and not settings.USE_MOCK_SERVICES:
                from services.story_pipeline import _unload_ollama_model
                await _unload_ollama_model()

        except Exception as exc:
            print(f"    WARNING: Image prompt generation failed: {exc}")
            return False

    # Reload sentences with updated prompts
    sentence_records = [
        dict(r) for r in await pool.fetch(
            "SELECT * FROM story_sentences WHERE story_id = $1 ORDER BY idx", story_id
        )
    ]

    # Generate missing images
    images_dir = Path(settings.data_path) / "stories" / story_uuid / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    for sr in sentence_records:
        if sr.get("has_image"):
            continue
        if not sr.get("image_prompt"):
            continue

        img_path = str(images_dir / f"sentence_{sr['idx']}.png")
        success = await comfyui_client.generate_image(
            prompt=sr["image_prompt"],
            negative_prompt=sr.get("negative_prompt", ""),
            output_path=img_path,
        )
        if success:
            await pool.execute(
                "UPDATE story_sentences SET image_path = $1, has_image = TRUE WHERE id = $2",
                img_path, sr["id"],
            )
            generated += 1
        else:
            print(f"    WARNING: Image failed for sentence {sr['idx']}")

    print(f"    Images: {generated} generated")
    return generated > 0


async def finish_stuck_story(pool, story_row, level_row, is_local):
    """For text_generated stories: generate images + audio, then mark ready."""
    story_id = story_row["id"]
    story_uuid = story_row["uuid"]
    title = story_row["title"]

    # First do images
    await backfill_story_images(pool, story_row, level_row, is_local)

    # Then audio
    sentence_records = [
        dict(r) for r in await pool.fetch(
            "SELECT * FROM story_sentences WHERE story_id = $1 ORDER BY idx", story_id
        )
    ]

    audio_dir = Path(settings.data_path) / "stories" / story_uuid / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    all_words = []
    for sr in sentence_records:
        rows = await pool.fetch(
            "SELECT * FROM story_words WHERE sentence_id = $1 ORDER BY idx", sr["id"],
        )
        all_words.extend(rows)

    audio_count = 0
    for word_row in all_words:
        if word_row.get("has_audio"):
            continue
        word_path = str(audio_dir / f"word_{word_row['id']}.wav")
        success = await tts_service.generate_word_audio_async(word_row["text"], word_path)
        if success:
            await pool.execute(
                "UPDATE story_words SET audio_path = $1, has_audio = TRUE WHERE id = $2",
                word_path, word_row["id"],
            )
            audio_count += 1

    for sr in sentence_records:
        sent_path = str(audio_dir / f"sentence_{sr['idx']}.wav")
        if Path(sent_path).exists():
            continue
        await tts_service.generate_sentence_audio_async(sr["text"], sent_path)
        audio_count += 1

    print(f"    Audio: {audio_count} generated")

    await pool.execute("UPDATE stories SET status = 'ready' WHERE id = $1", story_id)
    print(f"    -> READY")


async def main():
    parser = argparse.ArgumentParser(description="Backfill missing images")
    parser.add_argument("--levels", nargs="+", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    await init_db()
    pool = get_pool()

    is_local = (
        settings.LLM_BACKEND == "ollama"
        and settings.TTS_BACKEND == "local"
        and settings.STORAGE_BACKEND == "local"
    )

    try:
        # Get level definitions
        levels_cache = {}
        for row in await pool.fetch("SELECT * FROM fp_levels ORDER BY sort_order"):
            levels_cache[row["level"]] = row

        # Find all stories needing work
        query = """
            SELECT s.*,
                   (SELECT count(*) FROM story_sentences ss WHERE ss.story_id = s.id) as sentence_count,
                   (SELECT count(*) FROM story_sentences ss WHERE ss.story_id = s.id AND ss.has_image) as image_count
            FROM stories s
            WHERE s.fp_level IS NOT NULL
              AND s.status IN ('ready', 'text_generated')
        """
        params = []
        if args.levels:
            query += " AND s.fp_level = ANY($1::text[])"
            params.append(args.levels)
        query += " ORDER BY (SELECT sort_order FROM fp_levels WHERE level = s.fp_level), s.id"

        stories = await pool.fetch(query, *params)

        # Filter to stories that need images or are stuck
        work = []
        for s in stories:
            level_row = levels_cache.get(s["fp_level"])
            if not level_row:
                continue
            needs_images = level_row["generate_images"] and s["image_count"] < s["sentence_count"]
            is_stuck = s["status"] == "text_generated"
            if needs_images or is_stuck:
                work.append((s, level_row, needs_images, is_stuck))

        print(f"Found {len(work)} stories needing work")
        if args.dry_run:
            for s, lr, ni, ist in work:
                tag = "STUCK+IMAGES" if ist and ni else "STUCK" if ist else "IMAGES"
                print(f"  [{tag}] Level {s['fp_level']:3s} | {s['title']} ({s['image_count']}/{s['sentence_count']} images)")
            return

        # Start ComfyUI for image gen
        if is_local and not settings.USE_MOCK_SERVICES:
            from services.story_pipeline import _manage_comfyui
            print("Starting ComfyUI...")
            await _manage_comfyui("start")

        completed = 0
        for i, (s, level_row, needs_images, is_stuck) in enumerate(work):
            print(f"  [{i+1}/{len(work)}] Level {s['fp_level']} | {s['title']} ({s['image_count']}/{s['sentence_count']} images)")
            try:
                if is_stuck:
                    await finish_stuck_story(pool, s, level_row, is_local)
                else:
                    await backfill_story_images(pool, s, level_row, is_local)
                completed += 1
            except Exception as exc:
                print(f"    ERROR: {exc}")

        if is_local and not settings.USE_MOCK_SERVICES:
            from services.story_pipeline import _manage_comfyui
            await _manage_comfyui("stop")
            await tts_service.unload_tts_async()

        print(f"\nCompleted {completed}/{len(work)} stories")

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
