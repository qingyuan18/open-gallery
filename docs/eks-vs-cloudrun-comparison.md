# EKS ComfyUI 推理部署方案 vs GCP Cloud Run 方案对比

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EKS ComfyUI 推理部署架构                                  │
│                                                                             │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────────────────────────┐    │
│  │  Client   │───▶│  ALB Ingress │───▶│  ComfyUI Service (ClusterIP)    │    │
│  └──────────┘    └─────────────┘    └──────────┬───────────────────────┘    │
│                                                 │                           │
│  ┌──────────────────────────────────────────────▼────────────────────────┐  │
│  │                    ComfyUI Pod (GPU Node)                             │  │
│  │  ┌─────────────────┐  ┌───────────────────────┐                      │  │
│  │  │  ComfyUI Server  │  │  CW Metrics Sidecar   │──▶ CloudWatch       │  │
│  │  │  (GPU Inference)  │  │  (Queue → Metrics)    │    (QueuePending)   │  │
│  │  └────────┬─────────┘  └───────────────────────┘          │          │  │
│  │           │ models mount (hostPath, NVMe direct I/O)      │          │  │
│  │  ┌────────▼─────────────────────────────────┐             │          │  │
│  │  │  /opt/dlami/nvme/comfyui-models (NVMe)   │             │          │  │
│  │  └──────────────────────────────────────────┘             │          │  │
│  └───────────────────────────────────────────────────────────┼──────────┘  │
│                                                               │            │
│  ┌────────────────────┐   ┌─────────────┐   ┌────────────────▼─────────┐  │
│  │  DaemonSet Prewarm  │   │  Karpenter   │   │   KEDA ScaledObject     │  │
│  │  (S3→NVMe Sync)     │   │  (Node Pool) │   │   (Pod Autoscaler)      │  │
│  │  每GPU节点自动预热    │   │  g5/g6e GPU  │   │   CloudWatch trigger    │  │
│  └─────────┬──────────┘   └──────┬──────┘   └─────────────────────────┘  │
│            │                      │                                        │
│  ┌─────────▼──────────┐   ┌──────▼──────────────────┐                     │
│  │  S3 Models Bucket   │   │  EC2 GPU Instances      │                     │
│  │  (Source of Truth)  │   │  NVMe SSD + SOCI Image  │                     │
│  └────────────────────┘   └─────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 一、弹性扩缩能力对比

| 维度 | EKS (KEDA + Karpenter) | GCP Cloud Run |
|------|----------------------|---------------|
| **Pod 级扩缩** | KEDA 基于 CloudWatch QueuePending 指标，pollingInterval=30s，scaleUp 稳定窗口 60s，精准匹配队列深度 | 基于并发请求数/CPU 利用率，无法感知推理队列语义 |
| **Node 级扩缩** | Karpenter 秒级感知 Pending Pod，自动选择 g5/g6e 最优实例族，支持 On-Demand/Spot 混合 | 由平台托管，仅支持 L4 和 RTX PRO 6000 两种 GPU，每实例限 1 GPU |
| **缩容策略** | cooldownPeriod=180s + scaleDown 稳定窗口 300s + Karpenter WhenEmpty 策略，避免 GPU 节点抖动 | 固定冷却期，无法针对 GPU 工作负载精细调优 |
| **最大弹性** | maxReplicaCount=10（可按需调整至数百），Karpenter 节点数理论上无上限 | 受区域 GPU 配额限制，最大实例数通常较低 |
| **多级扩缩联动** | KEDA（Pod）→ Karpenter（Node）两级联动，解耦应用扩缩与基础设施扩缩 | 单一托管扩缩，黑盒不可调 |

**核心优势**: EKS 方案的 KEDA + Karpenter 两级联动提供了**队列感知的语义级扩缩**能力。KEDA 通过 Sidecar 实时采集 ComfyUI 队列深度并发布到 CloudWatch，实现"有任务就扩、空闲就缩"的精准弹性；Karpenter 在秒级响应 Pending Pod 并智能选择最优 GPU 实例，整体从请求到 GPU 就绪的端到端扩容可控制在 **2-3 分钟**内。

