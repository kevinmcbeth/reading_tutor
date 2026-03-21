import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from auth import get_current_family
from models.api_models import SpeechRecognitionResponse
from rate_limit import check_rate_limit
from services.resolver import transcribe_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/speech", tags=["speech"])


@router.post("/recognize", response_model=SpeechRecognitionResponse)
async def recognize(
    request: Request,
    audio: UploadFile = File(...),
    target_word: Optional[str] = Form(default=None),
    family_id: int = Depends(get_current_family),
):
    """Recognize speech from an audio upload (WebM/WAV from browser MediaRecorder)."""
    await check_rate_limit(
        request.app.state.redis, family_id, "speech", 120, 3600
    )

    MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB
    audio_bytes = await audio.read(MAX_UPLOAD_SIZE + 1)
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(audio_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25MB)")

    try:
        result = await transcribe_async(audio_bytes, target_word=target_word)
    except RuntimeError as exc:
        logger.error("Speech recognition failed: %s", exc)
        raise HTTPException(status_code=503, detail="Speech recognition unavailable")

    return SpeechRecognitionResponse(**result)
