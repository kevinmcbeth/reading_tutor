"""F&P Guided Reading Level endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth import get_current_family
from database import get_pool
from endpoints.stories import _build_story_response, _job_from_row
from models.api_models import (
    FPLevelResponse,
    FPLevelSet,
    FPProgressResponse,
    FPStartRequest,
    FPStoryPrompt,
    GenerationJobResponse,
    StoryResponse,
)

FP_ADVANCE_THRESHOLD = 0.90
FP_ADVANCE_STORIES = 3
FP_DROP_THRESHOLD = 0.70
FP_DROP_STORIES = 3

router = APIRouter(prefix="/api/fp", tags=["fp"])


@router.get("/levels", response_model=list[FPLevelResponse])
async def list_fp_levels(family_id: int = Depends(get_current_family)):
    """List all F&P level definitions."""
    pool = get_pool()
    rows = await pool.fetch("SELECT * FROM fp_levels ORDER BY sort_order")
    return [
        FPLevelResponse(
            id=r["id"],
            level=r["level"],
            sort_order=r["sort_order"],
            grade_range=r["grade_range"],
            min_sentences=r["min_sentences"],
            max_sentences=r["max_sentences"],
            generate_images=r["generate_images"],
            image_support=r["image_support"],
            description=r["description"],
        )
        for r in rows
    ]


@router.get("/stories", response_model=list[StoryResponse])
async def list_fp_stories(
    level: str = Query(...),
    family_id: int = Depends(get_current_family),
):
    """List stories at a specific F&P level."""
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT * FROM stories WHERE fp_level = $1 AND status = 'ready' "
        "AND (family_id = $2 OR family_id IS NULL) ORDER BY created_at DESC",
        level, family_id,
    )
    results = []
    for row in rows:
        results.append(await _build_story_response(pool, row))
    return results


@router.post("/generate", response_model=GenerationJobResponse)
async def generate_fp_story(
    prompt: FPStoryPrompt,
    request: Request,
    family_id: int = Depends(get_current_family),
):
    """Generate a story at a specific F&P level."""
    pool = get_pool()

    # Verify level exists
    level_row = await pool.fetchrow(
        "SELECT * FROM fp_levels WHERE level = $1", prompt.level
    )
    if not level_row:
        raise HTTPException(status_code=400, detail=f"Unknown F&P level: {prompt.level}")

    story_id = await pool.fetchval(
        "INSERT INTO stories (family_id, topic, fp_level, theme, status) "
        "VALUES ($1, $2, $3, $4, 'pending') RETURNING id",
        family_id, prompt.topic, prompt.level, prompt.theme,
    )

    job_id = await pool.fetchval(
        "INSERT INTO generation_jobs (story_id, status) VALUES ($1, 'pending') RETURNING id",
        story_id,
    )

    await request.app.state.arq_redis.enqueue_job(
        "generate_fp_story_task",
        story_id=story_id,
        job_id=job_id,
        topic=prompt.topic,
        fp_level=prompt.level,
        theme=prompt.theme,
    )

    row = await pool.fetchrow("SELECT * FROM generation_jobs WHERE id = $1", job_id)
    return _job_from_row(row)


@router.get("/child/{child_id}/progress", response_model=FPProgressResponse)
async def get_fp_progress(child_id: int, family_id: int = Depends(get_current_family)):
    """Get child's F&P progress at their current level."""
    pool = get_pool()

    child = await pool.fetchrow(
        "SELECT * FROM children WHERE id = $1 AND family_id = $2",
        child_id, family_id,
    )
    if not child:
        raise HTTPException(status_code=403, detail="Child does not belong to your family")

    fp_level = child["fp_level"]
    if not fp_level:
        raise HTTPException(status_code=404, detail="Child has not started leveled reading")

    # Get progress at current level
    progress_rows = await pool.fetch(
        "SELECT * FROM fp_progress WHERE child_id = $1 AND fp_level = $2 "
        "ORDER BY completed_at DESC",
        child_id, fp_level,
    )

    stories_at_level = len(progress_rows)
    stories_passed = sum(1 for r in progress_rows if r["accuracy"] >= FP_ADVANCE_THRESHOLD)
    avg_accuracy = (
        sum(r["accuracy"] for r in progress_rows) / stories_at_level
        if stories_at_level > 0
        else 0.0
    )

    # Check advancement / drop suggestions
    suggest_advance = False
    suggest_drop = False

    if stories_at_level >= FP_ADVANCE_STORIES:
        recent = progress_rows[:FP_ADVANCE_STORIES]
        if all(r["accuracy"] >= FP_ADVANCE_THRESHOLD for r in recent):
            suggest_advance = True

    if stories_at_level >= FP_DROP_STORIES:
        recent = progress_rows[:FP_DROP_STORIES]
        if all(r["accuracy"] < FP_DROP_THRESHOLD for r in recent):
            suggest_drop = True

    return FPProgressResponse(
        child_id=child_id,
        fp_level=fp_level,
        stories_at_level=stories_at_level,
        stories_passed=stories_passed,
        average_accuracy=avg_accuracy,
        suggest_advance=suggest_advance,
        suggest_drop=suggest_drop,
    )


@router.post("/child/{child_id}/level", response_model=dict)
async def set_fp_level(
    child_id: int, data: FPLevelSet, family_id: int = Depends(get_current_family)
):
    """Parent override of child's F&P level."""
    pool = get_pool()

    child = await pool.fetchrow(
        "SELECT * FROM children WHERE id = $1 AND family_id = $2",
        child_id, family_id,
    )
    if not child:
        raise HTTPException(status_code=403, detail="Child does not belong to your family")

    # Verify level exists
    level_row = await pool.fetchrow(
        "SELECT * FROM fp_levels WHERE level = $1", data.level
    )
    if not level_row:
        raise HTTPException(status_code=400, detail=f"Unknown F&P level: {data.level}")

    await pool.execute(
        "UPDATE children SET fp_level = $1, fp_level_set_by = 'parent' WHERE id = $2",
        data.level, child_id,
    )
    return {"detail": f"Level set to {data.level}", "level": data.level}


@router.post("/child/{child_id}/start", response_model=dict)
async def start_fp_mode(
    child_id: int, data: FPStartRequest, family_id: int = Depends(get_current_family)
):
    """Initialize child into leveled reading mode."""
    pool = get_pool()

    child = await pool.fetchrow(
        "SELECT * FROM children WHERE id = $1 AND family_id = $2",
        child_id, family_id,
    )
    if not child:
        raise HTTPException(status_code=403, detail="Child does not belong to your family")

    # Verify level exists
    level_row = await pool.fetchrow(
        "SELECT * FROM fp_levels WHERE level = $1", data.starting_level
    )
    if not level_row:
        raise HTTPException(status_code=400, detail=f"Unknown F&P level: {data.starting_level}")

    await pool.execute(
        "UPDATE children SET fp_level = $1, fp_level_set_by = 'parent' WHERE id = $2",
        data.starting_level, child_id,
    )
    return {"detail": f"Leveled reading started at level {data.starting_level}", "level": data.starting_level}
