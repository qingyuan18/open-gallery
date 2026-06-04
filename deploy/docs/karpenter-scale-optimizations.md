# ComfyUI on EKS — 扩容优化总结

把 comfyui Pod 冷启动（0 → 首次 workflow 可用）从 **~10 分钟** 压到 **~2 分钟内**。

测试环境：`g7e.4xlarge` spot (`us-east-1b`)，`comfyui-s3:latest` 镜像 (~17 GiB)，Flux 测试模型集 ~22 GiB（烘进 AMI）。

---

## 总览

| 阶段 | 基线（HyperPod Karpenter） | §1–§9 优化后 | §10–§13 chunked-dd | §14 image-baked（最终） |
|---|---|---|---|---|
| NodeClaim → EC2 Running | ~60 s | ~2 s | ~2 s | ~2 s |
| EC2 Running → kubelet 注册 | ~100 s | ~25 s | ~25 s | ~25 s |
| 镜像拉取（17 GiB） | ECR ~5 min | 0（本地命中） | 0 | 0 |
| 模型同步（22 GiB） | DaemonSet ~2–5 min | DaemonSet ~2–5 min | ~24 s（chunked dd EBS→NVMe） | **0**（模型在镜像内） |
| KEDA 感知 → HPA 扩容 | ~42 s | ~14 s | ~14 s | ~14 s |
| Pod 容器启动 → 2/2 Ready | ~75 s | ~30 s | ~30 s | ~30 s |
| **T0 → Node Ready** | ~7 min | ~2 min 27 s | ~72 s | **~50 s**（实测最佳） |
| **T0 → Pod Ready** | ~10 min | ~3 min | ~109 s | **~104 s** |
| **T0 → 首张 Flux 图** | **~10 min+** | — | ~131 s | **~126 s** |
| Pod 删除 → node 完全终止 | 8–10 min | 8–10 min | 3–4 min | 3–4 min |

§10–§13 的 chunked dd 实测 **22 GiB / 24 s ≈ 938 MB/s**，打满 EBS gp3 1000 MB/s 上限。
§14 把模型烘进 Docker 镜像后，cp 这一步直接消失，节点 Ready 进一步压到 ~50 s。

---

## 1. 从 HyperPod 托管 Karpenter 切到自管 EKS Karpenter

HyperPod 托管 Karpenter 有不好排查的 "filtered out all available instance types" 重试循环，而且 node 生命周期跟 SageMaker 5 分钟 deep-health-check 耦合。自管 EKS Karpenter 直接可控。

**部署步骤**：

1. 跑官方 quickstart CloudFormation，创建 `KarpenterNodeRole-hp-eks`、SQS + EventBridge（中断事件）、IAM 托管策略。
2. 新建 `KarpenterControllerRole-hp-eks`，使用 Pod Identity 信任策略（principal `pods.eks.amazonaws.com`），挂上 CF stack 的 6 个托管策略。
3. 为 `kube-system/karpenter` 关联 Pod Identity。
4. `helm install karpenter ... --skip-crds`（先 `--server-side --force-conflicts` 强制 apply CRD，HyperPod 已有 CRD 会冲突）。
5. aws-auth ConfigMap 必须包含：
   ```yaml
   mapRoles: |
     - rolearn: arn:aws:iam::ACCT:role/KarpenterNodeRole-hp-eks
       username: system:node:{{EC2PrivateDNSName}}
       groups: [system:bootstrappers, system:nodes]
   ```
   EKS Access Entry `type: EC2` 用 `{{SessionName}}`，和 AL2023 AMI 的 `--hostname-override=<private-dns>` 不匹配，会挂掉 Node 授权，所以 node role 保持走 aws-auth。
6. 应用 `karpenter-ec2nodeclass-gpu.yaml` + `karpenter-nodepool-gpu.yaml`。

Karpenter 1 个副本（移除默认 topology-spread 约束，不再要求多 AZ）。

---

## 2. 自定义 AMI 预拉 comfyui 镜像

基于 `amazon-eks-node-al2023-x86_64-nvidia-1.31` 构建，把 `comfyui-s3:latest` 预拉到 containerd 的 `k8s.io` namespace。Pod 用 `imagePullPolicy: IfNotPresent` 本地命中，零 ECR 流量。

