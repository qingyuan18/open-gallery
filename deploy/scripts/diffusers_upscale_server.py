"""FastAPI front for the SD x4 Upscaler diffusers pipeline.

Endpoints
---------
GET  /healthz   200 once the pipeline is loaded onto the GPU
GET  /queue     {"queue_pending": [...], "queue_running": [...]} — same shape
                as ComfyUI's /queue, so the existing comfyui-cw-metrics sidecar
                can be reused unchanged
POST /upscale   multipart upload (`image`) + optional form fields
                (`prompt`, `num_inference_steps`, `guidance_scale`).
                Returns image/png.

Concurrency
-----------
The pipeline is not thread-safe and a single L40S can only run one diffusion
job at a time, so all requests serialize through an asyncio.Lock. Pending
requests sit in queue_pending until the lock is acquired, at which point they
move to queue_running. The /queue endpoint reports those counts so KEDA can
scale on QueuePending exactly the same way it does for ComfyUI.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image

LOG = logging.getLogger("upscale")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

MODEL_PATH = os.getenv("MODEL_PATH", "/opt/program/models/x4-upscaler")
DEFAULT_PROMPT = os.getenv("DEFAULT_PROMPT", "a high resolution photo")
DEFAULT_STEPS = int(os.getenv("DEFAULT_STEPS", "20"))
DEFAULT_GUIDANCE = float(os.getenv("DEFAULT_GUIDANCE", "7.0"))
MAX_INPUT_PX = int(os.getenv("MAX_INPUT_PX", "512"))  # x4 -> 2048 px

# The diffusers pipeline runs blocking torch ops; protect with a lock and run
# the actual call inside asyncio.to_thread so the event loop keeps serving
# /healthz and /queue while a job is in-flight.
_pipe = None
_pipe_lock = asyncio.Lock()
_queue_pending: dict[str, dict] = {}
_queue_running: dict[str, dict] = {}


def _load_pipeline():
    """Load StableDiffusionUpscalePipeline from local snapshot in fp16 onto CUDA."""
    from diffusers import StableDiffusionUpscalePipeline

    LOG.info("Loading pipeline from %s", MODEL_PATH)
    t0 = time.time()
    pipe = StableDiffusionUpscalePipeline.from_pretrained(
        MODEL_PATH,
        torch_dtype=torch.float16,
        variant="fp16",
        local_files_only=True,
    )
    pipe.to("cuda")
    # xformers is built into the nvcr image; SDPA is fine and avoids extra deps.
    pipe.set_progress_bar_config(disable=True)
    LOG.info("Pipeline ready in %.1fs", time.time() - t0)
    return pipe


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipe
    # Load synchronously at startup; readiness probe will only flip after this
    # returns, which is the desired behavior.
    _pipe = await asyncio.to_thread(_load_pipeline)
    yield
    _pipe = None


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    if _pipe is None:
        raise HTTPException(status_code=503, detail="pipeline not loaded")
    return {"status": "ok"}


@app.get("/queue")
async def queue():
    # Match ComfyUI's response shape so the comfyui-cw-metrics sidecar (which
    # parses queue_pending / queue_running list lengths) Just Works.
    return JSONResponse(
        {
            "queue_pending": list(_queue_pending.values()),
            "queue_running": list(_queue_running.values()),
        }
    )


def _run_upscale(
    image: Image.Image,
    prompt: str,
    num_inference_steps: int,
    guidance_scale: float,
) -> Image.Image:
    out = _pipe(
        prompt=prompt,
        image=image,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
    )
    return out.images[0]


@app.post("/upscale")
async def upscale(
    image: UploadFile = File(...),
    prompt: str = Form(DEFAULT_PROMPT),
    num_inference_steps: int = Form(DEFAULT_STEPS),
    guidance_scale: float = Form(DEFAULT_GUIDANCE),
):
    if _pipe is None:
        raise HTTPException(status_code=503, detail="pipeline not loaded")

    raw = await image.read()
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid image: {exc}") from exc

    if max(img.size) > MAX_INPUT_PX:
        raise HTTPException(
            status_code=400,
            detail=f"input must be <= {MAX_INPUT_PX}px on the long side (got {img.size})",
        )

    job_id = uuid.uuid4().hex
    _queue_pending[job_id] = {"job_id": job_id, "size": img.size}

    async with _pipe_lock:
        _queue_pending.pop(job_id, None)
        _queue_running[job_id] = {"job_id": job_id, "size": img.size}
        try:
            t0 = time.time()
            result = await asyncio.to_thread(
                _run_upscale, img, prompt, num_inference_steps, guidance_scale
            )
            elapsed = time.time() - t0
            LOG.info("job=%s in=%s out=%s steps=%d %.2fs", job_id, img.size, result.size, num_inference_steps, elapsed)
        finally:
            _queue_running.pop(job_id, None)

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), log_level="info")
