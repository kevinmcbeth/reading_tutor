from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth import get_current_family
from database import get_pool
from models.api_models import (
    BatchPrompt,
    DEFAULT_PAGE_LIMIT,
    GenerationJobResponse,
    MAX_PAGE_LIMIT,
    MetaPrompt,
    SentenceResponse,
    StoryPrompt,
    StoryResponse,
    WordResponse,
)
from rate_limit import check_rate_limit

router = APIRouter(prefix="/api/stories", tags=["stories"])


async def _build_story_response(pool, story_row) -> StoryResponse:
    """Build a full StoryResponse with sentences and words in 2 queries."""
    story_id = story_row["id"]

    sentence_rows = await pool.fetch(
        "SELECT * FROM story_sentences WHERE story_id = $1 ORDER BY idx",
        story_id,
    )

    if not sentence_rows:
        return StoryResponse(
            id=story_id,
            title=story_row["title"],
            topic=story_row["topic"],
            difficulty=story_row["difficulty"],
            theme=story_row["theme"],
            style=story_row["style"],
            status=story_row["status"],
            sentences=[],
        )

    sentence_ids = [s["id"] for s in sentence_rows]

    # Fetch all words for all sentences in one query
    word_rows = await pool.fetch(
        "SELECT * FROM story_words WHERE sentence_id = ANY($1) ORDER BY sentence_id, idx",
        sentence_ids,
    )

    # Group words by sentence_id
    words_by_sentence: dict[int, list] = defaultdict(list)
    for w in word_rows:
        words_by_sentence[w["sentence_id"]].append(
            WordResponse(
                id=w["id"],
                idx=w["idx"],
                text=w["text"],
                has_audio=w["has_audio"],
                is_challenge_word=w["is_challenge_word"],
            )
        )

    sentences = [
        SentenceResponse(
            id=s["id"],
            idx=s["idx"],
            text=s["text"],
            image_path=s["image_path"],
            has_image=s["has_image"],
            words=words_by_sentence.get(s["id"], []),
        )
        for s in sentence_rows
    ]

    return StoryResponse(
        id=story_id,
        title=story_row["title"],
        topic=story_row["topic"],
        difficulty=story_row["difficulty"],
        theme=story_row["theme"],
        style=story_row["style"],
        fp_level=story_row.get("fp_level"),
        status=story_row["status"],
        sentences=sentences,
    )


async def _build_story_responses_batch(pool, story_rows) -> list[StoryResponse]:
    """Build StoryResponses for multiple stories in 2 bulk queries (not N+1)."""
    if not story_rows:
        return []

    story_ids = [r["id"] for r in story_rows]

    # Bulk fetch all sentences
    all_sentences = await pool.fetch(
        "SELECT * FROM story_sentences WHERE story_id = ANY($1) ORDER BY story_id, idx",
        story_ids,
    )

    if not all_sentences:
        return [
            StoryResponse(
                id=r["id"], title=r["title"], topic=r["topic"],
                difficulty=r["difficulty"], theme=r["theme"],
                style=r["style"], status=r["status"], sentences=[],
            )
            for r in story_rows
        ]

    sentence_ids = [s["id"] for s in all_sentences]

    # Bulk fetch all words
    all_words = await pool.fetch(
        "SELECT * FROM story_words WHERE sentence_id = ANY($1) ORDER BY sentence_id, idx",
        sentence_ids,
    )

    # Group words by sentence_id
    words_by_sentence: dict[int, list] = defaultdict(list)
    for w in all_words:
        words_by_sentence[w["sentence_id"]].append(
            WordResponse(
                id=w["id"], idx=w["idx"], text=w["text"],
                has_audio=w["has_audio"], is_challenge_word=w["is_challenge_word"],
            )
        )

    # Group sentences by story_id
    sentences_by_story: dict[int, list] = defaultdict(list)
    for s in all_sentences:
        sentences_by_story[s["story_id"]].append(
            SentenceResponse(
                id=s["id"], idx=s["idx"], text=s["text"],
                image_path=s["image_path"], has_image=s["has_image"],
                words=words_by_sentence.get(s["id"], []),
            )
        )

    return [
        StoryResponse(
            id=r["id"], title=r["title"], topic=r["topic"],
            difficulty=r["difficulty"], theme=r["theme"],
            style=r["style"], status=r["status"],
            sentences=sentences_by_story.get(r["id"], []),
        )
        for r in story_rows
    ]