**构建流程**（参考 [`deploy/scripts`](../scripts/)）：

1. 从 `ami-06c3bbfab4ca9568d` 起一台 `g6e.2xlarge` builder（EKS 优化 AL2023 NVIDIA AMI，80 GiB root）。
2. SSM 进入，`systemctl start containerd`，然后：
   ```
   ctr -n k8s.io images pull --user AWS:$TOKEN \
     687912291502.dkr.ecr.us-east-1.amazonaws.com/comfyui-s3:latest
   ```
3. `systemctl stop containerd`，`cloud-init clean --logs`，sync，停机。
4. `aws ec2 create-image --no-reboot`，等 available。
5. 销毁 builder。

最终 AMI：`ami-0612079d793ce76d8`，root snapshot 80 GiB。

**Karpenter 侧** — [`karpenter-ec2nodeclass-gpu.yaml`](../k8s-manifests/karpenter-ec2nodeclass-gpu.yaml)：

```yaml
spec:
  amiFamily: AL2023
  amiSelectorTerms:
  - id: ami-0612079d793ce76d8
  blockDeviceMappings:              # 必须匹配 snapshot 大小
  - deviceName: /dev/xvda
    ebs: { volumeSize: 80Gi, volumeType: gp3, deleteOnTermination: true }
```

**Deployment 侧** — [`comfyui-deployment.yaml`](../k8s-manifests/comfyui-deployment.yaml)：

```yaml
containers:
- image: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/comfyui-s3:latest
  imagePullPolicy: IfNotPresent
```

---

## 3. AMI snapshot 开启 Fast Snapshot Restore (FSR)

不开 FSR 时，新 EBS volume 首次读会 lazy-hydrate，`systemd-analyze blame` 看到 initrd 里有 ~30 s 等根 NVMe；containerd + kubelet 启动后的镜像块读也走慢路径。

给 AMI snapshot 在每个可能落地的 AZ 开 FSR：

```bash
aws ec2 enable-fast-snapshot-restores \
  --availability-zones us-east-1b \
  --source-snapshot-ids snap-00e380f5a10613925 \
  --region us-east-1
```

成本：~$0.75/hour/AZ（~$540/月/AZ）。状态流转 `enabling → optimizing → enabled`（30–60 min）。

**实测 `Launched → Registered`**：
- 不开 FSR：~103 s
- 开 FSR：**~25 s**

---

## 4. NodePool 加 taint，防止其他 Deployment 蹭 GPU 节点

`hyperpod-dependencies-*`、`spark-operator-*`、`keda-*` 等都没 `nodeSelector`，会蹭到第一台可用 node。一旦锚定到 Karpenter GPU 节点，`consolidationPolicy: WhenEmpty` 不触发，node 永远不缩。

**NodePool taint** — [`karpenter-nodepool-gpu.yaml`](../k8s-manifests/karpenter-nodepool-gpu.yaml)：

```yaml
template:
  spec:
    taints:
    - key: nvidia.com/gpu
      value: "true"
      effect: NoSchedule
```

**comfyui 工作负载对应 toleration**：

```yaml
tolerations:
- { key: nvidia.com/gpu, operator: Exists, effect: NoSchedule }
```

同时应用到 [`comfyui-deployment.yaml`](../k8s-manifests/comfyui-deployment.yaml) 和 [`comfyui-nvme-prewarm-daemonset.yaml`](../k8s-manifests/comfyui-nvme-prewarm-daemonset.yaml)。标准 GPU daemonset（`nvidia-device-plugin`）本身就 tolerate `nvidia.com/gpu`。

---

## 5. NodePool 开 spot 容量

`us-east-1b` 的 on-demand `g6e.2xlarge` 频繁返回 `InsufficientInstanceCapacity`，Karpenter 会缓存 15 分钟拒绝再要。加 spot 为主要容量类型就能避开缓存循环，还能便宜 ~70%：

```yaml
requirements:
- key: karpenter.sh/capacity-type
  operator: In
  values: ["spot", "on-demand"]
```

---

## 6. NVMe 通过 NodeClass userData 挂载

