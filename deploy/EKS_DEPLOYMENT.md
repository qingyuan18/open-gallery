# Open Gallery + ComfyUI AWS EKS 部署指南

本目录包含在 AWS EKS 上部署 Open Gallery 和 ComfyUI 的完整配置和脚本。

---

## 📋 目录结构

```
deploy/
├── EKS_DEPLOYMENT.md                      # 本文档 (部署指南)
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
│   ├── comfyui-service.yaml               # ComfyUI 服务 (内部)
│   ├── comfyui-configmap.yaml             # ComfyUI 配置
│   ├── comfyui-hpa.yaml                   # 自动扩展配置
│   │
│   ├── s3-pv-pvc.yaml                     # S3 持久卷配置
│   └── s3-csi-policy.json                 # S3 CSI IAM 策略
│
└── scripts/                               # 部署脚本
    ├── build-and-push.sh                  # 构建和推送镜像
    ├── deploy-to-eks.sh                   # 部署到 EKS
    ├── setup-s3-csi.sh                    # S3 CSI 设置 (可选)
    └── upload-models-to-s3.sh             # 上传模型到 S3 (可选)
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
# 1. 在 EKS 控制台安装 S3 CSI Driver
# 导航到: EKS Console → Clusters → [Your Cluster] → Add-ons → Get more add-ons
# 选择: Mountpoint for Amazon S3 CSI Driver
# 或使用 AWS CLI:
aws eks create-addon \
    --cluster-name your-cluster-name \
    --addon-name aws-mountpoint-s3-csi-driver \
    --region us-west-2

# 2. 创建 S3 Bucket 并上传模型
aws s3 mb s3://your-comfyui-models-bucket
./scripts/upload-models-to-s3.sh -i

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

#### 在 EKS 控制台安装 S3 CSI Driver

1. 打开 AWS EKS 控制台
2. 选择你的集群
3. 点击 "Add-ons" 标签
4. 点击 "Get more add-ons"
5. 选择 "Mountpoint for Amazon S3 CSI Driver"
6. 点击 "Next" → "Create"

或使用 AWS CLI:

```bash
aws eks create-addon \
    --cluster-name your-cluster-name \
    --addon-name aws-mountpoint-s3-csi-driver \
    --region us-west-2
```

#### 配置 IAM 和上传模型

```bash
# 创建 IAM 策略
aws iam create-policy \
    --policy-name ComfyUI-S3-CSI-Policy \
    --policy-document file://k8s-manifests/s3-csi-policy.json

# 为 Service Account 创建 IAM Role
eksctl create iamserviceaccount \
    --name comfyui-s3-sa \
    --namespace default \
    --cluster your-cluster-name \
    --attach-policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/ComfyUI-S3-CSI-Policy \
    --approve

# 上传模型到 S3
./scripts/upload-models-to-s3.sh -i
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
# 检查 S3 CSI Driver
kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-mountpoint-s3-csi-driver

# 检查 PVC 状态
kubectl get pvc comfyui-models-pvc

# 检查 PV 状态
kubectl get pv comfyui-models-pv
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

## 📚 相关文档

- **[CONFIG-GUIDE.md](CONFIG-GUIDE.md)** - 配置管理详细指南
  - 配置传递流程
  - ConfigMap 完整示例
  - API Keys 管理
  - 常见问题解决

---

## 🔐 安全最佳实践

1. **使用 Secrets 存储敏感信息** - API Keys 不要放在 ConfigMap
2. **启用 HTTPS** - 在 Ingress 中配置 ACM 证书
3. **网络策略** - 限制 Pod 间通信
4. **IRSA** - 使用 IAM Roles for Service Accounts
5. **镜像扫描** - 启用 ECR 镜像扫描

---

**版本:** 2.0.0  
**状态:** 生产就绪  
**最后更新:** 2025-10-09

