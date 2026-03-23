#!/usr/bin/env python3
"""Live monitor for story backfill progress.

Refreshes every few seconds showing per-level image/audio/status progress.

Usage:
    python scripts/monitor_backfill.py
    python scripts/monitor_backfill.py --interval 10
"""
import argparse
import asyncio
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "backend"))

from config import settings
from database import init_db, close_db, get_pool


def bar(done, total, width=20):
    if total == 0:
        return "░" * width
    filled = int(width * done / total)
    return "█" * filled + "░" * (width - filled)


def pct(done, total):
    if total == 0:
        return "  --%"
    return f"{done / total * 100:4.0f}%"


async def fetch_stats(pool):
    rows = await pool.fetch("""
        SELECT
            fl.level,
            fl.sort_order,
            fl.generate_images,
            count(DISTINCT s.id) AS total_stories,
            count(DISTINCT s.id) FILTER (WHERE s.status = 'ready') AS ready_stories,
            count(DISTINCT s.id) FILTER (WHERE s.status = 'text_generated') AS stuck_stories,
            count(ss.id) AS total_sentences,
            count(ss.id) FILTER (WHERE ss.has_image) AS sentences_with_images,
            count(ss.id) FILTER (WHERE ss.image_prompt IS NOT NULL AND ss.image_prompt != '') AS sentences_with_prompts,
            (SELECT count(*) FROM story_words sw
             JOIN story_sentences ss2 ON ss2.id = sw.sentence_id
             JOIN stories s2 ON s2.id = ss2.story_id
             WHERE s2.fp_level = fl.level) AS total_words,
            (SELECT count(*) FROM story_words sw
             JOIN story_sentences ss2 ON ss2.id = sw.sentence_id
             JOIN stories s2 ON s2.id = ss2.story_id
             WHERE s2.fp_level = fl.level AND sw.has_audio) AS words_with_audio
        FROM fp_levels fl
        LEFT JOIN stories s ON s.fp_level = fl.level AND s.status IN ('ready', 'text_generated')
        LEFT JOIN story_sentences ss ON ss.story_id = s.id
        GROUP BY fl.level, fl.sort_order, fl.generate_images
        ORDER BY fl.sort_order
    """)
    return rows


async def run(interval):
    await init_db()
    pool = get_pool()

    try:
        while True:
            stats = await fetch_stats(pool)
            cols = shutil.get_terminal_size((80, 24)).columns

            # Clear screen
            print("\033[2J\033[H", end="")

            now = datetime.now().strftime("%H:%M:%S")
            print(f"  Story Backfill Monitor  ·  {now}  ·  refresh {interval}s")
            print()

            # Totals
            total_stories = sum(r["total_stories"] for r in stats)
            ready_stories = sum(r["ready_stories"] for r in stats)
            total_sent = sum(r["total_sentences"] for r in stats)
            total_img = sum(r["sentences_with_images"] for r in stats)
            total_prompts = sum(r["sentences_with_prompts"] for r in stats)
            total_words = sum(r["total_words"] for r in stats)
            total_audio = sum(r["words_with_audio"] for r in stats)

            print(f"  Stories ready:  {bar(ready_stories, total_stories, 30)} {pct(ready_stories, total_stories)}  ({ready_stories}/{total_stories})")
            print(f"  Image prompts:  {bar(total_prompts, total_sent, 30)} {pct(total_prompts, total_sent)}  ({total_prompts}/{total_sent})")
            print(f"  Images done:    {bar(total_img, total_sent, 30)} {pct(total_img, total_sent)}  ({total_img}/{total_sent})")
            print(f"  Word audio:     {bar(total_audio, total_words, 30)} {pct(total_audio, total_words)}  ({total_audio}/{total_words})")
            print()

            # Header
            print(f"  {'LVL':<4} {'STATUS':<10} {'STORIES':<10} {'IMG PROMPTS':<20} {'IMAGES':<20} {'WORD AUDIO':<20}")
            print(f"  {'─'*4} {'─'*10} {'─'*10} {'─'*20} {'─'*20} {'─'*20}")

            for r in stats:
                level = r["level"]
                total = r["total_stories"]
                ready = r["ready_stories"]
                stuck = r["stuck_stories"]
                sents = r["total_sentences"]
                imgs = r["sentences_with_images"]
                prompts = r["sentences_with_prompts"]
                words = r["total_words"]
                audio = r["words_with_audio"]

                if total == 0:
                    continue

                # Status indicator
                if ready == total:
                    if imgs == sents and (audio == words or words == 0):
                        status = "\033[32m✓ done\033[0m"
                    elif imgs == sents:
                        status = "\033[33m◐ audio\033[0m"
                    else:
                        status = "\033[33m◐ imgs\033[0m"
                elif ready > 0:
                    status = "\033[33m◑ partial\033[0m"
                else:
                    status = "\033[31m○ stuck\033[0m"

                p_bar = bar(prompts, sents, 8)
                i_bar = bar(imgs, sents, 8)
                a_bar = bar(audio, words, 8)

                print(f"  {level:<4} {status:<19} {ready:>3}/{total:<5} "
                      f"{p_bar} {pct(prompts, sents)} "
                      f"{i_bar} {pct(imgs, sents)} "
                      f"{a_bar} {pct(audio, words)}")

            print()
            print("  Ctrl+C to exit")

            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        print("\n")
    finally:
        await close_db()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(run(args.interval))


if __name__ == "__main__":
    main()
