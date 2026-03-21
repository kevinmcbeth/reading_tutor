"""Amazon Bedrock client for Claude Haiku text generation."""

import asyncio
import json
import logging
import re
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

VALID_STYLES = {"cartoon", "soft_pastoral", "watercolor", "realistic", "bright_pop"}

_bedrock_client = None


def _get_client():
    global _bedrock_client
    if _bedrock_client is None:
        import boto3
        _bedrock_client = boto3.client(
            "bedrock-runtime", region_name=settings.AWS_REGION
        )
    return _bedrock_client


def _read_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text().strip()


def _parse_json(text: str):
    """Parse JSON from LLM output, handling code fences."""
    text = text.strip()
    # Find first { or [
    for i, ch in enumerate(text):
        if ch in ("{", "["):
            text = text[i:]
            break

    # Strip trailing non-JSON
    for i in range(len(text) - 1, -1, -1):
        if text[i] in ("}", "]"):
            text = text[: i + 1]
            break

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            return json.loads(match.group(1).strip())
        raise


def _invoke_sync(system_prompt: str, user_message: str) -> str:
    """Synchronous Bedrock invoke with retry on throttling."""
    import botocore.exceptions

    client = _get_client()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-10-08",
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    })

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.invoke_model(
                modelId=settings.BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            result = json.loads(response["body"].read())
            return result["content"][0]["text"]
        except botocore.exceptions.ClientError as exc:
            if exc.response["Error"]["Code"] == "ThrottlingException" and attempt < max_retries - 1:
                import time
                wait = 2 ** attempt
                logger.warning("Bedrock throttled, retrying in %ds", wait)
                time.sleep(wait)
            else:
                raise


async def generate_text(system_prompt: str, user_message: str) -> str:
    """Async wrapper around Bedrock invoke."""
    return await asyncio.to_thread(_invoke_sync, system_prompt, user_message)


async def generate_story(topic: str, difficulty: str, theme: str | None = None) -> dict:
    """Generate a story using Bedrock. Returns parsed JSON dict."""
    system_prompt = _read_prompt("story_system.txt")
    user_prompt = f"Write a {difficulty} story about {topic}."
    if theme:
        user_prompt += f" Theme: {theme}."
    user_prompt += "\n\nRespond with valid JSON only, no other text."

    content = await generate_text(system_prompt, user_prompt)
    result = _parse_json(content)

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
        f"Sentences:\n{sentences_text}\n\n"
        "Respond with valid JSON only, no other text."
    )

    content = await generate_text(system_prompt, user_prompt)
    result = _parse_json(content)

    if isinstance(result, dict) and "prompts" in result:
        result = result["prompts"]

    return result


async def generate_meta_prompts(description: str, count: int = 5) -> list[dict]:
    """Generate story prompts from a description."""
    system_prompt = _read_prompt("meta_prompt_system.txt")
    user_prompt = (
        f"{description}. Generate {count} story prompts.\n\n"
        "Respond with valid JSON only, no other text."
    )

    content = await generate_text(system_prompt, user_prompt)
    result = _parse_json(content)

    if isinstance(result, dict) and "prompts" in result:
        result = result["prompts"]

    return result