Karpenter 新 node 自带 instance-store NVMe 但不会自动格式化。`comfyui-nvme-prewarm` DaemonSet 要把 ~67 GiB 模型同步到 `/opt/dlami/nvme`，这里必须是真 NVMe（不是 80 GiB 的 EBS root）。

[`karpenter-ec2nodeclass-gpu.yaml`](../k8s-manifests/karpenter-ec2nodeclass-gpu.yaml) 的 `userData`（MIME multipart）：

```bash
# 选第一个未分区的 NVMe 块设备（跳过 EBS root，root 是已分区的）
for d in /dev/nvme*n1; do
  [ -b "$d" ] || continue
  findmnt -n "$d" >/dev/null 2>&1 && continue
  lsblk -nr "$d" | awk 'NR>1 && $6=="part"{found=1} END{exit !found}' && continue
  DEV="$d"; break
done
mkfs.xfs -f "$DEV"
echo "UUID=$(blkid -s UUID -o value $DEV)  /opt/dlami/nvme  xfs  defaults,nofail  0 0" >> /etc/fstab
mount -a
```

---

## 7. aws-cli S3 调优 + VPC S3 Gateway Endpoint

[`comfyui-nvme-prewarm-daemonset.yaml`](../k8s-manifests/comfyui-nvme-prewarm-daemonset.yaml) 参数：

```bash
aws configure set default.s3.max_concurrent_requests 50
aws configure set default.s3.multipart_chunksize 64MB
aws s3 sync s3://comfyui-models-bucket-.../models/ /opt/dlami/nvme/comfyui-models/
```

创建 VPC S3 Gateway Endpoint，流量走 AWS 骨干而非 NAT：

```bash
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-093a5a42b8a9299c8 \
  --service-name com.amazonaws.us-east-1.s3 \
  --vpc-endpoint-type Gateway \
  --route-table-ids <VPC 内所有 RT>
```

**实测**：峰值吞吐 ~205 → ~310 MiB/s，稳态仍 200–230 MiB/s，瓶颈是 `g6e.2xlarge` 网卡基线带宽。换大实例（`g6e.4xlarge` 10 Gbps 基线）或 FSx Lustre 共享卷可进一步缩短。

---

## 8. 压缩 KEDA 触发段（CloudWatch 链路）

调优前 "队列增长 → HPA 扩容" 中间要 ~42 秒：sidecar 轮询 10s + CloudWatch ingest ~20s + KEDA 轮询 10s + HPA 同步 ≤15s。

调优后：**~14 秒**（−28s）。剩余下限是 CloudWatch ingest + HPA 15 秒同步周期，AWS 侧不可改。

**Sidecar** — [`comfyui-deployment.yaml`](../k8s-manifests/comfyui-deployment.yaml) 的 sidecar env `POLL_INTERVAL_SEC: "2"`（原 10）。sidecar 已经发高分辨率指标（`StorageResolution=1`）。

**KEDA ScaledObject** — [`comfyui-keda-scaledobject.yaml`](../k8s-manifests/comfyui-keda-scaledobject.yaml)：

```yaml
spec:
  pollingInterval: 5            # 原 10
  triggers:
  - type: aws-cloudwatch
    metadata:
      metricStatPeriod: "10"    # 原 30（需要高分辨率指标）
      metricCollectionTime: "30" # 原 60（必须 ≥ 2× period）
      awsRegion: "${AWS_REGION}" # 部署时必须被 envsubst 替换
```

**部署坑**：`awsRegion` 用了 `${AWS_REGION}` 占位符，**必须走 envsubst**，不然 KEDA 报 `failed to resolve service endpoint`：

```bash
AWS_REGION=us-east-1 envsubst \
  < deploy/k8s-manifests/comfyui-keda-scaledobject.yaml \
  | kubectl apply -f -
```

---

## 9. 缩短 Pod readiness 等待

comfyui 容器的 `readinessProbe.initialDelaySeconds: 60` 让容器启动后白等 60 秒才开始探测，但 ComfyUI HTTP 通常 20 秒内就起了。KEDA/Karpenter 都只看队列指标和 pending pod，探测早期失败只是 kubelet warning，无伤大雅。

[`comfyui-deployment.yaml`](../k8s-manifests/comfyui-deployment.yaml)：

