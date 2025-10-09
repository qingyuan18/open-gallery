# Open Gallery 配置管理指南

## ⚠️ 重要说明

在 EKS 部署中，Open Gallery 的配置通过 **Kubernetes ConfigMap** 管理。

**关键点:**
- ✅ ConfigMap 包含**完整的** `config.toml` 配置
- ⚠️ ConfigMap 会**完全覆盖**镜像中的 `config.toml`
- ❌ 如果 ConfigMap 缺少配置项，这些配置会丢失

---

## 📁 配置文件位置

### 本地开发环境
```
server/user_data/config.toml  ← 直接读取本地文件
```

### EKS 部署环境
```
Kubernetes ConfigMap → 挂载到 Pod → /app/server/user_data/config.toml
```

---

## 🔄 配置传递流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. ConfigMap (k8s-manifests/open-gallery-configmap.yaml)   │
│    包含完整的 config.toml 内容                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Kubernetes 存储到 etcd                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Pod 启动时，kubelet 挂载 ConfigMap                        │
│    volumeMounts:                                            │
│    - mountPath: /app/server/user_data/config.toml          │
│      subPath: config.toml                                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 容器内的文件系统                                           │
│    /app/server/user_data/config.toml                        │
│    ↑                                                         │
│    └─ 这个文件来自 ConfigMap，覆盖了镜像中的原文件             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. config_service.py 读取配置                                │
│    app_config = parse_toml('/app/server/user_data/config.toml') │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. 应用代码使用配置                                           │
│    comfyui.py: api_url = config_service.app_config['comfyui']['url'] │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 ConfigMap 结构

### 完整的 ConfigMap 示例

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: open-gallery-config
  namespace: default
data:
  config.toml: |
    # 必须包含所有配置项！
    
    [database]
    type = "sqlite"
    
    [database.sqlite]
    # path = "/app/server/user_data/database.db"
    
    [anthropic]
    models = { "claude-3-7-sonnet-latest" = { type = "text" } }
    url = "https://api.anthropic.com/v1/"
    api_key = ""
    max_tokens = 8192
    
    [openai]
    models = { 
        "gpt-4o" = { type = "text" }, 
        "gpt-4o-mini" = { type = "text" }
    }
    url = "https://api.openai.com/v1/"
    api_key = ""
    max_tokens = 8192
    
    [bedrock]
    models = {
        "us.anthropic.claude-3-7-sonnet-20250219-v1:0" = { type = "text" }
    }
    url = ""
    api_key = ""
    max_tokens = 8192
    region = "us-west-2"
    
    [siliconflow]
    models = {
        "deepseek-ai/DeepSeek-V3" = { type = "text" }
    }
    url = "https://api.siliconflow.cn/v1/"
    api_key = ""
    max_tokens = 8192
    
    [comfyui]
    models = {
        "flux-kontext" = { type = "comfyui", media_type = "image" },
        "qwen-image-multiple" = { type = "comfyui", media_type = "image" },
        "flux-t2i" = { type = "comfyui", media_type = "image" },
        "wan-t2v" = { type = "comfyui", media_type = "video" },
        "wan-i2v" = { type = "comfyui", media_type = "video" }
    }
    url = "http://comfyui-service.default.svc.cluster.local:8188"
    api_key = ""
```

---

## 🔧 修改配置

### 方法 1: 编辑 YAML 文件（推荐）

```bash
# 1. 编辑 ConfigMap YAML
vim k8s-manifests/open-gallery-configmap.yaml

# 2. 应用更改
kubectl apply -f k8s-manifests/open-gallery-configmap.yaml

# 3. 重启 Pod 使配置生效
kubectl rollout restart deployment/open-gallery

# 4. 验证配置
kubectl exec -it <pod-name> -- cat /app/server/user_data/config.toml
```

### 方法 2: 直接编辑 ConfigMap

```bash
# 直接编辑
kubectl edit configmap open-gallery-config

# 重启 Pod
kubectl rollout restart deployment/open-gallery
```

### 方法 3: 使用 kubectl patch

```bash
# 更新单个配置项（需要完整的 TOML 内容）
kubectl patch configmap open-gallery-config \
  --type merge \
  -p '{"data":{"config.toml":"完整的配置内容..."}}'

kubectl rollout restart deployment/open-gallery
```

---

## 🔑 API Keys 管理

### ❌ 不推荐：在 ConfigMap 中存储

```yaml
# 不安全！ConfigMap 是明文存储
[anthropic]
api_key = "sk-ant-xxxxx"  # ← 不要这样做
```

### ✅ 推荐：使用 Kubernetes Secrets

#### 步骤 1: 创建 Secret

```bash
kubectl create secret generic open-gallery-secrets \
  --from-literal=anthropic-api-key='sk-ant-xxxxx' \
  --from-literal=openai-api-key='sk-xxxxx' \
  --from-literal=siliconflow-api-key='sk-xxxxx'
