# Open Gallery + ComfyUI AWS EKS 部署指南

本目录包含在 AWS EKS 上部署 Open Gallery 和 ComfyUI 的完整配置和脚本。

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





## � 部署顺序小结

完整的部署流程如下：

```bash
cd deploy

# 0) 安装/验证 AWS Load Balancer Controller（使用 Pod Identity）
# 参考下文 "附录：安装 AWS Load Balancer Controller" 章节

# 1) 安装 S3 CSI Driver（用于挂载 S3 bucket）
./scripts/setup-s3-csi.sh \
    --cluster-name <cluster-name> \
    --bucket comfyui-models-bucket-687912291502 \
    --use-pod-identity

./scripts/setup-s3-csi.sh \
    --cluster-name <cluster-name> \
    --bucket open-gallery-files-bucket-687912291502 \
    --use-pod-identity

# 2) 配置 Open Gallery Pod Identity（用于 DynamoDB/S3/Bedrock 访问）⭐ 新增
./scripts/setup-open-gallery-pod-identity.sh \
    --cluster-name <cluster-name> \
    --region us-west-2

# 3) 为节点打标签（重要！）
# GPU 节点
kubectl get nodes -o json | jq -r '.items[] | select(.metadata.labels."node.kubernetes.io/instance-type" | test("ml\\.g6e|ml\\.g5|g5\\.|g6e\\.")) | .metadata.name' | xargs -I {} kubectl label nodes {} workload=gpu --overwrite

# CPU 节点
kubectl get nodes -o json | jq -r '.items[] | select(.metadata.labels."node.kubernetes.io/instance-type" | test("ml\\.g6e|ml\\.g5|g5\\.|g6e\\.") | not) | .metadata.name' | xargs -I {} kubectl label nodes {} workload=cpu --overwrite

# 验证标签
kubectl get nodes -L workload


    # 3.4) 构建并推送 DaemonSet 预热镜像（AWS CLI + boto3）
    ./scripts/build-and-push.sh --app daemonset-s3-sync
    # DaemonSet 镜像使用 latest 标签；已在 YAML 中设置 imagePullPolicy: Always 以强制拉取最新镜像

    # 3.5) 关联 NVMe 预热 DaemonSet 的 Pod Identity 并部署（AWS CLI）
    export CLUSTER_NAME=hp-eks-03

    # 查找现有 S3 CSI 的 Role ARN（优先 EKS Pod Identity 的 describe，其次 IRSA 注解）
    export S3_CSI_NS=kube-system
    export S3_CSI_SA=s3-csi-driver-sa
    export S3_CSI_ASSOC_ID=$(aws eks list-pod-identity-associations \
        --cluster-name $CLUSTER_NAME \
        --namespace $S3_CSI_NS \
        --service-account $S3_CSI_SA \
        --query 'associations[0].associationId' \
        --output text 2>/dev/null || true)
    if [ -n "$S3_CSI_ASSOC_ID" ] && [ "$S3_CSI_ASSOC_ID" != "None" ]; then
      export S3_CSI_ROLE_ARN=$(aws eks describe-pod-identity-association \
          --cluster-name $CLUSTER_NAME \
          --association-id $S3_CSI_ASSOC_ID \
          --query 'association.roleArn' \
          --output text 2>/dev/null || true)
    fi
    if [ -z "$S3_CSI_ROLE_ARN" ] || [ "$S3_CSI_ROLE_ARN" = "None" ]; then
      S3_CSI_ROLE_ARN=$(kubectl -n $S3_CSI_NS get sa $S3_CSI_SA -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}' 2>/dev/null || true)
    fi
    echo "S3_CSI_ROLE_ARN=$S3_CSI_ROLE_ARN"

    # 先关联 default/comfyui-prewarm-sa 到该 Role（可复用同一 Role）
    aws eks create-pod-identity-association \
        --cluster-name $CLUSTER_NAME \
        --namespace default \
        --service-account comfyui-prewarm-sa \
        --role-arn $S3_CSI_ROLE_ARN

    # 重新部署（若存在旧版本先删除）
    export AWS_REGION=${AWS_REGION:-us-west-2}
    export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    envsubst '${AWS_ACCOUNT_ID} ${AWS_REGION}' < k8s-manifests/comfyui-nvme-prewarm-daemonset.yaml | kubectl delete -f - --ignore-not-found
    envsubst '${AWS_ACCOUNT_ID} ${AWS_REGION}' < k8s-manifests/comfyui-nvme-prewarm-daemonset.yaml | kubectl apply  -f -

    # 检查 DaemonSet 与日志（每个 workload=gpu 节点应有 1 个 Pod）
    kubectl -n default get ds,pods -l app=comfyui-nvme-prewarm
    kubectl logs -l app=comfyui-nvme-prewarm -f --all-containers

# 4) 应用 PV/PVC（模型 + 文件）
kubectl apply -f k8s-manifests/s3-pv-pvc.yaml                     # ComfyUI 模型（只读）
kubectl apply -f k8s-manifests/open-gallery-files-pv-pvc.yaml     # Open Gallery 文件（读写）

# 5) 构建与部署
./scripts/build-and-push.sh --app comfyui-s3
./scripts/build-and-push.sh --app open-gallery
./scripts/deploy-to-eks.sh

# 6) 获取 ALB 地址
kubectl get ingress open-gallery-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' && echo
```

