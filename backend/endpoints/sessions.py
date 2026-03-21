import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_family
from database import get_pool
from models.api_models import SessionComplete, SessionCreate, SessionResponse

logger = logging.getLogger(__name__)

FP_ADVANCE_THRESHOLD = 0.90
FP_ADVANCE_STORIES = 3
FP_DROP_THRESHOLD = 0.70
FP_DROP_STORIES = 3

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _session_from_row(row) -> SessionResponse:
    return SessionResponse(
        id=row["id"],
        child_id=row["child_id"],
        story_id=row["story_id"],
        attempt_number=row["attempt_number"],
        score=row["score"],
        total_words=row["total_words"],
        completed_at=str(row["completed_at"]) if row["completed_at"] else None,
    )


@router.post("/", response_model=SessionResponse, status_code=201)
async def create_session(
    session: SessionCreate, family_id: int = Depends(get_current_family)
):
    pool = get_pool()

    # Verify child belongs to family
    child = await pool.fetchrow(
        "SELECT id FROM children WHERE id = $1 AND family_id = $2",
        session.child_id, family_id,
    )
    if not child:
        raise HTTPException(status_code=403, detail="Child does not belong to your family")

    # Calculate attempt number
    row = await pool.fetchrow(
        "SELECT COUNT(*) as cnt FROM sessions WHERE child_id = $1 AND story_id = $2",
        session.child_id, session.story_id,
    )
    attempt_number = row["cnt"] + 1

    # Count all words in the story
    row = await pool.fetchrow(
        """SELECT COUNT(*) as cnt FROM story_words
           WHERE sentence_id IN
           (SELECT id FROM story_sentences WHERE story_id = $1)""",
        session.story_id,
    )
    total_words = row["cnt"]

    result = await pool.fetchrow(
        "INSERT INTO sessions (child_id, story_id, attempt_number, total_words) "
        "VALUES ($1, $2, $3, $4) RETURNING *",
        session.child_id, session.story_id, attempt_number, total_words,
    )
    return _session_from_row(result)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: int, family_id: int = Depends(get_current_family)):
    pool = get_pool()
    row = await pool.fetchrow(
        """SELECT s.* FROM sessions s
           JOIN children c ON s.child_id = c.id
           WHERE s.id = $1 AND c.family_id = $2""",
        session_id, family_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_from_row(row)


@router.post("/{session_id}/complete", response_model=SessionResponse)
async def complete_session(
    session_id: int, data: SessionComplete, family_id: int = Depends(get_current_family)
):
    pool = get_pool()

    session_row = await pool.fetchrow(
        """SELECT s.* FROM sessions s
           JOIN children c ON s.child_id = c.id
           WHERE s.id = $1 AND c.family_id = $2""",
        session_id, family_id,
    )
    if not session_row:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_row["completed_at"] is not None:
        raise HTTPException(status_code=400, detail="Session already completed")

    # Validate that all word_ids belong to this session's story
    valid_word_ids = await pool.fetch(
        """SELECT sw.id FROM story_words sw
           JOIN story_sentences ss ON sw.sentence_id = ss.id
           WHERE ss.story_id = $1""",
        session_row["story_id"],
    )
    valid_ids = {r["id"] for r in valid_word_ids}
    submitted_ids = {r.word_id for r in data.results}
    invalid_ids = submitted_ids - valid_ids
    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid word IDs for this story: {sorted(invalid_ids)}",
        )

    score = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            for result in data.results:
                await conn.execute(
                    "INSERT INTO session_words (session_id, word_id, attempts, correct) "
                    "VALUES ($1, $2, $3, $4)",
                    session_id, result.word_id, result.attempts, result.correct,
                )
                if result.correct:
                    score += 1

            now = datetime.now(timezone.utc)
            await conn.execute(
                "UPDATE sessions SET score = $1, completed_at = $2 WHERE id = $3",
                score, now, session_id,
            )

    row = await pool.fetchrow("SELECT * FROM sessions WHERE id = $1", session_id)
    result = _session_from_row(row)

    # F&P progression tracking
    story_row = await pool.fetchrow(
        "SELECT fp_level FROM stories WHERE id = $1", session_row["story_id"]
    )
    if story_row and story_row["fp_level"]:
        fp_level = story_row["fp_level"]
        total_words = session_row["total_words"] or 0
        accuracy = score / total_words if total_words > 0 else 0.0

        # Record progress
        await pool.execute(
            "INSERT INTO fp_progress (child_id, fp_level, story_id, session_id, accuracy) "
            "VALUES ($1, $2, $3, $4, $5)",
            session_row["child_id"], fp_level, session_row["story_id"], session_id, accuracy,
        )

        # Check auto-advancement
        child = await pool.fetchrow(
            "SELECT * FROM children WHERE id = $1", session_row["child_id"]
        )
        if child and child["fp_level"] == fp_level:
            recent = await pool.fetch(
                "SELECT accuracy FROM fp_progress WHERE child_id = $1 AND fp_level = $2 "
                "ORDER BY completed_at DESC LIMIT $3",
                session_row["child_id"], fp_level, FP_ADVANCE_STORIES,
            )
            if (
                len(recent) >= FP_ADVANCE_STORIES
                and all(r["accuracy"] >= FP_ADVANCE_THRESHOLD for r in recent)
            ):
                # Auto-advance to next level
                next_level = await pool.fetchrow(
                    "SELECT level FROM fp_levels WHERE sort_order = "
                    "(SELECT sort_order + 1 FROM fp_levels WHERE level = $1)",
                    fp_level,
                )
                if next_level:
                    await pool.execute(
                        "UPDATE children SET fp_level = $1, fp_level_set_by = 'auto' WHERE id = $2",
                        next_level["level"], session_row["child_id"],
                    )
                    logger.info(
                        "Child %d auto-advanced from %s to %s",
                        session_row["child_id"], fp_level, next_level["level"],
                    )

    return result


@router.get("/child/{child_id}", response_model=list[SessionResponse])
async def list_child_sessions(
    child_id: int, family_id: int = Depends(get_current_family)
):
    pool = get_pool()

    # Verify child belongs to family
    child = await pool.fetchrow(
        "SELECT id FROM children WHERE id = $1 AND family_id = $2",
        child_id, family_id,
    )
    if not child:
        raise HTTPException(status_code=403, detail="Child does not belong to your family")

    rows = await pool.fetch(
        "SELECT * FROM sessions WHERE child_id = $1 ORDER BY id DESC",
        child_id,
    )
    return [_session_from_row(r) for r in rows]
