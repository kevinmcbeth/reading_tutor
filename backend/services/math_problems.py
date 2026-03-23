"""Generate math problems by subject and grade level.

Arithmetic problems are generated algorithmically with grade-appropriate
number ranges. Word problems will use LLM generation (future).
"""

import json
import random

# Grade-level ranges for operands
# grade_level: 0=K, 1=1st, 2=2nd, 3=3rd, 4=4th

ADDITION_RANGES = {
    0: (0, 5),       # K: within 5
    1: (0, 20),      # 1st: within 20
    2: (0, 100),     # 2nd: two-digit
    3: (0, 1000),    # 3rd: three-digit
    4: (0, 10000),   # 4th: four-digit
}

SUBTRACTION_RANGES = {
    0: (0, 5),
    1: (0, 20),
    2: (0, 100),
    3: (0, 1000),
    4: (0, 10000),
}

MULTIPLICATION_RANGES = {
    2: (1, 5),       # 2nd: easy times tables
    3: (1, 10),      # 3rd: full times tables
    4: (1, 12),      # 4th: extended tables + two-digit
}

DIVISION_RANGES = {
    2: (1, 5),       # 2nd: divide by small numbers
    3: (1, 10),      # 3rd: standard division facts
    4: (1, 12),      # 4th: larger divisors
}

SUBJECTS = {
    "addition": {
        "display_name": "Addition",
        "emoji": "+",
        "grades": [0, 1, 2, 3, 4],
        "input_mode": "speech",
        "description": "Practice adding numbers",
    },
    "subtraction": {
        "display_name": "Subtraction",
        "emoji": "-",
        "grades": [0, 1, 2, 3, 4],
        "input_mode": "speech",
        "description": "Practice subtracting numbers",
    },
    "multiplication": {
        "display_name": "Multiplication",
        "emoji": "\u00d7",
        "grades": [2, 3, 4],
        "input_mode": "speech",
        "description": "Practice multiplying numbers",
    },
    "division": {
        "display_name": "Division",
        "emoji": "\u00f7",
        "grades": [2, 3, 4],
        "input_mode": "speech",
        "description": "Practice dividing numbers",
    },
    "word_problems": {
        "display_name": "Word Problems",
        "emoji": "W",
        "grades": [1, 2, 3, 4],
        "input_mode": "speech",
        "description": "Solve math stories",
        "coming_soon": True,
    },
    "counting": {
        "display_name": "Counting & Numbers",
        "emoji": "#",
        "grades": [0, 1],
        "input_mode": "tap",
        "description": "Count objects and recognize numbers",
        "coming_soon": True,
    },
    "comparison": {
        "display_name": "Comparison & Ordering",
        "emoji": "<>",
        "grades": [0, 1],
        "input_mode": "tap",
        "description": "Greater than, less than, ordering",
        "coming_soon": True,
    },
    "patterns": {
        "display_name": "Patterns & Sequences",
        "emoji": "~",
        "grades": [0, 1, 2],
        "input_mode": "tap",
        "description": "Complete patterns and sequences",
        "coming_soon": True,
    },
    "place_value": {
        "display_name": "Place Value",
        "emoji": "P",
        "grades": [1, 2, 3, 4],
        "input_mode": "tap",
        "description": "Understand tens, hundreds, thousands",
        "coming_soon": True,
    },
    "time": {
        "display_name": "Time",
        "emoji": "T",
        "grades": [1, 2, 3],
        "input_mode": "tap",
        "description": "Read clocks and tell time",
        "coming_soon": True,
    },
    "money": {
        "display_name": "Money",
        "emoji": "$",
        "grades": [2, 3],
        "input_mode": "tap",
        "description": "Count coins and make change",
        "coming_soon": True,
    },
    "measurement": {
        "display_name": "Measurement",
        "emoji": "M",
        "grades": [1, 2, 3, 4],
        "input_mode": "tap",
        "description": "Length, weight, and capacity",
        "coming_soon": True,
    },
    "fractions": {
        "display_name": "Fractions",
        "emoji": "F",
        "grades": [2, 3, 4],
        "input_mode": "tap",
        "description": "Understand and work with fractions",
        "coming_soon": True,
    },
    "geometry": {
        "display_name": "Geometry",
        "emoji": "G",
        "grades": [0, 1, 2, 3, 4],
        "input_mode": "tap",
        "description": "Shapes, angles, and spatial thinking",
        "coming_soon": True,
    },
}

GRADE_NAMES = {0: "K", 1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}