## 启用 S3 CSI 缓存（emptyDir + metadata-ttl 20s）

说明：已在 `k8s-manifests/s3-pv-pvc.yaml` 与 `k8s-manifests/open-gallery-files-pv-pvc.yaml` 中启用 emptyDir 本地缓存并设置 metadata-ttl 为 20 秒（同时为 emptyDir 设置大小上限）。对已部署与未部署环境均可按以下“删除并重建 PV/PVC”的通用步骤生效：

```bash
# 1) 暂停依赖这些 PVC 的工作负载（可选，如果已部署）
kubectl scale deployment/comfyui --replicas=0 || true
kubectl scale deployment/open-gallery --replicas=0 || true

# 2) 删除旧的 PV/PVC（不会影响 S3 中的数据）
kubectl delete -f k8s-manifests/s3-pv-pvc.yaml --ignore-not-found
kubectl delete -f k8s-manifests/open-gallery-files-pv-pvc.yaml --ignore-not-found

# 3) 重新创建 PV/PVC（包含缓存配置）
kubectl apply -f k8s-manifests/s3-pv-pvc.yaml
kubectl apply -f k8s-manifests/open-gallery-files-pv-pvc.yaml

# 4) 等待 PVC 绑定
echo 'Waiting 5s for PVC to bind...' && sleep 5
kubectl get pvc

# 5) 重新拉起工作负载（如果此前有部署）
kubectl rollout restart deployment/comfyui || true
kubectl rollout restart deployment/open-gallery || true
```

注意：
- emptyDir 缓存是节点本地的临时空间，Pod 迁移到其他节点时缓存会重建；
- 如需更大/持久/高 IOPS 缓存，可参考 Mountpoint CSI Driver 仓库的 docs/CACHING.md 中的 ephemeral（EBS/本地 NVMe）方案。



**权限分离**

| ServiceAccount | 用途 | 权限范围 |
|---------------|------|---------|
| `s3-csi-driver-sa` | S3 CSI Driver | 挂载 S3 bucket |
| `open-gallery-sa` | Open Gallery App | DynamoDB + S3 + Bedrock |
| `aws-load-balancer-controller` | ALB Controller | 创建/管理 ALB |


## �🔍 故障排除

### Pod 无法启动

