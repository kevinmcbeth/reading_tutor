"""Mock Ollama client — returns deterministic canned responses without GPU."""

import asyncio
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures"


def _load_mock_story() -> dict:
    fixture = FIXTURES_DIR / "mock_story.json"
    if fixture.exists():
        return json.loads(fixture.read_text())
    return {
        "title": "The Brave Little Fox",
        "style": "cartoon",
        "sentences": [
            {"text": "Once upon a time there was a brave little fox.", "challenge_words": [7, 8]},
            {"text": "The fox loved to explore the forest.", "challenge_words": [3, 6]},
            {"text": "One day the fox found a sparkling river.", "challenge_words": [5, 7]},
        ],
    }


async def generate_story(topic: str, difficulty: str, theme: str | None = None) -> dict:
    await asyncio.sleep(0.05)
    story = _load_mock_story()
    story["title"] = f"Story about {topic}"
    return story


async def generate_image_prompts(
    story_text: str, style: str, sentences: list[dict]
) -> list[dict]:
    await asyncio.sleep(0.05)
    return [
        {
            "sentence_index": i,
            "image_prompt": f"A {style} illustration of: {s['text'][:50]}",
            "negative_prompt": "blurry, dark, scary",
        }
        for i, s in enumerate(sentences)
    ]


async def generate_meta_prompts(description: str, count: int = 5) -> list[dict]:
    await asyncio.sleep(0.05)
    return [
        {"topic": f"{description} part {i + 1}", "difficulty": "easy", "theme": None}
        for i in range(count)
    ]
