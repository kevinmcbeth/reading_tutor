import asyncio
import logging
import re
import uuid as uuid_mod
from datetime import datetime, timezone
from pathlib import Path

from config import settings
from database import get_pool
from services import comfyui_client, storage_service

logger = logging.getLogger(__name__)

# Common words that are NOT challenge words at medium difficulty
COMMON_WORDS = {
    "a", "an", "the", "is", "am", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "about",
    "and", "but", "or", "not", "no", "so", "if", "it", "its", "he",
    "she", "we", "they", "me", "him", "her", "us", "them", "my", "his",
    "our", "your", "i", "you", "this", "that", "up", "out",
}


def _get_llm_client():
    """Return the appropriate LLM client based on config."""
    if settings.LLM_BACKEND == "bedrock":
        from services import bedrock_client
        return bedrock_client
    else:
        from services import ollama_client
        return ollama_client


async def log_generation(job_id: int, level: str, message: str) -> None:
    """Insert a log entry for a generation job."""
    pool = get_pool()
    await pool.execute(
        "INSERT INTO generation_logs (job_id, level, message) VALUES ($1, $2, $3)",
        job_id, level, message,
    )
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn("[job=%d] %s", job_id, message)


_ALLOWED_JOB_COLUMNS = {"status", "progress_pct", "completed_at"}
_ALLOWED_STORY_COLUMNS = {"title", "style", "uuid", "status"}


async def _update_job(job_id: int, **kwargs) -> None:
    """Update generation_jobs fields (whitelisted columns only)."""
    pool = get_pool()
    invalid = set(kwargs) - _ALLOWED_JOB_COLUMNS
    if invalid:
        raise ValueError(f"Invalid job columns: {invalid}")
    sets = []
    vals = []
    for i, (k, v) in enumerate(kwargs.items(), 1):
        sets.append(f"{k} = ${i}")
        vals.append(v)
    vals.append(job_id)
    await pool.execute(
        f"UPDATE generation_jobs SET {', '.join(sets)} WHERE id = ${len(vals)}",
        *vals,
    )


async def _update_story(story_id: int, **kwargs) -> None:
    """Update stories fields (whitelisted columns only)."""
    pool = get_pool()
    invalid = set(kwargs) - _ALLOWED_STORY_COLUMNS
    if invalid:
        raise ValueError(f"Invalid story columns: {invalid}")
    sets = []
    vals = []
    for i, (k, v) in enumerate(kwargs.items(), 1):
        sets.append(f"{k} = ${i}")
        vals.append(v)
    vals.append(story_id)
    await pool.execute(
        f"UPDATE stories SET {', '.join(sets)} WHERE id = ${len(vals)}",
        *vals,
    )


async def _check_cancelled(job_id: int) -> bool:
    """Check if a job has been cancelled."""
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT status FROM generation_jobs WHERE id = $1", job_id
    )
    return row is not None and row["status"] == "cancelled"


async def _manage_comfyui(action: str) -> None:
    """Start or stop ComfyUI via systemctl to manage GPU memory (local mode only)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "systemctl", action, "comfyui",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        if action == "start":
            await asyncio.sleep(10)
        elif action == "stop":
            await asyncio.sleep(3)
    except Exception as exc:
        logger.warning("Failed to %s ComfyUI: %s", action, exc)


async def _unload_ollama_model() -> None:
    """Unload the Ollama model to free GPU memory."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={"model": settings.OLLAMA_MODEL, "keep_alive": 0},
            )
        logger.info("Ollama model %s unloaded", settings.OLLAMA_MODEL)
    except Exception as exc:
        logger.warning("Failed to unload Ollama model: %s", exc)


async def _preload_ollama_model() -> None:
    """Preload the Ollama model back into GPU memory."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={"model": settings.OLLAMA_MODEL, "prompt": "", "keep_alive": -1},
            )
        logger.info("Ollama model %s reloaded", settings.OLLAMA_MODEL)
    except Exception as exc:
        logger.warning("Failed to reload Ollama model: %s", exc)


def _tokenize(text: str) -> list[str]:
    """Split sentence text into words, preserving punctuation attached to words."""
    return text.split()


def _is_challenge_word(
    word: str, word_idx: int, difficulty: str, challenge_indices: list[int]
) -> bool:
    """Determine if a word is a challenge word based on difficulty."""
    clean = re.sub(r"[^\w]", "", word).lower()
    if difficulty == "easy":
        return word_idx in challenge_indices
    elif difficulty == "medium":
        return clean not in COMMON_WORDS
    else:  # hard
        return True


def _is_local_mode() -> bool:
    """Check if we're running all services locally (single machine)."""
    return (
        settings.LLM_BACKEND == "ollama"
        and settings.TTS_BACKEND == "local"
        and settings.STORAGE_BACKEND == "local"
    )


