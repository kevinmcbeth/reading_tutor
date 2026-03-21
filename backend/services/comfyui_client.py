import asyncio
import json
import logging
import random
from pathlib import Path

import httpx

from config import settings

logger = logging.getLogger(__name__)

WORKFLOW_PATH = Path(__file__).parent.parent / "workflows" / "txt2img_children.json"

MAX_POLL_TIME = 300  # 5 minutes
POLL_INTERVAL_INITIAL = 1  # seconds
POLL_INTERVAL_MAX = 10  # seconds
POLL_BACKOFF_FACTOR = 1.5


def _build_workflow(
    prompt: str, negative_prompt: str, width: int, height: int
) -> dict:
    """Build a ComfyUI workflow, using template if available or default SDXL."""
    if WORKFLOW_PATH.exists():
        workflow = json.loads(WORKFLOW_PATH.read_text())
        # Try to inject prompt values into the template
        for node in workflow.values():
            if isinstance(node, dict):
                inputs = node.get("inputs", {})
                if node.get("class_type") == "CLIPTextEncode":
                    if inputs.get("text", "") == "" or "positive" in str(inputs):
                        inputs["text"] = prompt
                if node.get("class_type") == "EmptyLatentImage":
                    inputs["width"] = width
                    inputs["height"] = height
        return workflow

    seed = random.randint(0, 2**32 - 1)
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 25,
                "cfg": 7.0,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "DreamShaperXL_Turbo_v2_1.safetensors"},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "reading_tutor",
                "images": ["8", 0],
            },
        },
    }


async def generate_image(
    prompt: str,
    negative_prompt: str,
    output_path: str,
    width: int = 1024,
    height: int = 768,
) -> bool:
    """Generate an image using ComfyUI. Returns True on success."""
    workflow = _build_workflow(prompt, negative_prompt, width, height)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            # Queue the prompt
            resp = await client.post(
                f"{settings.COMFYUI_URL}/prompt",
                json={"prompt": workflow},
            )
            resp.raise_for_status()
            prompt_id = resp.json()["prompt_id"]

            # Poll for completion with exponential backoff
            elapsed = 0.0
            interval = POLL_INTERVAL_INITIAL
            while elapsed < MAX_POLL_TIME:
                await asyncio.sleep(interval)
                elapsed += interval
                interval = min(interval * POLL_BACKOFF_FACTOR, POLL_INTERVAL_MAX)

                hist_resp = await client.get(
                    f"{settings.COMFYUI_URL}/history/{prompt_id}"
                )
                hist_resp.raise_for_status()
                history = hist_resp.json()

                if prompt_id not in history:
                    continue

                job_data = history[prompt_id]
                if job_data.get("status", {}).get("completed", False) or "outputs" in job_data:
                    # Find the output image filename
                    outputs = job_data.get("outputs", {})
                    filename = None
                    for node_output in outputs.values():
                        images = node_output.get("images", [])
                        if images:
                            filename = images[0].get("filename")
                            break

                    if not filename:
                        logger.error("No output image found in ComfyUI response")
                        return False

                    # Download the image
                    img_resp = await client.get(
                        f"{settings.COMFYUI_URL}/view",
                        params={
                            "filename": filename,
                            "subfolder": "",
                            "type": "output",
                        },
                    )
                    img_resp.raise_for_status()
                    output.write_bytes(img_resp.content)
                    return True

            logger.error("ComfyUI image generation timed out after %ds", MAX_POLL_TIME)
            return False

    except httpx.HTTPError as exc:
        logger.error("ComfyUI HTTP error: %s", exc)
        return False
    except Exception as exc:
        logger.error("ComfyUI unexpected error: %s", exc)
        return False
