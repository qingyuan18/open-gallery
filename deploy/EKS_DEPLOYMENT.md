# Open Gallery + ComfyUI AWS EKS 部署指南

本目录包含在 AWS EKS 上部署 Open Gallery 和 ComfyUI 的完整配置和脚本。

---

## 📋 目录结构

```
deploy/
├── EKS_DEPLOYMENT.md                      # 本文档 (完整部署指南)
├── COMFYUI_S3_STANDALONE.md               # ComfyUI-S3 独立测试部署指南
├── CONFIG-GUIDE.md                        # 配置管理详细指南
│
├── Dockerfiles
│   ├── open-gallery.dockerfile            # Open Gallery 应用镜像
│   ├── comfyui-embedded.dockerfile        # ComfyUI (模型嵌入)
│   └── comfyui-s3.dockerfile              # ComfyUI (S3 挂载)
│
├── k8s-manifests/                         # Kubernetes 配置文件
│   ├── open-gallery-deployment.yaml       # Open Gallery 部署
│   ├── open-gallery-service.yaml          # Open Gallery 服务
│   ├── open-gallery-ingress.yaml          # ALB Ingress (外部访问)
│   ├── open-gallery-configmap.yaml        # Open Gallery 配置
│   │
│   ├── comfyui-deployment.yaml            # ComfyUI 部署 (S3 模式)
│   ├── comfyui-deployment-embedded.yaml   # ComfyUI 部署 (Embedded 模式)
│   ├── comfyui-s3-standalone.yaml         # ComfyUI-S3 独立测试部署
│   ├── comfyui-service.yaml               # ComfyUI 服务 (内部)
│   ├── comfyui-configmap.yaml             # ComfyUI 配置
│   ├── comfyui-hpa.yaml                   # 自动扩展配置
│   │
│   ├── s3-pv-pvc.yaml                     # S3 持久卷配置
│   └── s3-csi-policy.json                 # S3 CSI IAM 策略
│
└── scripts/                               # 部署脚本
    ├── build-and-push.sh                  # 构建和推送镜像
    ├── deploy-to-eks.sh                   # 部署到 EKS (完整部署)
    ├── deploy-comfyui-s3-standalone.sh    # ComfyUI-S3 独立测试部署
    ├── setup-s3-csi.sh                    # S3 CSI 设置 (支持 Pod Identity 和 IRSA)
    └── upload-models-to-s3.sh             # 上传模型到 S3
```

---

## 🏗️ 架构说明

```
Internet
   │
   ▼
AWS ALB (Application Load Balancer)
   │
   ▼
Open Gallery Service (ClusterIP:80)
   │
   ├─► Open Gallery Pod (Frontend + Backend)
   │   └─► Port 57988
   │
   └─► ComfyUI Service (ClusterIP:8188) [内部服务]
       └─► ComfyUI Pod (GPU)
           └─► Port 8188
```

**关键特性:**
- ✅ Open Gallery 通过 ALB 对外暴露
- ✅ ComfyUI 仅作为内部服务，通过 ClusterIP 访问
- ✅ 支持两种 ComfyUI 部署模式：Embedded (模型打包) 和 S3 (模型挂载)

---

## 📦 部署模式对比

### Embedded 模式 (推荐用于开发/测试)

- 模型打包在 Docker 镜像中
- 镜像大小: ~50-100GB
- 构建时间: 30-60 分钟
- 无需 S3 配置

### S3 模式 (推荐用于生产环境)

- 模型从 S3 挂载
- 镜像大小: ~5-10GB
- 构建时间: 5-10 分钟
- 需要 S3 CSI Driver

---


## ⚙️ 前置条件

### 必需资源

- ✅ **现有 EKS 集群** (已配置 GPU 节点组)
- ✅ **AWS CLI** 已配置凭证
- ✅ **kubectl** 已连接到 EKS 集群
- ✅ **Docker** 已安装
- ✅ **AWS Load Balancer Controller** 已安装在集群中
- ✅ **NVIDIA Device Plugin** 已安装 (用于 GPU 支持)

### 验证集群

```bash
# 检查集群连接
kubectl cluster-info

# 检查 GPU 节点
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'

# 检查 ALB Controller
kubectl get deployment -n kube-system aws-load-balancer-controller
```

---

## 🚀 快速开始

### 方式零: ComfyUI-S3 独立测试 (最快速)

**仅测试 ComfyUI-S3，不包含 Open Gallery**

```bash
# 一键部署 ComfyUI-S3 用于测试
cd deploy
./scripts/deploy-comfyui-s3-standalone.sh

# 部署完成后，使用 port-forward 访问
kubectl port-forward -n comfyui-test <pod-name> 8188:8188

# 浏览器访问
open http://localhost:8188
```

详细说明请参考: **[COMFYUI_S3_STANDALONE.md](COMFYUI_S3_STANDALONE.md)**

---

### 方式一: Embedded 模式 (最简单)