async def run_story_generation(
    story_id: int,
    job_id: int,
    topic: str,
    difficulty: str,
    theme: str | None = None,
) -> None:
    """Run the full story generation pipeline."""
    pool = get_pool()
    llm = _get_llm_client()
    is_local = _is_local_mode()

    try:
        # --- Stage 1: Generate story text ---
        if await _check_cancelled(job_id):
            return

        await log_generation(job_id, "info", f"Starting story generation for '{topic}'")
        await _update_job(job_id, status="generating_text")

        try:
            story_data = await llm.generate_story(topic, difficulty, theme)
        except Exception as exc:
            await log_generation(job_id, "error", f"Story text generation failed: {exc}")
            await _update_job(
                job_id, status="failed", completed_at=datetime.now(timezone.utc)
            )
            await _update_story(story_id, status="failed")
            return

        title = story_data.get("title", topic)
        style = story_data.get("style", "cartoon")
        sentences = story_data.get("sentences", [])

        # Generate UUID for file paths
        story_uuid = str(uuid_mod.uuid4())

        await _update_story(
            story_id, title=title, style=style, uuid=story_uuid, status="text_generated"
        )

        # Save sentences and words to DB
        sentence_records = []
        async with pool.acquire() as conn:
            async with conn.transaction():
                for idx, sent in enumerate(sentences):
                    if isinstance(sent, str):
                        text = sent
                        challenge_indices = []
                    else:
                        text = sent.get("text", "")
                        challenge_indices = sent.get("challenge_words", [])

                    sentence_id = await conn.fetchval(
                        "INSERT INTO story_sentences (story_id, idx, text) "
                        "VALUES ($1, $2, $3) RETURNING id",
                        story_id, idx, text,
                    )
                    sentence_records.append(
                        {"id": sentence_id, "idx": idx, "text": text}
                    )

                    words = _tokenize(text)
                    for w_idx, word in enumerate(words):
                        is_challenge = _is_challenge_word(
                            word, w_idx, difficulty, challenge_indices
                        )
                        await conn.execute(
                            "INSERT INTO story_words (sentence_id, idx, text, is_challenge_word) "
                            "VALUES ($1, $2, $3, $4)",
                            sentence_id, w_idx, word, is_challenge,
                        )

        await log_generation(
            job_id,
            "info",
            f"Story text generated: '{title}' ({len(sentences)} sentences)",
        )

        # --- Stage 2: Generate image prompts ---
        if await _check_cancelled(job_id):
            return

        try:
            image_prompts = await llm.generate_image_prompts(
                " ".join(sr["text"] for sr in sentence_records),
                style,
                [{"text": sr["text"]} for sr in sentence_records],
            )
        except Exception as exc:
            await log_generation(
                job_id, "warning", f"Image prompt generation failed: {exc}"
            )
            image_prompts = []

        # Update sentence records with image prompts
        for ip in image_prompts:
            if isinstance(ip, str):
                continue
            s_idx = ip.get("sentence_index", 0)
            if s_idx < len(sentence_records):
                sid = sentence_records[s_idx]["id"]
                await pool.execute(
                    "UPDATE story_sentences SET image_prompt = $1, negative_prompt = $2 "
                    "WHERE id = $3",
                    ip.get("image_prompt", ""),
                    ip.get("negative_prompt", ""),
                    sid,
                )

        await log_generation(job_id, "info", "Image prompts generated")

        # GPU memory management — only needed in local mode
        if is_local:
            await _unload_ollama_model()
            await log_generation(job_id, "info", "Ollama model unloaded to free GPU memory")

        # --- Stage 3: Generate images ---
        if await _check_cancelled(job_id):
            return

        if is_local:
            await log_generation(job_id, "info", "Starting ComfyUI for image generation")
            await _manage_comfyui("start")

        await _update_job(job_id, status="generating_images")

        # In local mode, ComfyUI writes to local disk directly via output_path.
        # In cloud mode, ComfyUI still writes to a temp path, then we upload to S3.
        if settings.STORAGE_BACKEND == "local":
            images_dir = (
                Path(settings.data_path) / "stories" / story_uuid / "images"
            )
            images_dir.mkdir(parents=True, exist_ok=True)

        total_tasks = len(image_prompts) if image_prompts else 0
        for i, ip in enumerate(image_prompts):
            if await _check_cancelled(job_id):
                return

            if isinstance(ip, str):
                continue
            s_idx = ip.get("sentence_index", 0)
            if s_idx >= len(sentence_records):
                continue
            sid = sentence_records[s_idx]["id"]

            storage_key = f"stories/{story_uuid}/images/sentence_{s_idx}.png"

            if settings.STORAGE_BACKEND == "s3":
                # ComfyUI generates to a temp file, then upload to S3
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name

                success = await comfyui_client.generate_image(
                    prompt=ip.get("image_prompt", ""),
                    negative_prompt=ip.get("negative_prompt", ""),
                    output_path=tmp_path,
                )

                if success:
                    img_data = Path(tmp_path).read_bytes()
                    storage_service.save_file(storage_key, img_data)
                    Path(tmp_path).unlink(missing_ok=True)

                    await pool.execute(
                        "UPDATE story_sentences SET image_path = $1, has_image = TRUE "
                        "WHERE id = $2",
                        storage_key, sid,
                    )
                else:
                    Path(tmp_path).unlink(missing_ok=True)
            else:
                img_path = str(images_dir / f"sentence_{s_idx}.png")
                success = await comfyui_client.generate_image(
                    prompt=ip.get("image_prompt", ""),
                    negative_prompt=ip.get("negative_prompt", ""),
                    output_path=img_path,
                )

                if success:
                    await pool.execute(
                        "UPDATE story_sentences SET image_path = $1, has_image = TRUE "
                        "WHERE id = $2",
                        img_path, sid,
                    )

            if success:
                await log_generation(
                    job_id, "info", f"Image generated for sentence {s_idx}"
                )
            else:
                await log_generation(
                    job_id, "warning", f"Image generation failed for sentence {s_idx}"
                )

            if total_tasks > 0:
                pct = ((i + 1) / total_tasks) * 60  # images are 0-60% of progress
                await _update_job(job_id, progress_pct=pct)

        # Stop ComfyUI — only in local mode
        if is_local:
            await log_generation(job_id, "info", "Stopping ComfyUI to free GPU for audio")
            await _manage_comfyui("stop")

        # --- Stage 4: Generate audio ---
        if await _check_cancelled(job_id):
            return

        await _update_job(job_id, status="generating_audio")

        if settings.STORAGE_BACKEND == "local":
            audio_dir = (
                Path(settings.data_path) / "stories" / story_uuid / "audio"
            )
            audio_dir.mkdir(parents=True, exist_ok=True)

        # Get all words from DB
        all_words = []
        for sr in sentence_records:
            rows = await pool.fetch(
                "SELECT * FROM story_words WHERE sentence_id = $1 ORDER BY idx",
                sr["id"],
            )
            all_words.extend(rows)

        total_audio = len(all_words) + len(sentence_records)
        completed_audio = 0

        # Generate word audio
        for word_row in all_words:
            if await _check_cancelled(job_id):
                return

            storage_key = f"stories/{story_uuid}/audio/word_{word_row['id']}.wav"

            if settings.TTS_BACKEND == "remote":
                from services import tts_client
                audio_data = await tts_client.generate_word_audio(word_row["text"])
                success = audio_data is not None
                if success:
                    storage_service.save_file(storage_key, audio_data)
                    await pool.execute(
                        "UPDATE story_words SET audio_path = $1, has_audio = TRUE WHERE id = $2",
                        storage_key, word_row["id"],
                    )
            else:
                from services import tts_service
                word_path = str(audio_dir / f"word_{word_row['id']}.wav")
                success = await tts_service.generate_word_audio_async(
                    word_row["text"], word_path
                )
                if success:
                    if settings.STORAGE_BACKEND == "s3":
                        storage_service.save_file(storage_key, Path(word_path).read_bytes())
                        Path(word_path).unlink(missing_ok=True)
                        await pool.execute(
                            "UPDATE story_words SET audio_path = $1, has_audio = TRUE WHERE id = $2",
                            storage_key, word_row["id"],
                        )
                    else:
                        await pool.execute(
                            "UPDATE story_words SET audio_path = $1, has_audio = TRUE WHERE id = $2",
                            word_path, word_row["id"],
                        )

            if success:
                await log_generation(
                    job_id, "info", f"Audio generated for word '{word_row['text']}'"
                )
            else:
                await log_generation(
                    job_id,
                    "warning",
                    f"Audio generation failed for word '{word_row['text']}'",
                )

            completed_audio += 1
            if total_audio > 0:
                pct = 60 + (completed_audio / total_audio) * 40
                await _update_job(job_id, progress_pct=pct)

        # Generate sentence audio
        for sr in sentence_records:
            if await _check_cancelled(job_id):
                return

            storage_key = f"stories/{story_uuid}/audio/sentence_{sr['idx']}.wav"

            if settings.TTS_BACKEND == "remote":
                from services import tts_client
                audio_data = await tts_client.generate_sentence_audio(sr["text"])
                success = audio_data is not None
                if success:
                    storage_service.save_file(storage_key, audio_data)
            else:
                from services import tts_service
                sent_path = str(audio_dir / f"sentence_{sr['idx']}.wav")
                success = await tts_service.generate_sentence_audio_async(
                    sr["text"], sent_path
                )
                if success and settings.STORAGE_BACKEND == "s3":
                    storage_service.save_file(storage_key, Path(sent_path).read_bytes())
                    Path(sent_path).unlink(missing_ok=True)

            if success:
                await log_generation(
                    job_id, "info", f"Audio generated for sentence {sr['idx']}"
                )
            else:
                await log_generation(
                    job_id,
                    "warning",
                    f"Audio generation failed for sentence {sr['idx']}",
                )

            completed_audio += 1
            if total_audio > 0:
                pct = 60 + (completed_audio / total_audio) * 40
                await _update_job(job_id, progress_pct=pct)

        # --- Complete ---
        await _update_job(
            job_id,
            status="completed",
            progress_pct=100,
            completed_at=datetime.now(timezone.utc),
        )
        await _update_story(story_id, status="ready")

        # Cleanup: unload models in local mode
        if is_local:
            from services import tts_service
            await tts_service.unload_tts_async()
            await log_generation(job_id, "info", "TTS model unloaded")
            await _preload_ollama_model()

        await log_generation(job_id, "info", "Story generation complete")

    except Exception as exc:
        await log_generation(job_id, "error", f"Pipeline error: {exc}")
        await _update_job(
            job_id, status="failed", completed_at=datetime.now(timezone.utc)
        )
        await _update_story(story_id, status="failed")


