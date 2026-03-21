#!/usr/bin/env python3
"""Generate stories across Fountas & Pinnell Guided Reading levels A-J.

Text characteristics and high-frequency word lists are sourced from:
- Fountas & Pinnell Continuum for Literacy Learning (2007)
- Fountas & Pinnell Benchmark Assessment System 1

Levels map to the app's existing difficulty system:
  A-C → easy, D-F → medium, G-J → hard

Usage:
    python scripts/generate_levelled_stories.py [--levels A B C] [--per-level 5]
"""
import argparse
import asyncio
import sys

import httpx

API = "http://127.0.0.1:8000"

# ---------------------------------------------------------------------------
# Fountas & Pinnell high-frequency word lists (Benchmark Assessment System 1)
# ---------------------------------------------------------------------------
# Beginning list (pre-Level A / Level A): 20 words
HFW_BEGINNING = {
    "me", "I", "can", "to", "my", "we", "in", "like", "it", "up",
    "mom", "the", "and", "he", "look", "is", "see", "come", "get", "at",
}

# Level 1 words (Levels B-C): adds 20 more
HFW_LEVEL1 = HFW_BEGINNING | {
    "jump", "here", "little", "went", "has", "girl", "will", "have",
    "ball", "make", "play", "was", "bike", "with", "they", "this",
    "bed", "feet", "one", "said",
}

# Level 2 words (Levels D-F): adds 20 more
HFW_LEVEL2 = HFW_LEVEL1 | {
    "want", "friend", "puppy", "basket", "could", "dark", "down", "road",
    "plant", "away", "morning", "three", "cool", "drop", "grass", "when",
    "first", "train", "queen", "scream",
}

# Level 3 words (Levels G-H): adds 20 more
HFW_LEVEL3 = HFW_LEVEL2 | {
    "plate", "year", "noise", "under", "twisted", "giant", "knives",
    "what", "around", "because", "forest", "once", "scramble", "again",
    "careful", "breakfast", "batter", "suddenly", "badge", "village",
}

# Level 4 words (Levels I-J): adds 20 more
HFW_LEVEL4 = HFW_LEVEL3 | {
    "silence", "serious", "nature", "station", "graceful", "heavy",
    "against", "excuse", "traffic", "reward", "plastic", "ocean",
    "perform", "delicious", "pebble", "understood", "destiny", "future",
    "anger", "honey",
}

