#!/usr/bin/env python3
"""Generate 100 story requests across easy/medium/hard difficulties."""
import asyncio
import httpx
import sys

API = "http://127.0.0.1:8000"

TOPICS = [
    # Animals
    "a clumsy penguin",
    "a brave little mouse",
    "a friendly dragon",
    "a lost baby turtle",
    "a singing bird",
    "a dancing bear",
    "a curious kitten",
    "a happy puppy",
    "a sleepy owl",
    "a silly monkey",
    "a tiny ladybug",
    "a noisy parrot",
    "a gentle elephant",
    "a sneaky raccoon",
    "a proud lion cub",
    "a fast cheetah",
    "a slow snail",
    "a playful dolphin",
    "a fuzzy caterpillar",
    "a hungry bunny",
    # Adventure
    "a pirate treasure hunt",
    "a magic flying carpet",
    "a secret garden",
    "a trip to space",
    "a jungle adventure",
    "a magical treehouse",
    "a rainbow bridge",
    "a hidden cave",
    "a hot air balloon",
    "an underwater kingdom",
    # Everyday
    "first day of school",
    "baking cookies together",
    "a rainy day inside",
    "building a snowman",
    "a trip to the zoo",
    "planting a flower garden",
    "learning to ride bikes",
    "a fun camping trip",
    "a birthday surprise party",
    "making new friends",
    # Fantasy
    "a tiny fairy",
    "a wizard's lost wand",
    "a talking teddy bear",
    "a cloud made of candy",
    "a magical paintbrush",
    "a friendly ghost",
    "a unicorn's first flight",
    "a monster under the bed",
    "shoes that can dance",
    "a wish-granting fish",
    # Nature & Science
    "a seed that grew big",
    "chasing butterflies",
    "a thunderstorm at night",
    "stars in the sky",
    "a volcano adventure",
    "ocean waves and sand",
    "a walk in the forest",
    "a colorful sunset",
    "a snowy winter morning",
    "spring flowers blooming",
    # Helpers & Community
    "a kind firefighter",
    "a helpful robot friend",
    "sharing with a neighbor",
    "the brave mail carrier",
    "a doctor who helps",
    # Food & Fun
    "a pancake so tall",
    "a pizza party",
    "an ice cream truck",
    "a lemonade stand",
    "a gingerbread house",
    # Silly & Funny
    "a backwards day",
    "socks that run away",
    "a burping frog prince",
    "a very wiggly worm",
    "a hat that talks",
    "an upside down house",
    "a dog who reads books",
    "pants made of jelly",
    "a cow on the moon",
    "a superhero baby",
]

DIFFICULTIES = ["easy", "medium", "hard"]


async def main():
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

    # Build 100 requests: cycle through difficulties
    requests = []
    for i, topic in enumerate(TOPICS):
        diff = DIFFICULTIES[i % 3]
        requests.append({"topic": topic, "difficulty": diff})

    # Pad to 100 if needed
    while len(requests) < 100:
        extra_idx = len(requests) - len(TOPICS)
        diff = DIFFICULTIES[extra_idx % 3]
        requests.append({"topic": TOPICS[extra_idx % len(TOPICS)], "difficulty": diff})

    requests = requests[:100]

    print(f"Queueing {len(requests)} stories...")
    easy = sum(1 for r in requests if r["difficulty"] == "easy")
    med = sum(1 for r in requests if r["difficulty"] == "medium")
    hard = sum(1 for r in requests if r["difficulty"] == "hard")
    print(f"  Easy: {easy}, Medium: {med}, Hard: {hard}")
    print()

    # Clear rate limits
    import redis
    r = redis.Redis()
    r.flushall()
    print("Rate limits cleared")

    # Submit all
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        for i, req in enumerate(requests):
            resp = await client.post(
                f"{API}/api/stories/generate",
                json=req,
                headers=headers,
            )
            if resp.status_code == 200:
                job = resp.json()
                print(f"  [{i+1:3d}/100] {req['difficulty']:6s} | {req['topic']} -> job {job['id']}")
            elif resp.status_code == 429:
                # Rate limited, flush and retry
                r.flushall()
                resp = await client.post(
                    f"{API}/api/stories/generate",
                    json=req,
                    headers=headers,
                )
                if resp.status_code == 200:
                    job = resp.json()
                    print(f"  [{i+1:3d}/100] {req['difficulty']:6s} | {req['topic']} -> job {job['id']} (retry)")
                else:
                    print(f"  [{i+1:3d}/100] FAILED: {resp.status_code} {resp.text[:80]}")
            else:
                print(f"  [{i+1:3d}/100] FAILED: {resp.status_code} {resp.text[:80]}")

    print()
    print("All 100 stories queued! Monitor progress with:")
    print("  journalctl -u reading-tutor-worker -f")


if __name__ == "__main__":
    asyncio.run(main())
