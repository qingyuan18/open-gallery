# MultiGPU CFG Split 部署指南

ComfyUI v0.23.0 引入的 `MultiGPU_WorkUnits` 节点（display name: `MultiGPU CFG Split`），把 classifier-free guidance 的正向和负向两次 forward 拆到两张 GPU 上并行执行，给真 CFG（cfg>1）的工作流带来近 ~2× 的采样加速。本文档记录在 4×L40S 实例上的部署与 benchmark 结果。

## 背景

经典 CFG 公式：

```
out = neg + cfg * (pos - neg)
```

`cfg > 1` 时每个采样步必须分别跑一次 pos 和一次 neg forward，把两个独立的预测做外推。`MultiGPU_WorkUnits` 把这两次 forward 分到两张 GPU 上并行：

```
                ┌── pos forward (GPU 0) ──┐
[KSampler] ─────┤                         ├── CFG combine ── next step
                └── neg forward (GPU 1) ──┘
```

**起源**：[PR #7063](https://github.com/comfyanonymous/ComfyUI/pull/7063)（合并于 2026-05-26，首发版本 v0.23.0）。
**实现位置**：[comfy_extras/nodes_multigpu.py](https://github.com/comfyanonymous/ComfyUI/blob/v0.23.0/comfy_extras/nodes_multigpu.py)，配合 [comfy/multigpu.py](https://github.com/comfyanonymous/ComfyUI/blob/v0.23.0/comfy/multigpu.py) 的 `create_multigpu_deepclones`。

### 适用条件

| 条件 | 说明 |
|---|---|
| ComfyUI ≥ v0.23.0 | 节点首次随该版本发布 |
| 多卡实例 | 至少 2 张同型号 GPU，建议 NVLink 或同 PCIe 根 |
| 工作流 cfg > 1 | cfg=1 时 ComfyUI 旁路 uncond 路径，第二张卡空转 |
| 真实 negative prompt | 不能是 None；ConditioningZeroOut 算真 conditioning，OK |
| 原生 ComfyUI 采样链路 | 仅对 `KSampler` / `KSamplerAdvanced` 等核心节点有效；kijai `WanVideoSampler` 等 forked sampler 无效 |

### 模型兼容性速查

| 模型 | cfg 默认 | CFG Split 受益 |
|---|---|---|
| Qwen-Image-Edit (2509/2511) | 2.5 | ✅ |
| Wan 2.2 i2v / t2v 14B（high-noise 阶段） | 3.5 | ✅ 仅 high 阶段，low 阶段 cfg=1 不受益 |
| Flux 2 [klein] base 开源权重 | 4.0 | ✅ |
| SDXL / SD3.5 / 普通 SD | 3 ~ 7 | ✅ |
| Flux.1 dev / schnell / Kontext | 1.0（FluxGuidance distilled） | ❌ |

## 安装部署

### 1. ComfyUI 升级到 v0.23.0+

```bash
cd /home/ubuntu/ComfyUI
git fetch origin --tags
git stash push -u -m pre-upgrade -- models output 2>/dev/null || true
git checkout v0.23.0
python3 -m pip install --break-system-packages -r requirements.txt
```

固定与现有 custom_nodes 兼容的依赖（v0.23.0 默认拉的 transformers/numpy/torch 太新，会破坏 custom_nodes 加载，并且 torch 2.12 + cu13 跟驱动 12.8 不兼容）：

```bash
python3 -m pip install --break-system-packages \
  "transformers==4.46.0" "tokenizers<0.21" "numpy<2.4"
python3 -m pip install --break-system-packages --force-reinstall \
  torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 \
  --index-url https://download.pytorch.org/whl/cu128
```

### 2. 必须 patch：绕过 comfy-aimdo 的 host_buffer

ComfyUI v0.23.0 把 `comfy_aimdo.host_buffer` 硬连接到 [comfy/memory_management.py:7](https://github.com/comfyanonymous/ComfyUI/blob/v0.23.0/comfy/memory_management.py#L7) 的 `read_tensor_file_slice_into`。当 `MultiGPU_WorkUnits` 触发 `deepclone_multigpu(new_load_device=cuda:1)` 重读模型权重时，aimdo 的 host_buffer 不是重入安全的，会报：

```
RuntimeError: hostbuf_file_reader_read failed
```

最简修复——让 `read_tensor_file_slice_into` 直接 fallback 到 PyTorch 原生 `readinto`：

```bash
sed -i 's|def read_tensor_file_slice_into(tensor, destination, stream=None, destination2=None):$|&\n    return False  # bypass aimdo host_buffer for MultiGPU CFG Split|' \
  /home/ubuntu/ComfyUI/comfy/memory_management.py
```

验证：

```bash
sed -n '17,22p' /home/ubuntu/ComfyUI/comfy/memory_management.py
```

应看到 `return False` 在 `def read_tensor_file_slice_into(...)` 后第一行。

> **注意**：`--disable-async-offload` / `--disable-dynamic-vram` flag 不能解决这个问题——aimdo 的 read 路径在 v0.23.0 是默认硬连接，不受 flag 控制。
>
> **不要使用 `--highvram`**：会把整个模型族锁在 GPU 0，加上 1536² latent activations 会 OOM（L40S 46GB 不够装 Qwen UNet 20GB + Qwen2.5-VL-7B + middleware）。

### 3. 模型放 NVMe（避免 EBS gp3 IO 瓶颈）

EBS gp3 默认 125 MB/s，加载 20GB+ 模型可能要数十分钟。AWS 实例自带 NVMe ephemeral（`/opt/dlami/nvme`）速度数 GB/s，建议把大模型搬过去并用软链：

```bash
mkdir -p /opt/dlami/nvme/comfyui-models
# 大模型从 EBS 复制到 NVMe（一次性）
cp /home/ubuntu/ComfyUI/models/diffusion_models/*.safetensors /opt/dlami/nvme/comfyui-models/
# 替换软链
cd /home/ubuntu/ComfyUI/models/diffusion_models
rm <model>.safetensors
ln -sf /opt/dlami/nvme/comfyui-models/<model>.safetensors <model>.safetensors
```

CLIP / VAE / LoRA 同理。

### 4. 启动多 ComfyUI 实例做 GPU 隔离

4 卡机上跑两个独立 ComfyUI、各占两张卡，互不干扰：

```bash
# Instance A: 端口 8188，物理 GPU 0+1
sudo -u ubuntu setsid bash -c 'cd /home/ubuntu/ComfyUI && \
  CUDA_VISIBLE_DEVICES=0,1 \
  nohup python3 main.py --listen 0.0.0.0 --port 8188 \
    --output-directory /home/ubuntu/ComfyUI/output/qwen \
    > /home/ubuntu/ComfyUI/comfyui-8188.log 2>&1 < /dev/null' &

# Instance B: 端口 8189，物理 GPU 2+3
sudo -u ubuntu setsid bash -c 'cd /home/ubuntu/ComfyUI && \
  CUDA_VISIBLE_DEVICES=2,3 \
  nohup python3 main.py --listen 0.0.0.0 --port 8189 \
    --output-directory /home/ubuntu/ComfyUI/output/wan \
    > /home/ubuntu/ComfyUI/comfyui-8189.log 2>&1 < /dev/null' &
```

`CUDA_VISIBLE_DEVICES=0,1` 让 A 进程内只看到两张卡并重新编号为 `cuda:0` / `cuda:1`，B 同理（其内部 `cuda:0` 实际是物理 GPU 2）。

等到 API 200 才能提交 prompt（端口 LISTEN ≠ API ready，server 在 fetch ComfyRegistry 时会拒绝 POST）：

```bash
while ! curl -sf -o /dev/null http://127.0.0.1:8188/system_stats; do sleep 5; done; echo "8188 OK"
while ! curl -sf -o /dev/null http://127.0.0.1:8189/system_stats; do sleep 5; done; echo "8189 OK"
```

### 5. 工作流添加 MultiGPU CFG Split 节点

在原工作流的 model 链最末端、KSampler 之前插入 `MultiGPU_WorkUnits` 节点：

```
原: UNETLoader → LoraLoader → ModelSamplingSD3 → KSampler
新: UNETLoader → LoraLoader → ModelSamplingSD3 → MultiGPU_WorkUnits → KSampler
```

JSON 节点结构：

```json
"50": {
  "inputs": {
    "model": ["47", 0],
    "max_gpus": 2
  },
  "class_type": "MultiGPU_WorkUnits",
  "_meta": { "title": "MultiGPU CFG Split" }
}
```

然后把 KSampler 的 `inputs.model` 由 `["47", 0]`（原 model 节点）改为 `["50", 0]`（CFG Split 节点）。

**Wan 2.2 dual-model**：每条 UNet 链各插一个 CFG Split 节点（high-noise 链需要、low-noise 链 cfg=1 时可省）。

参考 workflow：
- [server/asset/qwen_image_edit_multigpu_workflow.json](../../server/asset/qwen_image_edit_multigpu_workflow.json)
- [server/asset/wan22_i2v_native_multigpu_workflow.json](../../server/asset/wan22_i2v_native_multigpu_workflow.json)

## Benchmark 结果

测试环境：i-09eec40c5a8af42f6，AWS g6e.12xlarge 派生，4×NVIDIA L40S（46GB each），ComfyUI v0.23.0 + 上述 patch，模型放 NVMe。每个工作流测 2 次（warm-up + timed）。

| 模型 / 工作流 | Baseline (avg) | CFG Split (avg) | 加速比 | 单步对比 |
|---|---|---|---|---|
| **Qwen-Image-Edit 2509 fp8** + Lightning 8-step LoRA<br>1536² latent, cfg=2.5, 8 steps | 146.71s | **73.13s** | **2.01×** | 17.6 → 8.74 s/it |
| **Wan 2.2 i2v 14B** + lightx2v 4-step LoRA<br>800×800 / 81 帧, dual-model | 254.56s | **166.44s** | **1.53×** | high: 36.6→23.0 s/it<br>low: 17.3 s/it (不变) |

### Qwen 接近理论 2×

整个 8 步 KSampler 都跑真 CFG（cfg=2.5），完美适配 CFG Split。

### Wan 2.2 只 1.53×

Dual-model 架构里：
- **High-noise 阶段**（步 0-4，cfg=3.5）：真 CFG → CFG Split 加速 ~1.6× （36.6→23.0 s/it）
- **Low-noise 阶段**（步 4-8，cfg=1.0）：lightx2v 4-step LoRA 蒸馏后 cfg=1，单 forward → CFG Split 完全不受益

理论上限：`baseline_total / (high/2 + low) = (4×36 + 4×17) / (4×18 + 4×17) ≈ 1.5×`，实测 1.53× 与之吻合。要追求 2×，需切换到 **non-distilled low-noise** 的工作流配置（让 low 段也跑 cfg>1）。

## 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `RuntimeError: hostbuf_file_reader_read failed` | 缺 patch | 应用步骤 2 的 patch |
| OOM on GPU 0 with `--highvram` | 模型族强制全锁 GPU 0 | 移除 `--highvram` flag |
| GPU 1 全程 0% util | cfg=1 / 工作流连接错误 | 确认 KSampler.cfg > 1，且 `model` 字段指向 `MultiGPU_WorkUnits` 节点 ID |
| 启动后 API 拒绝 POST `/api/prompt` | ComfyUI-Manager 在 fetch ComfyRegistry，server 还没 ready | 等到 `/system_stats` 返回 200 再提交，或 `mv custom_nodes/ComfyUI-Manager{,.bak}` |
| `cp: cannot stat ...` 软链断 | EBS 上的源文件已删但软链还指着 | 重建软链或重新下载 |

## 生产部署 Checklist

- [ ] 容器镜像中烘入 ComfyUI v0.23.0
- [ ] 镜像构建脚本里加上 memory_management.py 的 patch（每次 `pip install comfy-aimdo` 后自动应用）
- [ ] 模型存 EFS / S3 + NVMe 缓存层（Karpenter 节点起来后并发拉到 NVMe）
- [ ] Karpenter NodePool 选用 2× 或 4× L40S 实例（`g6e.12xlarge` / `g6e.48xlarge`）
- [ ] 工作流模板更新带 `MultiGPU_WorkUnits` 的版本，`max_gpus` 与 NodePool GPU 数对齐
- [ ] CloudWatch metric: 双卡场景下 GPU 1 util 应在采样阶段 >70%（监控指标低 = CFG Split 没生效）