```bash
# 1. 设置环境变量
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# 2. 构建和推送镜像
cd deploy
./scripts/build-and-push.sh

# 3. 部署到 EKS
./scripts/deploy-to-eks.sh

# 4. 获取访问 URL
kubectl get ingress open-gallery-ingress
```

### 方式二: S3 模式 (生产推荐)

```bash
# 1. 设置 S3 CSI Driver (使用 Pod Identity)
./scripts/setup-s3-csi.sh \
    --cluster-name your-cluster-name \
    --bucket comfyui-models-bucket-687912291502 \
    --use-pod-identity

# 2. 上传模型到 S3
./scripts/upload-models-to-s3.sh --bucket comfyui-models-bucket-687912291502

# 3. 更新 k8s-manifests/s3-pv-pvc.yaml 中的 bucketName

# 4. 构建和推送镜像
./scripts/build-and-push.sh --app comfyui-s3
./scripts/build-and-push.sh --app open-gallery

# 5. 部署到 EKS (S3 模式)
./scripts/deploy-to-eks.sh --comfyui-mode s3

# 6. 获取访问 URL
kubectl get ingress open-gallery-ingress
```

---

## 📝 详细部署步骤

### 步骤 1: 构建 Docker 镜像

```bash
cd deploy

# 构建所有镜像
./scripts/build-and-push.sh

# 或仅构建特定镜像
./scripts/build-and-push.sh --app open-gallery
./scripts/build-and-push.sh --app comfyui-embedded
./scripts/build-and-push.sh --app comfyui-s3

# 使用自定义标签
./scripts/build-and-push.sh --app open-gallery --tag v1.0.0
```

### 步骤 2: (可选) 配置 S3 模型存储

**仅在使用 S3 模式时需要**

#### S3 CSI Driver 安装方式

```bash
# 步骤 1: 创建 IAM 策略
aws iam create-policy \
    --policy-name ComfyUI-S3-CSI-Policy \
    --policy-document file://k8s-manifests/s3-csi-policy.json

# 步骤 2: 安装 S3 CSI Driver (EKS Add-on)
aws eks create-addon \
    --cluster-name your-cluster-name \
    --addon-name aws-mountpoint-s3-csi-driver \
    --region us-west-2

# 步骤 3: 创建 Pod Identity 关联
aws eks create-pod-identity-association \
    --cluster-name your-cluster-name \
    --namespace kube-system \
    --service-account s3-csi-driver-sa \
    --role-arn arn:aws:iam::ACCOUNT_ID:role/ComfyUI-S3-CSI-Role

# 或使用自动化脚本 (推荐)
./scripts/setup-s3-csi.sh \
    --cluster-name your-cluster-name \
    --bucket comfyui-models-bucket-687912291502 \
    --use-pod-identity  # 使用 Pod Identity 而非 IRSA
```


#### 上传模型到 S3

```bash
# 创建 S3 bucket (如果不存在)
aws s3 mb s3://your-comfyui-models-bucket

# 上传所有 ComfyUI 模型
./scripts/upload-models-to-s3.sh \
    --bucket your-comfyui-models-bucket \
    --region us-west-2

# 可选参数
./scripts/upload-models-to-s3.sh \
    --bucket your-bucket \
    --skip-existing \
    --parallel 8 \
    --dry-run  # 预览要上传的文件
```

### 步骤 3: 部署到 EKS

```bash
# Embedded 模式 (默认)
./scripts/deploy-to-eks.sh

# S3 模式
./scripts/deploy-to-eks.sh --comfyui-mode s3

# 仅部署 Open Gallery
./scripts/deploy-to-eks.sh --skip-comfyui
```

### 步骤 4: 验证部署

```bash
# 查看所有 Pods
kubectl get pods

# 查看服务
kubectl get svc

# 查看 Ingress 和 ALB URL
kubectl get ingress open-gallery-ingress

# 查看日志
kubectl logs -f deployment/open-gallery
kubectl logs -f deployment/comfyui
```

---

## 🔧 配置管理

### 配置文件说明

Open Gallery 的配置通过 **Kubernetes ConfigMap** 管理。

**⚠️ 重要:** ConfigMap 会**完全覆盖**镜像中的 `config.toml`，因此必须包含所有配置项。

详细的配置管理指南请参考: [CONFIG-GUIDE.md](CONFIG-GUIDE.md)

### 关键配置项

```toml
# ComfyUI 内部端点 (不要修改)
[comfyui]
url = "http://comfyui-service.default.svc.cluster.local:8188"

# 数据库配置
[database]
type = "sqlite"  # 或 "dynamodb"

# LLM API Keys (通过环境变量或 Secret 设置)
[anthropic]
api_key = ""  # 留空，使用环境变量

[openai]
api_key = ""  # 留空，使用环境变量
```

### 修改配置

```bash
# 1. 编辑 ConfigMap YAML
vim k8s-manifests/open-gallery-configmap.yaml

# 2. 应用更改
kubectl apply -f k8s-manifests/open-gallery-configmap.yaml

# 3. 重启 Pod 使配置生效
kubectl rollout restart deployment/open-gallery
```