```

#### 步骤 2: 在 Deployment 中引用

```yaml
# k8s-manifests/open-gallery-deployment.yaml
spec:
  containers:
  - name: open-gallery
    env:
    - name: ANTHROPIC_API_KEY
      valueFrom:
        secretKeyRef:
          name: open-gallery-secrets
          key: anthropic-api-key
    - name: OPENAI_API_KEY
      valueFrom:
        secretKeyRef:
          name: open-gallery-secrets
          key: openai-api-key
```

#### 步骤 3: ConfigMap 中留空

```toml
[anthropic]
api_key = ""  # 留空，使用环境变量 ANTHROPIC_API_KEY

[openai]
api_key = ""  # 留空，使用环境变量 OPENAI_API_KEY
```

---

## 🎯 关键配置项说明

### ComfyUI 端点

```toml
[comfyui]
url = "http://comfyui-service.default.svc.cluster.local:8188"
```

**重要:**
- ✅ 使用 Kubernetes 内部 DNS
- ✅ 格式: `http://<service-name>.<namespace>.svc.cluster.local:<port>`
- ❌ 不要使用外部 URL 或 IP 地址

### 数据库配置

```toml
[database]
type = "sqlite"  # 或 "dynamodb"

[database.sqlite]
# 默认路径，无需修改
# path = "/app/server/user_data/database.db"

[database.dynamodb]
region = "us-west-2"
```

### LLM Providers

```toml
[anthropic]
models = { "claude-3-7-sonnet-latest" = { type = "text" } }
url = "https://api.anthropic.com/v1/"
api_key = ""  # 使用环境变量
max_tokens = 8192

[bedrock]
# 使用 AWS IRSA，无需 api_key
api_key = ""
region = "us-west-2"
```

---

## 🔍 验证配置

### 检查 ConfigMap

```bash
# 查看 ConfigMap 内容
kubectl get configmap open-gallery-config -o yaml

# 查看配置文件内容
kubectl get configmap open-gallery-config -o jsonpath='{.data.config\.toml}'
```

### 检查 Pod 中的配置

```bash
# 进入 Pod
kubectl exec -it <pod-name> -- /bin/bash

# 查看配置文件
cat /app/server/user_data/config.toml

# 检查环境变量
env | grep API_KEY
```

### 检查配置是否生效

```bash
# 查看应用日志
kubectl logs -f deployment/open-gallery

# 应该看到配置加载成功的日志
# 例如: "Loaded config from /app/server/user_data/config.toml"
```

---

## 🚨 常见问题

### 问题 1: 配置更新后不生效

**原因:** Pod 没有重启

**解决:**
```bash
kubectl rollout restart deployment/open-gallery
```

### 问题 2: 部分配置丢失

**原因:** ConfigMap 不完整，缺少某些配置项

**解决:**
1. 从 `server/config_example_dynamodb.toml` 复制完整配置
2. 更新 ConfigMap
3. 重启 Pod

### 问题 3: ComfyUI 连接失败

**检查:**
```bash
# 1. 检查 ComfyUI Service
kubectl get svc comfyui-service

# 2. 检查配置中的 URL
kubectl get configmap open-gallery-config -o jsonpath='{.data.config\.toml}' | grep -A 2 "\[comfyui\]"

# 3. 测试连接
kubectl exec -it <open-gallery-pod> -- \
  curl http://comfyui-service.default.svc.cluster.local:8188
```

---

## 📚 最佳实践

### 1. 版本控制

将 ConfigMap YAML 文件纳入 Git 版本控制：

```bash
git add k8s-manifests/open-gallery-configmap.yaml
git commit -m "Update Open Gallery configuration"
```

### 2. 多环境配置

为不同环境创建不同的 ConfigMap：

```bash
# 开发环境
k8s-manifests/open-gallery-configmap-dev.yaml

# 生产环境
k8s-manifests/open-gallery-configmap-prod.yaml
```

### 3. 配置验证

部署前验证 TOML 语法：

```bash
# 使用 Python 验证
python3 -c "import toml; toml.load(open('config.toml'))"
```

### 4. 备份配置

定期备份 ConfigMap：

```bash
kubectl get configmap open-gallery-config -o yaml > backup-$(date +%Y%m%d).yaml
```

---

## 🔄 配置更新流程

```
1. 编辑配置
   ├─ vim k8s-manifests/open-gallery-configmap.yaml
   └─ 确保包含所有配置项
   
2. 验证语法
   └─ 检查 TOML 格式是否正确
   
3. 应用更改
   └─ kubectl apply -f k8s-manifests/open-gallery-configmap.yaml
   
4. 重启 Pod
   └─ kubectl rollout restart deployment/open-gallery
   
5. 验证生效
   ├─ kubectl logs -f deployment/open-gallery
   └─ kubectl exec -it <pod> -- cat /app/server/user_data/config.toml
```

---

**版本:** 1.0.0  
**最后更新:** 2025-10-09

