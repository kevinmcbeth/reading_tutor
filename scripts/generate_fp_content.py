#!/usr/bin/env python3
"""Generate F&P leveled reading content across all levels.

Usage:
    python scripts/generate_fp_content.py                    # All levels, 10 stories each
    python scripts/generate_fp_content.py --levels A B C     # Specific levels
    python scripts/generate_fp_content.py --count 20         # 20 per level
    python scripts/generate_fp_content.py --skip-existing    # Idempotent reruns
"""
import argparse
import asyncio
import random
import sys

import httpx

API = "http://127.0.0.1:8000"

# Topic pools organized by complexity tier
TIER_1_TOPICS = [
    # Concrete nouns — levels A-D
    "a cat", "a dog", "a ball", "my mom", "my dad", "a fish", "a bird",
    "a hat", "a bus", "a cup", "a bed", "a sun", "a box", "a frog",
    "my pet", "a pig", "a hen", "a fox", "a bug", "a toy",
]

TIER_2_TOPICS = [
    # Simple plots — levels E-H
    "a lost kitten", "a trip to the park", "a rainy day", "a new friend",
    "a missing shoe", "a big surprise", "a funny hat", "a little garden",
    "a brave puppy", "a sleepy bear", "a sunny picnic", "a silly goose",
    "a trip to the zoo", "baking a cake", "a snowman melting",
    "learning to swim", "a magic penny", "a runaway ball",
    "a birthday wish", "a colorful kite",
]

TIER_3_TOPICS = [
    # Complex stories — levels I-N
    "a brave mouse goes on an adventure", "a squirrel prepares for winter",
    "two friends build a treehouse", "a fox and a rabbit learn to share",
    "a caterpillar dreams of flying", "a dragon who is afraid of fire",
    "an owl teaches the forest animals", "a journey across a magical river",
    "a clever ant solves a big problem", "a lighthouse keeper and the storm",
    "a robot discovers what friendship means", "a penguin visits a tropical island",
    "a tiny seed grows into the tallest tree", "a baker who makes wish-granting bread",
    "a lost letter that travels the world", "a young artist paints a new world",
    "a detective cat solves a mystery", "a shipwrecked sailor and a helpful dolphin",
    "twins discover a secret passage", "a musician who can talk to animals",
]

TIER_4_TOPICS = [
    # Sophisticated themes — levels O-Z2
    "a child discovers a hidden library beneath the school",
    "an ancient map leads to an unexpected discovery",
    "a young inventor creates something that changes the town",
    "a mysterious stranger arrives with an impossible story",
    "a time capsule reveals secrets about the past",
    "a community comes together after a natural disaster",
    "a young astronomer discovers something extraordinary",
    "an old bookshop holds more than just books",
    "a friendship tested by a difficult choice",
    "a journey to understand a family mystery",
    "a student discovers they can hear the thoughts of trees",
    "an abandoned garden holds the key to healing a broken family",
    "a young journalist uncovers a forgotten hero's story",
    "a chess prodigy faces their greatest opponent",
    "a translator discovers a language that changes reality",
    "a photographer's pictures start predicting the future",
    "a refugee child finds belonging through music",
    "an exchange student bridges two very different worlds",
    "a young coder's creation develops a mind of its own",
    "a village elder's stories turn out to be literally true",
]

LEVEL_TO_TIER = {
    "A": 1, "B": 1, "C": 1, "D": 1,
    "E": 2, "F": 2, "G": 2, "H": 2,
    "I": 3, "J": 3, "K": 3, "L": 3, "M": 3, "N": 3,
    "O": 4, "P": 4, "Q": 4, "R": 4, "S": 4, "T": 4,
    "U": 4, "V": 4, "W": 4, "X": 4, "Y": 4, "Z": 4,
    "Z1": 4, "Z2": 4,
}

TIER_TOPICS = {
    1: TIER_1_TOPICS,
    2: TIER_2_TOPICS,
    3: TIER_3_TOPICS,
    4: TIER_4_TOPICS,
}

ALL_LEVELS = [
    "A", "B", "C", "D", "E", "F", "G", "H",
    "I", "J", "K", "L", "M", "N",
    "O", "P", "Q", "R", "S", "T",
    "U", "V", "W", "X", "Y", "Z", "Z1", "Z2",
]


async def main():
    parser = argparse.ArgumentParser(description="Generate F&P leveled reading content")
    parser.add_argument("--levels", nargs="+", default=None, help="Specific levels to generate")
    parser.add_argument("--count", type=int, default=10, help="Stories per level")
    parser.add_argument("--skip-existing", action="store_true", help="Skip levels that already have stories")
    args = parser.parse_args()

    levels = args.levels or ALL_LEVELS

    # Login
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(
            f"{API}/api/auth/login",
            json={"username": "test", "password": "test123"},
        )
        if resp.status_code != 200:
            print(f"Login failed: {resp.text}")
            sys.exit(1)
        token = resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # Clear rate limits
    try:
        import redis
        r = redis.Redis()
        r.flushall()
        print("Rate limits cleared")
    except Exception:
        print("Warning: Could not clear rate limits")

    total_generated = 0

    for level in levels:
        if level not in LEVEL_TO_TIER:
            print(f"Unknown level: {level}, skipping")
            continue

        tier = LEVEL_TO_TIER[level]
        topics = TIER_TOPICS[tier]

        if args.skip_existing:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.get(
                    f"{API}/api/fp/stories",
                    params={"level": level},
                    headers=headers,
                )
                if resp.status_code == 200:
                    existing = len(resp.json())
                    if existing >= args.count:
                        print(f"Level {level}: {existing} stories already exist, skipping")
                        continue

        print(f"\nLevel {level} (Tier {tier}): generating {args.count} stories")

        # Pick topics, cycling through the pool
        selected_topics = []
        for i in range(args.count):
            selected_topics.append(topics[i % len(topics)])
        random.shuffle(selected_topics)

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            for i, topic in enumerate(selected_topics):
                resp = await client.post(
                    f"{API}/api/fp/generate",
                    json={"topic": topic, "level": level},
                    headers=headers,
                )
                if resp.status_code == 200:
                    job = resp.json()
                    print(f"  [{i+1:3d}/{args.count}] Level {level:3s} | {topic} -> job {job['id']}")
                    total_generated += 1
                elif resp.status_code == 429:
                    # Rate limited — clear and retry
                    try:
                        r.flushall()
                    except Exception:
                        pass
                    resp = await client.post(
                        f"{API}/api/fp/generate",
                        json={"topic": topic, "level": level},
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        job = resp.json()
                        print(f"  [{i+1:3d}/{args.count}] Level {level:3s} | {topic} -> job {job['id']} (retry)")
                        total_generated += 1
                    else:
                        print(f"  [{i+1:3d}/{args.count}] FAILED: {resp.status_code} {resp.text[:80]}")
                else:
                    print(f"  [{i+1:3d}/{args.count}] FAILED: {resp.status_code} {resp.text[:80]}")

    print(f"\nQueued {total_generated} F&P stories! Monitor progress with:")
    print("  journalctl -u reading-tutor-worker -f")


if __name__ == "__main__":
    asyncio.run(main())
