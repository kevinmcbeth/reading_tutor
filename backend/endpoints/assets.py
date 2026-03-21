from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from config import settings
from database import get_pool
from services import storage_service

router = APIRouter(prefix="/api/assets", tags=["assets"])


async def _get_story_uuid(story_id: int) -> str:
    """Get the UUID for a story. No auth required — UUIDs are unguessable."""
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT uuid FROM stories WHERE id = $1",
        story_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Story not found")
    return row["uuid"] or str(story_id)


@router.get("/image/{story_id}/{sentence_idx}")
async def get_image(story_id: int, sentence_idx: int):
    story_dir = await _get_story_uuid(story_id)
    key = f"stories/{story_dir}/images/sentence_{sentence_idx}.png"

    if settings.STORAGE_BACKEND == "s3":
        url = storage_service.get_url(key)
        return RedirectResponse(url=url, status_code=302)

    image_path = settings.data_path / key
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(
        str(image_path),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/audio/word/{story_id}/{word_id}")
async def get_word_audio(story_id: int, word_id: int):
    story_dir = await _get_story_uuid(story_id)
    key = f"stories/{story_dir}/audio/word_{word_id}.wav"

    if settings.STORAGE_BACKEND == "s3":
        url = storage_service.get_url(key)
        return RedirectResponse(url=url, status_code=302)

    audio_path = settings.data_path / key
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(
        str(audio_path),
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/audio/sentence/{story_id}/{sentence_idx}")
async def get_sentence_audio(story_id: int, sentence_idx: int):
    story_dir = await _get_story_uuid(story_id)
    key = f"stories/{story_dir}/audio/sentence_{sentence_idx}.wav"

    if settings.STORAGE_BACKEND == "s3":
        url = storage_service.get_url(key)
        return RedirectResponse(url=url, status_code=302)

    audio_path = settings.data_path / key
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(
        str(audio_path),
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=86400"},
    )
