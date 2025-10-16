# ComfyUI-S3 Standalone Deployment Guide

快速部署和测试 ComfyUI-S3 在 EKS 上的独立部署指南。

---

## 📋 概述

这个部署方式专门用于快速测试 ComfyUI-S3，特点：

- ✅ **独立命名空间**: 部署在 `comfyui-test` 命名空间，不影响其他服务
- ✅ **快速构建**: 只构建 ComfyUI-S3 镜像（5-10分钟）
- ✅ **简化配置**: 最小化配置，专注于功能测试
- ✅ **Port-Forward 访问**: 通过 kubectl port-forward 快速访问
- ✅ **易于清理**: 删除命名空间即可完全清理

---

## 🚀 快速开始

### 前置条件

1. **EKS 集群已配置 GPU 节点**
   ```bash
   kubectl get nodes -o wide | grep gpu
   ```

2. **S3 CSI Driver 已安装**
   ```bash
   kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-mountpoint-s3-csi-driver
   ```

3. **模型已上传到 S3**
   ```bash
   aws s3 ls s3://comfyui-models-bucket-687912291502/models/
   ```

### 一键部署

```bash
cd deploy
./scripts/deploy-comfyui-s3-standalone.sh
```

部署完成后，脚本会显示 port-forward 命令。

---

## 📝 详细步骤

### 步骤 1: 准备 S3 模型（如果还没有）

```bash
# 上传模型到 S3
./scripts/upload-models-to-s3.sh \
    --bucket comfyui-models-bucket-687912291502 \
    --region us-west-2
```

### 步骤 2: 安装 S3 CSI Driver（如果还没有）

```bash
# 使用 Pod Identity（推荐）
./scripts/setup-s3-csi.sh \
    --cluster-name your-cluster-name \
    --bucket comfyui-models-bucket-687912291502 \
    --use-pod-identity
```

### 步骤 3: 部署 ComfyUI-S3

```bash
## open-gallery根目录下执行：
# 完整部署（构建镜像 + 部署， 先不mount s3模型）
bash deploy/scripts/deploy-comfyui-s3-standalone.sh --no-s3-mount 

## 完整构建（重新build）
bash deploy/scripts/deploy-comfyui-s3-standalone.sh   --bucket comfyui-models-bucket-687912291502  --gpu-node-type ml.g6e.4xlarge --yes

# 使用已有镜像（跳过构建）
bash deploy/scripts/deploy-comfyui-s3-standalone.sh --skip-build  --bucket comfyui-models-bucket-687912291502  --gpu-node-type ml.g6e.4xlarge --yes

# 自定义 S3 bucket
bash deploy/scripts/deploy-comfyui-s3-standalone.sh --bucket comfyui-models-bucket-687912291502

# 使用更大的 GPU 实例
bash deploy/scripts/deploy-comfyui-s3-standalone.sh --gpu-node-type ml.g6e.2xlarge
```

### 步骤 4: 访问 ComfyUI

```bash
# 获取 Pod 名称
POD_NAME=$(kubectl get pods -n comfyui-test -l app=comfyui-s3-test -o jsonpath='{.items[0].metadata.name}')

# Port-forward
kubectl port-forward -n comfyui-test $POD_NAME 8188:8188

# 在浏览器中打开
open http://localhost:8188
```

---

## 🔧 常用命令

### 查看状态

```bash
# 查看 Pod 状态
kubectl get pods -n comfyui-test

# 查看详细信息
kubectl describe pod -n comfyui-test -l app=comfyui-s3-test

# 查看日志
kubectl logs -n comfyui-test -l app=comfyui-s3-test -f

# 查看 S3 挂载状态
kubectl exec -n comfyui-test -it $POD_NAME -- ls -la /opt/program/models
```

### 调试

```bash
# 进入 Pod
kubectl exec -n comfyui-test -it $POD_NAME -- /bin/bash

# 检查 S3 挂载
kubectl exec -n comfyui-test -it $POD_NAME -- df -h

# 查看环境变量
kubectl exec -n comfyui-test -it $POD_NAME -- env | grep -E 'NVIDIA|AWS'

# 检查 GPU
kubectl exec -n comfyui-test -it $POD_NAME -- nvidia-smi
```

### 更新部署

