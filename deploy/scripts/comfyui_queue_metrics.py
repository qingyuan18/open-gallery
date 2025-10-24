#!/usr/bin/env python3
import os
import time
import json
import sys
from datetime import datetime, timezone

import boto3
import requests

# Configuration via environment variables
QUEUE_URL = os.getenv("COMFYUI_QUEUE_URL", "http://127.0.0.1:8188/queue")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SEC", "10"))

METRIC_NAMESPACE = os.getenv("METRIC_NAMESPACE", "ComfyUI")
METRIC_NAME = os.getenv("METRIC_NAME", "QueuePending")
DIMENSION_NAME = os.getenv("METRIC_DIMENSION_NAME", "Deployment")
DIMENSION_VALUE = os.getenv("METRIC_DIMENSION_VALUE", "comfyui")

# Optional: also publish total queue = running + pending
PUBLISH_TOTAL = os.getenv("PUBLISH_TOTAL", "false").lower() in ("1", "true", "yes")
TOTAL_METRIC_NAME = os.getenv("TOTAL_METRIC_NAME", "QueueTotal")

# CloudWatch client uses EKS Pod Identity credentials (no static keys needed)
CW_REGION = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION")
if not CW_REGION:
    print("[queue-metrics] ERROR: AWS_DEFAULT_REGION not set", file=sys.stderr)
    sys.exit(1)

cw = boto3.client("cloudwatch", region_name=CW_REGION)


def get_queue_lengths():
    try:
        resp = requests.get(QUEUE_URL, timeout=2)
        resp.raise_for_status()
        data = resp.json()
        pending = len(data.get("queue_pending", []))
        running = len(data.get("queue_running", []))
        return pending, running
    except Exception as e:
        print(f"[queue-metrics] WARN: failed to fetch {QUEUE_URL}: {e}", file=sys.stderr)
        return None, None


def put_metric(name: str, value: float):
    try:
        cw.put_metric_data(
            Namespace=METRIC_NAMESPACE,
            MetricData=[{
                "MetricName": name,
                "Dimensions": [{"Name": DIMENSION_NAME, "Value": DIMENSION_VALUE}],
                "Timestamp": datetime.now(timezone.utc),
                "Value": float(value),
                "Unit": "Count",
                "StorageResolution": 60,
            }]
        )
    except Exception as e:
        print(f"[queue-metrics] WARN: failed to put metric {name}={value}: {e}", file=sys.stderr)


def main():
    print(f"[queue-metrics] Starting: queue={QUEUE_URL}, ns={METRIC_NAMESPACE}, metric={METRIC_NAME}, dim={DIMENSION_NAME}={DIMENSION_VALUE}, interval={POLL_INTERVAL}s")
    while True:
        pending, running = get_queue_lengths()
        if pending is not None:
            put_metric(METRIC_NAME, pending)
            if PUBLISH_TOTAL:
                total = pending + (running or 0)
                put_metric(TOTAL_METRIC_NAME, total)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