# ---------------------------------------------------------------------------
# Formal F&P text descriptors per level (Continuum for Literacy Learning, 2007)
# ---------------------------------------------------------------------------
LEVELS = {
    "A": {
        "difficulty": "easy",
        "constraints": (
            "Fountas & Pinnell Guided Reading Level A.\n"
            "TEXT CHARACTERISTICS (you must follow ALL of these):\n"
            "- Simple factual text, animal fantasy, or realistic fiction\n"
            "- One line of text per page (one sentence per page)\n"
            "- Repeating language pattern with 3-6 words per page, "
            "where only one word changes each repetition\n"
            "- Familiar, easy content about everyday things\n"
            "- Short, predictable sentences\n"
            "- Almost all vocabulary must come from this sight-word list: "
            "me, I, can, to, my, we, in, like, it, up, mom, the, and, "
            "he, look, is, see, come, get, at. "
            "You may add ONE simple noun per sentence (cat, dog, ball, etc.) "
            "but all other words must be from this list.\n"
            "- Total story: 3-4 sentences, each following the same pattern\n"
            "- NO dialogue, NO compound sentences, NO multisyllable words"
        ),
        "topics": [
            "a cat",
            "a dog",
            "things I see",
            "things I like",
            "my toys",
            "at the park",
            "things that go up",
            "my family",
            "animals I see",
            "colors",
        ],
    },
    "B": {
        "difficulty": "easy",
        "constraints": (
            "Fountas & Pinnell Guided Reading Level B.\n"
            "TEXT CHARACTERISTICS (you must follow ALL of these):\n"
            "- Simple factual text, animal fantasy, or realistic fiction\n"
            "- Simple, one-dimensional characters\n"
            "- Two or more lines of text per page\n"
            "- Repeating language patterns with 3-7 words per page, "
            "with slight variation allowed\n"
            "- Very familiar themes and ideas\n"
            "- Short, predictable sentences\n"
            "- Almost all vocabulary must come from this sight-word list: "
            "me, I, can, to, my, we, in, like, it, up, mom, the, and, "
            "he, look, is, see, come, get, at, jump, here, little, went, "
            "has, girl, will, have, ball, make, play, was, bike, with, "
            "they, this, bed, feet, one, said. "
            "You may use simple nouns for the topic but keep all other "
            "words from this list.\n"
            "- Total story: 3-4 sentences\n"
            "- NO compound sentences, NO multisyllable words except 'little'"
        ),
        "topics": [
            "a red ball",
            "my pet cat",
            "I can jump",
            "things I play with",
            "at the park",
            "my big dog",
            "bugs I see",
            "we go up",
            "a fun hat",
            "in the sun",
        ],
    },
    "C": {
        "difficulty": "easy",
        "constraints": (
            "Fountas & Pinnell Guided Reading Level C.\n"
            "TEXT CHARACTERISTICS (you must follow ALL of these):\n"
            "- Simple factual text, animal fantasy, or realistic fiction\n"
            "- Amusing, one-dimensional characters\n"
            "- Familiar, easy content\n"
            "- Introduction of dialogue — assigned by 'said' in most cases\n"
            "- Many sentences with prepositional phrases and adjectives\n"
            "- Almost all vocabulary familiar to children — greater range of "
            "high-frequency words from this list: "
            "me, I, can, to, my, we, in, like, it, up, mom, the, and, "
            "he, look, is, see, come, get, at, jump, here, little, went, "
            "has, girl, will, have, ball, make, play, was, bike, with, "
            "they, this, bed, feet, one, said. "
            "You may also use simple adjectives (big, red, happy, funny) "
            "and action verbs (run, eat, sit, go).\n"
            "- Some simple contractions and possessives allowed (it's, mom's)\n"
            "- Two to five lines of text per page\n"
            "- Some ellipses, commas, quotation marks, question marks, "
            "and exclamation points\n"
            "- Total story: 3-5 sentences\n"
            "- Keep words to one syllable except common two-syllable words "
            "(little, funny, happy, puppy, mommy)"
        ),
        "topics": [
            "a little frog",
            "playing in the rain",
            "a happy puppy",
            "my red bike",
            "baking with mom",
            "a funny hat",
            "the big bear",
            "going to the park",
            "a silly cat",
            "time for bed",
        ],
    },
    "D": {
        "difficulty": "medium",
        "constraints": (
            "Fountas & Pinnell Guided Reading Level D.\n"
            "TEXT CHARACTERISTICS (you must follow ALL of these):\n"
            "- Simple factual text, animal fantasy, or realistic fiction\n"
            "- Amusing, one-dimensional characters\n"
            "- Familiar, easy content, themes, and ideas\n"
            "- Simple dialogue (some split dialogue)\n"
            "- Many sentences with prepositional phrases and adjectives\n"
            "- Some longer sentences (some with more than six words)\n"
            "- Some simple contractions and possessives (words with "
            "apostrophes)\n"
            "- Two to six lines of text per page\n"
            "- Some sentences turn over to the next line\n"
            "- Some words with -s and -ing endings\n"
            "- Fewer repetitive language patterns than earlier levels\n"
            "- Vocabulary should be mostly from high-frequency words plus "
            "simple decodable words. Allowed high-frequency words include: "
            "want, friend, puppy, could, dark, down, road, away, morning, "
            "three, when, first — in addition to all earlier level words.\n"
            "- Total story: 4-6 sentences"
        ),
        "topics": [
            "a lost kitten",
            "first day at school",
            "making a sandcastle",
            "a bird that cannot fly",
            "helping in the garden",
            "a snowy morning",
            "a little boat",
            "a picnic with friends",
            "finding a ladybug",
            "a trip to the library",
        ],
    },
    "E": {
        "difficulty": "medium",
        "constraints": (
            "Fountas & Pinnell Guided Reading Level E.\n"
            "TEXT CHARACTERISTICS (you must follow ALL of these):\n"
            "- Simple informational texts, simple animal fantasy, realistic "
            "fiction, very simple retellings of traditional tales, simple "
            "plays\n"
            "- Some texts with sequential information\n"
            "- Familiar content that expands beyond home, neighborhood, "
            "and school\n"
            "- Most concepts supported by pictures\n"
            "- More literary stories and language\n"
            "- Concrete, easy-to-understand ideas\n"
            "- Some longer sentences — more than ten words\n"
            "- Some three-syllable words allowed\n"
            "- Some sentences with verb preceding subject\n"
            "- Variation of dialogue words: said, cried, shouted\n"
            "- Easy contractions allowed\n"
            "- Mostly words with easy, predictable spelling patterns\n"
            "- Two to eight lines of print per page\n"
            "- Total story: 5-6 sentences"
        ),
        "topics": [
            "a squirrel hiding acorns",
            "two friends sharing a toy",
            "a caterpillar becoming a butterfly",
            "a child helping a neighbor",
            "a kite that flies too high",
            "a penguin who wants to dance",
            "baking cookies that look funny",
            "a puddle adventure after rain",
            "planting seeds and watching them grow",
            "a mouse and a lion become friends",
        ],
    },
    "F": {
        "difficulty": "medium",
        "constraints": (
            "Fountas & Pinnell Guided Reading Level F.\n"
            "TEXT CHARACTERISTICS (you must follow ALL of these):\n"
            "- Simple informational texts, simple animal fantasy, realistic "
            "fiction, very simple retellings of traditional tales, simple "
            "plays\n"
            "- Some texts with sequential information\n"
            "- Familiar content that expands beyond home, neighborhood, "
            "and school\n"
            "- Both simple and split dialogue, speaker usually assigned\n"
            "- Some longer stretches of dialogue\n"
            "- Some longer sentences — more than ten words — with "
            "prepositional phrases, adjectives, and dialogue\n"
            "- Variation in placement of subject, verb, adjectives, "
            "and adverbs\n"
            "- Some compound sentences conjoined by 'and'\n"
            "- Many words with inflectional endings (-s, -ed, -ing)\n"
            "- Most texts three to eight lines of text per page\n"
            "- Periods, commas, quotation marks, exclamation points, "
            "question marks, and ellipses\n"
            "- Total story: 5-7 sentences"
        ),
        "topics": [
            "a dragon who is afraid of fire",
            "a teddy bear that comes alive at night",
            "a child who discovers a secret door",
            "an owl who stays up during the day",
            "a tortoise who wins a surprising race",
            "a cloud that wanted to be a rainbow",
            "a little fish exploring the ocean",
            "a robot who learns to paint",
            "a fox and a rabbit share a den",
            "a child who talks to the moon",
        ],
    },
    "G": {
        "difficulty": "hard",
        "constraints": (
            "Fountas & Pinnell Guided Reading Level G.\n"
            "TEXT CHARACTERISTICS (you must follow ALL of these):\n"
            "- Informational texts, simple animal fantasy, realistic fiction, "
            "traditional literature (folktales)\n"
            "- Some longer texts with repeating longer and more complex "
            "patterns\n"
            "- Some unusual formats, such as questions followed by answers "
            "or letters\n"
            "- Some texts with sequential information\n"
            "- Familiar content that expands beyond home, neighborhood, "
            "and school\n"
            "- Some texts with settings that are not typical of many "
            "children's experience\n"
            "- Some sentences that are questions in simple sentences "
            "and in dialogue\n"
            "- Sentences with clauses and embedded phrases\n"
            "- Some complex letter-sound relationships in words\n"
            "- Some content-specific words introduced, explained, and "
            "illustrated in the text\n"
            "- Most texts three to eight lines of print per page\n"
            "- Total story: 7-8 sentences"
        ),
        "topics": [
            "a brave mouse who explores a castle",
            "a child who builds a treehouse with grandpa",
            "a baby whale learning to swim",
            "a magical garden where flowers talk",
            "a lost star trying to find its way home",
            "a baker who makes the tallest cake",
            "twin foxes on their first adventure",
            "a rainstorm that brings unexpected visitors",
            "a child inventor who builds a flying machine",
            "a friendly giant who helps a tiny village",
        ],
    },
    "H": {
        "difficulty": "hard",
        "constraints": (
            "Fountas & Pinnell Guided Reading Level H.\n"
            "TEXT CHARACTERISTICS (you must follow ALL of these):\n"
            "- Informational texts, simple animal fantasy, realistic fiction, "
            "traditional literature (folktales)\n"
            "- Narratives with more episodes and less repetition\n"
            "- Accessible content that expands beyond home, school, "
            "and neighborhood\n"
            "- Multiple episodes taking place across time\n"
            "- Some stretches of descriptive language\n"
            "- Wide variety in words used to assign dialogue to speaker\n"
            "- Some complex letter-sound relationships in words\n"
            "- Some complex spelling patterns\n"
            "- Some easy compound words\n"
            "- Most texts with no or only minimal illustrations\n"
            "- Italics indicating unspoken thought\n"
            "- Most texts three to eight lines of print per page\n"
            "- Total story: 8-9 sentences"
        ),
        "topics": [
            "a pirate parrot who finds a treasure map",
            "a snow leopard cub lost in a blizzard",
            "a wizard's apprentice who mixes up a spell",
            "a family of rabbits preparing for winter",
            "a submarine adventure to find a sunken ship",
            "a painter whose pictures come to life",
            "a firefighter rescuing a kitten from a tree",
            "a magical hat that grants one wish per day",
            "a town where it rains candy every Tuesday",
            "a child astronaut visiting a friendly planet",
        ],
    },
    "I": {
        "difficulty": "hard",
        "constraints": (
            "Fountas & Pinnell Guided Reading Level I.\n"
            "TEXT CHARACTERISTICS (you must follow ALL of these):\n"
            "- Informational texts, simple animal fantasy, realistic fiction, "
            "traditional literature (folktales)\n"
            "- Some informational texts with a table of contents and/or "
            "a glossary\n"
            "- Narratives with multiple episodes and little repetition of "
            "similar episodes; more elaborated episodes\n"
            "- Underlying organizational structures used and presented "
            "clearly (description, compare and contrast, problem and "
            "solution)\n"
            "- Some unusual formats, such as letters or questions followed "
            "by answers\n"
            "- Both familiar content and some new content children may "
            "not know\n"
            "- Contain a few abstract concepts that are highly supported "
            "by text and illustrations\n"
            "- Longer sentences that can carry over to two or three lines\n"
            "- Many two-to-three-syllable words from all parts of speech\n"
            "- Some complex spelling patterns\n"
            "- Some complex letter-sound relationships in words\n"
            "- Eight to sixteen pages of print\n"
            "- Three to eight lines of text per page\n"
            "- Total story: 9-10 sentences"
        ),
        "topics": [
            "a detective cat solving a mystery in the barn",
            "a group of animals starting a school in the forest",
            "a child who discovers they can talk to animals",
            "a magical library where books take you inside the story",
            "a sea turtle's long journey home across the ocean",
            "a shy dragon who performs in a talent show",
            "a clockmaker who builds a clock that stops time",
            "a team of insects building a bridge across a stream",
            "a princess who would rather be an explorer",
            "a snowman who travels to see the summer",
        ],
    },
    "J": {
        "difficulty": "hard",
        "constraints": (
            "Fountas & Pinnell Guided Reading Level J.\n"
            "TEXT CHARACTERISTICS (you must follow ALL of these):\n"
            "- Informational texts, simple animal fantasy, realistic fiction, "
            "traditional literature (folktales), some simple biographies "
            "on familiar subjects\n"
            "- Beginning chapter books with illustrations\n"
            "- Underlying organizational structures used and presented "
            "clearly (description, compare and contrast, problem and "
            "solution)\n"
            "- Some unusual formats, such as letters or questions followed "
            "by answers\n"
            "- Some ideas new to most children\n"
            "- Some texts with settings that are not familiar to most "
            "children\n"
            "- Varied placement of subject, verb, adjectives, and adverbs "
            "in sentences\n"
            "- Contain some abstract concepts that are highly supported "
            "by text and illustrations\n"
            "- Some complex spelling patterns and letter-sound "
            "relationships in words\n"
            "- Many lines of print on a page\n"
            "- Total story: 9-10 sentences"
        ),
        "topics": [
            "a young inventor who creates a machine to clean the ocean",
            "a wolf who learns that kindness is stronger than fear",
            "an old lighthouse keeper and the storm of the century",
            "a village of mice who build a hot air balloon",
            "a child who paints a door that opens to another world",
            "a bear family who adopts a lost baby bird",
            "a river otter who teaches a beaver to have fun",
            "a tiny seed that grows into the tallest tree in the forest",
            "a musician whose songs can change the weather",
            "a colony of ants who discover a mountain of sugar",
        ],
    },
}


