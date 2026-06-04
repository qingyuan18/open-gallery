#!/bin/bash
# Test KEDA + Karpenter horizontal scaling for comfyui Deployment
# Usage: ./test-keda-karpenter-scaling.sh [--submit N] [--watch] [--check] [--metric] [--region REGION]

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }
step()  { echo -e "${BLUE}[→]${NC} $1"; }

AWS_REGION="${AWS_REGION:-us-east-1}"
NAMESPACE="default"
DEPLOY_NAME="comfyui"
SERVICE_NAME="comfyui-service"
NUM_JOBS=10
ACTION="all"

while [[ $# -gt 0 ]]; do
  case $1 in
    --submit)   ACTION="submit"; NUM_JOBS="${2:-10}"; shift 2 ;;
    --watch)    ACTION="watch"; shift ;;
    --check)    ACTION="check"; shift ;;
    --metric)   ACTION="metric"; shift ;;
    --region)   AWS_REGION="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [--check] [--submit N] [--watch] [--metric] [--region REGION]"
      echo "  (no args)   Run full flow: check → submit 10 jobs → watch"
      echo "  --check     Verify prerequisites only"
      echo "  --submit N  Submit N dummy prompts to trigger scale-out"
      echo "  --watch     Watch pods/hpa/nodes in a loop"
      echo "  --metric    Query CloudWatch QueuePending metric"
      exit 0 ;;
    *) err "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Prerequisites check ──────────────────────────────────────────────
check_prereqs() {
  step "Checking prerequisites..."
  local ok=true

  # KEDA operator
  if kubectl get pods -n keda -l app=keda-operator --no-headers 2>/dev/null | grep -q Running; then
    info "KEDA operator running"
  else
    err "KEDA operator not found in namespace 'keda'"; ok=false
  fi

  # Karpenter (self-managed pods OR HyperPod managed — check NodePool CRD as fallback)
  if kubectl get pods -n kube-system -l app.kubernetes.io/name=karpenter --no-headers 2>/dev/null | grep -q Running; then
    info "Karpenter running (self-managed)"
  elif kubectl get pods -A -l app.kubernetes.io/name=karpenter --no-headers 2>/dev/null | grep -q Running; then
    info "Karpenter running (self-managed)"
  elif kubectl get crd nodepools.karpenter.sh &>/dev/null; then
    info "Karpenter NodePool CRD found (HyperPod managed)"
  else
    err "Karpenter not found"; ok=false
  fi

  # NVIDIA device plugin
  if kubectl get ds -A --no-headers 2>/dev/null | grep -q nvidia; then
    info "NVIDIA device plugin found"
  else
    warn "NVIDIA device plugin not detected (GPU scheduling may fail)"
  fi

  # Deployment
  if kubectl get deploy "$DEPLOY_NAME" -n "$NAMESPACE" &>/dev/null; then
    local ready
    ready=$(kubectl get deploy "$DEPLOY_NAME" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')
    info "Deployment '$DEPLOY_NAME' exists (ready replicas: ${ready:-0})"
  else
    err "Deployment '$DEPLOY_NAME' not found in namespace '$NAMESPACE'"; ok=false
  fi

  # KEDA ScaledObject
  if kubectl get scaledobject comfyui-cw-scaler -n "$NAMESPACE" &>/dev/null; then
    info "KEDA ScaledObject 'comfyui-cw-scaler' exists"
  else
    err "KEDA ScaledObject not found"; ok=false
  fi

  # Karpenter NodePool (check both 'gpu' for standard EKS and 'gpu-hp' for HyperPod)
  if kubectl get nodepool gpu-hp &>/dev/null; then
    info "Karpenter NodePool 'gpu-hp' exists (HyperPod)"
  elif kubectl get nodepool gpu &>/dev/null; then
    info "Karpenter NodePool 'gpu' exists"
  else
    warn "Karpenter NodePool not found (new nodes won't be provisioned)"
  fi

  # HPA (created by KEDA)
  if kubectl get hpa -n "$NAMESPACE" --no-headers 2>/dev/null | grep -q comfyui; then
    info "HPA created by KEDA found"
  else
    warn "HPA not yet created (KEDA may create it after first metric)"
  fi

  if [ "$ok" = false ]; then
    err "Some prerequisites missing. Fix them before testing."
    exit 1
  fi
  echo ""
  info "All critical prerequisites met!"
}

# ── Submit dummy prompts ─────────────────────────────────────────────
submit_jobs() {
  step "Submitting $NUM_JOBS prompts to ComfyUI to trigger scale-out..."

  # Port-forward in background
  local pf_pid=""
  if ! curl -s --max-time 2 http://localhost:8188/ &>/dev/null; then
    step "Starting port-forward to $SERVICE_NAME..."
    kubectl port-forward -n "$NAMESPACE" "svc/$SERVICE_NAME" 8188:8188 &>/dev/null &
    pf_pid=$!
    sleep 3
    if ! curl -s --max-time 3 http://localhost:8188/ &>/dev/null; then
      err "Cannot reach ComfyUI at localhost:8188. Is the pod ready?"
      kill "$pf_pid" 2>/dev/null || true
      exit 1
    fi
    info "Port-forward established (PID $pf_pid)"
  fi

  # A minimal valid ComfyUI prompt (KSampler workflow)
  local prompt_tpl='{"prompt":{"3":{"class_type":"KSampler","inputs":{"seed":SEED,"steps":50,"cfg":7,"sampler_name":"euler","scheduler":"normal","denoise":1,"model":["4",0],"positive":["6",0],"negative":["7",0],"latent_image":["5",0]}},"4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":"sd_xl_base_1.0.safetensors"}},"5":{"class_type":"EmptyLatentImage","inputs":{"width":1024,"height":1024,"batch_size":1}},"6":{"class_type":"CLIPTextEncode","inputs":{"text":"a beautiful landscape, mountains, sunset, 8k","clip":["4",1]}},"7":{"class_type":"CLIPTextEncode","inputs":{"text":"bad quality, blurry","clip":["4",1]}}}}'

  local success=0
  for i in $(seq 1 "$NUM_JOBS"); do
    local body="${prompt_tpl//SEED/$((RANDOM * i))}"
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8188/prompt \
      -H "Content-Type: application/json" -d "$body") || true
    if [ "$code" = "200" ]; then
      ((success++))
    else
      warn "Prompt $i returned HTTP $code"
    fi
  done
  info "Submitted $success/$NUM_JOBS prompts"

  # Check queue
  local queue
  queue=$(curl -s http://localhost:8188/queue 2>/dev/null || echo '{}')
  local pending running
  pending=$(echo "$queue" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('queue_pending',[])))" 2>/dev/null || echo "?")
  running=$(echo "$queue" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('queue_running',[])))" 2>/dev/null || echo "?")
  info "Queue status: pending=$pending, running=$running"

  if [ -n "$pf_pid" ]; then
    warn "Port-forward still running (PID $pf_pid). Kill with: kill $pf_pid"
  fi

  echo ""
  info "Now wait ~1-2 min for CloudWatch metric to propagate, then KEDA will scale."
  info "Run '$0 --watch' to observe scaling."
}