```bash
# 查看 Pod 详细信息
kubectl describe pod <pod-name>

# 查看 Pod 日志
kubectl logs <pod-name>

# comfyui Pod检查
POD_NAME=$(kubectl get pods  -l app=comfyui -o jsonpath='{.items[0].metadata.name}') 
kubectl port-forward  $POD_NAME 8188:8188

# 查看集群事件
kubectl get events --sort-by='.lastTimestamp'

# 常见问题 1: 节点选择器不匹配
# 错误信息: "0/2 nodes are available: 2 node(s) didn't match Pod's node affinity/selector"
# 解决方案: 为节点打标签
kubectl get nodes -L workload  # 检查标签
kubectl label nodes <node-name> workload=gpu --overwrite  # GPU 节点
kubectl label nodes <node-name> workload=cpu --overwrite  # CPU 节点

# 常见问题 2: PVC 不存在
# 错误信息: "persistentvolumeclaim "xxx-pvc" not found"
# 解决方案: 创建 PVC
kubectl apply -f k8s-manifests/s3-pv-pvc.yaml
kubectl apply -f k8s-manifests/open-gallery-files-pv-pvc.yaml
```

### DaemonSet 日志排查
```bash
kubectl -n default logs -l app=comfyui-nvme-prewarm --tail=50 --all-containers
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

### DynamoDB 访问问题

#### 问题 1: "Unable to locate credentials"

**错误日志：**
```
Error creating DynamoDB tables: Unable to locate credentials
Error initializing DynamoDB: Unable to locate credentials
```

**原因：** Pod 没有 AWS 凭证访问 DynamoDB

**解决方案：**

```bash
# 1. 检查 ServiceAccount 是否存在
kubectl get sa open-gallery-sa -n default

# 2. 检查 Pod 是否使用了正确的 ServiceAccount
kubectl get pod -l app=open-gallery -o yaml | grep serviceAccountName

# 3. 检查 Pod Identity Association
aws eks list-pod-identity-associations \
    --cluster-name hp-eks-03 \
    --namespace default \
    --service-account open-gallery-sa

# 4. 如果 Association 不存在，重新运行设置脚本
cd deploy
./scripts/setup-open-gallery-pod-identity.sh \
    --cluster-name your-cluster-name \
    --region us-west-2

# 5. 重启 Pod 使配置生效
kubectl rollout restart deployment/open-gallery
```

#### 问题 2: ConfigMap 未挂载或路径错误

**错误日志：**
```
Config file not found or invalid, using defaults: [Errno 2] No such file or directory: '/app/server/user_data/config.toml'
```

**原因：** ConfigMap 挂载路径不正确

**解决方案：**

```bash
# 1. 检查 ConfigMap 是否存在
kubectl get configmap open-gallery-config -n default

# 2. 检查 Pod 的 Volume 挂载
kubectl get pod -l app=open-gallery -o yaml | grep -A 10 volumeMounts