---

## 📊 常用命令

### 查看状态

```bash
# 查看所有资源
kubectl get all

# 查看 Pods
kubectl get pods -l app=open-gallery
kubectl get pods -l app=comfyui

# 查看日志
kubectl logs -f deployment/open-gallery
kubectl logs -f deployment/comfyui
```

### 扩缩容

```bash
# 手动扩展
kubectl scale deployment open-gallery --replicas=3
kubectl scale deployment comfyui --replicas=2

# 启用自动扩展
kubectl apply -f k8s-manifests/comfyui-hpa.yaml
```

### 更新部署

```bash
# 更新镜像
kubectl set image deployment/open-gallery \
    open-gallery=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/open-gallery:v2.0.0

# 重启部署
kubectl rollout restart deployment/open-gallery
kubectl rollout restart deployment/comfyui
```

---

## 🔍 故障排除

### Pod 无法启动

```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name>
kubectl get events --sort-by='.lastTimestamp'
```

### ALB 未创建

```bash
kubectl logs -n kube-system deployment/aws-load-balancer-controller
kubectl describe ingress open-gallery-ingress
```

### ComfyUI 连接失败

```bash
kubectl get svc comfyui-service
kubectl run test-pod --rm -it --image=busybox -- \
    wget -O- http://comfyui-service.default.svc.cluster.local:8188
```

### S3 挂载问题

```bash
# 检查 S3 CSI Driver Pods
kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-mountpoint-s3-csi-driver

# 检查 CSI Driver 状态
kubectl get csidriver s3.csi.aws.com

# 检查 PVC 状态
kubectl get pvc comfyui-models-pvc

# 检查 PV 状态
kubectl get pv comfyui-models-pv

# 对于 SageMaker HyperPod，检查 add-on 状态
aws eks describe-addon \
    --cluster-name your-cluster-name \
    --addon-name aws-mountpoint-s3-csi-driver \
    --region us-west-2

# 检查 Service Account 和 IRSA
kubectl get sa s3-csi-driver-sa -n kube-system -o yaml

# 测试 S3 访问
kubectl run s3-test --rm -it --image=busybox -- \
    sh -c "ls -la /mnt/s3" \
    --overrides='{"spec":{"volumes":[{"name":"s3-vol","persistentVolumeClaim":{"claimName":"comfyui-models-pvc"}}],"containers":[{"name":"s3-test","image":"busybox","volumeMounts":[{"name":"s3-vol","mountPath":"/mnt/s3"}]}]}}'
```

#### 常见 S3 CSI 问题

**问题 1: PVC 一直处于 Pending 状态**
```bash
# 检查 PVC 事件
kubectl describe pvc comfyui-models-pvc

# 常见原因:
# - S3 bucket 不存在或无权限访问
# - CSI driver 未正确安装
# - IRSA 配置错误
```

**问题 2: Pod Identity 关联错误**
```bash
# 检查 Pod Identity 关联
aws eks list-pod-identity-associations \
    --cluster-name your-cluster-name

# 查看特定关联详情
aws eks describe-pod-identity-association \
    --cluster-name your-cluster-name \
    --association-id ASSOCIATION_ID

# 如果使用 IRSA，检查 Service Account 注解
kubectl get sa s3-csi-driver-sa -n kube-system -o yaml
```

**问题 3: 挂载权限错误**
```bash
# 检查 IAM 策略是否包含必要权限
aws iam get-policy-version \
    --policy-arn arn:aws:iam::ACCOUNT:policy/ComfyUI-S3-CSI-Policy \
    --version-id v1

# 检查 IAM role 信任策略
aws iam get-role --role-name ComfyUI-S3-CSI-Role

# 对于 Pod Identity，确认信任策略包含:
# "Service": "pods.eks.amazonaws.com"

# 检查 S3 bucket 策略
aws s3api get-bucket-policy --bucket comfyui-models-bucket-687912291502
```

---

## 🧹 清理资源

```bash
# 删除所有部署
kubectl delete -f k8s-manifests/open-gallery-ingress.yaml
kubectl delete -f k8s-manifests/open-gallery-deployment.yaml
kubectl delete -f k8s-manifests/open-gallery-service.yaml
kubectl delete -f k8s-manifests/comfyui-deployment.yaml
kubectl delete -f k8s-manifests/comfyui-service.yaml

# 删除 ConfigMaps
kubectl delete -f k8s-manifests/open-gallery-configmap.yaml
kubectl delete -f k8s-manifests/comfyui-configmap.yaml

# 删除 S3 资源 (如果使用)
kubectl delete -f k8s-manifests/s3-pv-pvc.yaml

# 删除 ECR 镜像
aws ecr delete-repository --repository-name open-gallery --force
aws ecr delete-repository --repository-name comfyui-embedded --force
aws ecr delete-repository --repository-name comfyui-s3 --force
```

---



