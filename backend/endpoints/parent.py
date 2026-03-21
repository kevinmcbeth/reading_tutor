from fastapi import APIRouter, Depends, HTTPException, Request

from auth import (
    create_access_token,
    create_refresh_token,
    get_current_family,
    hash_password,
    is_refresh_token_valid,
    revoke_refresh_token,
    store_refresh_token,
    verify_password,
)
from database import get_pool
from models.api_models import (
    AnalyticsResponse,
    FamilyCreate,
    FamilyLogin,
    RefreshRequest,
    TokenResponse,
)

from jose import JWTError, jwt
from config import settings

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
router = APIRouter(prefix="/api/parent", tags=["parent"])


@auth_router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: FamilyCreate, request: Request):
    pool = get_pool()

    existing = await pool.fetchrow(
        "SELECT id FROM families WHERE username = $1", data.username
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    pw_hash = hash_password(data.password)
    display = data.display_name or data.username

    family_id = await pool.fetchval(
        "INSERT INTO families (username, password_hash, display_name) "
        "VALUES ($1, $2, $3) RETURNING id",
        data.username, pw_hash, display,
    )

    access = create_access_token(family_id)
    refresh = create_refresh_token(family_id)
    await store_refresh_token(request.app.state.redis, refresh, family_id)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        family_id=family_id,
        display_name=display,
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(data: FamilyLogin, request: Request):
    pool = get_pool()

    row = await pool.fetchrow(
        "SELECT id, password_hash, display_name FROM families WHERE username = $1",
        data.username,
    )
    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access = create_access_token(row["id"])
    refresh = create_refresh_token(row["id"])
    await store_refresh_token(request.app.state.redis, refresh, row["id"])

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        family_id=row["id"],
        display_name=row["display_name"],
    )


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, request: Request):
    try:
        payload = jwt.decode(
            data.refresh_token, settings.JWT_SECRET, algorithms=["HS256"]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        family_id = int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Check that the refresh token has not been revoked
    if not await is_refresh_token_valid(request.app.state.redis, data.refresh_token):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT display_name FROM families WHERE id = $1", family_id
    )
    if not row:
        raise HTTPException(status_code=401, detail="Family not found")

    # Revoke the old refresh token (rotation)
    await revoke_refresh_token(request.app.state.redis, data.refresh_token)

    access = create_access_token(family_id)
    new_refresh = create_refresh_token(family_id)
    await store_refresh_token(request.app.state.redis, new_refresh, family_id)

    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        family_id=family_id,
        display_name=row["display_name"],
    )


async def _get_child_analytics(pool, child_id: int) -> AnalyticsResponse:
    """Build analytics for a single child in one query + one query for missed words."""
    row = await pool.fetchrow(
        """SELECT COUNT(*) AS total_sessions,
                  COALESCE(
                      AVG(CAST(score AS REAL) / CASE WHEN total_words = 0 THEN 1 ELSE total_words END),
                      0
                  ) AS avg_score
           FROM sessions
           WHERE child_id = $1 AND completed_at IS NOT NULL""",
        child_id,
    )
    total_sessions = row["total_sessions"]
    average_score = round((row["avg_score"] or 0) * 100, 1)

    missed_rows = await pool.fetch(
        """SELECT sw.text, COUNT(*) as miss_count
           FROM session_words sesw
           JOIN story_words sw ON sesw.word_id = sw.id
           JOIN sessions s ON sesw.session_id = s.id
           WHERE s.child_id = $1 AND sesw.correct = FALSE
           GROUP BY sw.text
           ORDER BY miss_count DESC
           LIMIT 20""",
        child_id,
    )

    commonly_missed = [
        {"word": r["text"], "count": r["miss_count"]} for r in missed_rows
    ]

    return AnalyticsResponse(
        child_id=child_id,
        total_sessions=total_sessions,
        average_score=average_score,
        commonly_missed_words=commonly_missed,
    )


@router.get("/analytics/{child_id}", response_model=AnalyticsResponse)
async def get_child_analytics(
    child_id: int, family_id: int = Depends(get_current_family)
):
    pool = get_pool()

    child = await pool.fetchrow(
        "SELECT * FROM children WHERE id = $1 AND family_id = $2",
        child_id, family_id,
    )
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    return await _get_child_analytics(pool, child_id)


@router.get("/analytics", response_model=list[AnalyticsResponse])
async def get_all_analytics(family_id: int = Depends(get_current_family)):
    pool = get_pool()

    children = await pool.fetch(
        "SELECT id FROM children WHERE family_id = $1 ORDER BY name", family_id
    )

    results = []
    for child in children:
        results.append(await _get_child_analytics(pool, child["id"]))

    return results