# 3. 进入 Pod 检查文件是否存在
POD=$(kubectl get pods -l app=open-gallery -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it $POD -- ls -la /app/server/user_data/

# 4. 如果文件不存在，检查 deployment 配置
kubectl get deployment open-gallery -o yaml | grep -A 5 volumeMounts

# 预期挂载路径应该是: /app/server/user_data (不是 /app/user_data)
```

#### 问题 3: DynamoDB 权限不足

**错误日志：**
```
AccessDeniedException: User is not authorized to perform: dynamodb:CreateTable
```

**解决方案：**

```bash
# 1. 检查 IAM Policy 是否包含必要权限
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws iam get-policy-version \
    --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/OpenGalleryAppPolicy \
    --version-id v1

# 2. 检查 Policy 是否附加到 Role
aws iam list-attached-role-policies --role-name OpenGalleryAppRole

# 3. 如果权限不足，更新 Policy
aws iam create-policy-version \
    --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/OpenGalleryAppPolicy \
    --policy-document file://k8s-manifests/open-gallery-iam-policy.json \
    --set-as-default
```

#### 问题 4: 测试 DynamoDB 访问

```bash
# 进入 Pod 测试 DynamoDB 连接
POD=$(kubectl get pods -l app=open-gallery -o jsonpath='{.items[0].metadata.name}')

# 测试 AWS 凭证是否注入
kubectl exec -it $POD -- env | grep AWS

# 测试 DynamoDB 访问
kubectl exec -it $POD -- python3 -c "
import boto3
client = boto3.client('dynamodb', region_name='us-west-2')
print('DynamoDB Tables:', client.list_tables())
"

# 测试创建表（如果没有权限会报错）
kubectl exec -it $POD -- python3 -c "
import boto3
client = boto3.client('dynamodb', region_name='us-west-2')
try:
    response = client.describe_table(TableName='jaaz-users')
    print('Table exists:', response['Table']['TableName'])
except client.exceptions.ResourceNotFoundException:
    print('Table does not exist yet (will be created on first run)')
except Exception as e:
    print('Error:', e)
"
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

# 检查 Service Account
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
```

**问题 2: Pod Identity 关联错误**
```bash
# 检查 Pod Identity 关联
aws eks list-pod-identity-associations \
    --cluster-name hp-eks-03

# 查看特定关联详情
aws eks describe-pod-identity-association \
    --cluster-name your-cluster-name \
    --association-id ASSOCIATION_ID


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

# 删除 S3 PV/PVC
kubectl delete -f k8s-manifests/s3-pv-pvc.yaml

# 删除 ECR 镜像
aws ecr delete-repository --repository-name open-gallery --force
aws ecr delete-repository --repository-name comfyui-s3 --force
```

---




---


## 附录：🔧 安装 AWS Load Balancer Controller（ALB Ingress）

Ingress 使用 AWS Load Balancer Controller 在 EC2 中创建真实的 ALB。若集群尚未安装，请按以下步骤安装。

### 完整安装步骤（使用 Pod Identity）

```bash
# 设置环境变量（根据实际情况修改）
export CLUSTER_NAME=hp-eks-03
export AWS_REGION=us-west-2
export VPC_ID=vpc-0f42e65b0eb5be613
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# ========== 步骤 1: 添加 Helm 仓库 ==========
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# ========== 步骤 2: 创建 IAM Policy ==========
# 下载官方 IAM Policy 文档
curl -o /tmp/alb-iam-policy.json \
  https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.7.0/docs/install/iam_policy.json

# 创建 IAM Policy（如果已存在会报错，可忽略）
aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file:///tmp/alb-iam-policy.json \
  --description "IAM policy for AWS Load Balancer Controller"

# 验证 Policy 已创建
aws iam get-policy \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy

# ========== 步骤 3: 创建 IAM Role（用于 Pod Identity）==========
ROLE_NAME=AWSLoadBalancerControllerRole

# 创建 Trust Policy（允许 EKS Pod Identity 服务假设此角色）
cat > /tmp/alb-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "pods.eks.amazonaws.com"},
    "Action": ["sts:AssumeRole", "sts:TagSession"]
  }]
}
EOF

# 创建 IAM Role
aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document file:///tmp/alb-trust-policy.json \
  --description "IAM role for AWS Load Balancer Controller Pod Identity"

# 附加 Policy 到 Role
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy

# 验证 Role 已创建
aws iam get-role --role-name $ROLE_NAME

# ========== 步骤 4: 使用 Helm 安装 ALB Controller ==========
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=$CLUSTER_NAME \
  --set region=$AWS_REGION \
  --set vpcId=$VPC_ID \
  --set serviceAccount.create=true \
  --set serviceAccount.name=aws-load-balancer-controller

# 等待 Deployment 就绪
kubectl -n kube-system rollout status deployment/aws-load-balancer-controller --timeout=300s

# ========== 步骤 5: 创建 Pod Identity Association ==========
# 将 Kubernetes ServiceAccount 关联到 IAM Role
aws eks create-pod-identity-association \
  --cluster-name $CLUSTER_NAME \
  --namespace kube-system \
  --service-account aws-load-balancer-controller \
  --role-arn arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}

# ========== 步骤 6: 验证安装 ==========
# 检查 Deployment
kubectl get deployment -n kube-system aws-load-balancer-controller

# 检查 Pods（应该有 2 个 Running）
kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller

# 检查 ServiceAccount
kubectl get sa -n kube-system aws-load-balancer-controller

