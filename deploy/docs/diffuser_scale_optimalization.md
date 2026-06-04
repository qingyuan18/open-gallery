# Diffusers Upscale on EKS — 冷启动扩容优化记录

把 `diffusers-upscale`（HuggingFace `StableDiffusionUpscalePipeline` × FastAPI）的冷启动（KEDA 触发 → 新节点 → pod ready → 首请求 200）从 **~9 分钟** 压到 **~1 分钟**。

测试环境：`g7e.4xlarge` spot（`us-east-1b` / `us-east-1d` FSR 已开启），`diffusers-upscale:latest` 镜像（含 SD x4 Upscaler fp16 权重，~7 GiB），AMI 烘进同款镜像。Warm anchor pod 跑在 SageMaker HyperPod 静态节点 `hyperpod-i-021146dc6ad9468dd`（L40S）防止 spot 回收造成 Service endpoint 全失。

工作目录：`/Users/tangqy/workspaces/open-gallery/deploy/`。

---

## 总览

最优实测：从 NodeClaim 创建到首个 `/upscale` 200 共 **65s**（不含 AWS 等容量）。

| 阶段 | 耗时 |
|---|---|
| NodeClaim 创建 → EC2 Launched | 3s |
| EC2 Launched → Node Registered | 21s |
| Node Registered → Node Ready | 13s |
| Node Ready → Pod Scheduled | 8s |
| Pod Scheduled → Container started | 2s |
| Container started → uvicorn up | 11s |
| uvicorn up → Pipeline ready | 0.7s |
| Pipeline ready → Pod Ready (healthz=200) | 2s |
| Pod Ready → 首个 /upscale 200 | ~5s |
| **合计** | **~65s** |




> KEDA poll → pod 创建固定 ~12s（CW publish + pollingInterval 决定）。等 AWS 容量是 spot 池供需波动，跟优化无关。

---

## 已实施的优化

每条标了**节省 X 秒**指相对没做这个优化时的耗时差。优化项之间不可加（互相耦合），但各自独立验证过。

### 1. 双 NodePool（spot 优先 + OD 兜底）—— 节省 spot 短缺时的 retry 死循环

单 NodePool 同时允许 `[spot, on-demand]` 时 Karpenter 仍偏好 spot，spot 拉不起来 OD 替补也很慢。改成两个独立 NodePool，spot pool 加 `weight: 10`：

```yaml
# upscale (spot)，weight=10 优先
requirements: [{key: karpenter.sh/capacity-type, values: [spot]}]
# upscale-od (on-demand)，无 weight 默认 0
requirements: [{key: karpenter.sh/capacity-type, values: [on-demand]}]
```

文件：[`karpenter-nodepool-diffusers-upscale.yaml`](../k8s-manifests/karpenter-nodepool-diffusers-upscale.yaml)。

### 2. AMI snapshot 双 AZ 都开 FSR —— `Launched → Registered` 1m39s → 21s（**省 ~78s**）

`us-east-1b`、`us-east-1d` 都给 boot snapshot 开 Fast Snapshot Restore。

```bash
aws ec2 enable-fast-snapshot-restores \
  --availability-zones us-east-1b us-east-1d \
  --source-snapshot-ids snap-0d616bae7ae37319b \
  --region us-east-1
```

成本：~$0.75/hour/AZ。**坑**：FSR 配额 region 级 = 5；增加新 AMI 前先 disable 旧 snapshot 的 FSR。

### 3. Karpenter `UNAVAILABLE_OFFERINGS_TTL=30s` —— spot 失败重试 3m → 30s（**省 ~150s**）

默认 cache TTL=180s，spot 一次拉起失败后 3min 内不会再尝试。

```bash
helm upgrade karpenter oci://public.ecr.aws/karpenter/karpenter \
  --version 1.12.0 -n kube-system --reuse-values \
  --set "controller.env[0].name=UNAVAILABLE_OFFERINGS_TTL" \
  --set "controller.env[0].value=30s"
```

### 4. 模型 + 镜像 双重烘进 AMI —— 镜像拉取 1m+ → 0s（**省 ~60s+**）

`huggingface_hub.snapshot_download` 把 SD x4 fp16 权重 build 进镜像；AMI build 时 `ctr -n k8s.io images pull` 预拉镜像到 containerd 本地。运行时 `imagePullPolicy: IfNotPresent` 直接命中。

```dockerfile
RUN python -c "from huggingface_hub import snapshot_download; \
    snapshot_download(repo_id='stabilityai/stable-diffusion-x4-upscaler', \
        local_dir='/opt/program/models/x4-upscaler', \
        allow_patterns=['*.json','*.txt','*.fp16.safetensors','tokenizer/*','scheduler/*'])"
ENV TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1
```

