#!/bin/bash
# Smoke test for diffusers-upscale Deployment.
# Port-forwards to the pod, sends a small test image to /upscale, saves the
# result, and reports timing. Use after the AMI bake + manifests are applied
# and the pod has come up.
#
# Usage:
#   ./test-diffusers-upscale.sh                      # uses Service
#   POD=diffusers-upscale-xxx ./test-diffusers-upscale.sh   # direct to a pod

set -euo pipefail

NAMESPACE="${NAMESPACE:-default}"
LOCAL_PORT="${LOCAL_PORT:-18000}"
OUT_FILE="${OUT_FILE:-/tmp/upscale-out.png}"
INPUT_FILE="${INPUT_FILE:-}"
PROMPT="${PROMPT:-a high resolution photo}"
STEPS="${STEPS:-20}"
GUIDANCE="${GUIDANCE:-7.0}"

if [ -n "${POD:-}" ]; then
  TARGET_KIND="pod"
  TARGET="$POD"
else
  TARGET_KIND="svc"
  TARGET="diffusers-upscale"
fi

echo "[smoke] Target: $TARGET_KIND/$TARGET (local :$LOCAL_PORT -> :8000)"

# Generate a tiny test image if none provided. 256x256 PIL gradient is enough
# to exercise the pipeline end-to-end.
if [ -z "$INPUT_FILE" ]; then
  INPUT_FILE="$(mktemp -t upscale-in-XXXXXX)".png
  python3 - "$INPUT_FILE" <<'PYEOF'
import sys
from PIL import Image, ImageDraw
img = Image.new("RGB", (256, 256))
draw = ImageDraw.Draw(img)
for y in range(256):
    draw.line([(0, y), (255, y)], fill=(y, (y * 2) % 256, (y * 3) % 256))
draw.rectangle([64, 64, 192, 192], outline=(255, 255, 255), width=4)
img.save(sys.argv[1])
print(f"[smoke] wrote test image: {sys.argv[1]} (256x256)")
PYEOF
fi

# Start port-forward in background
kubectl port-forward "$TARGET_KIND/$TARGET" -n "$NAMESPACE" "$LOCAL_PORT:8000" >/tmp/upscale-pf.log 2>&1 &
PF_PID=$!
trap "kill $PF_PID 2>/dev/null || true" EXIT

# Wait for /healthz
echo "[smoke] waiting for /healthz on :$LOCAL_PORT..."
for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$LOCAL_PORT/healthz" >/dev/null 2>&1; then
    echo "[smoke] /healthz OK after ${i}s"
    break
  fi
  sleep 1
done
curl -fsS "http://127.0.0.1:$LOCAL_PORT/healthz" >/dev/null

echo "[smoke] POST /upscale steps=$STEPS guidance=$GUIDANCE"
T0=$(date +%s)
curl -fsS -o "$OUT_FILE" \
  -F "image=@${INPUT_FILE}" \
  -F "prompt=${PROMPT}" \
  -F "num_inference_steps=${STEPS}" \
  -F "guidance_scale=${GUIDANCE}" \
  "http://127.0.0.1:$LOCAL_PORT/upscale"
T1=$(date +%s)

SIZE=$(wc -c <"$OUT_FILE" | tr -d ' ')
echo "[smoke] DONE in $((T1 - T0))s, output=$OUT_FILE (${SIZE} bytes)"
file "$OUT_FILE" || true
