#!/usr/bin/env python3
"""Resume stories stuck in 'text_generated' status by running remaining pipeline stages.

Stories get stuck when the image/audio generation batch is interrupted.
This script picks up where it left off: generates image prompts, images, audio,
then marks the story as 'ready'.

Usage:
    python scripts/resume_stuck_stories.py                   # All stuck stories
    python scripts/resume_stuck_stories.py --levels H I      # Specific levels only
    python scripts/resume_stuck_stories.py --dry-run         # Preview what would run
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config import settings
from database import init_db, close_db, get_pool
from services import comfyui_client, tts_service
from services.story_pipeline import _is_local_mode


async def resume_story(pool, story_row, level_row):
    """Resume image + audio generation for a single stuck story."""
    story_id = story_row["id"]
    story_uuid = story_row["uuid"]
    fp_level = story_row["fp_level"]
    title = story_row["title"]
    style = story_row["style"] or "cartoon"
    generate_images = level_row["generate_images"]
    image_support = level_row.get("image_support", "none")
    is_local = _is_local_mode()

    sentence_records = [
        dict(r) for r in await pool.fetch(
            "SELECT * FROM story_sentences WHERE story_id = $1 ORDER BY idx", story_id
        )
    ]
    if not sentence_records:
        print(f"  SKIP {title} (id={story_id}): no sentences found")
        return False

    # --- Stage 2: Generate image prompts (if needed) ---
    missing_prompts = generate_images and any(
        not sr.get("image_prompt") for sr in sentence_records
    )

    if missing_prompts:
        try:
            from services import ollama_client
            from services.story_pipeline import _normalize_image_prompts
            story_text = " ".join(sr["text"] for sr in sentence_records)
            image_prompts = await ollama_client.generate_fp_image_prompts(
                story_text,
                style,
                [{"text": sr["text"]} for sr in sentence_records],
                image_support or "heavy",
            )
            image_prompts = _normalize_image_prompts(image_prompts, len(sentence_records))

            for ip in image_prompts:
                s_idx = ip.get("sentence_index", 0)
                if s_idx < len(sentence_records):
                    sid = sentence_records[s_idx]["id"]
                    await pool.execute(
                        "UPDATE story_sentences SET image_prompt = $1, negative_prompt = $2 "
                        "WHERE id = $3",
                        ip.get("image_prompt", ""),
                        ip.get("negative_prompt", ""),
                        sid,
                    )
            print(f"    Generated {len(image_prompts)} image prompts")

            if is_local and not settings.USE_MOCK_SERVICES:
                from services.story_pipeline import _unload_ollama_model
                await _unload_ollama_model()

        except Exception as exc:
            print(f"    WARNING: Image prompt generation failed: {exc}")

    # Reload sentence records (may have updated image_prompt)
    sentence_records = [
        dict(r) for r in await pool.fetch(
            "SELECT * FROM story_sentences WHERE story_id = $1 ORDER BY idx", story_id
        )
    ]

    # --- Stage 3: Generate images ---
    if generate_images:
        images_dir = Path(settings.data_path) / "stories" / story_uuid / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

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
                    "UPDATE story_sentences SET image_path = $1, has_image = TRUE "
                    "WHERE id = $2",
                    img_path, sr["id"],
                )
                print(f"    Image generated for sentence {sr['idx']}")
            else:
                print(f"    WARNING: Image failed for sentence {sr['idx']}")

    # --- Stage 4: Generate audio ---
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
        success = await tts_service.generate_sentence_audio_async(sr["text"], sent_path)
        if success:
            audio_count += 1

    print(f"    Generated {audio_count} audio files")

    # --- Mark ready ---
    await pool.execute(
        "UPDATE stories SET status = 'ready' WHERE id = $1", story_id
    )
    print(f"    -> READY")
    return True


async def main():
    parser = argparse.ArgumentParser(description="Resume stuck stories")
    parser.add_argument("--levels", nargs="+", default=None, help="Only resume specific levels")
    parser.add_argument("--dry-run", action="store_true", help="Just show what would be resumed")
    args = parser.parse_args()

    await init_db()
    pool = get_pool()

    try:
        query = "SELECT * FROM stories WHERE status = 'text_generated'"
        params = []
        if args.levels:
            query += " AND fp_level = ANY($1::text[])"
            params.append(args.levels)
        query += " ORDER BY fp_level, id"

        stories = await pool.fetch(query, *params)
        print(f"Found {len(stories)} stuck stories")

        if args.dry_run:
            for s in stories:
                print(f"  Level {s['fp_level']:3s} | {s['title']} (id={s['id']})")
            return

        # Cache level definitions
        levels_cache = {}
        for row in await pool.fetch("SELECT * FROM fp_levels"):
            levels_cache[row["level"]] = row

        is_local = _is_local_mode()

        # Start ComfyUI if needed for image generation
        if is_local and not settings.USE_MOCK_SERVICES:
            any_needs_images = any(
                levels_cache.get(s["fp_level"], {}).get("generate_images")
                for s in stories
            )
            if any_needs_images:
                from services.story_pipeline import _manage_comfyui
                print("Starting ComfyUI...")
                await _manage_comfyui("start")

        completed = 0
        for s in stories:
            level_row = levels_cache.get(s["fp_level"])
            if not level_row:
                print(f"  SKIP {s['title']}: unknown level {s['fp_level']}")
                continue

            print(f"  [{completed+1}/{len(stories)}] Level {s['fp_level']} | {s['title']}")
            try:
                if await resume_story(pool, s, level_row):
                    completed += 1
            except Exception as exc:
                print(f"    ERROR: {exc}")
                # Mark failed so it doesn't get retried endlessly
                await pool.execute(
                    "UPDATE stories SET status = 'failed' WHERE id = $1", s["id"]
                )

        if is_local and not settings.USE_MOCK_SERVICES:
            from services.story_pipeline import _manage_comfyui
            await _manage_comfyui("stop")
            await tts_service.unload_tts_async()

        print(f"\nCompleted {completed}/{len(stories)} stories")

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
