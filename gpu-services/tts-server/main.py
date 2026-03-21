"""FastAPI wrapper around F5-TTS for remote audio generation."""

import io
import logging
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="TTS Service")

# Global TTS instance, loaded on startup
_tts = None
_reference_voice = os.environ.get("REFERENCE_VOICE", "/models/reference_voice.wav")


class TTSRequest(BaseModel):
    text: str
    type: str = "word"  # "word" or "sentence"


@app.on_event("startup")
def load_model():
    global _tts
    from f5_tts.api import F5TTS
    _tts = F5TTS()
    logger.info("F5-TTS model loaded")


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _tts is not None}


@app.post("/generate")
def generate(req: TTSRequest):
    if _tts is None:
        raise HTTPException(status_code=503, detail="TTS model not loaded")

    try:
        # Generate to a temporary file in memory
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        _tts.infer(
            gen_text=req.text,
            ref_file=_reference_voice,
            ref_text="",
            file_wave=tmp_path,
        )

        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()

        os.unlink(tmp_path)

        from fastapi.responses import Response
        return Response(content=audio_bytes, media_type="audio/wav")

    except Exception as exc:
        logger.error("TTS generation failed for '%s': %s", req.text, exc)
        raise HTTPException(status_code=500, detail=str(exc))
