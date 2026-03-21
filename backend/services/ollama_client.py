import json
import logging
import re
from pathlib import Path

import httpx

from config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

VALID_STYLES = {"cartoon", "soft_pastoral", "watercolor", "realistic", "bright_pop"}


def _read_prompt(filename: str) -> str:
    """Read a system prompt file."""
    return (PROMPTS_DIR / filename).read_text().strip()


def _strip_think_tags(text: str) -> str:
    """Strip any <think>...</think> blocks and content before the first JSON delimiter."""
    # Remove think blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.strip()
    # Find first { or [
    for i, ch in enumerate(text):
        if ch in ("{", "["):
            return text[i:]
    return text


def _parse_json(text: str):
    """Parse JSON from LLM output, stripping think tags if needed."""
    cleaned = _strip_think_tags(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON between code fences
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            return json.loads(match.group(1).strip())
        raise


async def _chat(system_prompt: str, user_prompt: str) -> str:
    """Send a chat request to Ollama and return the response content."""
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        resp = await client.post(f"{settings.OLLAMA_URL}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


async def generate_story(topic: str, difficulty: str, theme: str | None = None) -> dict:
    """Generate a story using Ollama. Returns parsed JSON dict."""
    system_prompt = _read_prompt("story_system.txt")
    user_prompt = f"Write a {difficulty} story about {topic}."
    if theme:
        user_prompt += f" Theme: {theme}."

    content = await _chat(system_prompt, user_prompt)
    result = _parse_json(content)

    # Validate style
    if result.get("style") not in VALID_STYLES:
        logger.warning(
            "Invalid style '%s' from LLM, defaulting to 'cartoon'", result.get("style")
        )
        result["style"] = "cartoon"

    return result


async def generate_image_prompts(
    story_text: str, style: str, sentences: list[dict]
) -> list[dict]:
    """Generate image prompts for each sentence."""
    system_prompt = _read_prompt("image_prompt_system.txt")
    sentences_text = "\n".join(
        f"[{i}] {s['text']}" for i, s in enumerate(sentences)
    )
    user_prompt = (
        f"Story text:\n{story_text}\n\n"
        f"Art style: {style}\n\n"
        f"Sentences:\n{sentences_text}"
    )

    content = await _chat(system_prompt, user_prompt)
    result = _parse_json(content)

    if isinstance(result, dict) and "prompts" in result:
        result = result["prompts"]

    return result


async def generate_meta_prompts(description: str, count: int = 5) -> list[dict]:
    """Generate story prompts from a description."""
    system_prompt = _read_prompt("meta_prompt_system.txt")
    user_prompt = f"{description}. Generate {count} story prompts."

    content = await _chat(system_prompt, user_prompt)
    result = _parse_json(content)

    if isinstance(result, dict) and "prompts" in result:
        result = result["prompts"]

    return result
