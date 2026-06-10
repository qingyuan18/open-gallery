#!/usr/bin/env bash
# Smoke-test the Envoy front-door.
# Usage:
#   bash 99-test.sh           # baseline: single /upscale via Envoy
#   bash 99-test.sh load N    # fire N concurrent requests (default 25) to observe
#                             # the 10-in-flight + 10-queued + reject pattern
set -euo pipefail

# Envoy Gateway provisions the data-plane Service in `envoy-gateway-system`,
# not in the Gateway's namespace. Discover it by the controller's labels.
NS=envoy-gateway-system
LOCAL_PORT=18080
SVC=$(kubectl get svc -n "$NS" \
  -l gateway.envoyproxy.io/owning-gateway-name=diffusers-gw \
  -l gateway.envoyproxy.io/owning-gateway-namespace=diffusers-lb \
  -o jsonpath='{.items[0].metadata.name}')
if [ -z "$SVC" ]; then
  echo "ERROR: Envoy data-plane service not found. Did the controller provision it yet?"
  echo "Try: kubectl get gateway diffusers-gw -n diffusers-lb"
  exit 1
fi
echo "Envoy svc: $NS/$SVC"

cleanup() {
  if [ -n "${PF:-}" ] && kill -0 "$PF" 2>/dev/null; then
    kill "$PF" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# Pick a free local port if 18080 is taken.
while lsof -iTCP:$LOCAL_PORT -sTCP:LISTEN -t >/dev/null 2>&1; do
  LOCAL_PORT=$((LOCAL_PORT + 1))
done
echo "Local port: $LOCAL_PORT"

kubectl port-forward -n "$NS" "svc/$SVC" "$LOCAL_PORT":80 >/tmp/pf-envoy.log 2>&1 &
PF=$!

for i in $(seq 1 30); do
  if curl -s --max-time 1 "http://127.0.0.1:$LOCAL_PORT/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.3
done

echo "==> /healthz:"
curl -s -o /dev/stdout -w "  http=%{http_code} time=%{time_total}s\n" "http://127.0.0.1:$LOCAL_PORT/healthz"

# Build a tiny test image once.
python3 -c "from PIL import Image; Image.new('RGB',(256,256),(128,64,200)).save('/tmp/test256.png')"

MODE="${1:-single}"
if [ "$MODE" = "load" ]; then
  N="${2:-25}"
  echo "==> Firing $N concurrent /upscale requests (maxParallel=10, maxPending=10, expect ~5 immediate 503s)"
  rm -f /tmp/envoy-load.txt
  for i in $(seq 1 "$N"); do
    (
      curl -s -o /dev/null \
        -w "req=$i code=%{http_code} time=%{time_total}s\n" \
        -X POST "http://127.0.0.1:$LOCAL_PORT/upscale" \
        -F "image=@/tmp/test256.png" \
        -F "num_inference_steps=20" \
        -F "prompt=a high resolution photo" >> /tmp/envoy-load.txt
    ) &
  done
  wait
  echo "--- per-request ---"
  cat /tmp/envoy-load.txt | sort
  echo "--- summary ---"
  awk -F'code=' '{split($2,a," "); print a[1]}' /tmp/envoy-load.txt | sort | uniq -c
else
  echo "==> Single /upscale via Envoy:"
  T0=$(date +%s.%N)
  curl -s -o /tmp/envoy-up.png \
    -w "http=%{http_code} time=%{time_total}s\n" \
    -X POST "http://127.0.0.1:$LOCAL_PORT/upscale" \
    -F "image=@/tmp/test256.png" \
    -F "num_inference_steps=20" \
    -F "prompt=a high resolution photo"
  file /tmp/envoy-up.png
fi