### 实施步骤

**Step 1: 安装 KEDA Operator 并配置 IRSA 权限**

```bash
# 安装 KEDA
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda --namespace keda --create-namespace

# 为 KEDA Operator ServiceAccount 绑定 CloudWatch 读取权限
kubectl apply -f deploy/k8s-manifests/keda-operator-serviceaccount-irsa.yaml
```

KEDA Operator SA 需要的 IAM Role 需包含 `cloudwatch:GetMetricData` 权限：

```yaml
# keda-operator-serviceaccount-irsa.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: keda-operator
  namespace: keda
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/ComfyUICloudWatchRole
```

**Step 2: 部署 TriggerAuthentication 和 ScaledObject**

```bash
kubectl apply -f deploy/k8s-manifests/comfyui-keda-triggerauth.yaml
kubectl apply -f deploy/k8s-manifests/comfyui-keda-scaledobject.yaml
```

ScaledObject 核心配置——基于 CloudWatch `QueuePending` 指标做队列感知扩缩：

```yaml
# comfyui-keda-scaledobject.yaml (关键字段)
spec:
  scaleTargetRef:
    name: comfyui
  minReplicaCount: 1
  maxReplicaCount: 10
  cooldownPeriod: 180
  pollingInterval: 30
  triggers:
  - type: aws-cloudwatch
    metadata:
      namespace: "ComfyUI"
      metricName: "QueuePending"
      targetMetricValue: "1"       # 每 Pod 1 个待处理任务
      metricStatPeriod: "30"
    authenticationRef:
      name: comfyui-cw-auth
```

**Step 3: 部署 Karpenter GPU NodePool**

标准 EKS 集群：

```bash
export CLUSTER_NAME=<your-cluster> AMI_ID=<dlami-id> SUBNET_ID_1=<subnet> SUBNET_ID_2=<subnet> SG_ID_1=<sg> SG_ID_2=<sg>
envsubst < deploy/k8s-manifests/karpenter-ec2nodeclass-gpu.yaml | kubectl apply -f -
kubectl apply -f deploy/k8s-manifests/karpenter-nodepool-gpu.yaml
```

NodePool 指定 g5/g6e 实例族，节点自动标记 `workload=gpu` 与 ComfyUI Deployment 的 nodeSelector 匹配：

```yaml
# karpenter-nodepool-gpu.yaml (关键字段)
spec:
  template:
    metadata:
      labels:
        workload: "gpu"
    spec:
      requirements:
      - key: karpenter.k8s.aws/instance-family
        operator: In
        values: ["g5", "g6e"]
  disruption:
    consolidationPolicy: WhenEmpty
    consolidateAfter: 2m
```

**Step 4: 验证两级联动**

```bash
# 查看 KEDA ScaledObject 状态
kubectl get scaledobject comfyui-cw-scaler -o wide

# 查看 HPA（KEDA 自动创建）
kubectl get hpa

# 观察扩容全链路：提交任务 → KEDA 扩 Pod → Karpenter 扩 Node
kubectl get pods -l app=comfyui -w
kubectl get nodes -l workload=gpu -w
kubectl logs -l app=comfyui-nvme-prewarm -f  # 观察新节点模型预热
```

**HyperPod EKS 适配**: 将 Step 3 替换为 HyperPod 专属资源即可，KEDA 部分无需改动：

```bash
# HyperPod 集群使用 HyperpodNodeClass 替代 EC2NodeClass
export HP_INSTANCE_GROUP_1=<your-instance-group>
envsubst < deploy/k8s-manifests/karpenter-hyperpod-nodeclass-gpu.yaml | kubectl apply -f -
kubectl apply -f deploy/k8s-manifests/karpenter-hyperpod-nodepool-gpu.yaml
```

