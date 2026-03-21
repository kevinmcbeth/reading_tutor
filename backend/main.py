import asyncio
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import redis.asyncio as aioredis
from arq import create_pool as create_arq_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import init_db, close_db, get_pool
from endpoints import assets, children, fp, generation, parent, sessions, speech, stories

logger = logging.getLogger(__name__)


def _parse_redis_settings(url: str) -> RedisSettings:
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    app.state.redis = aioredis.from_url(settings.REDIS_URL)
    app.state.arq_redis = await create_arq_pool(
        _parse_redis_settings(settings.REDIS_URL)
    )
    yield
    # Shutdown
    await app.state.redis.aclose()
    await app.state.arq_redis.close()
    await close_db()


app = FastAPI(
    title="Reading Tutor",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_timeout_middleware(request: Request, call_next):
    """Cancel requests that exceed the configured timeout."""
    try:
        return await asyncio.wait_for(
            call_next(request), timeout=settings.REQUEST_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning("Request timed out: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=504, content={"detail": "Request timed out"})


app.include_router(parent.auth_router)
app.include_router(stories.router)
app.include_router(children.router)
app.include_router(sessions.router)
app.include_router(assets.router)
app.include_router(parent.router)
app.include_router(generation.router)
app.include_router(speech.router)
app.include_router(fp.router)


@app.get("/api/health")
async def health():
    """Basic liveness check."""
    return {"status": "ok"}


@app.get("/api/health/ready")
async def health_ready(request: Request):
    """Readiness check — verifies database and Redis connectivity."""
    checks = {}

    # Database
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    # Redis
    try:
        await request.app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )
