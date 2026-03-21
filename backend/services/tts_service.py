import asyncio
import logging
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

_tts_instance = None
_tts_available = True
_semaphore = asyncio.Semaphore(8)


def _get_tts():
    """Lazy-load the F5TTS instance."""
    global _tts_instance, _tts_available
    if not _tts_available:
        return None
    if _tts_instance is None:
        try:
            from f5_tts.api import F5TTS

            _tts_instance = F5TTS()
        except ImportError:
            logger.warning(
                "F5-TTS is not installed. TTS generation will be disabled."
            )
            _tts_available = False
            return None
        except Exception as exc:
            logger.warning("Failed to initialize F5-TTS: %s", exc)
            _tts_available = False
            return None
    return _tts_instance


def generate_word_audio(word: str, output_path: str) -> bool:
    """Generate audio for a single word. Returns True on success."""
    tts = _get_tts()
    if tts is None:
        return False

    try:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        ref_file = str(Path(__file__).parent.parent / settings.REFERENCE_VOICE)
        tts.infer(
            gen_text=word,
            ref_file=ref_file,
            ref_text="",
            file_wave=output_path,
        )
        return True
    except Exception as exc:
        logger.error("TTS word generation failed for '%s': %s", word, exc)
        return False


def generate_sentence_audio(sentence: str, output_path: str) -> bool:
    """Generate audio for a full sentence. Returns True on success."""
    tts = _get_tts()
    if tts is None:
        return False

    try:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        ref_file = str(Path(__file__).parent.parent / settings.REFERENCE_VOICE)
        tts.infer(
            gen_text=sentence,
            ref_file=ref_file,
            ref_text="",
            file_wave=output_path,
        )
        return True
    except Exception as exc:
        logger.error("TTS sentence generation failed: %s", exc)
        return False


def unload_tts() -> None:
    """Unload the TTS model to free GPU memory."""
    global _tts_instance
    if _tts_instance is not None:
        del _tts_instance
        _tts_instance = None
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("TTS model unloaded and GPU cache cleared")


async def unload_tts_async() -> None:
    """Async wrapper to unload TTS model."""
    await asyncio.to_thread(unload_tts)


async def generate_word_audio_async(word: str, output_path: str) -> bool:
    """Async wrapper that offloads TTS to a thread with GPU semaphore."""
    async with _semaphore:
        return await asyncio.to_thread(generate_word_audio, word, output_path)


async def generate_sentence_audio_async(sentence: str, output_path: str) -> bool:
    """Async wrapper that offloads TTS to a thread with GPU semaphore."""
    async with _semaphore:
        return await asyncio.to_thread(generate_sentence_audio, sentence, output_path)