```yaml
# karpenter-hyperpod-nodeclass-gpu.yaml
apiVersion: karpenter.sagemaker.amazonaws.com/v1
kind: HyperpodNodeClass
metadata:
  name: gpu-hp
spec:
  instanceGroups:
  - ${HP_INSTANCE_GROUP_1}    # InstanceGroup desired count 设为 0，由 Karpenter 按需拉起
```

> HyperPod 集群需启用 `NodeProvisioningMode=Continuous` 和 `NodeRecovery=Automatic`。Karpenter 通过 `HyperpodNodeClass` 管理节点生命周期，GPU 硬件故障时自动替换节点。

## 二、模型加载与存储性能对比

### 2.1 Lustre/S3 → NVMe 预热加速

| 维度 | EKS (DaemonSet + NVMe) | GCP Cloud Run |
|------|----------------------|---------------|
| **模型存储层** | S3 作为 Source of Truth，DaemonSet 预热同步至节点本地 NVMe SSD | GCS FUSE mount 或 NFS 挂载，无本地 SSD；in-memory volume 占用容器内存配额 |
| **同步机制** | DaemonSet `comfyui-nvme-prewarm` 在 GPU 节点就绪后立即 `aws s3 sync` 全量模型至 NVMe | 无预热机制，依赖运行时按需拉取 |
| **存储介质** | EC2 实例本地 NVMe SSD（g5: 最高 3.8GB/s 顺序读取） | 网络文件系统（GCS FUSE，受网络带宽限制） |
| **可扩展至 Lustre** | 可替换 S3 为 FSx for Lustre（聚合带宽 TB/s 级），通过 Lustre PV/PVC 挂载后同步至 NVMe，大幅加速多节点并行同步 | 无对应高性能并行文件系统 |

> **Lustre 加速路径**: S3 Bucket → FSx for Lustre（自动关联 S3，提供 200MB/s/TiB 基线吞吐） → DaemonSet 同步至 NVMe。对于 50GB+ 模型集合，Lustre 聚合带宽相比直接 S3 下载可提速 **3-5x**。

### 2.2 HostPath 挂载 vs Cloud Run Mount 性能

| 维度 | EKS hostPath (NVMe) | Cloud Run Volume Mount |
|------|---------------------|----------------------|
| **挂载方式** | `hostPath` 直接映射宿主机 NVMe 路径，零抽象层开销 | GCS FUSE mount / NFS / in-memory volume（tmpfs，占用内存配额），无本地磁盘选项 |
| **I/O 延迟** | **微秒级** — 本地 NVMe 块设备直连，无网络往返 | **毫秒级** — 每次 read 需网络往返或 FUSE 缓存查找 |
| **随机读性能** | NVMe 4K 随机读 ~500K IOPS，模型权重加载近乎瞬时 | FUSE 随机读受限于网络 RTT，大模型加载耗时显著 |
| **推理热路径** | 模型权重常驻内存后，checkpoint swap/LoRA 热切换直接从 NVMe 读取，延迟 < 1s | LoRA/checkpoint 切换需从 GCS FUSE 远程拉取，延迟数秒至数十秒；in-memory volume 可缓存但受内存配额限制 |

**关键差异**: ComfyUI 推理涉及频繁的模型权重加载（diffusion model、VAE、CLIP、LoRA），EKS 方案中模型已预热至 NVMe 后通过 hostPath 挂载，**读取延迟比 Cloud Run 的 FUSE mount 低 2-3 个数量级**，直接影响首次推理延迟和模型切换速度。

### 实施步骤

**Step 1: 上传模型至 S3（Source of Truth）**

```bash
# 将 checkpoints/LoRA/VAE/CLIP 等模型文件同步至 S3
aws s3 sync ./models s3://comfyui-models-bucket-${AWS_ACCOUNT_ID}/models/ --region us-west-2
```

**Step 2: 部署 NVMe 预热 DaemonSet**

```bash
kubectl apply -f deploy/k8s-manifests/comfyui-nvme-prewarm-daemonset.yaml
```

