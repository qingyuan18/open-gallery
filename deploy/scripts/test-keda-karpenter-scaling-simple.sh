#!/bin/bash
# Simplified KEDA + Karpenter scale-out test.
#
# Difference vs test-keda-karpenter-scaling.sh:
#   * Assumes the GPU AMI has Flux models pre-baked at /opt/comfyui-models-seed
#     and EC2NodeClass userData copies them to /opt/dlami/nvme/comfyui-models
#     before the kubelet marks the node Ready.
#   * Therefore comfyui-nvme-prewarm DaemonSet is NOT a prerequisite, and the
#     end-to-end timer measures: prompt submit -> CW metric -> KEDA -> HPA ->
#     Karpenter -> EC2 boot (incl. seed copy) -> kubelet Ready -> pod Ready.
#
# Usage:
#   ./test-keda-karpenter-scaling-simple.sh                # full flow (10 jobs)
#   ./test-keda-karpenter-scaling-simple.sh --submit 20    # custom job count
#   ./test-keda-karpenter-scaling-simple.sh --watch        # observe only
#   ./test-keda-karpenter-scaling-simple.sh --check        # prereqs only
#   ./test-keda-karpenter-scaling-simple.sh --metric       # query CloudWatch

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
      sed -n '2,20p' "$0"; exit 0 ;;
    *) err "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Prerequisites: same as the original, minus the prewarm DaemonSet ─────
check_prereqs() {
  step "Checking prerequisites..."
  local ok=true

  if kubectl get pods -n keda -l app=keda-operator --no-headers 2>/dev/null | grep -q Running; then
    info "KEDA operator running"
  else
    err "KEDA operator not found"; ok=false
  fi

  if kubectl get crd nodepools.karpenter.sh &>/dev/null; then
    info "Karpenter NodePool CRD found"
  else
    err "Karpenter not installed"; ok=false
  fi

  if kubectl get deploy "$DEPLOY_NAME" -n "$NAMESPACE" &>/dev/null; then
    local ready
    ready=$(kubectl get deploy "$DEPLOY_NAME" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')
    info "Deployment '$DEPLOY_NAME' (ready=${ready:-0})"
  else
    err "Deployment '$DEPLOY_NAME' not found"; ok=false
  fi

  if kubectl get scaledobject comfyui-cw-scaler -n "$NAMESPACE" &>/dev/null; then
    info "KEDA ScaledObject present"
  else
    err "KEDA ScaledObject missing"; ok=false
  fi

  if kubectl get nodepool gpu &>/dev/null; then
    info "Karpenter NodePool 'gpu' present"
  else
    warn "NodePool 'gpu' not found (no new nodes will be provisioned)"
  fi

  # Confirm the Flux-preloaded AMI is in use.
  local ami
  ami=$(kubectl get ec2nodeclass gpu -o jsonpath='{.spec.amiSelectorTerms[0].id}' 2>/dev/null || echo "")
  if [ -n "$ami" ]; then
    info "EC2NodeClass amiSelectorTerms: $ami"
  else
    warn "Could not read EC2NodeClass 'gpu' AMI"
  fi

  # Active warning if the prewarm DaemonSet is still around (it shouldn't be).
  if kubectl get ds comfyui-nvme-prewarm -n "$NAMESPACE" &>/dev/null; then
    warn "comfyui-nvme-prewarm DaemonSet still exists — delete it for a clean test:"
    warn "  kubectl delete ds comfyui-nvme-prewarm -n $NAMESPACE"
  else
    info "Prewarm DaemonSet absent (as expected)"
  fi

  [ "$ok" = false ] && { err "Fix prerequisites first."; exit 1; }
  echo ""; info "Prerequisites OK"
}

# ── Submit dummy prompts ─────────────────────────────────────────────────
submit_jobs() {
  step "Submitting $NUM_JOBS prompts..."

  local pf_pid=""
  if ! curl -s --max-time 2 http://localhost:8188/ &>/dev/null; then
    step "Port-forwarding $SERVICE_NAME..."
    kubectl port-forward -n "$NAMESPACE" "svc/$SERVICE_NAME" 8188:8188 &>/dev/null &
    pf_pid=$!
    sleep 3
    curl -s --max-time 3 http://localhost:8188/ &>/dev/null \
      || { err "ComfyUI not reachable"; kill "$pf_pid" 2>/dev/null || true; exit 1; }
    info "Port-forward up (pid=$pf_pid)"
  fi

  # Flux-based workflow (uses the models we baked into the AMI).
  local prompt_tpl='{"prompt":{
    "1":{"class_type":"UNETLoader","inputs":{"unet_name":"flux1-dev-fp8.safetensors","weight_dtype":"fp8_e4m3fn"}},
    "2":{"class_type":"DualCLIPLoader","inputs":{"clip_name1":"t5xxl_fp8_e4m3fn.safetensors","clip_name2":"clip_l.safetensors","type":"flux"}},
    "3":{"class_type":"VAELoader","inputs":{"vae_name":"ae.safetensors"}},
    "4":{"class_type":"CLIPTextEncode","inputs":{"text":"a serene mountain lake at sunrise","clip":["2",0]}},
    "5":{"class_type":"CLIPTextEncode","inputs":{"text":"","clip":["2",0]}},
    "6":{"class_type":"EmptyLatentImage","inputs":{"width":1024,"height":1024,"batch_size":1}},
    "7":{"class_type":"KSampler","inputs":{"seed":SEED,"steps":20,"cfg":1.0,"sampler_name":"euler","scheduler":"simple","denoise":1,"model":["1",0],"positive":["4",0],"negative":["5",0],"latent_image":["6",0]}},
    "8":{"class_type":"VAEDecode","inputs":{"samples":["7",0],"vae":["3",0]}},
    "9":{"class_type":"SaveImage","inputs":{"filename_prefix":"flux","images":["8",0]}}
  }}'

  local success=0
  for i in $(seq 1 "$NUM_JOBS"); do
    local body="${prompt_tpl//SEED/$((RANDOM * i))}"
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8188/prompt \
      -H "Content-Type: application/json" -d "$body") || true
    [ "$code" = "200" ] && ((success++)) || warn "Prompt $i HTTP $code"
  done
  info "Submitted $success/$NUM_JOBS"

  local queue pending running
  queue=$(curl -s http://localhost:8188/queue 2>/dev/null || echo '{}')
  pending=$(echo "$queue" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('queue_pending',[])))" 2>/dev/null || echo "?")
  running=$(echo "$queue" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('queue_running',[])))" 2>/dev/null || echo "?")
  info "Queue: pending=$pending running=$running"

  [ -n "$pf_pid" ] && warn "Port-forward still alive (pid=$pf_pid). kill $pf_pid when done."

  echo ""
  info "Wait ~30-60s for CloudWatch -> KEDA -> Karpenter -> new GPU node Ready."
  info "Run '$0 --watch' to follow scale-out."
}

