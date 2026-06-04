# KEDA + Karpenter 扩缩容延迟基准测试

基于 50GB 测试镜像（见 [soci-benchmark-image.md](soci-benchmark-image.md)），保持最小 1 台 GPU 节点常驻，最大弹性 10 台，通过不同并发/总请求量压测，测量请求级 P90/P95/P99 延迟。

> 参考部署文档：`keda_scale` 分支 `deploy/EKS_DEPLOYMENT.md`

## 一、环境准备

### 1.1 确认组件就绪

```bash
kubectl get scaledobject comfyui-cw-scaler -n default
kubectl get nodepools gpu -o wide
kubectl get ds comfyui-nvme-prewarm -o wide

export ECR_REGISTRY=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
```

### 1.2 配置扩缩边界：min=1, max=10

**KEDA ScaledObject**（Pod 层）：

```bash
kubectl patch scaledobject comfyui-cw-scaler --type=merge -p '
spec:
  minReplicaCount: 1
  maxReplicaCount: 10
'
kubectl get scaledobject comfyui-cw-scaler -o jsonpath='{.spec.minReplicaCount} {.spec.maxReplicaCount}' && echo
# 预期: 1 10
```

**Karpenter NodePool**（节点层）：

```bash
kubectl patch nodepool gpu --type=merge -p '
spec:
  limits:
    nvidia.com/gpu: "10"
'
kubectl get nodepool gpu -o jsonpath='{.spec.limits}' && echo
# 预期: {"nvidia.com/gpu":"10"}
```

> HyperPod EKS：`kubectl patch nodepool gpu-hp --type=merge -p 'spec: {limits: {"nvidia.com/gpu": "10"}}'`

### 1.3 切换至 50GB 测试镜像

```bash
# 备份原始镜像
kubectl get deploy comfyui -o jsonpath='{.spec.template.spec.containers[0].image}' > /tmp/original-image.txt

# 切换
kubectl set image deployment/comfyui comfyui=${ECR_REGISTRY}/comfyui-s3-bench:50g
kubectl rollout status deployment/comfyui --timeout=600s
```

### 1.4 确认基线状态

```bash
# 应有 1 个 Pod Running、1 个 GPU 节点
kubectl get pods -l app=comfyui -o wide
kubectl get nodes -l workload=gpu -o wide
```

## 二、压测矩阵

使用不同并发数和总请求量组合，覆盖从不触发扩容到触发满弹的场景：

| 测试组 | 并发数 | 总请求数 | 预期行为 |
|--------|-------|---------|---------|
| T1 | 1 | 20 | 单 Pod 处理，不触发扩容（基线） |
| T2 | 5 | 50 | 队列积压，KEDA 扩容 2-3 Pod |
| T3 | 10 | 100 | 中等压力，扩容 4-6 Pod + 新节点 |
| T4 | 20 | 200 | 高压力，扩容至接近上限，Karpenter 弹多个新节点 |
| T5 | 30 | 300 | 极限压力，触发 max=10 上限，观察排队延迟 |

## 三、压测执行

### 3.1 准备压测 workflow

将一个标准的 ComfyUI workflow JSON 存为测试 payload：

```bash
# 使用项目中现有的 workflow，或创建一个简单的测试 payload
cat > /tmp/bench-payload.json <<'EOF'
{
  "prompt": {
    "1": {
      "class_type": "CheckpointLoaderSimple",
      "inputs": { "ckpt_name": "sd_xl_base_1.0.safetensors" }
    },
    "2": {
      "class_type": "CLIPTextEncode",
      "inputs": { "text": "benchmark test image", "clip": ["1", 1] }
    },
    "3": {
      "class_type": "CLIPTextEncode",
      "inputs": { "text": "", "clip": ["1", 1] }
    },
    "4": {
      "class_type": "KSampler",
      "inputs": {
        "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
        "latent_image": ["5", 0],
        "seed": 42, "steps": 20, "cfg": 7.0,
        "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0
      }
    },
    "5": {
      "class_type": "EmptyLatentImage",
      "inputs": { "width": 1024, "height": 1024, "batch_size": 1 }
    },
    "6": {
      "class_type": "VAEDecode",
      "inputs": { "samples": ["4", 0], "vae": ["1", 2] }
    },
    "7": {
      "class_type": "SaveImage",
      "inputs": { "images": ["6", 0], "filename_prefix": "bench" }
    }
  }
}
EOF
```

### 3.2 压测脚本

```bash
#!/bin/bash
# bench.sh — 并发压测 ComfyUI 并采集请求级延迟
set -euo pipefail

CONCURRENCY=${1:?用法: bench.sh <并发数> <总请求数>}
TOTAL=${2:?用法: bench.sh <并发数> <总请求数>}
COMFYUI_URL="http://$(kubectl get svc comfyui-service -o jsonpath='{.spec.clusterIP}'):8188"
RESULTS_FILE="bench-c${CONCURRENCY}-n${TOTAL}.csv"

echo "target: $COMFYUI_URL  concurrency: $CONCURRENCY  total: $TOTAL"
echo "request_id,start_epoch_ms,end_epoch_ms,latency_ms,http_code" > $RESULTS_FILE

submit_request() {
  local id=$1
  local start_ms=$(date +%s%3N)
  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${COMFYUI_URL}/prompt" \
    -H "Content-Type: application/json" \
    -d @/tmp/bench-payload.json)
  local end_ms=$(date +%s%3N)
  local latency=$((end_ms - start_ms))
  echo "${id},${start_ms},${end_ms},${latency},${http_code}" >> $RESULTS_FILE
}

# 并发控制：使用 fd 作为信号量
exec 3<> <(:)
for ((i=0; i<CONCURRENCY; i++)); do echo >&3; done

for ((i=1; i<=TOTAL; i++)); do
  read -u3
  {
    submit_request $i
    echo >&3
  } &
done
wait

echo "压测完成，结果: $RESULTS_FILE"
```

