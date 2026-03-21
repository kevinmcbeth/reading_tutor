from contextlib import asynccontextmanager
from urllib.parse import urlparse

import redis.asyncio as aioredis
from arq import create_pool as create_arq_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db, close_db
from endpoints import assets, children, generation, parent, sessions, speech, stories


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

app.include_router(parent.auth_router)
app.include_router(stories.router)
app.include_router(children.router)
app.include_router(sessions.router)
app.include_router(assets.router)
app.include_router(parent.router)
app.include_router(generation.router)
app.include_router(speech.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
