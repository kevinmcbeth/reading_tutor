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


def _build_fp_vocabulary_rules(vocab: dict) -> str:
    """Build vocabulary rules text from level JSONB data."""
    vtype = vocab.get("type", "grade_appropriate")
    if vtype == "sight_words_only":
        words = ", ".join(vocab.get("words", []))
        return (
            f"VOCABULARY RULES (STRICT):\n"
            f"- Use ONLY these words: {words}\n"
            f"- Every word in every sentence MUST come from this list\n"
            f"- Use simple pattern sentences like 'I see a ___' or 'I like my ___'\n"
            f"- No words outside this list are allowed"
        )
    elif vtype == "cvc_plus_sight":
        max_syl = vocab.get("max_syllables", 1)
        return (
            f"VOCABULARY RULES:\n"
            f"- Use sight words plus simple CVC (consonant-vowel-consonant) words\n"
            f"- Maximum {max_syl} syllable(s) per word\n"
            f"- Examples of allowed words: cat, dog, run, big, hop, sit, red, hat\n"
            f"- Keep sentences under 6 words each\n"
            f"- No complex or multi-syllable words"
        )
    elif vtype == "expanding":
        max_syl = vocab.get("max_syllables", 2)
        allow_contr = vocab.get("allow_contractions", True)
        rules = (
            f"VOCABULARY RULES:\n"
            f"- Use common words up to {max_syl} syllables\n"
            f"- Simple dialogue is allowed (use quotation marks)\n"
        )
        if allow_contr:
            rules += "- Contractions are allowed (don't, can't, it's)\n"
        rules += "- Avoid uncommon or academic vocabulary"
        return rules
    elif vtype == "varied":
        rules = "VOCABULARY RULES:\n- Use varied, rich vocabulary appropriate for the grade level\n"
        if vocab.get("allow_compound"):
            rules += "- Compound words are allowed (butterfly, sunshine)\n"
        if vocab.get("allow_literary"):
            rules += "- Literary language is allowed (suddenly, whispered, enormous)\n"
        return rules
    else:
        return "VOCABULARY: Use grade-appropriate vocabulary. No specific restrictions."


def _build_fp_level_instructions(level: str) -> str:
    """Build level-specific writing instructions."""
    if level in ("A", "B"):
        return (
            "LEVEL-SPECIFIC INSTRUCTIONS:\n"
            "- Use repetitive, predictable pattern text\n"
            "- One idea per sentence\n"
            "- Example patterns: 'I see a [noun].' 'I like my [noun].' 'I can [verb].'\n"
            "- Each sentence should follow the same pattern with one word changed\n"
            "- No dialogue, no complex sentence structures"
        )
    elif level in ("C", "D"):
        return (
            "LEVEL-SPECIFIC INSTRUCTIONS:\n"
            "- Simple plot with beginning and end\n"
            "- Keep sentences under 6 words\n"
            "- Some repetition but introduce slight variation\n"
            "- Simple action sequences (ran, jumped, sat)\n"
            "- No dialogue yet"
        )
    elif level in ("E", "F", "G", "H"):
        return (
            "LEVEL-SPECIFIC INSTRUCTIONS:\n"
            "- Clear beginning, middle, and end\n"
            "- Simple dialogue is allowed with speech marks\n"
            "- Vary sentence length and structure\n"
            "- Include descriptive words (big, little, happy, sad)\n"
            "- Characters can have simple emotions and motivations"
        )
    elif level in ("I", "J", "K", "L", "M", "N"):
        return (
            "LEVEL-SPECIFIC INSTRUCTIONS:\n"
            "- Develop characters with distinct personalities\n"
            "- Include a problem and solution\n"
            "- Use varied sentence structures and lengths\n"
            "- Literary language is encouraged\n"
            "- Multiple episodes or events in the story"
        )
    else:
        return (
            "LEVEL-SPECIFIC INSTRUCTIONS:\n"
            "- Write a complete narrative with developed characters\n"
            "- Include themes, conflict, and resolution\n"
            "- Use sophisticated vocabulary naturally\n"
            "- Vary sentence structure for rhythm and effect\n"
            "- The story should challenge and engage the reader"
        )


async def generate_fp_story(topic: str, level_data: dict) -> dict:
    """Generate an F&P leveled story. level_data is a dict from the fp_levels table."""
    template = _read_prompt("fp_story_system.txt")

    vocab = level_data.get("vocabulary_constraints", {})
    if isinstance(vocab, str):
        import json as _json
        vocab = _json.loads(vocab)

    system_prompt = template.format(
        level=level_data["level"],
        grade_range=level_data.get("grade_range", ""),
        min_sentences=level_data["min_sentences"],
        max_sentences=level_data["max_sentences"],
        vocabulary_rules=_build_fp_vocabulary_rules(vocab),
        level_specific_instructions=_build_fp_level_instructions(level_data["level"]),
    )

    user_prompt = f"Write a Level {level_data['level']} story about {topic}."

    content = await _chat(system_prompt, user_prompt)
    result = _parse_json(content)

    # Validate style
    if result.get("style") not in VALID_STYLES:
        logger.warning("Invalid style '%s' from LLM, defaulting to 'cartoon'", result.get("style"))
        result["style"] = "cartoon"

    # For levels A-D, validate vocabulary (retry once if invalid)
    # Allow topic nouns — the topic words themselves are always permitted
    if vocab.get("type") == "sight_words_only":
        allowed = set(w.lower() for w in vocab.get("words", []))
        # Extract simple nouns from the topic so they're allowed
        topic_words = set(re.sub(r"[^\w\s]", "", topic.lower()).split())
        allowed |= topic_words
        sentences = result.get("sentences", [])
        for sent in sentences:
            text = sent.get("text", "") if isinstance(sent, dict) else sent
            words = text.lower().split()
            for w in words:
                clean = re.sub(r"[^\w]", "", w)
                if clean and clean not in allowed:
                    logger.warning("Vocab violation at level %s: '%s' not in allowed list, retrying", level_data["level"], clean)
                    content = await _chat(system_prompt, user_prompt + " IMPORTANT: Use ONLY the allowed sight words plus the topic noun.")
                    result = _parse_json(content)
                    if result.get("style") not in VALID_STYLES:
                        result["style"] = "cartoon"
                    return result

    return result


async def generate_fp_image_prompts(
    story_text: str, style: str, sentences: list[dict], image_support: str
) -> list[dict]:
    """Generate image prompts for an F&P story, adjusting detail by image_support level."""
    template = _read_prompt("fp_image_prompt_system.txt")
    system_prompt = template.format(
        level="",  # not critical for image prompts
        image_support=image_support,
    )

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
