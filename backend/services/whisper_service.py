import asyncio
import logging
import math
import tempfile
from pathlib import Path

import numpy as np

from config import settings

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio, pad_or_trim
    from faster_whisper.tokenizer import Tokenizer
    from faster_whisper.transcribe import get_ctranslate2_storage

    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False
    logger.warning(
        "faster-whisper not installed. Speech recognition will be unavailable. "
        "Install with: pip install faster-whisper"
    )

_model: "WhisperModel | None" = None
_semaphore = asyncio.Semaphore(1)

N_BEST = 5
SAMPLING_TEMPERATURE = 0.4


def _get_model() -> "WhisperModel":
    """Lazy-load the Whisper model (singleton)."""
    global _model
    if _model is None:
        if not _WHISPER_AVAILABLE:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Install with: pip install faster-whisper"
            )
        logger.info(
            "Loading Whisper model %s on device %s",
            settings.WHISPER_MODEL,
            settings.WHISPER_DEVICE,
        )
        _model = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type="default",
        )
        logger.info("Whisper model loaded successfully")
    return _model


def _softmax(scores: list[float]) -> list[float]:
    """Convert log-prob scores to normalized probabilities."""
    max_s = max(scores)
    exps = [math.exp(s - max_s) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]


def transcribe(audio_bytes: bytes, target_word: str | None = None) -> dict:
    """Transcribe audio bytes and return N-best hypotheses with probabilities.

    Uses the CTranslate2 model directly to generate multiple hypotheses
    via sampling, giving benefit of the doubt for similar-sounding words.

    Args:
        audio_bytes: Raw audio data (WebM, WAV, etc.)
        target_word: Optional expected word to bias recognition toward.

    Returns:
        dict with keys: transcript, alternatives, confidence
        - alternatives is a list of {"text": str, "probability": float}
          sorted by probability descending
    """
    model = _get_model()

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    try:
        tmp.write(audio_bytes)
        tmp.close()

        # Decode audio and extract mel features
        audio = decode_audio(str(tmp_path), sampling_rate=16000)
        features = model.feature_extractor(audio)
        features = pad_or_trim(features)
        features = get_ctranslate2_storage(np.expand_dims(features, 0))

        # Encode audio features
        encoder_output = model.model.encode(features)

        # Build tokenizer and prompt
        tokenizer = Tokenizer(
            model.hf_tokenizer,
            model.model.is_multilingual,
            task="transcribe",
            language="en",
        )

        initial_prompt = None
        if target_word:
            initial_prompt = f"The child is reading the word: {target_word}"

        prompt = model.get_prompt(
            tokenizer,
            previous_tokens=[],
            without_timestamps=True,
            prefix=initial_prompt,
        )

        # Generate N-best hypotheses via sampling
        results = model.model.generate(
            encoder_output,
            [prompt],
            beam_size=1,
            num_hypotheses=N_BEST,
            sampling_topk=0,
            sampling_temperature=SAMPLING_TEMPERATURE,
            return_scores=True,
            return_no_speech_prob=True,
            max_length=448,
            suppress_blank=True,
        )

        result = results[0]

        # Decode each hypothesis and collect scores
        hypotheses: list[dict] = []
        seen: set[str] = set()
        for i in range(len(result.sequences_ids)):
            tokens = result.sequences_ids[i]
            score = result.scores[i]
            text = tokenizer.decode(tokens).strip()
            if not text:
                continue
            low = text.lower()
            if low in seen:
                continue
            seen.add(low)
            hypotheses.append({"text": text, "score": score})

        if not hypotheses:
            return {
                "transcript": "",
                "alternatives": [],
                "confidence": 0.0,
            }

        # Convert log-prob scores to probabilities
        probs = _softmax([h["score"] for h in hypotheses])
        alternatives = [
            {"text": h["text"], "probability": round(p, 4)}
            for h, p in zip(hypotheses, probs)
        ]
        alternatives.sort(key=lambda x: x["probability"], reverse=True)

        best = alternatives[0]

        return {
            "transcript": best["text"],
            "alternatives": alternatives,
            "confidence": best["probability"],
        }
    finally:
        tmp_path.unlink(missing_ok=True)


async def transcribe_async(
    audio_bytes: bytes, target_word: str | None = None
) -> dict:
    """Async wrapper for transcribe that offloads to a thread with GPU semaphore."""
    async with _semaphore:
        return await asyncio.to_thread(transcribe, audio_bytes, target_word)
