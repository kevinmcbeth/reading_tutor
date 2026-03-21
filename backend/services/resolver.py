"""Service resolver — imports from mocks or real implementations based on config."""

from config import settings

if settings.USE_MOCK_SERVICES:
    from services.mocks.mock_ollama import (
        generate_image_prompts,
        generate_meta_prompts,
        generate_story,
    )
    from services.mocks.mock_comfyui import generate_image
    from services.mocks.mock_tts import (
        generate_sentence_audio_async,
        generate_word_audio_async,
        unload_tts_async,
    )
    from services.mocks.mock_whisper import transcribe_async
else:
    from services.ollama_client import (
        generate_image_prompts,
        generate_meta_prompts,
        generate_story,
    )
    from services.comfyui_client import generate_image
    from services.tts_service import (
        generate_sentence_audio_async,
        generate_word_audio_async,
        unload_tts_async,
    )
    from services.whisper_service import transcribe_async

__all__ = [
    "generate_story",
    "generate_image_prompts",
    "generate_meta_prompts",
    "generate_image",
    "generate_word_audio_async",
    "generate_sentence_audio_async",
    "unload_tts_async",
    "transcribe_async",
]