def _generate_addition(grade_level: int, recent_problems: list[dict] | None = None) -> dict:
    lo, hi = ADDITION_RANGES.get(grade_level, (0, 10))
    recent_pairs = set()
    if recent_problems:
        for p in recent_problems:
            d = p.get("problem_data", {})
            if isinstance(d, str):
                d = json.loads(d)
            recent_pairs.add((d.get("a"), d.get("b")))

    for _ in range(50):
        a = random.randint(lo, hi)
        b = random.randint(lo, hi)
        if (a, b) not in recent_pairs and (b, a) not in recent_pairs:
            break

    answer = a + b
    return {
        "problem_type": "addition",
        "problem_data": {"a": a, "b": b, "operation": "+"},
        "correct_answer": str(answer),
        "display": f"{a} + {b} = ?",
    }


def _generate_subtraction(grade_level: int, recent_problems: list[dict] | None = None) -> dict:
    lo, hi = SUBTRACTION_RANGES.get(grade_level, (0, 10))
    recent_pairs = set()
    if recent_problems:
        for p in recent_problems:
            d = p.get("problem_data", {})
            if isinstance(d, str):
                d = json.loads(d)
            recent_pairs.add((d.get("a"), d.get("b")))

    for _ in range(50):
        a = random.randint(lo, hi)
        b = random.randint(lo, a)  # Ensure non-negative result
        if (a, b) not in recent_pairs:
            break

    answer = a - b
    return {
        "problem_type": "subtraction",
        "problem_data": {"a": a, "b": b, "operation": "-"},
        "correct_answer": str(answer),
        "display": f"{a} - {b} = ?",
    }


def _generate_multiplication(grade_level: int, recent_problems: list[dict] | None = None) -> dict:
    lo, hi = MULTIPLICATION_RANGES.get(grade_level, (1, 10))
    recent_pairs = set()
    if recent_problems:
        for p in recent_problems:
            d = p.get("problem_data", {})
            if isinstance(d, str):
                d = json.loads(d)
            recent_pairs.add((d.get("a"), d.get("b")))

    for _ in range(50):
        a = random.randint(lo, hi)
        b = random.randint(lo, hi)
        # Grade 4: occasionally use two-digit x one-digit
        if grade_level == 4 and random.random() < 0.3:
            a = random.randint(10, 99)
            b = random.randint(2, 9)
        if (a, b) not in recent_pairs and (b, a) not in recent_pairs:
            break

    answer = a * b
    return {
        "problem_type": "multiplication",
        "problem_data": {"a": a, "b": b, "operation": "\u00d7"},
        "correct_answer": str(answer),
        "display": f"{a} \u00d7 {b} = ?",
    }


def _generate_division(grade_level: int, recent_problems: list[dict] | None = None) -> dict:
    lo, hi = DIVISION_RANGES.get(grade_level, (1, 10))
    recent_pairs = set()
    if recent_problems:
        for p in recent_problems:
            d = p.get("problem_data", {})
            if isinstance(d, str):
                d = json.loads(d)
            recent_pairs.add((d.get("a"), d.get("b")))

    for _ in range(50):
        divisor = random.randint(max(lo, 1), hi)
        if grade_level == 4 and random.random() < 0.2:
            # Grade 4: two-digit dividends with possible remainders
            dividend = random.randint(divisor, divisor * 12)
            # For now, keep whole-number results
            dividend = divisor * (dividend // divisor)
        else:
            quotient = random.randint(0 if grade_level < 2 else 1, hi)
            dividend = divisor * quotient
        if (dividend, divisor) not in recent_pairs:
            break

    answer = dividend // divisor
    return {
        "problem_type": "division",
        "problem_data": {"a": dividend, "b": divisor, "operation": "\u00f7"},
        "correct_answer": str(answer),
        "display": f"{dividend} \u00f7 {divisor} = ?",
    }


GENERATORS = {
    "addition": _generate_addition,
    "subtraction": _generate_subtraction,
    "multiplication": _generate_multiplication,
    "division": _generate_division,
}


def generate_problem(subject: str, grade_level: int, recent_problems: list[dict] | None = None) -> dict:
    """Generate a single math problem for the given subject and grade level.

    Returns a dict with: problem_type, problem_data, correct_answer, display
    """
    generator = GENERATORS.get(subject)
    if not generator:
        raise ValueError(f"No generator for subject: {subject}")

    subject_info = SUBJECTS.get(subject)
    if subject_info and grade_level not in subject_info["grades"]:
        raise ValueError(f"Grade {grade_level} not available for {subject}")

    return generator(grade_level, recent_problems)


def get_subjects() -> list[dict]:
    """Return all subjects with metadata."""
    result = []
    for key, info in SUBJECTS.items():
        result.append({
            "subject": key,
            "display_name": info["display_name"],
            "emoji": info["emoji"],
            "grades": info["grades"],
            "grade_names": [GRADE_NAMES[g] for g in info["grades"]],
            "input_mode": info["input_mode"],
            "description": info["description"],
            "coming_soon": info.get("coming_soon", False),
        })
    return result