def _fp_is_challenge_word(word: str, fp_level: str, vocab: dict) -> bool:
    """Determine if a word is a challenge word for F&P levels."""
    clean = re.sub(r"[^\w]", "", word).lower()
    if not clean:
        return False

    vtype = vocab.get("type", "grade_appropriate")
    if vtype in ("sight_words_only", "cvc_plus_sight"):
        # At levels A-D, ALL words are challenge words (kids are learning them all)
        return True
    elif vtype == "expanding":
        # At levels E-H, common words are not challenges
        return clean not in COMMON_WORDS
    else:
        # At levels I+, use existing logic (non-common words are challenges)
        return clean not in COMMON_WORDS


async def run_fp_story_generation(
    story_id: int,
    job_id: int,
    topic: str,
    fp_level: str,
    theme: str | None = None,
) -> None:
    """Run the full F&P story generation pipeline."""
    pool = get_pool()

    try:
        # Load level definition
        level_row = await pool.fetchrow(
            "SELECT * FROM fp_levels WHERE level = $1", fp_level
        )
        if not level_row:
            await log_generation(job_id, "error", f"Unknown F&P level: {fp_level}")
            await _update_job(job_id, status="failed", completed_at=datetime.utcnow())
            await _update_story(story_id, status="failed")
            return

        level_data = dict(level_row)
        vocab = level_data.get("vocabulary_constraints", {})
        if isinstance(vocab, str):
            import json
            vocab = json.loads(vocab)

        generate_images = level_data["generate_images"]
        image_support = level_data.get("image_support", "none")

        # --- Stage 1: Generate story text ---
        if await _check_cancelled(job_id):
            return

        await log_generation(job_id, "info", f"Starting F&P Level {fp_level} story generation for '{topic}'")
        await _update_job(job_id, status="generating_text")

        try:
            story_data = await ollama_client.generate_fp_story(topic, level_data)
        except Exception as exc:
            await log_generation(job_id, "error", f"Story text generation failed: {exc}")
            await _update_job(job_id, status="failed", completed_at=datetime.utcnow())
            await _update_story(story_id, status="failed")
            return

        title = story_data.get("title", topic)
        style = story_data.get("style", "cartoon")
        sentences = story_data.get("sentences", [])

        story_uuid = str(uuid_mod.uuid4())

        await _update_story(
            story_id, title=title, style=style, uuid=story_uuid, status="text_generated"
        )

        # Save sentences and words to DB
        sentence_records = []
        async with pool.acquire() as conn:
            async with conn.transaction():
                for idx, sent in enumerate(sentences):
                    if isinstance(sent, str):
                        text = sent
                        challenge_indices = []
                    else:
                        text = sent.get("text", "")
                        challenge_indices = sent.get("challenge_words", [])

                    sentence_id = await conn.fetchval(
                        "INSERT INTO story_sentences (story_id, idx, text) "
                        "VALUES ($1, $2, $3) RETURNING id",
                        story_id, idx, text,
                    )
                    sentence_records.append(
                        {"id": sentence_id, "idx": idx, "text": text}
                    )

                    words = _tokenize(text)
                    for w_idx, word in enumerate(words):
                        is_challenge = _fp_is_challenge_word(word, fp_level, vocab)
                        await conn.execute(
                            "INSERT INTO story_words (sentence_id, idx, text, is_challenge_word) "
                            "VALUES ($1, $2, $3, $4)",
                            sentence_id, w_idx, word, is_challenge,
                        )

        await log_generation(
            job_id, "info",
            f"F&P Level {fp_level} story generated: '{title}' ({len(sentences)} sentences)",
        )

        if generate_images:
            # --- Stage 2: Generate image prompts ---
            if await _check_cancelled(job_id):
                return

            try:
                image_prompts = await ollama_client.generate_fp_image_prompts(
                    " ".join(sr["text"] for sr in sentence_records),
                    style,
                    [{"text": sr["text"]} for sr in sentence_records],
                    image_support,
                )
            except Exception as exc:
                await log_generation(job_id, "warning", f"Image prompt generation failed: {exc}")
                image_prompts = []

            for ip in image_prompts:
                if isinstance(ip, str):
                    continue
                s_idx = ip.get("sentence_index", 0)
                if s_idx < len(sentence_records):
                    sid = sentence_records[s_idx]["id"]
                    await pool.execute(
                        "UPDATE story_sentences SET image_prompt = $1, negative_prompt = $2 "
                        "WHERE id = $3",
                        ip.get("image_prompt", ""), ip.get("negative_prompt", ""), sid,
                    )

            await log_generation(job_id, "info", "Image prompts generated")
            await _unload_ollama_model()
            await log_generation(job_id, "info", "Ollama model unloaded to free GPU memory")

            # --- Stage 3: Generate images ---
            if await _check_cancelled(job_id):
                return

            await log_generation(job_id, "info", "Starting ComfyUI for image generation")
            await _manage_comfyui("start")
            await _update_job(job_id, status="generating_images")
            images_dir = Path(settings.data_path) / "stories" / story_uuid / "images"
            images_dir.mkdir(parents=True, exist_ok=True)

            total_tasks = len(image_prompts) if image_prompts else 0
            for i, ip in enumerate(image_prompts):
                if await _check_cancelled(job_id):
                    return
                if isinstance(ip, str):
                    continue
                s_idx = ip.get("sentence_index", 0)
                if s_idx >= len(sentence_records):
                    continue
                sid = sentence_records[s_idx]["id"]
                img_path = str(images_dir / f"sentence_{s_idx}.png")

                success = await comfyui_client.generate_image(
                    prompt=ip.get("image_prompt", ""),
                    negative_prompt=ip.get("negative_prompt", ""),
                    output_path=img_path,
                )

                if success:
                    await pool.execute(
                        "UPDATE story_sentences SET image_path = $1, has_image = TRUE WHERE id = $2",
                        img_path, sid,
                    )
                    await log_generation(job_id, "info", f"Image generated for sentence {s_idx}")
                else:
                    await log_generation(job_id, "warning", f"Image generation failed for sentence {s_idx}")

                if total_tasks > 0:
                    pct = ((i + 1) / total_tasks) * 60
                    await _update_job(job_id, progress_pct=pct)

            await log_generation(job_id, "info", "Stopping ComfyUI to free GPU for audio")
            await _manage_comfyui("stop")
        else:
            # No images — skip straight to audio
            await _unload_ollama_model()
            await log_generation(job_id, "info", f"Level {fp_level}: skipping image generation (images disabled)")

        # --- Stage 4: Generate audio ---
        if await _check_cancelled(job_id):
            return

        await _update_job(job_id, status="generating_audio")
        audio_dir = Path(settings.data_path) / "stories" / story_uuid / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        all_words = []
        for sr in sentence_records:
            rows = await pool.fetch(
                "SELECT * FROM story_words WHERE sentence_id = $1 ORDER BY idx", sr["id"],
            )
            all_words.extend(rows)

        total_audio = len(all_words) + len(sentence_records)
        completed_audio = 0

        for word_row in all_words:
            if await _check_cancelled(job_id):
                return
            word_path = str(audio_dir / f"word_{word_row['id']}.wav")
            success = await tts_service.generate_word_audio_async(word_row["text"], word_path)
            if success:
                await pool.execute(
                    "UPDATE story_words SET audio_path = $1, has_audio = TRUE WHERE id = $2",
                    word_path, word_row["id"],
                )
            completed_audio += 1
            if total_audio > 0:
                base_pct = 60 if generate_images else 0
                range_pct = 40 if generate_images else 100
                pct = base_pct + (completed_audio / total_audio) * range_pct
                await _update_job(job_id, progress_pct=pct)

        for sr in sentence_records:
            if await _check_cancelled(job_id):
                return
            sent_path = str(audio_dir / f"sentence_{sr['idx']}.wav")
            success = await tts_service.generate_sentence_audio_async(sr["text"], sent_path)
            completed_audio += 1
            if total_audio > 0:
                base_pct = 60 if generate_images else 0
                range_pct = 40 if generate_images else 100
                pct = base_pct + (completed_audio / total_audio) * range_pct
                await _update_job(job_id, progress_pct=pct)

        # --- Complete ---
        await _update_job(
            job_id, status="completed", progress_pct=100, completed_at=datetime.utcnow(),
        )
        await _update_story(story_id, status="ready")
        await tts_service.unload_tts_async()
        await log_generation(job_id, "info", "TTS model unloaded")
        await _preload_ollama_model()
        await log_generation(job_id, "info", f"F&P Level {fp_level} story generation complete")

    except Exception as exc:
        await log_generation(job_id, "error", f"Pipeline error: {exc}")
        await _update_job(job_id, status="failed", completed_at=datetime.utcnow())
        await _update_story(story_id, status="failed")


