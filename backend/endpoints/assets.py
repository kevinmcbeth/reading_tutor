from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import settings
from database import get_pool

router = APIRouter(prefix="/api/assets", tags=["assets"])


async def _get_story_uuid(story_id: int) -> str:
    """Get the UUID for a story, falling back to the story ID for legacy stories."""
    pool = get_pool()
    row = await pool.fetchrow("SELECT uuid FROM stories WHERE id = $1", story_id)
    if not row:
        raise HTTPException(status_code=404, detail="Story not found")
    return row["uuid"] or str(story_id)


@router.get("/image/{story_id}/{sentence_idx}")
async def get_image(story_id: int, sentence_idx: int):
    story_dir = await _get_story_uuid(story_id)
    image_path = (
        settings.data_path / "stories" / story_dir / "images" / f"sentence_{sentence_idx}.png"
    )
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
    audio_path = (
        settings.data_path / "stories" / story_dir / "audio" / f"word_{word_id}.wav"
    )
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
    audio_path = (
        settings.data_path
        / "stories"
        / story_dir
        / "audio"
        / f"sentence_{sentence_idx}.wav"
    )
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(
        str(audio_path),
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=86400"},
    )
