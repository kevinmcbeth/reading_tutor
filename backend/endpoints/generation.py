from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_family
from database import get_pool
from models.api_models import GenerationJobResponse, GenerationLogResponse

router = APIRouter(prefix="/api/generation", tags=["generation"])


def _job_from_row(row) -> GenerationJobResponse:
    return GenerationJobResponse(
        id=row["id"],
        story_id=row["story_id"],
        status=row["status"],
        progress_pct=row["progress_pct"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
        completed_at=str(row["completed_at"]) if row["completed_at"] else None,
    )


@router.get("/jobs", response_model=list[GenerationJobResponse])
async def list_jobs(family_id: int = Depends(get_current_family)):
    pool = get_pool()
    rows = await pool.fetch(
        """SELECT gj.* FROM generation_jobs gj
           JOIN stories s ON gj.story_id = s.id
           WHERE s.family_id = $1
           ORDER BY gj.created_at DESC""",
        family_id,
    )
    return [_job_from_row(r) for r in rows]


@router.get("/jobs/{job_id}", response_model=GenerationJobResponse)
async def get_job(job_id: int, family_id: int = Depends(get_current_family)):
    pool = get_pool()
    row = await pool.fetchrow(
        """SELECT gj.* FROM generation_jobs gj
           JOIN stories s ON gj.story_id = s.id
           WHERE gj.id = $1 AND s.family_id = $2""",
        job_id, family_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_from_row(row)


@router.get("/jobs/{job_id}/logs", response_model=list[GenerationLogResponse])
async def get_job_logs(job_id: int, family_id: int = Depends(get_current_family)):
    pool = get_pool()

    job = await pool.fetchrow(
        """SELECT gj.id FROM generation_jobs gj
           JOIN stories s ON gj.story_id = s.id
           WHERE gj.id = $1 AND s.family_id = $2""",
        job_id, family_id,
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    rows = await pool.fetch(
        "SELECT * FROM generation_logs WHERE job_id = $1 ORDER BY timestamp",
        job_id,
    )
    return [
        GenerationLogResponse(
            id=r["id"],
            level=r["level"],
            message=r["message"],
            timestamp=str(r["timestamp"]) if r["timestamp"] else None,
        )
        for r in rows
    ]


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: int, family_id: int = Depends(get_current_family)):
    """Cancel a running generation job by setting DB status to cancelled.

    The pipeline checks for cancellation at each stage.
    """
    pool = get_pool()

    row = await pool.fetchrow(
        """SELECT gj.* FROM generation_jobs gj
           JOIN stories s ON gj.story_id = s.id
           WHERE gj.id = $1 AND s.family_id = $2""",
        job_id, family_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    if row["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Job is already {row['status']}",
        )

    await pool.execute(
        "UPDATE generation_jobs SET status = 'cancelled' WHERE id = $1",
        job_id,
    )

    return {"detail": "Job cancellation requested"}