async def run_batch_generation(prompts: list[dict]) -> list[int]:
    """Create jobs for each prompt and run them serially. Returns list of job IDs."""
    pool = get_pool()
    llm = _get_llm_client()
    job_ids = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for p in prompts:
                story_id = await conn.fetchval(
                    "INSERT INTO stories (topic, difficulty, theme, status) "
                    "VALUES ($1, $2, $3, 'pending') RETURNING id",
                    p["topic"], p["difficulty"], p.get("theme"),
                )
                job_id = await conn.fetchval(
                    "INSERT INTO generation_jobs (story_id, status) "
                    "VALUES ($1, 'pending') RETURNING id",
                    story_id,
                )
                job_ids.append(job_id)
                p["_story_id"] = story_id
                p["_job_id"] = job_id

    for p in prompts:
        await run_story_generation(
            story_id=p["_story_id"],
            job_id=p["_job_id"],
            topic=p["topic"],
            difficulty=p["difficulty"],
            theme=p.get("theme"),
        )

    return job_ids


async def run_meta_generation(description: str, count: int = 5) -> list[int]:
    """Generate story prompts from a description, then run batch generation."""
    llm = _get_llm_client()
    meta_prompts = await llm.generate_meta_prompts(description, count)
    prompts = []
    for mp in meta_prompts:
        prompts.append(
            {
                "topic": mp.get("topic", description),
                "difficulty": mp.get("difficulty", "easy"),
                "theme": mp.get("theme"),
            }
        )
    return await run_batch_generation(prompts)