DaemonSet 通过 `nodeSelector: workload: gpu` 确保仅在 GPU 节点上运行，节点就绪后自动执行 `aws s3 sync` 将模型预热至本地 NVMe：

```yaml
# comfyui-nvme-prewarm-daemonset.yaml (关键字段)
spec:
  template:
    spec:
      serviceAccountName: comfyui-prewarm-sa   # IRSA 绑定 S3 只读权限
      nodeSelector:
        workload: gpu
      containers:
      - name: prewarm
        args:
        - |
          aws s3 sync "s3://comfyui-models-bucket-${AWS_ACCOUNT_ID}/models/" \
                      "/opt/dlami/nvme/comfyui-models/"
          sleep infinity
        volumeMounts:
        - name: nvme-host
          mountPath: /opt/dlami/nvme/comfyui-models
      volumes:
      - name: nvme-host
        hostPath:
          path: /opt/dlami/nvme/comfyui-models
          type: DirectoryOrCreate
```

**Step 3: ComfyUI Deployment 中配置 hostPath 挂载**

ComfyUI Pod 以只读方式挂载已预热的 NVMe 模型目录，零网络开销：

```yaml
# comfyui-deployment.yaml (关键字段)
spec:
  template:
    spec:
      containers:
      - name: comfyui
        volumeMounts:
        - name: nvme-host
          mountPath: /opt/program/models
          readOnly: true            # 只读挂载，模型写入由 DaemonSet 管理
        readinessProbe:
          httpGet:
            path: /
            port: 8188
          initialDelaySeconds: 60   # 等待模型加载至 GPU 显存
          periodSeconds: 10
      volumes:
      - name: nvme-host
        hostPath:
          path: /opt/dlami/nvme/comfyui-models
          type: DirectoryOrCreate
```

**Step 4: 验证模型预热和挂载**

```bash
# 确认 DaemonSet 在所有 GPU 节点运行
kubectl get ds comfyui-nvme-prewarm -o wide

# 查看预热日志
kubectl logs -l app=comfyui-nvme-prewarm --tail=20

# 进入 ComfyUI Pod 验证模型文件已就位
kubectl exec -it deploy/comfyui -c comfyui -- ls -lh /opt/program/models/
```

**HyperPod EKS 适配**: HyperPod 管理的 GPU 节点（g5/g6e）默认配备本地 NVMe SSD，DaemonSet 和 hostPath 挂载路径与标准 EKS 完全一致，无需任何改动。若 HyperPod 集群已配置 FSx for Lustre，可选择将 DaemonSet 的同步源从 S3 切换为 Lustre 挂载点，利用 Lustre 聚合带宽（TB/s 级）加速多节点并行同步。

## 三、推理提速全链路优化手段

EKS 方案在模型推理的全生命周期中提供了多层次提速手段，这些在 Cloud Run 托管环境中难以实现：

| 优化手段 | EKS 实现方式 | Cloud Run 可行性 |
|----------|------------|-----------------|
| **SOCI 镜像 Lazy Loading** | ECR + SOCI Index，容器启动时仅拉取必需层，镜像就绪时间从分钟级降至 **10-20 秒** | 不支持，依赖 Artifact Registry 全量拉取 |
| **DaemonSet 模型预热** | GPU 节点就绪即触发 S3→NVMe 全量同步，Pod 调度时模型已就位 | 无 DaemonSet 概念，无法实现节点级预热 |
| **GPU 驱动预加载** | NVIDIA DLAMI 预装 CUDA/cuDNN/驱动，Karpenter 指定 AMI，省去运行时安装 | 平台管理，驱动版本不可控 |
| **CUDA Graph / TorchCompile 缓存** | 首次推理编译后缓存至 NVMe，后续 Pod 可通过 hostPath 复用编译产物 | 每次冷启动重新编译，无持久化缓存 |
| **模型权重内存预加载** | 通过 readinessProbe（initialDelaySeconds=60s）确保模型加载完毕才接流量 | 支持但粒度粗，无法配合预热逻辑 |
| **Session Affinity** | ClientIP 亲和（3h TTL），同用户请求路由到同一 Pod，命中已加载模型/LoRA | 支持但受平台缩容策略影响，亲和性不稳定 |
| **NVMe tmpfs 加速** | 推理中间产物（生成图片、临时张量）写入 NVMe ephemeral storage（60Gi），避免网络 I/O | 仅 in-memory volume（tmpfs），占用容器内存配额，无本地 SSD/NVMe 选项 |