async def main():
    parser = argparse.ArgumentParser(
        description="Generate levelled reading stories (F&P Guided Reading A-J)"
    )
    parser.add_argument(
        "--levels",
        nargs="+",
        default=list(LEVELS.keys()),
        choices=list(LEVELS.keys()),
        help="Which levels to generate (default: all A-J)",
    )
    parser.add_argument(
        "--per-level",
        type=int,
        default=10,
        help="Number of stories per level (default: 10, max 10)",
    )
    parser.add_argument(
        "--api",
        default=API,
        help=f"API base URL (default: {API})",
    )
    args = parser.parse_args()

    per_level = min(args.per_level, 10)

    # Login
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(
            f"{args.api}/api/auth/login",
            json={"username": "test", "password": "test123"},
        )
        if resp.status_code != 200:
            print(f"Login failed: {resp.text}")
            sys.exit(1)
        token = resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # Build requests
    requests = []
    for level in args.levels:
        info = LEVELS[level]
        topics = info["topics"][:per_level]
        for topic in topics:
            requests.append({
                "topic": topic,
                "difficulty": info["difficulty"],
                "theme": f"level-{level}",
                "level": level,
                "display_topic": topic,
            })

    total = len(requests)
    print(f"Generating {total} levelled stories across {len(args.levels)} levels")
    print("(Fountas & Pinnell Guided Reading text characteristics)")
    print()
    for level in args.levels:
        count = sum(1 for r in requests if r["level"] == level)
        diff = LEVELS[level]["difficulty"]
        print(f"  Level {level} ({diff:6s}): {count} stories")
    print()

    # Clear rate limits
    try:
        import redis
        r = redis.Redis(port=6380)
        r.flushall()
        print("Rate limits cleared")
    except Exception:
        print("Warning: could not clear rate limits (redis not available?)")

    # Submit all via /api/fp/generate so stories get fp_level set
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        for i, req in enumerate(requests):
            resp = await client.post(
                f"{args.api}/api/fp/generate",
                json={
                    "topic": req["topic"],
                    "level": req["level"],
                    "theme": req["theme"],
                },
                headers=headers,
            )
            if resp.status_code == 200:
                job = resp.json()
                print(
                    f"  [{i+1:3d}/{total}] Level {req['level']} "
                    f"({req['difficulty']:6s}) | {req['display_topic']} "
                    f"-> job {job['id']}"
                )
            elif resp.status_code == 429:
                try:
                    import redis
                    redis.Redis(port=6380).flushall()
                except Exception:
                    pass
                resp = await client.post(
                    f"{args.api}/api/fp/generate",
                    json={
                        "topic": req["topic"],
                        "level": req["level"],
                        "theme": req["theme"],
                    },
                    headers=headers,
                )
                if resp.status_code == 200:
                    job = resp.json()
                    print(
                        f"  [{i+1:3d}/{total}] Level {req['level']} "
                        f"({req['difficulty']:6s}) | {req['display_topic']} "
                        f"-> job {job['id']} (retry)"
                    )
                else:
                    print(
                        f"  [{i+1:3d}/{total}] FAILED: "
                        f"{resp.status_code} {resp.text[:80]}"
                    )
            else:
                print(
                    f"  [{i+1:3d}/{total}] FAILED: "
                    f"{resp.status_code} {resp.text[:80]}"
                )

    print()
    print(f"All {total} levelled stories queued! Monitor progress with:")
    print("  journalctl -u reading-tutor-worker -f")


if __name__ == "__main__":
    asyncio.run(main())