文件：[`diffusers-upscale.dockerfile`](../diffusers-upscale.dockerfile)、[`build-diffusers-upscale-ami.sh`](../scripts/build-diffusers-upscale-ami.sh)。

### 5. Page-cache prewarm —— `Container start → Pipeline ready` 22s → 12s（**省 ~10s**）

FSR 解决"EBS 块在不在"，但 OS page cache 是 per-EC2 实例的，第一次 dlopen 还是物理 IO（torch `_C.so` 1.6 GiB、`libtorch_cuda.so` 1.3 GiB）。entrypoint 启动后并发 `cat *.so > /dev/null` 触发 readahead，**与 Python 解释器启动并行跑**，等 import 触发 dlopen 时 page cache 已经命中：

```dockerfile
RUN cat > /opt/program/prewarm.sh <<'SHEOF'
#!/bin/bash
T=/usr/local/lib/python3.12/dist-packages/torch/lib
for f in "$T/libtorch_cuda.so" "$T/libtorch_cpu.so" \
         "$T/libtorch_cuda_linalg.so" "$T/libtorch_python.so" \
         "$T/../torch/_C.cpython-312-x86_64-linux-gnu.so"; do
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
CMD ["/opt/program/prewarm.sh"]
```

具体拆解：`Container start → uvicorn` 14s→11s；`uvicorn → Pipeline ready` 8.2s→0.7s（mmap fp16 时已命中 cache）。

### 6. KEDA pollingInterval=5s + scaleUp stabilizationWindow=0 —— KEDA 滞后压到 ~12s

[`diffusers-upscale-keda-scaledobject.yaml`](../k8s-manifests/diffusers-upscale-keda-scaledobject.yaml)：

```yaml
pollingInterval: 5
cooldownPeriod: 120
advanced:
  horizontalPodAutoscalerConfig:
    behavior:
      scaleUp:   { stabilizationWindowSeconds: 0 }
      scaleDown: { stabilizationWindowSeconds: 180 }
```

KEDA 这段固定 ~12s（CW publish 滞后 + 1 轮 polling），物理下界。

### 7. Warm anchor pod（防 Service endpoints 全失，**不影响冷启动时间**）

Service 的 endpoints = `app=diffusers-upscale` 全部 pod。只有 KEDA 管理的 spot pod 时，spot 一旦回收 Service 直接没 endpoint，外部 ingress 立刻 5xx，CW 指标也停了，KEDA 自身回不来。

放一个静态 Deployment 锚定到 HyperPod 静态节点（L40S）作为兜底：

```yaml
nodeSelector: { kubernetes.io/hostname: hyperpod-i-021146dc6ad9468dd }
labels:
  app: diffusers-upscale     # 命中 Service selector
  role: warm-anchor           # 给 KEDA scaleTarget 区分（KEDA 选的是另一个 Deployment）
```

---

## 8. Karpenter cache 软死锁的 escape hatch

`UNAVAILABLE_OFFERINGS_TTL=30s` 控制单次失败的 cache 寿命。但当 AWS 在某 AZ × 实例类型上**持续**返回 `UnfulfillableCapacity`，每次重试都会重新加入 cache — 即使容量回来了 TTL 也救不了，会卡几分钟才下次尝试。

**观察**：`kubectl logs -n kube-system -l app.kubernetes.io/name=karpenter --since=2m | grep "skipping, nodepool requirements filtered out all instance types"`，连续多分钟出现说明卡住了。

**强制 escape**：`kubectl delete pod -n kube-system <karpenter-pod>` — 重启 controller 清空 in-memory cache，下个 reconcile 立刻重新探 AWS。

> 长期方案：扩 NodePool 允许的实例类型（如加 `g6e.4xlarge`、`g6.4xlarge` 兜底），而不是死磕单一 `g7e.4xlarge`。

---

## 9. 未实施的进阶优化项

### 9.1 nvidia-device-plugin 提前注册（预期省 5-10s）

DPL 注册 GPU 容量是 schedule 必经路径。把 DaemonSet 加 `priorityClassName: system-node-critical`，必要时把 plugin 二进制预装进 AMI（不走容器拉镜像）。当前 `Node Ready → Pod Scheduled` 8s 主要花在这上面。

### 9.2 CUDA / cuDNN cache 烘进镜像（预期省 4-6s）

每次新 pod 起来，`pipe.to("cuda")` 和首次推理会现编译 GPU kernel。CUDA 把编译结果写在 `~/.nv/ComputeCache`，但 pod 每次新建这个目录就空。

