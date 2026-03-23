"""Math practice module endpoints."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from auth import get_current_family
from database import get_pool
from services.math_problems import generate_problem, get_subjects

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/math", tags=["math"])


async def _verify_child_ownership(pool, child_id: int, family_id: int):
    row = await pool.fetchrow(
        "SELECT id FROM children WHERE id = $1 AND family_id = $2",
        child_id, family_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Child not found")


# --- Pydantic models ---

class MathSessionCreate(BaseModel):
    child_id: int
    subject: str


class MathAnswerSubmit(BaseModel):
    answer: str
    transcript: Optional[str] = None
    alternatives: Optional[list[str]] = None


class MathExchangeRateUpdate(BaseModel):
    math_problems_per_coin: int
    child_id: Optional[int] = None


class MathGradeLevelSet(BaseModel):
    grade_level: int


# --- Subject listing ---

@router.get("/subjects")
async def list_subjects():
    return get_subjects()


# --- Progress ---

@router.get("/progress/{child_id}")
async def get_progress(
    child_id: int,
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    await _verify_child_ownership(pool, child_id, family_id)

    rows = await pool.fetch(
        "SELECT * FROM math_progress WHERE child_id = $1 ORDER BY subject",
        child_id,
    )
    return [
        {
            "subject": r["subject"],
            "grade_level": r["grade_level"],
            "problems_attempted": r["problems_attempted"],
            "problems_correct": r["problems_correct"],
            "streak": r["streak"],
            "best_streak": r["best_streak"],
            "accuracy": round(r["problems_correct"] / max(r["problems_attempted"], 1) * 100, 1),
            "set_by": r["set_by"],
        }
        for r in rows
    ]


@router.put("/progress/{child_id}/{subject}")
async def set_grade_level(
    child_id: int,
    subject: str,
    body: MathGradeLevelSet,
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    await _verify_child_ownership(pool, child_id, family_id)

    if body.grade_level < 0 or body.grade_level > 4:
        raise HTTPException(status_code=400, detail="Grade level must be 0-4")

    subjects = get_subjects()
    valid_subjects = {s["subject"] for s in subjects}
    if subject not in valid_subjects:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject}")

    await pool.execute(
        """INSERT INTO math_progress (child_id, subject, grade_level, set_by)
           VALUES ($1, $2, $3, 'parent')
           ON CONFLICT (child_id, subject) DO UPDATE
           SET grade_level = $3, set_by = 'parent', updated_at = NOW()""",
        child_id, subject, body.grade_level,
    )
    return {"child_id": child_id, "subject": subject, "grade_level": body.grade_level}


# --- Sessions ---

@router.post("/sessions")
async def start_session(
    body: MathSessionCreate,
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    await _verify_child_ownership(pool, body.child_id, family_id)

    subjects = get_subjects()
    subject_info = next((s for s in subjects if s["subject"] == body.subject), None)
    if not subject_info:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {body.subject}")
    if subject_info.get("coming_soon"):
        raise HTTPException(status_code=400, detail=f"{body.subject} is coming soon")

    # Get or create progress record to find grade level
    progress = await pool.fetchrow(
        "SELECT grade_level FROM math_progress WHERE child_id = $1 AND subject = $2",
        body.child_id, body.subject,
    )
    grade_level = progress["grade_level"] if progress else subject_info["grades"][0]

    row = await pool.fetchrow(
        """INSERT INTO math_sessions (child_id, subject, grade_level)
           VALUES ($1, $2, $3) RETURNING *""",
        body.child_id, body.subject, grade_level,
    )

    # Ensure progress record exists
    await pool.execute(
        """INSERT INTO math_progress (child_id, subject, grade_level)
           VALUES ($1, $2, $3)
           ON CONFLICT (child_id, subject) DO NOTHING""",
        body.child_id, body.subject, grade_level,
    )

    return {
        "id": row["id"],
        "child_id": row["child_id"],
        "subject": row["subject"],
        "grade_level": row["grade_level"],
        "started_at": str(row["started_at"]) if row["started_at"] else None,
    }


@router.post("/sessions/{session_id}/problem")
async def next_problem(
    session_id: int,
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    session = await pool.fetchrow(
        """SELECT ms.*, c.family_id FROM math_sessions ms
           JOIN children c ON c.id = ms.child_id
           WHERE ms.id = $1""",
        session_id,
    )
    if not session or session["family_id"] != family_id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["completed_at"]:
        raise HTTPException(status_code=400, detail="Session already completed")

    # Get recent problems to avoid repeats
    recent = await pool.fetch(
        """SELECT problem_data, correct_answer FROM math_problems
           WHERE session_id = $1 ORDER BY answered_at DESC LIMIT 5""",
        session_id,
    )
    recent_problems = []
    for r in recent:
        data = r["problem_data"]
        if isinstance(data, str):
            data = json.loads(data)
        recent_problems.append({"problem_data": data, "correct_answer": r["correct_answer"]})

    problem = generate_problem(session["subject"], session["grade_level"], recent_problems)

    # Store the problem
    row = await pool.fetchrow(
        """INSERT INTO math_problems (session_id, problem_type, problem_data, correct_answer)
           VALUES ($1, $2, $3, $4) RETURNING id""",
        session_id, problem["problem_type"],
        json.dumps(problem["problem_data"]), problem["correct_answer"],
    )

    # Count total problems in this session (including the one just inserted)
    problem_count = await pool.fetchval(
        "SELECT COUNT(*) FROM math_problems WHERE session_id = $1", session_id
    )

    return {
        "problem_id": row["id"],
        "display": problem["display"],
        "problem_data": problem["problem_data"],
        "problem_number": int(problem_count),
    }


@router.post("/sessions/{session_id}/answer")
async def submit_answer(
    session_id: int,
    body: MathAnswerSubmit,
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    session = await pool.fetchrow(
        """SELECT ms.*, c.family_id FROM math_sessions ms
           JOIN children c ON c.id = ms.child_id
           WHERE ms.id = $1""",
        session_id,
    )
    if not session or session["family_id"] != family_id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["completed_at"]:
        raise HTTPException(status_code=400, detail="Session already completed")

    # Get the most recent unanswered problem
    problem = await pool.fetchrow(
        """SELECT * FROM math_problems
           WHERE session_id = $1 AND child_answer IS NULL
           ORDER BY id DESC LIMIT 1""",
        session_id,
    )
    if not problem:
        raise HTTPException(status_code=400, detail="No pending problem")

    # Check answer - try direct match and number parsing
    from services.number_parser import check_answer

    correct_value = int(problem["correct_answer"])
    is_correct = False

    # Direct string match
    if body.answer.strip() == problem["correct_answer"]:
        is_correct = True
    else:
        # Try number parsing on the answer itself
        all_transcripts = [body.answer]
        if body.transcript:
            all_transcripts.append(body.transcript)
        if body.alternatives:
            all_transcripts.extend(body.alternatives)
        is_correct = check_answer(correct_value, body.answer, all_transcripts)

    await pool.execute(
        """UPDATE math_problems SET child_answer = $1, correct = $2, answered_at = NOW()
           WHERE id = $3""",
        body.answer, is_correct, problem["id"],
    )

    return {
        "correct": is_correct,
        "correct_answer": problem["correct_answer"],
        "child_answer": body.answer,
        "problem_id": problem["id"],
    }


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: int,
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    session = await pool.fetchrow(
        """SELECT ms.*, c.family_id FROM math_sessions ms
           JOIN children c ON c.id = ms.child_id
           WHERE ms.id = $1""",
        session_id,
    )
    if not session or session["family_id"] != family_id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["completed_at"]:
        raise HTTPException(status_code=400, detail="Session already completed")

    # Count results
    stats = await pool.fetchrow(
        """SELECT COUNT(*) as total,
                  COALESCE(SUM(CASE WHEN correct THEN 1 ELSE 0 END), 0) as correct_count
           FROM math_problems WHERE session_id = $1""",
        session_id,
    )
    total = int(stats["total"])
    correct_count = int(stats["correct_count"])

    # Update session
    await pool.execute(
        """UPDATE math_sessions
           SET problems_attempted = $1, problems_correct = $2, completed_at = NOW()
           WHERE id = $3""",
        total, correct_count, session_id,
    )

    # Update progress
    child_id = session["child_id"]
    subject = session["subject"]

    progress = await pool.fetchrow(
        "SELECT * FROM math_progress WHERE child_id = $1 AND subject = $2",
        child_id, subject,
    )

    new_attempted = (progress["problems_attempted"] if progress else 0) + total
    new_correct = (progress["problems_correct"] if progress else 0) + correct_count
    old_streak = progress["streak"] if progress else 0
    old_best = progress["best_streak"] if progress else 0

    # Streak: if all correct in session, add to streak; otherwise reset
    if total > 0 and correct_count == total:
        new_streak = old_streak + total
    else:
        new_streak = 0
    new_best = max(old_best, new_streak)

    # Progression logic
    current_grade = progress["grade_level"] if progress else session["grade_level"]
    set_by = progress["set_by"] if progress else "auto"
    parent_floor = current_grade if set_by == "parent" else 0
    advanced = False

    if new_attempted >= 10:
        # Check accuracy over last 20 problems
        recent_accuracy_row = await pool.fetchrow(
            """SELECT COUNT(*) as total,
                      COALESCE(SUM(CASE WHEN correct THEN 1 ELSE 0 END), 0) as correct_count
               FROM (
                   SELECT mp.correct
                   FROM math_problems mp
                   JOIN math_sessions ms ON ms.id = mp.session_id
                   WHERE ms.child_id = $1 AND ms.subject = $2 AND mp.child_answer IS NOT NULL
                   ORDER BY mp.answered_at DESC
                   LIMIT 20
               ) recent""",
            child_id, subject,
        )
        recent_total = int(recent_accuracy_row["total"]) if recent_accuracy_row else 0
        recent_correct = int(recent_accuracy_row["correct_count"]) if recent_accuracy_row else 0

        if recent_total >= 10:
            recent_accuracy = recent_correct / recent_total
            if recent_accuracy >= 0.8 and current_grade < 4:
                current_grade += 1
                advanced = True
            elif recent_accuracy < 0.5 and current_grade > parent_floor:
                current_grade -= 1

    await pool.execute(
        """INSERT INTO math_progress (child_id, subject, grade_level, problems_attempted,
               problems_correct, streak, best_streak, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
           ON CONFLICT (child_id, subject) DO UPDATE
           SET grade_level = $3, problems_attempted = $4, problems_correct = $5,
               streak = $6, best_streak = $7, updated_at = NOW()""",
        child_id, subject, current_grade, new_attempted, new_correct, new_streak, new_best,
    )

    accuracy = round(correct_count / max(total, 1) * 100, 1)

    return {
        "session_id": session_id,
        "subject": subject,
        "problems_attempted": total,
        "problems_correct": correct_count,
        "accuracy": accuracy,
        "streak": new_streak,
        "best_streak": new_best,
        "grade_level": current_grade,
        "advanced": advanced,
        "perfect": total > 0 and correct_count == total,
    }


# --- Coin Integration ---

async def _get_math_exchange_rate(pool, child_id: int, family_id: int) -> int:
    child_rate = await pool.fetchval(
        "SELECT math_problems_per_coin FROM children WHERE id = $1", child_id
    )
    if child_rate is not None:
        return child_rate
    family_rate = await pool.fetchval(
        "SELECT math_problems_per_coin FROM families WHERE id = $1", family_id
    )
    return family_rate or 20


async def _get_math_problem_balance(pool, child_id: int) -> tuple[int, int]:
    """Return (total_problems_correct, total_problems_converted)."""
    earned = await pool.fetchval(
        """SELECT COALESCE(SUM(problems_correct), 0) FROM math_sessions
           WHERE child_id = $1 AND completed_at IS NOT NULL""",
        child_id,
    )
    converted = await pool.fetchval(
        "SELECT COALESCE(SUM(problems_spent), 0) FROM math_coin_conversions WHERE child_id = $1",
        child_id,
    )
    return int(earned), int(converted)


@router.get("/balance/{child_id}")
async def get_math_balance(
    child_id: int,
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    await _verify_child_ownership(pool, child_id, family_id)

    problems_earned, problems_converted = await _get_math_problem_balance(pool, child_id)
    rate = await _get_math_exchange_rate(pool, child_id, family_id)

    return {
        "child_id": child_id,
        "problems_available": problems_earned - problems_converted,
        "math_problems_per_coin": rate,
        "coins_convertible": (problems_earned - problems_converted) // rate if rate > 0 else 0,
    }


@router.post("/convert/{child_id}")
async def convert_math_to_coins(
    child_id: int,
    coins: int = Query(..., ge=1, description="Number of coins to buy"),
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    await _verify_child_ownership(pool, child_id, family_id)

    rate = await _get_math_exchange_rate(pool, child_id, family_id)
    problems_needed = coins * rate

    problems_earned, problems_converted = await _get_math_problem_balance(pool, child_id)
    problems_available = problems_earned - problems_converted

    if problems_available < problems_needed:
        max_coins = problems_available // rate
        raise HTTPException(
            status_code=400,
            detail=f"Not enough problems. Need {problems_needed}, have {problems_available}. Max coins: {max_coins}.",
        )

    # Insert into math_coin_conversions
    await pool.execute(
        "INSERT INTO math_coin_conversions (child_id, problems_spent, coins_earned) VALUES ($1, $2, $3)",
        child_id, problems_needed, coins,
    )

    # Also insert into shared coin_conversions so coins appear in reward shop
    await pool.execute(
        "INSERT INTO coin_conversions (child_id, words_spent, coins_earned) VALUES ($1, 0, $2)",
        child_id, coins,
    )

    return {
        "detail": f"Converted {problems_needed} math problems into {coins} coins",
        "problems_spent": problems_needed,
        "coins_earned": coins,
        "problems_remaining": problems_available - problems_needed,
    }


# --- Exchange rate ---

@router.get("/exchange-rate")
async def get_math_exchange_rate(family_id: int = Depends(get_current_family)):
    pool = get_pool()
    family_rate = await pool.fetchval(
        "SELECT math_problems_per_coin FROM families WHERE id = $1", family_id
    )
    children = await pool.fetch(
        "SELECT id, name, math_problems_per_coin FROM children WHERE family_id = $1 ORDER BY name",
        family_id,
    )
    return {
        "family_rate": family_rate or 20,
        "children": [
            {"child_id": c["id"], "name": c["name"], "math_problems_per_coin": c["math_problems_per_coin"]}
            for c in children
        ],
    }


@router.put("/exchange-rate")
async def set_math_exchange_rate(
    body: MathExchangeRateUpdate,
    family_id: int = Depends(get_current_family),
):
    if body.math_problems_per_coin < 1 or body.math_problems_per_coin > 10000:
        raise HTTPException(status_code=400, detail="Rate must be between 1 and 10,000")
    pool = get_pool()

    if body.child_id is not None:
        await _verify_child_ownership(pool, body.child_id, family_id)
        await pool.execute(
            "UPDATE children SET math_problems_per_coin = $1 WHERE id = $2",
            body.math_problems_per_coin, body.child_id,
        )
        return {"child_id": body.child_id, "math_problems_per_coin": body.math_problems_per_coin}
    else:
        await pool.execute(
            "UPDATE families SET math_problems_per_coin = $1 WHERE id = $2",
            body.math_problems_per_coin, family_id,
        )
        return {"math_problems_per_coin": body.math_problems_per_coin}
