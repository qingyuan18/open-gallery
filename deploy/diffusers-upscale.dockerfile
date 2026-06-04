# Diffusers-based image upscaler (SD x4 Upscaler) — model baked into image.
#
# Pairs with:
#   * cloud-build-diffusers-upscale.sh   builds & pushes to ECR
#   * build-diffusers-upscale-ami.sh     bakes an AMI that pre-pulls this image
#   * k8s-manifests/diffusers-upscale-*.yaml
#
# Independent from comfyui-s3 / comfyui-s3-flux — no shared image tag, model
# directory, or KEDA dimensionValue.
#
# Why a different image: this is a single-purpose FastAPI service running the
# HuggingFace `StableDiffusionUpscalePipeline`. It does not need ComfyUI or
# the Flux/Wan/Qwen weights. Image is small (~7 GiB after fp16 weights) so
# cold pull from a freshly baked AMI is fast.
#
# CUDA / PyTorch: use the same nvcr base as comfyui-s3-flux to keep the GPU
# stack uniform across nodes (sm_89 = L40S, sm_86 = A10g, sm_120 = Blackwell).

# NGC PyTorch 25.03 ships PyTorch 2.7 wheels compiled with sm_120 (Blackwell)
# capability — required because g7e.4xlarge spot pool randomly returns RTX PRO
# 6000 Blackwell. The older 24.12 base only goes up to sm_90 and crashes with
# `CUDA capability sm_120 unsupported` on those nodes.
FROM nvcr.io/nvidia/pytorch:25.03-py3

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/program/hf-cache

# Build SG only allows :443 outbound by default; the AWS regional Ubuntu mirror
# supports HTTPS. Same trick as comfyui-s3-flux.dockerfile.
RUN for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do \
      [ -f "$f" ] && sed -i \
        -e 's|http://archive.ubuntu.com|https://us-east-1.ec2.archive.ubuntu.com|g' \
        -e 's|http://security.ubuntu.com|https://us-east-1.ec2.archive.ubuntu.com|g' \
        -e 's|http://us-east-1.ec2.archive.ubuntu.com|https://us-east-1.ec2.archive.ubuntu.com|g' \
        "$f" || true; \
    done \
 && echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/99retries \
 && apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# numpy<2: torchvision/opencv in this base image still target the numpy 1.x ABI;
# numpy 2.x silently breaks tensor↔ndarray conversions (the same bug that bit
# comfyui-s3-flux SaveImage).
RUN pip install --no-cache-dir \
        "numpy<2" \
        "diffusers==0.32.2" \
        "transformers==4.48.0" \
        "accelerate==1.2.1" \
        "safetensors>=0.4.5" \
        "huggingface_hub>=0.27.0" \
        "fastapi==0.115.6" \
        "uvicorn[standard]==0.32.1" \
        "pillow>=10.4.0" \
        "python-multipart==0.0.19"

# Bake the SD x4 Upscaler weights into the image. Downloaded once at build time
# from HuggingFace; runtime container has no network dep on HF.
#
# We pull only fp16 safetensors + config to keep the image lean. The
# StableDiffusionUpscalePipeline at runtime is loaded with torch_dtype=fp16,
# variant="fp16" — see server.py.
ARG HF_MODEL_ID=stabilityai/stable-diffusion-x4-upscaler
ARG HF_REVISION=main
RUN HF_MODEL_ID="${HF_MODEL_ID}" HF_REVISION="${HF_REVISION}" python -c "\
import os; \
from huggingface_hub import snapshot_download; \
snapshot_download(repo_id=os.environ['HF_MODEL_ID'], revision=os.environ['HF_REVISION'], \
    local_dir='/opt/program/models/x4-upscaler', \
    allow_patterns=['*.json','*.txt','*.fp16.safetensors','tokenizer/*','scheduler/*'])"

# After the download, switch to offline mode so the runtime container never
# tries to phone home (no internet egress assumed in EKS workload SG).
ENV TRANSFORMERS_OFFLINE=1 \
    HF_HUB_OFFLINE=1

WORKDIR /opt/program

# Embed the FastAPI server inline so the cloud-build script only has to ship a
# single Dockerfile (no multi-file build context). Keep deploy/scripts/diffusers_upscale_server.py
# in sync if you edit either side — the standalone copy is what runs locally.
RUN cat > /opt/program/server.py <<'PYEOF'
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
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

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

_pipe = None
_pipe_lock = asyncio.Lock()
_queue_pending: dict[str, dict] = {}
_queue_running: dict[str, dict] = {}


def _load_pipeline():
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
    pipe.set_progress_bar_config(disable=True)
    LOG.info("Pipeline ready in %.1fs", time.time() - t0)
    return pipe


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipe
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
    return JSONResponse({
        "queue_pending": list(_queue_pending.values()),
        "queue_running": list(_queue_running.values()),
    })


def _run_upscale(image, prompt, num_inference_steps, guidance_scale):
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
PYEOF

# Cold-start: page-cache prewarm before Python import. EBS-backed roots have
# zero page cache on first boot, so torch's ~1.6 GiB of .so files take 4-6s
# of physical I/O on the first dlopen even with FSR (FSR fills blocks, not
# pages). Streaming the hot files with `cat > /dev/null` from N parallel
# fadvise(WILLNEED) readers populates page cache while Python is still
# starting, cutting torch+diffusers import wall-time roughly in half.
RUN cat > /opt/program/prewarm.sh <<'SHEOF'
#!/bin/bash
# Read big shared libs in parallel into page cache, then exec server.
# fadvise WILLNEED via vmtouch isn't available; plain `cat > /dev/null`
# triggers readahead which is sufficient on a 1000 MiB/s gp3 volume.
set -u
T=/usr/local/lib/python3.12/dist-packages/torch/lib
D=/usr/local/lib/python3.12/dist-packages
for f in \
  "$T/libtorch_cuda.so" \
  "$T/libtorch_cpu.so" \
  "$T/libtorch_cuda_linalg.so" \
  "$T/libtorch_python.so" \
  "$D/torch/_C.cpython-312-x86_64-linux-gnu.so"; do
  [ -r "$f" ] && cat "$f" > /dev/null &
done
M=/opt/program/models/x4-upscaler
for f in "$M/unet/diffusion_pytorch_model.fp16.safetensors" \
         "$M/text_encoder/model.fp16.safetensors" \
         "$M/vae/diffusion_pytorch_model.fp16.safetensors"; do
  [ -r "$f" ] && cat "$f" > /dev/null &
done
exec python -u /opt/program/server.py
SHEOF
RUN chmod +x /opt/program/prewarm.sh

EXPOSE 8000

# uvicorn binds to 0.0.0.0:8000. /healthz returns 200 once the pipeline is
# loaded; /upscale accepts a multipart image and returns a PNG.
CMD ["/opt/program/prewarm.sh"]
