from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_family
from database import get_pool
from models.api_models import (
    ChildCreate,
    ChildResponse,
    DEFAULT_PAGE_LIMIT,
    LeaderboardEntry,
    MAX_PAGE_LIMIT,
)

router = APIRouter(prefix="/api/children", tags=["children"])


def _child_from_row(row) -> ChildResponse:
    return ChildResponse(
        id=row["id"],
        name=row["name"],
        avatar=row["avatar"],
        fp_level=row.get("fp_level"),
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


@router.get("/", response_model=list[ChildResponse])
async def list_children(
    family_id: int = Depends(get_current_family),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(0, ge=0),
):
    pool = get_pool()
    rows = await pool.fetch(
        """SELECT c.*,
                  COALESCE(SUM(s.score), 0) AS total_words_read,
                  COUNT(s.id) AS total_sessions
           FROM children c
           LEFT JOIN sessions s ON s.child_id = c.id AND s.completed_at IS NOT NULL
           WHERE c.family_id = $1
           GROUP BY c.id
           ORDER BY c.name
           LIMIT $2 OFFSET $3""",
        family_id, limit, offset,
    )
    results = []
    for r in rows:
        child = _child_from_row(r)
        child.total_words_read = r["total_words_read"]
        child.total_sessions = r["total_sessions"]
        results.append(child)
    return results


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def leaderboard(family_id: int = Depends(get_current_family)):
    pool = get_pool()
    rows = await pool.fetch(
        """SELECT c.name, c.avatar,
                  COALESCE(SUM(s.score), 0) as total_words,
                  COUNT(s.id) as total_sessions
           FROM children c
           LEFT JOIN sessions s ON s.child_id = c.id AND s.completed_at IS NOT NULL
           WHERE c.family_id = $1
           GROUP BY c.id, c.name, c.avatar
           HAVING COALESCE(SUM(s.score), 0) > 0
           ORDER BY total_words DESC
           LIMIT 20""",
        family_id,
    )
    return [
        LeaderboardEntry(
            name=r["name"],
            avatar=r["avatar"],
            total_words=r["total_words"],
            total_sessions=r["total_sessions"],
        )
        for r in rows
    ]


@router.post("/", response_model=ChildResponse, status_code=201)
async def create_child(
    child: ChildCreate, family_id: int = Depends(get_current_family)
):
    pool = get_pool()
    row = await pool.fetchrow(
        "INSERT INTO children (family_id, name, avatar) VALUES ($1, $2, $3) "
        "RETURNING *",
        family_id, child.name, child.avatar,
    )
    return _child_from_row(row)


@router.get("/{child_id}", response_model=ChildResponse)
async def get_child(child_id: int, family_id: int = Depends(get_current_family)):
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM children WHERE id = $1 AND family_id = $2",
        child_id, family_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Child not found")
    return _child_from_row(row)


@router.put("/{child_id}", response_model=ChildResponse)
async def update_child(
    child_id: int, child: ChildCreate, family_id: int = Depends(get_current_family)
):
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM children WHERE id = $1 AND family_id = $2",
        child_id, family_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Child not found")

    row = await pool.fetchrow(
        "UPDATE children SET name = $1, avatar = $2 WHERE id = $3 RETURNING *",
        child.name, child.avatar, child_id,
    )
    return _child_from_row(row)


@router.delete("/{child_id}")
async def delete_child(child_id: int, family_id: int = Depends(get_current_family)):
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM children WHERE id = $1 AND family_id = $2",
        child_id, family_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Child not found")

    await pool.execute("DELETE FROM children WHERE id = $1", child_id)
    return {"detail": "Child deleted"}