```yaml
readinessProbe:
  httpGet: { path: /, port: 8188 }
  initialDelaySeconds: 10    # 原 60
  periodSeconds: 5           # 原 10
  failureThreshold: 3
```

Ready 时刻 = "ComfyUI 首次应答 HTTP"，不再是"容器启动满 60 秒"。

---

## 10. 把 Flux 测试模型预烘到 AMI（替代 prewarm DaemonSet）

> 跟前面"被回滚的尝试"里的"全量 128 GiB 烘进 AMI"不同：这版只烘 **Flux 测试集（~22 GiB）**，启动时拷到 NVMe。彻底干掉 `comfyui-nvme-prewarm` DaemonSet 路径。

### 为什么干掉 daemonset

老路径：节点 Ready → DaemonSet 调度 → 拉 daemonset 镜像 → `aws s3 sync` 22 GiB → `sleep infinity` → comfyui pod 才能挂载到非空 NVMe。整个链路 **2–5 分钟**。

新路径：模型在 AMI EBS root 里（`/opt/comfyui-models-seed`），节点启动 userData 阶段直接本地 `dd` 到 NVMe。 **Node Ready 时模型已就位**，pod 调度即跑。

### AMI v2 — 90 GiB / 1000 MB/s gp3

烘焙脚本 [`build-flux-preloaded-ami.sh`](../scripts/build-flux-preloaded-ami.sh) 现支持参数化：

```bash
ROOT_VOLUME_GIB=90 \
ROOT_VOLUME_IOPS=16000 \
ROOT_VOLUME_THROUGHPUT_MBPS=1000 \
NEW_AMI_NAME="comfyui-s3-flux-preloaded-90G-1000MBps-..." \
./deploy/scripts/build-flux-preloaded-ami.sh
```

烘焙时下载这 4 个文件到 `/opt/comfyui-models-seed/models/...`：

| 文件 | 大小 |
|---|---|
| `diffusion_models/flux1-dev-fp8.safetensors` | 16.1 GiB |
| `text_encoders/t5xxl_fp8_e4m3fn.safetensors` | 4.6 GiB |
| `clip/clip_l.safetensors` | 1.6 GiB |
| `vae/ae.safetensors` | 0.32 GiB |

最终 AMI：`ami-0455c87301b10cddf`，root snapshot **90 GiB**，gp3 **16000 IOPS / 1000 MB/s**。FSR 在 us-east-1b 启用。

EC2NodeClass 同步：

```yaml
spec:
  amiSelectorTerms:
  - id: ami-0455c87301b10cddf
  blockDeviceMappings:
  - deviceName: /dev/xvda
    ebs:
      volumeSize: 90Gi
      volumeType: gp3
      iops: 16000
      throughput: 1000
      deleteOnTermination: true
```

### 启动时 EBS → NVMe 高速拷贝（chunked parallel dd）

userData 在 NVMe 挂载完成后，把 seed 拷到 `/opt/dlami/nvme/comfyui-models`。这一步演化经历了几版：

| 实现 | cp 耗时 | 说明 |
|---|---|---|
| `cp -a SEED/. DST/` 串行 | 125 s | 单线程，~180 MB/s，远低于 EBS 上限 |
| `xargs -P 8 cp -a` | 83 s | 仅 4 个大文件，并发上限被文件数限制 |
| chunked dd（>2 GiB） + 小文件 cp | 61 s | clip_l (1.6 GiB) 没过阈值 → 走 cp 慢路径；且大文件外层串行 |
| **chunked dd 全部文件 + 跨文件并发 (MAX_PAR=16)** | **24 s** | 22 GiB / 24 s ≈ **938 MB/s**，几乎打满 1000 MB/s |

最终方案的关键点：
- **阈值降到 100 MiB**，几乎所有文件都走 dd 分支（用字节单位 `-size -107374182c` 避开 GNU `find -size NG` 的整数舍入坑）
- **truncate 预分配** + 8 个 `dd` 写非重叠 byte range（`oflag=seek_bytes`）
- **跨文件并发**：所有文件的所有 chunk 同时投到队列，semaphore 限 16 路（避免 kernel queue 抖动）