# ── Watch ────────────────────────────────────────────────────────────────
watch_scaling() {
  step "Watching scaling (Ctrl+C to stop)"
  local start_ts=$(date +%s)
  while true; do
    local elapsed=$(( $(date +%s) - start_ts ))
    echo -e "${BLUE}── $(date +%H:%M:%S)  (+${elapsed}s) ──${NC}"
    echo -e "${GREEN}Deployment:${NC}"
    kubectl get deploy "$DEPLOY_NAME" -n "$NAMESPACE" --no-headers 2>/dev/null || echo "  none"
    echo -e "${GREEN}HPA:${NC}"
    kubectl get hpa -n "$NAMESPACE" --no-headers 2>/dev/null | grep comfyui || echo "  none"
    echo -e "${GREEN}Pods (with phase):${NC}"
    kubectl get pods -n "$NAMESPACE" -l app=comfyui \
      -o custom-columns=NAME:.metadata.name,PHASE:.status.phase,READY:.status.containerStatuses[0].ready,NODE:.spec.nodeName \
      --no-headers 2>/dev/null || echo "  none"
    echo -e "${GREEN}NodeClaims:${NC}"
    kubectl get nodeclaims --no-headers 2>/dev/null || echo "  none"
    echo -e "${GREEN}GPU Nodes (workload=gpu):${NC}"
    kubectl get nodes -l workload=gpu \
      -o custom-columns=NAME:.metadata.name,STATUS:.status.conditions[?\(@.type==\"Ready\"\)].status,AGE:.metadata.creationTimestamp \
      --no-headers 2>/dev/null || echo "  none"
    echo ""
    sleep 5
  done
}

query_metric() {
  step "QueuePending (last 10 min)"
  local start end
  start=$(date -u -v-10M +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S)
  end=$(date -u +%Y-%m-%dT%H:%M:%S)
  aws cloudwatch get-metric-statistics \
    --namespace ComfyUI --metric-name QueuePending \
    --dimensions Name=Deployment,Value=comfyui \
    --start-time "$start" --end-time "$end" \
    --period 30 --statistics Average Maximum \
    --region "$AWS_REGION" --output table
}

case "$ACTION" in
  check)  check_prereqs ;;
  submit) submit_jobs ;;
  watch)  watch_scaling ;;
  metric) query_metric ;;
  all)    check_prereqs; echo ""; submit_jobs; echo ""; watch_scaling ;;
esac