### 实施步骤

**Step 1: 构建 SOCI 索引加速镜像拉取**

```bash
# 推送 ComfyUI 镜像至 ECR
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/comfyui-s3:latest

# 为镜像创建 SOCI Index（Lazy Loading 索引）
soci create ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/comfyui-s3:latest
soci push --ref ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/comfyui-s3:latest
```

Karpenter EC2NodeClass 中指定预装 SOCI snapshotter 的 DLAMI AMI，节点启动后自动启用 Lazy Loading：

```yaml
# karpenter-ec2nodeclass-gpu.yaml (关键字段)
spec:
  amiFamily: AL2023
  amiSelectorTerms:
  - id: ${AMI_ID}    # 选择预装 SOCI snapshotter + NVIDIA 驱动的 DLAMI
```

**节点侧 SOCI 配置（HyperPod 生命周期脚本）**: 在 HyperPod EKS 集群中，SOCI 的启用通过 `on_create` 生命周期脚本完成（参考 `deploy/scripts/on_create_eks_v3.sh`）。脚本在节点初始化时自动执行以下配置：

1) **containerd 配置**: 将 snapshotter 切换为 `soci`，启用 `discard_unpacked_layers` 和 snapshot annotations，并注册 SOCI proxy plugin：

```toml
# /opt/sagemaker/containerd/config.toml (由 on_create 脚本生成)
[plugins."io.containerd.grpc.v1.cri".containerd]
default_runtime_name = "nvidia"
snapshotter = "soci"                      # 使用 SOCI 作为默认 snapshotter
discard_unpacked_layers = true            # 丢弃已解包层，节省磁盘空间
disable_snapshot_annotations = false      # 保留 annotation 以支持 lazy loading

[proxy_plugins.soci]
type = "snapshot"
address = "/run/soci-snapshotter-grpc/soci-snapshotter-grpc.sock"

[proxy_plugins.soci.exports]
root = "/opt/dlami/nvme/soci-snapshotter-grpc"   # SOCI 数据存储在 NVMe 上
```

2) **SOCI snapshotter 配置**: 启用并行拉取/解包，配合 `unpigz` 加速 gzip 解压：

```toml
# /etc/soci-snapshotter-grpc/config.toml (由 on_create 脚本生成)
[content_store]
  type = "containerd"

[pull_modes.parallel_pull_unpack]
  enable = true
  max_concurrent_downloads = 50
  max_concurrent_downloads_per_image = 10
  concurrent_download_chunk_size = "8mb"
  max_concurrent_unpacks = 20
  discard_unpacked_layers = true
  [pull_modes.parallel_pull_unpack.decompress_streams."gzip"]
    path = "/usr/bin/unpigz"              # 多线程 gzip 解压
    args = ["-d", "-c"]

[cri_keychain]
  enable_keychain = true                  # 代理 ImageService，缓存 ECR 认证
  image_service_path = "/run/containerd/containerd.sock"
```

3) **systemd override**: 通过 override 让 containerd 加载自定义配置：

```bash
# /etc/systemd/system/containerd.service.d/override.conf
[Service]
Environment="CONTAINERD_CONFIG=/opt/sagemaker/containerd/config.toml"
ExecStart=
ExecStart=/usr/bin/containerd --config $CONTAINERD_CONFIG
```

4) **NVMe 目录初始化**: SOCI snapshotter 数据根目录指向 NVMe，确保层数据的读写性能：

```bash
mkdir -p /opt/dlami/nvme/soci-snapshotter-grpc
```