可以在 docker build 时跑一遍 `pipe.to("cuda")` + 一张 1×1 像素的 dummy forward，把编译好的 cache 烙进镜像层。

**实施门槛**：
- cloud-build 实例需要 GPU（当前 CPU build 跑不了）。
- cache 跟 GPU 架构绑定。`g7e.4xlarge` spot 池随机给 L40S（sm_89）或 RTX PRO 6000 Blackwell（sm_120）两种，build 时需要双架构都跑一遍。
- cache 跟 PyTorch + CUDA driver 版本绑死，base image 一升级就要全部重编。

---

## 10. 已尝试但放弃的优化项

### 10.1 VPC CNI Prefix Delegation

想用 `ENABLE_PREFIX_DELEGATION=true` 让 ENI 一次性预分配 /28 IP block 来削减 CNI sandbox 创建延迟。

实施后 HyperPod 节点（`aws-node` DaemonSet）立即 CrashLoopBackOff（IPAMD 50051 GRPC timeout）。HyperPod 的 EFA + 专用 ENI 跟 Prefix Delegation 不兼容。

**回退**：直接 `kubectl set env ds aws-node ENABLE_PREFIX_DELEGATION=false`，再 `aws eks update-addon` 把 addon configValues 也对齐到 false 防止 controller reconcile 重新打开。

结论：此优化在混合 HyperPod + 自管节点的集群里不可用。

### 10.2 nvidia-device-plugin 双 DaemonSet 去重

集群里有两个 DPL：`kube-system/nvidia-device-plugin`（v0.14.1，所有节点）和 `hyperpod-dependencies/nvidia-device-plugin-*`（v0.16.1）。担心冲突拖慢 register。

实际查了 hyperpod-dependencies 那个 DS 的 nodeAffinity 已经限定到 `ml.*` SageMaker 实例类型，从来不会 schedule 到 g7e.4xlarge spot 节点。无需改。

---

## 11. 已知风险

- **g7e.4xlarge 池容量短缺**：多次遇到 `us-east-1b` + `us-east-1d` 同时 `UnfulfillableCapacity`。spot 短缺一段时间后 OD 也会被波及。当前已加 `upscale-od` 兜底，但仍是单一实例类型，建议扩到 `g6e.4xlarge`、`g6.4xlarge` 多类型 fallback。
- **Karpenter 软死锁**：spot+OD 同时 unavailable 时，Karpenter cache 长时间不刷新；workaround 是 `kubectl delete pod` 重启 controller，参考 §8。
- **VPC CNI addon 与 DS env 漂移**：addon 自动 reconcile 会把 DS 改回 `ENABLE_PREFIX_DELEGATION=true`，必须保证 addon configValues 也是 false。已修复（addon update id `4626f63e-...`）。
- **FSR 配额是 region 级 = 5**：增加新 AMI 时记得先 disable 旧 snapshot 的 FSR。
- **Warm anchor 占用一颗 HyperPod L40S GPU**：长期占着 ml.g6e.4xlarge 的一个 GPU 槽位。如果 HyperPod 节点本身要改用途，需要换到其他静态节点。
- **GPU 异构（L40S vs Blackwell）**：`g7e.4xlarge` spot 池随机给两种 GPU。base image 必须支持 sm_89 + sm_120 两个架构（已用 `nvcr.io/nvidia/pytorch:25.03-py3`）。如果未来烘 cuDNN cache，需要双架构都烘。

---

## 12. 文件索引

manifests:
- [`diffusers-upscale-deployment.yaml`](../k8s-manifests/diffusers-upscale-deployment.yaml)
- [`diffusers-upscale-service.yaml`](../k8s-manifests/diffusers-upscale-service.yaml)
- [`diffusers-upscale-keda-scaledobject.yaml`](../k8s-manifests/diffusers-upscale-keda-scaledobject.yaml)
- [`karpenter-ec2nodeclass-diffusers-upscale.yaml`](../k8s-manifests/karpenter-ec2nodeclass-diffusers-upscale.yaml)
- [`karpenter-nodepool-diffusers-upscale.yaml`](../k8s-manifests/karpenter-nodepool-diffusers-upscale.yaml)

build / bake:
- [`diffusers-upscale.dockerfile`](../diffusers-upscale.dockerfile)
- [`scripts/cloud-build-diffusers-upscale.sh`](../scripts/cloud-build-diffusers-upscale.sh)
- [`scripts/build-diffusers-upscale-ami.sh`](../scripts/build-diffusers-upscale-ami.sh)

测试 / 压测:
- [`scripts/test-diffusers-upscale.sh`](../scripts/test-diffusers-upscale.sh)
- [`scripts/diffusers_upscale_server.py`](../scripts/diffusers_upscale_server.py)
