# Sidecar image to push ComfyUI queue metrics to CloudWatch
# Minimal Python + boto3 + requests
FROM python:3.12-alpine

RUN pip install --no-cache-dir boto3 requests

# Copy in the metrics pusher script (mounted path in repo)
# The deploy scripts build from repo root, so this path is valid as build context
COPY deploy/scripts/comfyui_queue_metrics.py /app/queue_metrics.py

ENV PYTHONUNBUFFERED=1
WORKDIR /app

ENTRYPOINT ["python", "/app/queue_metrics.py"]