> 以上配置由 HyperPod 生命周期脚本 `on_create_eks_v3.sh` 在节点创建时自动执行，Karpenter 拉起的新 GPU 节点无需手动干预即可具备 SOCI Lazy Loading 能力。对于标准 EKS 集群，需通过 Karpenter EC2NodeClass 的 `userData` 字段或选择预装 SOCI 的 DLAMI AMI 实现等效配置。

**Step 2: 部署 CloudWatch Metrics Sidecar**

Sidecar 以独立容器运行在 ComfyUI Pod 中，每 10 秒采集队列深度并推送至 CloudWatch：

```yaml
# comfyui-deployment.yaml 中的 Sidecar 容器
- name: comfyui-cw-metrics
  image: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/comfyui-queue-metrics:latest
  env:
  - name: COMFYUI_QUEUE_URL
    value: "http://127.0.0.1:8188/queue"
  - name: METRIC_NAMESPACE
    value: "ComfyUI"
  - name: METRIC_NAME
    value: "QueuePending"
  - name: POLL_INTERVAL_SEC
    value: "10"
  resources:
    requests:
      cpu: 50m
      memory: 64Mi
```

**Step 3: 部署 ComfyUI Service（Session Affinity + Readiness）**

```bash
kubectl apply -f deploy/k8s-manifests/comfyui-deployment.yaml
kubectl apply -f deploy/k8s-manifests/comfyui-service.yaml
```

Service 配置 ClientIP 亲和，同用户请求路由到同一 Pod，复用已加载的模型和 LoRA：

```yaml
# comfyui-service.yaml (关键字段)
spec:
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 10800    # 3 小时亲和窗口
```

Deployment 配置 GPU 资源和 Ephemeral Storage，推理中间产物写入 NVMe 支持的本地存储：

```yaml
# comfyui-deployment.yaml (关键字段)
spec:
  template:
    spec:
      containers:
      - name: comfyui
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "32Gi"
            ephemeral-storage: "30Gi"
          limits:
            nvidia.com/gpu: 1
            memory: "56Gi"
            ephemeral-storage: "60Gi"
        env:
        - name: NVIDIA_VISIBLE_DEVICES
          value: "all"
```

**Step 4: 验证全链路优化效果**

```bash
# 确认 SOCI Lazy Loading 生效（镜像拉取应在 10-20s 内完成）
kubectl describe pod -l app=comfyui | grep -A5 "Events"

# 查看 CloudWatch 指标是否正常推送
aws cloudwatch get-metric-statistics \
  --namespace ComfyUI --metric-name QueuePending \
  --start-time $(date -u -v-5M +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 30 --statistics Average

# 验证 Session Affinity（同一 client 多次请求应路由到同一 Pod）
kubectl get endpoints comfyui-service -o wide
```

**HyperPod EKS 适配**: 所有优化手段在 HyperPod EKS 上均可落地。SOCI Lazy Loading 已通过 HyperPod `on_create` 生命周期脚本（`deploy/scripts/on_create_eks_v3.sh`）自动完成 containerd snapshotter 切换和 SOCI 配置，Karpenter 拉起的新节点开箱即用，无需额外操作。HyperPod 节点自带 NVIDIA 驱动预装。Sidecar Metrics、Session Affinity、Ephemeral Storage 均为标准 Kubernetes 特性，无兼容性问题。HyperPod 额外提供 `NodeRecovery=Automatic`，GPU 硬件故障时自动替换节点并重新执行生命周期脚本，SOCI 配置随之自动恢复。

## 四、综合对比总结