# 检查 Pod Identity Association
aws eks list-pod-identity-associations \
  --cluster-name $CLUSTER_NAME \
  --namespace kube-system \
  --service-account aws-load-balancer-controller

# 查看 Controller 日志（确认没有凭证错误）
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller --tail=50
```

### 验证 ALB Controller 是否正常工作

```bash
# 1. 检查 Controller 状态
kubectl get deployment -n kube-system aws-load-balancer-controller

# 预期输出：
# NAME                           READY   UP-TO-DATE   AVAILABLE   AGE
# aws-load-balancer-controller   2/2     2            2           5m

# 2. 检查 Pod 日志，确认没有凭证错误
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller --tail=100

# 不应该看到类似这样的错误：
# ❌ "no EC2 IMDS role found"
# ❌ "failed to refresh cached credentials"

# 3. 部署测试 Ingress 以触发 ALB 创建（二选一）
# 方式 A：使用部署脚本（推荐，包含 IngressClass/Ingress）
cd deploy && ./scripts/deploy-to-eks.sh --skip-comfyui --yes

# 方式 B：手动应用 IngressClass、Service 与 Ingress
cd deploy/k8s-manifests
kubectl apply -f open-gallery-service.yaml
kubectl apply -f alb-ingress-class.yaml
kubectl apply -f open-gallery-ingress.yaml

# 4. 检查 Ingress 与 ALB
kubectl get ingress -A

# ADDRESS 列应该显示 ALB 的 DNS 名称（需要等待 2-3 分钟）
# 例如: k8s-default-opengall-xxxxxxxxxx.us-west-2.elb.amazonaws.com

# 4. 在 AWS 控制台验证
# EC2 > Load Balancers > 应该能看到新创建的 ALB
```

### 常见问题排查

#### 问题 1: "no EC2 IMDS role found" 错误

**原因**: Pod Identity Association 未创建或未生效

**解决方案**:
```bash
# 检查 Pod Identity Association 是否存在
aws eks list-pod-identity-associations \
  --cluster-name $CLUSTER_NAME \
  --namespace kube-system

# 如果不存在，重新创建
aws eks create-pod-identity-association \
  --cluster-name $CLUSTER_NAME \
  --namespace kube-system \
  --service-account aws-load-balancer-controller \
  --role-arn arn:aws:iam::${ACCOUNT_ID}:role/AWSLoadBalancerControllerRole

# 重启 ALB Controller Pods
kubectl rollout restart deployment/aws-load-balancer-controller -n kube-system
```

#### 问题 2: Ingress 创建后 ADDRESS 一直为空

**原因**: ALB Controller 没有权限创建 ALB

**解决方案**:
```bash
# 1. 检查 Controller 日志
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller --tail=100

# 2. 检查 Ingress 事件
kubectl describe ingress <ingress-name> -n <namespace>

# 3. 确认 IAM Policy 已附加到 Role
aws iam list-attached-role-policies --role-name AWSLoadBalancerControllerRole
```

#### 问题 3: 重新安装 ALB Controller

如果需要完全重新安装：

```bash
# 1. 删除 Pod Identity Association
ASSOC_ID=$(aws eks list-pod-identity-associations \
  --cluster-name $CLUSTER_NAME \
  --namespace kube-system \
  --service-account aws-load-balancer-controller \
  --query 'associations[0].associationId' \
  --output text)

aws eks delete-pod-identity-association \
  --cluster-name $CLUSTER_NAME \
  --association-id $ASSOC_ID

# 2. 卸载 Helm Chart
helm uninstall aws-load-balancer-controller -n kube-system

# 3. 删除 ServiceAccount（如果存在）
kubectl delete sa aws-load-balancer-controller -n kube-system

# 4. 重新执行上面的完整安装步骤
```

---

**安装成功后**，`k8s-manifests/open-gallery-ingress.yaml` 会自动在 EC2 中创建 ALB。脚本 `scripts/deploy-to-eks.sh` 已包含 Ingress 应用和等待逻辑。

---

