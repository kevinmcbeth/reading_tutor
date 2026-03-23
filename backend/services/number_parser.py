"""Convert spoken number words to integers (0-9999 range)."""

ONES = {
    "zero": 0, "oh": 0, "o": 0,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}

TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

MULTIPLIERS = {"hundred": 100, "thousand": 1000}


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, normalize whitespace."""
    result = []
    for ch in text.lower():
        if ch.isalnum() or ch == ' ' or ch == '-':
            result.append(ch)
    return ' '.join(''.join(result).split())


def _try_parse_words(words: list[str]) -> int | None:
    """Parse a list of number-word tokens into an integer."""
    if not words:
        return None

    total = 0
    current = 0

    for word in words:
        # Handle hyphenated words like "twenty-three"
        parts = word.split('-')
        for part in parts:
            if part in ONES:
                current += ONES[part]
            elif part in TENS:
                current += TENS[part]
            elif part == "hundred":
                if current == 0:
                    current = 1
                current *= 100
            elif part == "thousand":
                if current == 0:
                    current = 1
                current *= 1000
                total += current
                current = 0
            elif part == "and":
                continue
            else:
                return None  # Unknown word

    total += current
    return total if total >= 0 else None


def _extract_digits(text: str) -> list[int]:
    """Extract all digit sequences from text."""
    results = []
    current = []
    for ch in text:
        if ch.isdigit():
            current.append(ch)
        else:
            if current:
                results.append(int(''.join(current)))
                current = []
    if current:
        results.append(int(''.join(current)))
    return results


def parse_spoken_number(transcript: str) -> list[int]:
    """Parse a spoken number transcript into possible integer values.

    Returns a list of candidate integers extracted from the transcript.
    Tries word-form parsing first, then digit extraction.
    """
    normalized = _normalize(transcript)
    candidates = []

    # Try parsing the whole thing as word-form numbers
    words = normalized.split()
    parsed = _try_parse_words(words)
    if parsed is not None:
        candidates.append(parsed)

    # Extract any raw digits
    digits = _extract_digits(normalized)
    for d in digits:
        if d not in candidates:
            candidates.append(d)

    # Also try parsing without "and" and common filler words
    filtered = [w for w in words if w not in ("and", "is", "equals", "the", "answer")]
    if filtered != words:
        parsed2 = _try_parse_words(filtered)
        if parsed2 is not None and parsed2 not in candidates:
            candidates.append(parsed2)

    return candidates


def check_answer(correct_answer: int, transcript: str, alternatives: list[str] | None = None) -> bool:
    """Check if any transcript (including alternatives) matches the correct answer."""
    all_transcripts = [transcript]
    if alternatives:
        all_transcripts.extend(alternatives)

    for t in all_transcripts:
        candidates = parse_spoken_number(t)
        if correct_answer in candidates:
            return True

    return False