| 评估维度 | EKS 方案 | Cloud Run 方案 |
|---------|---------|---------------|
| **冷启动端到端** | SOCI(~15s) + NVMe预热模型(已就位) + 模型加载(~45s) ≈ **~60-90s** | 镜像拉取(~120s) + FUSE模型加载(~60-180s) ≈ **3-5min** |
| **模型切换延迟** | NVMe hostPath 直读 < **1s** | GCS FUSE 远程拉取 **10-30s** |
| **扩缩精度** | 队列语义感知，Pod/Node 两级联动 | 并发/CPU 指标，单级黑盒 |
| **GPU 实例选择** | Karpenter 支持 g5/g6e/p4d 等任意族 | 仅支持 NVIDIA L4 (24GB) 和 RTX PRO 6000 (96GB)，每实例限 1 GPU |
| **成本优化** | Spot 实例 + WhenEmpty 缩容 + 精准扩缩避免过度配置 | GPU 按秒计费（L4: $0.000187/s ≈ $0.67/h），无 GPU 空闲计费，但无 Spot/CUD 折扣 |
| **生态集成** | CloudWatch 监控 + IRSA/Pod Identity + ALB + WAF 全栈 | GCP 生态闭环，跨云能力弱 |
| **运维复杂度** | 中等（需管理 KEDA/Karpenter/DaemonSet） | 低（全托管） |

**结论**: EKS 方案通过 KEDA 队列感知扩缩 + Karpenter 智能节点供给 + SOCI 镜像懒加载 + DaemonSet NVMe 预热 + hostPath 零开销挂载的全链路优化组合，在 GPU 推理场景下实现了**冷启动时间降低 3-4x、模型切换延迟降低 10-30x、扩缩精度和成本效率显著优于 Cloud Run** 的综合优势。对于高吞吐、低延迟、多模型切换频繁的 ComfyUI 推理工作负载，EKS 方案是更优的生产级选择。

### HyperPod EKS 部署可行性总结

在 AWS HyperPod EKS 集群上部署本方案整体**可行且推荐**，与标准 EKS 的差异仅在 Karpenter 节点管理层，其余组件开箱即用。

**标准 EKS → HyperPod EKS 适配清单：**

| 组件 | 标准 EKS | HyperPod EKS | 需改动 |
|------|---------|-------------|--------|
| Karpenter NodeClass | `EC2NodeClass` | `HyperpodNodeClass` | **是** |
| Karpenter NodePool | `nodeClassRef.kind: EC2NodeClass` | `nodeClassRef.kind: HyperpodNodeClass` | **是** |
| SOCI 配置 | AMI 预装或 userData 脚本 | `on_create` 生命周期脚本自动配置 | 否（已内置） |
| KEDA ScaledObject | 无变化 | 无变化 | 否 |
| DaemonSet 预热 | 无变化 | 无变化 | 否 |
| ComfyUI Deployment | 无变化 | 无变化 | 否 |
| Service / Ingress | 无变化 | 无变化 | 否 |

**HyperPod 专属部署命令：**

```bash
# 替换标准 EKS 的 EC2NodeClass + NodePool
export HP_INSTANCE_GROUP_1=<your-hyperpod-instance-group>
envsubst < deploy/k8s-manifests/karpenter-hyperpod-nodeclass-gpu.yaml | kubectl apply -f -
kubectl apply -f deploy/k8s-manifests/karpenter-hyperpod-nodepool-gpu.yaml

# 其余组件与标准 EKS 完全一致
kubectl apply -f deploy/k8s-manifests/comfyui-nvme-prewarm-daemonset.yaml
kubectl apply -f deploy/k8s-manifests/comfyui-keda-triggerauth.yaml
kubectl apply -f deploy/k8s-manifests/comfyui-keda-scaledobject.yaml
kubectl apply -f deploy/k8s-manifests/comfyui-deployment.yaml
kubectl apply -f deploy/k8s-manifests/comfyui-service.yaml
```

**HyperPod 独有优势：**
- **节点故障自愈**: `NodeRecovery=Automatic`，GPU 硬件故障时自动替换节点，无需人工干预
- **NVMe 存储**: HyperPod GPU 实例（g5/g6e/p4d）均配备本地 NVMe SSD，DaemonSet 预热路径一致
- **SOCI Lazy Loading**: 已通过 `on_create_eks_v3.sh` 生命周期脚本自动配置 containerd snapshotter + SOCI 并行拉取，新节点开箱即用