[`karpenter-ec2nodeclass-gpu.yaml`](../k8s-manifests/karpenter-ec2nodeclass-gpu.yaml) 的 userData 节选：

```bash
LARGE_BYTES=$((100 * 1024 * 1024))
CHUNKS=8
MAX_PAR=16
SEED_DIR="/opt/comfyui-models-seed/models"   # 注意 /models 后缀，对齐 deployment hostPath
MODELS_DIR="/opt/dlami/nvme/comfyui-models"

# 小文件直接并发 cp
(cd "$SEED_DIR" && find . -type f -size -"${LARGE_BYTES}"c -print0) \
  | (cd "$MODELS_DIR" && xargs -0 -r -P 8 -I{} cp -a "$SEED_DIR"/{} ./{})

# 大文件：truncate 预分配 → 跨文件 + 跨 chunk 并发 dd（最多 16 路）
sem() { while [ "$(jobs -rp | wc -l)" -ge "$MAX_PAR" ]; do wait -n; done; }
while IFS= read -r -d '' src; do
  size=$(stat -c %s "$src"); chunk=$(( (size + CHUNKS - 1) / CHUNKS ))
  for i in $(seq 0 $((CHUNKS - 1))); do
    offset=$((i * chunk)); length=$chunk
    [ $((offset + length)) -gt "$size" ] && length=$((size - offset))
    sem
    dd if="$src" of="$dst" bs=4M skip="$offset" seek="$offset" count="$length" \
       iflag=skip_bytes,count_bytes oflag=seek_bytes conv=notrunc status=none &
  done
done < "$LARGE_LIST"
wait
```

### Node Ready 时间对比（实测）

| 阶段 | DaemonSet 路径（老） | AMI v2 + chunked dd（新） |
|---|---|---|
| EC2 boot + cloud-init + cp seed | — | **~24 s** |
| nodeadm + kubelet | ~5 s | ~2 s |
| **NodeClaim → Node Ready** | ~150 s | **~72 s** |
| daemonset sync 22 GiB | 2–5 min | 0（已就位） |
| **Pod 可调度并见到模型** | T0 + 5–7 min | **T0 + ~72 s** |

### 路径对齐坑（重要）

- AMI seed 在 host 上是 `/opt/comfyui-models-seed/models/<subtype>/...`
- ComfyUI 容器期望 `/opt/program/models/<subtype>/...`（来自 deployment 的 `mountPath`）
- hostPath 挂的是 `/opt/dlami/nvme/comfyui-models/`

所以 userData 必须从 **`/opt/comfyui-models-seed/models`**（不是顶层 `/opt/comfyui-models-seed`）开始拷，否则容器内会多一层 `models/`，ComfyUI 启动时 scan 模型目录得到空 list，`UNETLoader/DualCLIPLoader/VAELoader` 在 `/prompt` 校验阶段全部 `value_not_in_list` 拒绝任务。

### 删除 prewarm DaemonSet

```bash
kubectl delete -f deploy/k8s-manifests/comfyui-nvme-prewarm-daemonset.yaml
```

---

## 11. 缩容策略调优（避免节点占用 8–10 min）

老配置缩容总时长 **~10 分钟**：KEDA cooldown 180s + HPA stabilization 300s + Karpenter consolidateAfter 120s，并且 `budget: 1` 强制串行。

新配置（中间路线）：

| 参数 | 老 | 新 | 说明 |
|---|---|---|---|
| KEDA `cooldownPeriod` | 180s | **120s** | metric 降到 0 后再等 120s 才允许缩 |
| HPA `scaleDown.stabilizationWindowSeconds` | 300s | **180s** | 减少抖动窗口 |
| Karpenter `consolidateAfter` | 2m | **1m** | 节点空 1 min 就回收 |
| Karpenter `disruption.budgets[0].nodes` | "1" | **"50%"** | 多节点并行下线 |

总缩容时间从 ~10 min → **~3–4 min**。生产上线前可调回保守值。

[`comfyui-keda-scaledobject.yaml`](../k8s-manifests/comfyui-keda-scaledobject.yaml)：

```yaml
spec:
  cooldownPeriod: 120
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          stabilizationWindowSeconds: 180
```

[`karpenter-nodepool-gpu.yaml`](../k8s-manifests/karpenter-nodepool-gpu.yaml)：