```bash
# 重新构建并部署新镜像
./scripts/deploy-comfyui-s3-standalone.sh

# 或手动重启 Pod
kubectl rollout restart deployment/comfyui-s3-test -n comfyui-test
```

---

## 🧹 清理资源

### 删除整个测试环境

```bash
# 删除命名空间（包含所有资源）
kubectl delete namespace comfyui-test

# 删除 PV（如果需要）
kubectl delete pv comfyui-models-pv-test
```

### 仅删除 Deployment

```bash
# 保留命名空间，只删除 Deployment
kubectl delete deployment comfyui-s3-test -n comfyui-test
```

---

## 🔍 故障排除

### Pod 无法启动

```bash
# 检查 Pod 事件
kubectl describe pod -n comfyui-test -l app=comfyui-s3-test

# 常见问题：
# 1. GPU 节点不可用
kubectl get nodes -l node.kubernetes.io/instance-type=g5.xlarge

# 2. S3 PVC 未绑定
kubectl get pvc -n comfyui-test

# 3. 镜像拉取失败
kubectl get events -n comfyui-test --sort-by='.lastTimestamp'
```

### S3 挂载失败

```bash
# 检查 S3 CSI Driver
kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-mountpoint-s3-csi-driver

# 检查 PV 状态
kubectl get pv comfyui-models-pv-test

# 检查 Pod Identity
kubectl get sa s3-csi-driver-sa -n kube-system -o yaml
```

### GPU 不可用

```bash
# 检查 GPU 资源
kubectl describe node -l node.kubernetes.io/instance-type=g5.xlarge | grep -A 5 "Allocated resources"

# 检查 NVIDIA Device Plugin
kubectl get pods -n kube-system -l name=nvidia-device-plugin-ds
```

---

## 📊 性能测试

### 测试 S3 读取速度

```bash
kubectl exec -n comfyui-test -it $POD_NAME -- bash -c "
time ls -lh /opt/program/models/diffusion_models/
"
```

### 测试模型加载

```bash
# 查看启动日志中的模型加载时间
kubectl logs -n comfyui-test $POD_NAME | grep -i "loading"
```

---

## 🔄 与完整部署的区别

| 特性 | Standalone 部署 | 完整部署 |
|------|----------------|---------|
| **命名空间** | `comfyui-test` | `default` |
| **Service** | ClusterIP (可选) | ClusterIP |
| **Ingress** | ❌ 无 | ✅ ALB Ingress |
| **Open Gallery** | ❌ 不包含 | ✅ 包含 |
| **访问方式** | Port-forward | 公网 ALB |
| **用途** | 快速测试 | 生产环境 |
| **清理** | 删除 namespace | 删除多个资源 |

---

## 📚 相关文档

- **[EKS_DEPLOYMENT.md](EKS_DEPLOYMENT.md)** - 完整的 EKS 部署指南
- **[CONFIG-GUIDE.md](CONFIG-GUIDE.md)** - 配置管理指南
- **ComfyUI-S3 Dockerfile**: `deploy/comfyui-s3.dockerfile`
- **部署脚本**: `deploy/scripts/deploy-comfyui-s3-standalone.sh`

---

## 💡 最佳实践

1. **开发测试流程**
   ```bash
   # 1. 修改代码
   # 2. 重新构建和部署
   ./scripts/deploy-comfyui-s3-standalone.sh
   
   # 3. Port-forward 测试
   kubectl port-forward -n comfyui-test $POD_NAME 8188:8188
   
   # 4. 验证功能
   # 5. 清理测试环境
   kubectl delete namespace comfyui-test
   ```

2. **使用已有镜像快速迭代**
   ```bash
   # 第一次：完整构建
   ./scripts/deploy-comfyui-s3-standalone.sh
   
   # 后续：跳过构建，快速部署
   ./scripts/deploy-comfyui-s3-standalone.sh --skip-build
   ```

3. **多环境测试**
   ```bash
   # 测试不同 GPU 实例类型
   ./scripts/deploy-comfyui-s3-standalone.sh --gpu-node-type g5.xlarge
   ./scripts/deploy-comfyui-s3-standalone.sh --gpu-node-type g5.2xlarge
   ```

---

**版本:** 1.0.0  
**最后更新:** 2025-10-10  
**适用于:** EKS 集群快速测试

