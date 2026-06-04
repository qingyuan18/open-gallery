# SOCI Lazy Loading 基准测试镜像构建指南

基于现有 ComfyUI 镜像（~30GB）构造 50GB 测试镜像，用于测量 SOCI Lazy Loading 的 P99/P95/P90 镜像拉取延迟。

## 1. 创建测试用 Dockerfile

```bash
cat > Dockerfile.soci-bench <<'EOF'
FROM ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/comfyui-s3:latest

# 填充 ~20GB 不可压缩随机数据（分 4 层，模拟真实镜像的多层结构）
RUN dd if=/dev/urandom of=/tmp/pad1.bin bs=1M count=5120
RUN dd if=/dev/urandom of=/tmp/pad2.bin bs=1M count=5120
RUN dd if=/dev/urandom of=/tmp/pad3.bin bs=1M count=5120
RUN dd if=/dev/urandom of=/tmp/pad4.bin bs=1M count=5120
EOF
```

> 使用 `/dev/urandom` 确保数据不可压缩，镜像实际拉取体积 ≈ 50GB。

## 2. 构建镜像

```bash
export AWS_ACCOUNT_ID=<your-account-id>
export AWS_REGION=us-west-2
export ECR_REGISTRY=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
export IMAGE_NAME=comfyui-s3-bench
export IMAGE_TAG=50g

# 替换 Dockerfile 中的变量
envsubst '${AWS_ACCOUNT_ID} ${AWS_REGION}' < Dockerfile.soci-bench > Dockerfile.soci-bench.resolved

# 构建（预留足够磁盘空间，构建过程需 ~80GB）
docker build -f Dockerfile.soci-bench.resolved -t ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} .
```

## 3. 推送至 ECR

```bash
# 创建 ECR 仓库（如不存在）
aws ecr create-repository --repository-name ${IMAGE_NAME} --region ${AWS_REGION} || true

# 登录 ECR
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin ${ECR_REGISTRY}

# 推送镜像
docker push ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
```

## 4. 创建 SOCI 索引

```bash
# 为 50GB 镜像创建 SOCI Index
soci create ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}

# 推送 SOCI Index 至同一 ECR 仓库
soci push --ref ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
```

## 5. 部署测试

修改 ComfyUI Deployment 镜像指向测试镜像，观察拉取延迟：

```bash
# 切换镜像
kubectl set image deployment/comfyui \
  comfyui=${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}

# 观察 Pod 启动事件，记录镜像拉取耗时
kubectl get pods -l app=comfyui -w
kubectl describe pod -l app=comfyui | grep -A10 "Events"
```

## 6. 清理

```bash
# 恢复原始镜像
kubectl set image deployment/comfyui \
  comfyui=${ECR_REGISTRY}/comfyui-s3:latest

# 删除测试镜像和仓库
aws ecr delete-repository --repository-name ${IMAGE_NAME} --force --region ${AWS_REGION}
```
