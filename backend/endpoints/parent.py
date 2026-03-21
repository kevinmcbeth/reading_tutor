from fastapi import APIRouter, Depends, HTTPException

from auth import (
    create_access_token,
    create_refresh_token,
    get_current_family,
    hash_password,
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
async def register(data: FamilyCreate):
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

    return TokenResponse(
        access_token=create_access_token(family_id),
        refresh_token=create_refresh_token(family_id),
        family_id=family_id,
        display_name=display,
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(data: FamilyLogin):
    pool = get_pool()

    row = await pool.fetchrow(
        "SELECT id, password_hash, display_name FROM families WHERE username = $1",
        data.username,
    )
    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return TokenResponse(
        access_token=create_access_token(row["id"]),
        refresh_token=create_refresh_token(row["id"]),
        family_id=row["id"],
        display_name=row["display_name"],
    )


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest):
    try:
        payload = jwt.decode(
            data.refresh_token, settings.JWT_SECRET, algorithms=["HS256"]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        family_id = int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT display_name FROM families WHERE id = $1", family_id
    )
    if not row:
        raise HTTPException(status_code=401, detail="Family not found")

    return TokenResponse(
        access_token=create_access_token(family_id),
        refresh_token=create_refresh_token(family_id),
        family_id=family_id,
        display_name=row["display_name"],
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

    row = await pool.fetchrow(
        "SELECT COUNT(*) as cnt FROM sessions WHERE child_id = $1 AND completed_at IS NOT NULL",
        child_id,
    )
    total_sessions = row["cnt"]

    row = await pool.fetchrow(
        "SELECT AVG(CAST(score AS REAL) / CASE WHEN total_words = 0 THEN 1 ELSE total_words END) as avg_score "
        "FROM sessions WHERE child_id = $1 AND completed_at IS NOT NULL",
        child_id,
    )
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


@router.get("/analytics", response_model=list[AnalyticsResponse])
async def get_all_analytics(family_id: int = Depends(get_current_family)):
    pool = get_pool()

    children = await pool.fetch(
        "SELECT * FROM children WHERE family_id = $1 ORDER BY name", family_id
    )

    results = []
    for child in children:
        child_id = child["id"]

        row = await pool.fetchrow(
            "SELECT COUNT(*) as cnt FROM sessions WHERE child_id = $1 AND completed_at IS NOT NULL",
            child_id,
        )
        total_sessions = row["cnt"]

        row = await pool.fetchrow(
            "SELECT AVG(CAST(score AS REAL) / CASE WHEN total_words = 0 THEN 1 ELSE total_words END) as avg_score "
            "FROM sessions WHERE child_id = $1 AND completed_at IS NOT NULL",
            child_id,
        )
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
            {"word": r["text"], "count": r["miss_count"]}
            for r in missed_rows
        ]

        results.append(
            AnalyticsResponse(
                child_id=child_id,
                total_sessions=total_sessions,
                average_score=average_score,
                commonly_missed_words=commonly_missed,
            )
        )

    return results