```yaml
disruption:
  consolidationPolicy: WhenEmpty
  consolidateAfter: 1m
  budgets:
  - nodes: "50%"
```

---

## 12. KEDA awsRegion 部署坑（线上踩过）

Round 5–6 之间用 `kubectl apply -f comfyui-keda-scaledobject.yaml` 覆盖了线上 ScaledObject，源文件里 `awsRegion: "${AWS_REGION}"` 没经 envsubst，**字面值进了 ScaledObject**，KEDA 直接报：

```
operation error CloudWatch: GetMetricData,
failed to resolve service endpoint,
Failed to parse uri: https://monitoring.${AWS_REGION}.amazonaws.com
```

HPA 显示 `<unknown>/1`，ScaledObject Active=False。**Trigger 不生效，没扩容**，但很容易看错。两个修复：

1. 源文件直接写死 `awsRegion: "us-east-1"`（已改，单一 region 部署足够）。
2. 或继续用 envsubst：`AWS_REGION=us-east-1 envsubst < ... | kubectl apply -f -`

热修复命令：

```bash
kubectl patch scaledobject comfyui-cw-scaler -n default --type=json \
  -p='[{"op":"replace","path":"/spec/triggers/0/metadata/awsRegion","value":"us-east-1"}]'
```

---

## 13. spot 容量与 ICE（容量耗尽行为）

压测期间 us-east-1b 的 g7e.4xlarge spot 池**会临时枯竭**：

```
MaxSpotInstanceCountExceeded
InsufficientInstanceCapacity: We currently do not have sufficient g7e.4xlarge
  capacity in the Availability Zone you requested (us-east-1b)
```

观察到的行为：
- Karpenter 持续撞 spot，看到一堆 ICE NodeClaim 在刷
- **3 分钟内 Karpenter 不会切到 on-demand**，TTL 控制的是"什么时候允许重新尝试这个组合"，过 TTL 还是先选 spot（更便宜）
- 实测 5–10 分钟后 spot 池自然恢复

### 调 unavailableOfferingsCacheTTL（不是真凶）

控制器启动参数（不是 NodePool/EC2NodeClass 字段）：

```yaml
- name: KARPENTER_UNAVAILABLE_OFFERINGS_TTL
  value: "30s"   # 默认 3m
```

**调短只是"更频繁地重新尝试 spot"，不会让 Karpenter 提前切 OD**。OD 总是跟 spot 一起作为候选，按价格排序选；spot 真没货时 Karpenter 才会选 OD —— 但前提是 NodePool 显式允许 OD，且 OD vCPU quota 够。

### 真正的容量保险

1. **多 instance type**：`g7e.4xlarge` + `g6e.4xlarge`（都是单 L40S，性能一致），spot 池跨型号同时枯竭概率比单一低很多。⚠️ `g6.4xlarge` 是 L4（24 GB），`g5.4xlarge` 是 A10G（24 GB），不是 L40S，根据模型显存需求酌情纳入。
2. **多 AZ**：FSR 每个 AZ 单独计费（~$540/月/AZ），按需扩展。
3. **预留 OD 容量配额**：检查 EC2 G 系列 OD vCPU quota，确认即时切到 OD 时账户不会 throttle。

---

## 14. 把 Flux 模型烘进 Docker 镜像（替代 §10 EBS-seed → NVMe cp）

§10–§13 把模型放在 AMI EBS root 上，开机 userData 阶段 chunked dd 拷到 NVMe（24 s）。这条路径已经很快，但仍引入了一段 cp 和一份 NVMe 副本。本节进一步把模型直接打进 Docker 镜像。

### 设计

```
ECR  ─►  Docker image (~50 GiB)              ─► 镜像里的
         ├─ /opt/program/                       /opt/program/models/
         └─ /opt/program/models/                ↑ ComfyUI 默认就读这里
            ├─ diffusion_models/flux1-dev-fp8.safetensors  (16 GiB)
            ├─ text_encoders/t5xxl_fp8_e4m3fn.safetensors  (4.6 GiB)
            ├─ clip/clip_l.safetensors                     (1.6 GiB)
            └─ vae/ae.safetensors                          (0.3 GiB)

AMI  ─►  containerd k8s.io 命名空间预拉这个镜像
         开机 → kubelet 找镜像 → IfNotPresent 命中 → 0 s pull
```