# ── Watch scaling ────────────────────────────────────────────────────
watch_scaling() {
  step "Watching scaling (Ctrl+C to stop)..."
  echo ""
  while true; do
    echo -e "${BLUE}── $(date +%H:%M:%S) ──${NC}"
    echo -e "${GREEN}Deployment:${NC}"
    kubectl get deploy "$DEPLOY_NAME" -n "$NAMESPACE" --no-headers 2>/dev/null || echo "  not found"
    echo -e "${GREEN}HPA:${NC}"
    kubectl get hpa -n "$NAMESPACE" --no-headers 2>/dev/null | grep comfyui || echo "  not found"
    echo -e "${GREEN}Pods:${NC}"
    kubectl get pods -n "$NAMESPACE" -l app=comfyui --no-headers 2>/dev/null || echo "  none"
    echo -e "${GREEN}GPU Nodes (workload=gpu):${NC}"
    kubectl get nodes -l workload=gpu --no-headers 2>/dev/null || echo "  none"
    echo -e "${GREEN}NodeClaims:${NC}"
    kubectl get nodeclaims --no-headers 2>/dev/null || echo "  none"
    echo ""
    sleep 10
  done
}

# ── Query CloudWatch metric ─────────────────────────────────────────
query_metric() {
  step "Querying CloudWatch QueuePending metric (last 10 min)..."
  local start end
  start=$(date -u -v-10M +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S)
  end=$(date -u +%Y-%m-%dT%H:%M:%S)

  aws cloudwatch get-metric-statistics \
    --namespace ComfyUI \
    --metric-name QueuePending \
    --dimensions Name=Deployment,Value=comfyui \
    --start-time "$start" \
    --end-time "$end" \
    --period 30 \
    --statistics Average Maximum \
    --region "$AWS_REGION" \
    --output table
}

# ── Main ─────────────────────────────────────────────────────────────
case "$ACTION" in
  check)  check_prereqs ;;
  submit) submit_jobs ;;
  watch)  watch_scaling ;;
  metric) query_metric ;;
  all)
    check_prereqs
    echo ""
    submit_jobs
    echo ""
    watch_scaling
    ;;
esac