def _job_from_row(row) -> GenerationJobResponse:
    return GenerationJobResponse(
        id=row["id"],
        story_id=row["story_id"],
        status=row["status"],
        progress_pct=row["progress_pct"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
        completed_at=str(row["completed_at"]) if row["completed_at"] else None,
    )


@router.get("", response_model=list[StoryResponse])
async def list_stories(
    difficulty: Optional[str] = Query(None),
    theme: Optional[str] = Query(None),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(0, ge=0),
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()

    query = "SELECT * FROM stories WHERE (family_id = $1 OR family_id IS NULL) AND status = 'ready'"
    params: list = [family_id]
    idx = 2
    if difficulty:
        query += f" AND difficulty = ${idx}"
        params.append(difficulty)
        idx += 1
    if theme:
        query += f" AND theme = ${idx}"
        params.append(theme)
        idx += 1
    query += f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
    params.extend([limit, offset])

    rows = await pool.fetch(query, *params)
    return await _build_story_responses_batch(pool, rows)


@router.get("/{story_id}", response_model=StoryResponse)
async def get_story(story_id: int, family_id: int = Depends(get_current_family)):
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM stories WHERE id = $1 AND (family_id = $2 OR family_id IS NULL)",
        story_id, family_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Story not found")
    return await _build_story_response(pool, row)


@router.post("/generate", response_model=GenerationJobResponse)
async def generate_story(
    prompt: StoryPrompt,
    request: Request,
    family_id: int = Depends(get_current_family),
):
    await check_rate_limit(request.app.state.redis, family_id, "generation", 10, 3600)

    pool = get_pool()

    story_id = await pool.fetchval(
        "INSERT INTO stories (family_id, topic, difficulty, theme, status) "
        "VALUES ($1, $2, $3, $4, 'pending') RETURNING id",
        family_id, prompt.topic, prompt.difficulty.value, prompt.theme,
    )

    job_id = await pool.fetchval(
        "INSERT INTO generation_jobs (story_id, status) VALUES ($1, 'pending') RETURNING id",
        story_id,
    )

    # Enqueue to arq worker
    await request.app.state.arq_redis.enqueue_job(
        "generate_story_task",
        story_id=story_id,
        job_id=job_id,
        topic=prompt.topic,
        difficulty=prompt.difficulty.value,
        theme=prompt.theme,
    )

    row = await pool.fetchrow(
        "SELECT * FROM generation_jobs WHERE id = $1", job_id
    )
    return _job_from_row(row)


@router.post("/generate/batch", response_model=list[GenerationJobResponse])
async def generate_batch(
    batch: BatchPrompt,
    request: Request,
    family_id: int = Depends(get_current_family),
):
    await check_rate_limit(request.app.state.redis, family_id, "generation", 10, 3600)

    pool = get_pool()
    jobs = []

    for prompt in batch.prompts:
        story_id = await pool.fetchval(
            "INSERT INTO stories (family_id, topic, difficulty, theme, status) "
            "VALUES ($1, $2, $3, $4, 'pending') RETURNING id",
            family_id, prompt.topic, prompt.difficulty.value, prompt.theme,
        )

        job_id = await pool.fetchval(
            "INSERT INTO generation_jobs (story_id, status) VALUES ($1, 'pending') RETURNING id",
            story_id,
        )

        # Enqueue each to arq worker
        await request.app.state.arq_redis.enqueue_job(
            "generate_story_task",
            story_id=story_id,
            job_id=job_id,
            topic=prompt.topic,
            difficulty=prompt.difficulty.value,
            theme=prompt.theme,
        )

        row = await pool.fetchrow(
            "SELECT * FROM generation_jobs WHERE id = $1", job_id
        )
        jobs.append(_job_from_row(row))

    return jobs


@router.post("/generate/meta", response_model=list[GenerationJobResponse])
async def generate_meta(
    meta: MetaPrompt,
    request: Request,
    family_id: int = Depends(get_current_family),
):
    await check_rate_limit(request.app.state.redis, family_id, "generation", 10, 3600)

    pool = get_pool()

    # Create a placeholder job for tracking the meta generation
    story_id = await pool.fetchval(
        "INSERT INTO stories (family_id, topic, difficulty, status) "
        "VALUES ($1, $2, 'easy', 'pending') RETURNING id",
        family_id, meta.description,
    )

    job_id = await pool.fetchval(
        "INSERT INTO generation_jobs (story_id, status) VALUES ($1, 'pending') RETURNING id",
        story_id,
    )

    # For meta generation, we still use arq but the task handles generating
    # prompts first, then running batch generation
    await request.app.state.arq_redis.enqueue_job(
        "generate_story_task",
        story_id=story_id,
        job_id=job_id,
        topic=meta.description,
        difficulty="easy",
        theme=None,
    )

    row = await pool.fetchrow(
        "SELECT * FROM generation_jobs WHERE id = $1", job_id
    )
    return [_job_from_row(row)]


@router.delete("/{story_id}")
async def delete_story(story_id: int, family_id: int = Depends(get_current_family)):
    pool = get_pool()

    row = await pool.fetchrow(
        "SELECT * FROM stories WHERE id = $1 AND family_id = $2",
        story_id, family_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Story not found")

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Delete session data
            await conn.execute(
                """DELETE FROM session_words WHERE session_id IN
                   (SELECT id FROM sessions WHERE story_id = $1)""",
                story_id,
            )
            await conn.execute(
                "DELETE FROM sessions WHERE story_id = $1", story_id
            )
            # Delete story words and sentences
            await conn.execute(
                """DELETE FROM story_words WHERE sentence_id IN
                   (SELECT id FROM story_sentences WHERE story_id = $1)""",
                story_id,
            )
            await conn.execute(
                "DELETE FROM story_sentences WHERE story_id = $1", story_id
            )
            # Delete generation data
            await conn.execute(
                "DELETE FROM generation_logs WHERE job_id IN "
                "(SELECT id FROM generation_jobs WHERE story_id = $1)",
                story_id,
            )
            await conn.execute(
                "DELETE FROM generation_jobs WHERE story_id = $1", story_id
            )
            await conn.execute("DELETE FROM stories WHERE id = $1", story_id)

    return {"detail": "Story deleted"}