deployment 不再挂 `hostPath: /opt/dlami/nvme/comfyui-models`，让容器**直接用镜像内的目录**。

### 实现

**[`deploy/comfyui-s3-flux.dockerfile`](../comfyui-s3-flux.dockerfile)** 在原 `comfyui-s3.dockerfile` 基础上加：

```dockerfile
RUN aws s3 cp s3://comfyui-models-bucket-${ACCT}/models/diffusion_models/flux1-dev-fp8.safetensors    /opt/program/models/diffusion_models/flux1-dev-fp8.safetensors    --region us-east-1 \
 && aws s3 cp s3://comfyui-models-bucket-${ACCT}/models/text_encoders/t5xxl_fp8_e4m3fn.safetensors    /opt/program/models/text_encoders/t5xxl_fp8_e4m3fn.safetensors    --region us-east-1 \
 && aws s3 cp s3://comfyui-models-bucket-${ACCT}/models/clip/clip_l.safetensors                       /opt/program/models/clip/clip_l.safetensors                       --region us-east-1 \
 && aws s3 cp s3://comfyui-models-bucket-${ACCT}/models/vae/ae.safetensors                            /opt/program/models/vae/ae.safetensors                            --region us-east-1
```

⚠️ 还要 pin ComfyUI 到 v0.3.64：

```dockerfile
ARG COMFYUI_COMMIT=v0.3.64
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /tmp/comfyui && \
    cd /tmp/comfyui && git checkout ${COMFYUI_COMMIT} && cd / && \
    cp -r /tmp/comfyui/. /opt/program/
```

**为什么 pin v0.3.64**：v0.3.64+ 引入了 `comfy/ldm/lightricks/vae/audio_vae.py`，启动时 unconditional `import torchaudio`，而 ComfyUI HEAD 拉的 torchaudio wheel 链接 `libcudart.so.13`，base image (`pytorch:24.12-py3`) 只有 `libcudart.so.12` → CrashLoopBackOff。v0.3.64 没这个文件。

### 云端 build（mac 不现实）

镜像 ~50 GiB，本地 build + push 受家庭带宽和 qemu emulation 双重拖累。脚本 [`cloud-build-comfyui-flux.sh`](../scripts/cloud-build-comfyui-flux.sh) 起一台同 region 的 c6i.4xlarge：

1. base64 嵌 Dockerfile 到 userData
2. 实例上 `dnf install docker` + 设 `daemon.json mtu: 1500`（避免 EC2 ENA 默认 9001 + Docker bridge 触发 PMTU 问题）
3. ECR login → `docker build` → `docker push`