### 3.3 执行压测矩阵

```bash
chmod +x bench.sh

# 开启监控（单独终端）
# 终端 1: Pod 变化
watch -n 3 'kubectl get pods -l app=comfyui -o wide'
# 终端 2: 节点变化
watch -n 5 'kubectl get nodes -l workload=gpu -o wide && echo "---" && kubectl get nodeclaims -o wide'
# 终端 3: KEDA/HPA 状态
watch -n 5 'kubectl get hpa -o wide && echo "---" && kubectl get scaledobject comfyui-cw-scaler -o wide'

# 依次执行各测试组（每组之间等待缩容稳定）
./bench.sh 1 20      # T1: 基线
sleep 600             # 等待缩容回到 1 Pod

./bench.sh 5 50      # T2: 轻度扩容
sleep 600

./bench.sh 10 100    # T3: 中等扩容
sleep 600

./bench.sh 20 200    # T4: 高压
sleep 600

./bench.sh 30 300    # T5: 极限
```

> 每组之间 sleep 600s（10 分钟）是为了等 KEDA cooldown（180s）+ scaleDown stabilization（300s）将 Pod 缩回 1，Karpenter consolidateAfter（2m）回收空节点，确保每组测试的起始状态一致。

### 3.4 采集扩缩过程数据

每组压测结束后，采集当轮扩缩容的关键事件：

```bash
# Pod 扩缩时间线
kubectl get events --sort-by='.lastTimestamp' | grep -E 'ScaledObject|HorizontalPodAutoscaler|Scaled'

# Karpenter 节点供给时间线
kubectl get events --sort-by='.lastTimestamp' | grep -E 'NodeClaim|Karpenter'

# 各 Pod 从 Pending → Ready 的耗时
kubectl get pods -l app=comfyui -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\t"}{.status.conditions[?(@.type=="PodScheduled")].lastTransitionTime}{"\t"}{.status.conditions[?(@.type=="Ready")].lastTransitionTime}{"\n"}{end}'
```

## 四、计算 P90/P95/P99

```bash
#!/bin/bash
# calc-percentiles.sh — 从 CSV 计算百分位数
FILE=${1:?用法: calc-percentiles.sh <csv文件>}

echo "=== $FILE ==="
tail -n +2 "$FILE" | cut -d',' -f4 | sort -n | awk '
  { vals[NR] = $1; sum += $1 }
  END {
    n = NR
    printf "样本数:  %d\n", n
    printf "最小值:  %dms\n", vals[1]
    printf "最大值:  %dms\n", vals[n]
    printf "平均值:  %.0fms\n", sum/n
    printf "P50:     %dms\n", vals[int(n*0.50+0.5)]
    printf "P90:     %dms\n", vals[int(n*0.90+0.5)]
    printf "P95:     %dms\n", vals[int(n*0.95+0.5)]
    printf "P99:     %dms\n", vals[int(n*0.99+0.5)]
  }
'
```

批量计算所有测试组：

```bash
chmod +x calc-percentiles.sh
for f in bench-c*.csv; do
  ./calc-percentiles.sh "$f"
  echo ""
done
```

## 五、结果记录

| 测试组 | 并发 | 总请求 | Pod 峰值 | 节点峰值 | P50 | P90 | P95 | P99 | 最大值 |
|--------|-----|-------|---------|---------|-----|-----|-----|-----|-------|
| T1 | 1 | 20 | | | | | | | |
| T2 | 5 | 50 | | | | | | | |
| T3 | 10 | 100 | | | | | | | |
| T4 | 20 | 200 | | | | | | | |
| T5 | 30 | 300 | | | | | | | |

**扩缩容行为记录：**

| 测试组 | 首次扩容触发时间 | 扩容至峰值耗时 | 新建节点数 | 节点供给平均耗时 | 缩容回 1 Pod 耗时 |
|--------|---------------|-------------|-----------|----------------|-----------------|
| T1 | — | — | 0 | — | — |
| T2 | | | | | |
| T3 | | | | | |
| T4 | | | | | |
| T5 | | | | | |

## 六、清理恢复

```bash
# 恢复原始镜像
ORIGINAL_IMAGE=$(cat /tmp/original-image.txt)
kubectl set image deployment/comfyui comfyui=${ORIGINAL_IMAGE}
kubectl rollout status deployment/comfyui --timeout=300s

# 恢复 KEDA 和 NodePool 配置（按需）
kubectl get scaledobject comfyui-cw-scaler -o wide
kubectl get nodepool gpu -o jsonpath='{.spec.limits}' && echo
```
