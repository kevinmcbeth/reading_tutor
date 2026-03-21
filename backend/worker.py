"""arq worker for background story generation.

Run with: arq backend.worker.WorkerSettings
"""
from datetime import timedelta
from urllib.parse import urlparse

from arq.connections import RedisSettings

from config import settings
from database import init_db, close_db
from services import story_pipeline


async def generate_story_task(
    ctx: dict,
    story_id: int,
    job_id: int,
    topic: str,
    difficulty: str,
    theme: str | None = None,
) -> None:
    """Generate a story in the worker process."""
    await story_pipeline.run_story_generation(
        story_id=story_id,
        job_id=job_id,
        topic=topic,
        difficulty=difficulty,
        theme=theme,
    )


async def generate_fp_story_task(
    ctx: dict,
    story_id: int,
    job_id: int,
    topic: str,
    fp_level: str,
    theme: str | None = None,
) -> None:
    """Generate an F&P leveled story in the worker process."""
    await story_pipeline.run_fp_story_generation(
        story_id=story_id,
        job_id=job_id,
        topic=topic,
        fp_level=fp_level,
        theme=theme,
    )


async def startup(ctx: dict) -> None:
    """Initialize DB pool and pre-load TTS model in worker."""
    await init_db()


async def shutdown(ctx: dict) -> None:
    """Clean up DB pool."""
    await close_db()


def _parse_redis_settings(url: str) -> RedisSettings:
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )


class WorkerSettings:
    functions = [generate_story_task, generate_fp_story_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 4
    job_timeout = timedelta(minutes=30)
    max_job_retries = 3
    queue_read_limit = 4
    keep_result = timedelta(hours=24)
    redis_settings = _parse_redis_settings(settings.REDIS_URL)