⚠️ **build 时容易踩的两个坑（已修复在脚本里）**：
- **SG 没开 80 出向**：`apt-get` 默认走 HTTP/80，[`hyperpod 的 sg-0176fe82167b34c56`](#) 默认只允许 443 → 全部 timeout。`aws ec2 authorize-security-group-egress` 加 80 出向。
- **Docker bridge MTU**：默认 9001 跟很多 PMTU-locked 站点不通。`/etc/docker/daemon.json` 里 `{"mtu": 1500}`。

### AMI 烘焙（不再下载模型，只 pre-pull 镜像）

[`build-flux-image-baked-ami.sh`](../scripts/build-flux-image-baked-ami.sh) 跟 `build-flux-preloaded-ami.sh` 的核心区别：

```bash
# Authenticate to ECR
TOKEN=$(aws ecr get-login-password --region $AWS_REGION)

# Pre-pull image into k8s.io namespace
ctr -n k8s.io images pull --user "AWS:$TOKEN" "$IMAGE_URI"
```

userData 不再有 S3 download。AMI snapshot 130 GiB（系统 ~28G + 镜像 cache ~50G）。

最终 AMI：`ami-05efa58052f4e25fc`，FSR enabled (us-east-1b)。

### Deployment 改动

[`comfyui-deployment-flux-baked.yaml`](../k8s-manifests/comfyui-deployment-flux-baked.yaml)：
- `image: comfyui-s3-flux:latest`
- **删除** `volumeMounts: /opt/program/models` 和 `volumes: nvme-host`（hostPath 会覆盖镜像里的模型）
- userData 仍 mkfs+mount NVMe（保留 scratch space）

### 路径对齐坑（重点）

ComfyUI 期望 `/opt/program/models/<subtype>/<file>`：
- ✅ 镜像里 `/opt/program/models/diffusion_models/flux1-dev-fp8.safetensors`
- ❌ 之前 §10 的 `/opt/dlami/nvme/comfyui-models/models/diffusion_models/...` 多了一层 `models/`

如果 deployment 仍挂着 hostPath 到 `/opt/program/models`，会**覆盖**镜像里的目录 → ComfyUI scan 出空 list → `/prompt` 校验时所有 LoadModel 节点报 `value_not_in_list`。

---

## 实测时间线（最新一次完整测量）

T0 = HTTP `POST /prompt`（KEDA 看到 metric > target → HPA → Karpenter）

| 事件 | 时间 |
|---|---|
| T0 | 提交 8 个重 Flux prompt（1536² × 50 step） |
| T0 + 25 s | NodeClaim 创建（Karpenter 决策）|
| T0 + 25 s | EC2 instance ID 出现 |
| **T0 + 50 s** | **Node Ready**（实测最佳记录） |
| T0 + ~52 s | Pod scheduled to node（image already present） |
| **T0 + 104 s** | **新 pod Ready**（comfyui container 起 HTTP server） |
| T0 + 108 s | 直发 prompt 进 queue.running |
| **T0 + 126 s** | **首张 Flux 图 sampler 完成**（20 step, 1024²） |

中间分解：

| 子阶段 | 耗时 |
|---|---|
| EC2 boot + cloud-init + nodeadm + kubelet ready | ~50 s |
| 镜像 pull（已在 AMI 缓存） | **0 s** |
| Pod scheduled → comfyui container Started | ~10 s |
| ComfyUI Python startup + import torch + scan models | ~40 s |
| HTTP submit → execution_start | ~4 s |
| KSampler 20 step + VAE decode（首次模型加载到 GPU） | ~18 s |

### 跟前几代方案对比

| 方案 | T0 → Node Ready | T0 → Pod Ready | T0 → 首张图 |
|---|---|---|---|
| HyperPod baseline + DaemonSet 拉模型 | ~7 min | ~10 min | **~10 min+** |
| §1–§9 + DaemonSet | ~2 min 27 s | ~3 min | （未测） |
| §10–§13 chunked dd EBS→NVMe | ~72 s | ~109 s | ~131 s |
| **§14 image-baked（最终）** | **~50 s** | **~104 s** | **~126 s** |

相比最初 HyperPod baseline，**端到端冷启动从 10+ 分钟 压到 ~2 分钟**，提速 ~80%。

### 已知限制

- **镜像膨胀**：~50 GiB 比 17 GiB 老镜像大近 3 倍。ECR 储存费、push/pull 时间都上升。生产部署如有多个模型集，建议每个 workload 一个 image+AMI 对，不要把所有模型塞一个镜像。
- **AMI snapshot 大小**：130 GiB（含镜像 cache），比 §10 的 90 GiB 大 ~40 GiB。EBS snapshot 按实际块计费，影响有限。
- **ComfyUI 锁版本 v0.3.64**：升级 ComfyUI 时要重新验证 torchaudio/CUDA 兼容性。可考虑改方案：换 base image 到 PyTorch 25.x（自带 cu13），ComfyUI 不用 pin。
- **numpy 2.x 兼容性**：当前镜像 SaveImage 阶段会因 numpy 1.x ↔ 2.x ABI 报错（`Numpy is not available`）。修复办法：`pip install "numpy<2"` 加进 Dockerfile（待下一次 build）。


## 已知限制

- **Scale-in**：EC2 `shutting-down → terminated` 要 5–10 分钟，Karpenter 管不了。从工作负载视角 pod 约 50 秒内消失（匹配 Deployment 的 terminationGracePeriod），node 多留一会儿不影响调度或计费。
- **Sync 吞吐**：受实例网卡上限约束，aws-cli 参数和 S3 都不是瓶颈。
