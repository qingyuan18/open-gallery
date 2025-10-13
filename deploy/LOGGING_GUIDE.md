# ComfyUI 日志管理指南

本文档说明如何查看和管理 ComfyUI 在 Kubernetes 中的运行日志。

---

## 📋 日志配置说明

### 当前配置

ComfyUI 的启动命令已配置为同时输出日志到：
1. **标准输出 (stdout)** - 可通过 `kubectl logs` 查看
2. **日志文件** - 保存在容器内 `/tmp/comfyui-logs/comfyui_runtime.log`

**启动命令：**
```bash
mkdir -p /tmp/comfyui-logs
echo "🚀 Starting ComfyUI at $(date)" | tee /tmp/comfyui-logs/comfyui_runtime.log
python -u main.py --listen 0.0.0.0 --port 8188 2>&1 | tee -a /tmp/comfyui-logs/comfyui_runtime.log
```

**特点：**
- ✅ 同时输出到 stdout 和文件
- ✅ `kubectl logs` 仍然可用
- ✅ 可以在容器内查看完整日志文件
- ⚠️ Pod 重启后日志文件会丢失（存储在 `/tmp`）

---

## 🔍 查看日志的方法

### 方法 1: 使用 kubectl logs（推荐）

**查看实时日志：**
```bash
# Standalone 部署
kubectl logs -f -n comfyui-test -l app=comfyui-s3-test

# 完整部署
kubectl logs -f -n default -l app=comfyui
```

**查看最近 100 行：**
```bash
kubectl logs -n comfyui-test -l app=comfyui-s3-test --tail=100
```

**查看特定时间范围：**
```bash
kubectl logs -n comfyui-test -l app=comfyui-s3-test --since=1h
```

---

### 方法 2: 查看容器内日志文件

**进入容器：**
```bash
# 获取 Pod 名称
POD_NAME=$(kubectl get pods -n comfyui-test -l app=comfyui-s3-test -o jsonpath='{.items[0].metadata.name}')

# 进入容器
kubectl exec -it -n comfyui-test $POD_NAME -- bash
```

**在容器内查看日志：**
```bash
# 查看完整日志
cat /tmp/comfyui-logs/comfyui_runtime.log

# 实时查看日志
tail -f /tmp/comfyui-logs/comfyui_runtime.log

# 搜索错误
grep -i error /tmp/comfyui-logs/comfyui_runtime.log

# 查看最后 50 行
tail -n 50 /tmp/comfyui-logs/comfyui_runtime.log
```

---

### 方法 3: 复制日志文件到本地

```bash
# 复制日志文件到本地
kubectl cp comfyui-test/$POD_NAME:/tmp/comfyui-logs/comfyui_runtime.log ./comfyui_runtime.log

# 在本地查看
cat comfyui_runtime.log
```

---

## 📊 日志持久化（可选）

如果需要在 Pod 重启后保留日志，可以使用以下方案：

### 方案 1: 使用 emptyDir（临时存储）

适用于短期调试，Pod 删除后日志丢失。

```yaml
volumeMounts:
- name: logs
  mountPath: /tmp/comfyui-logs

volumes:
- name: logs
  emptyDir: {}
```

### 方案 2: 使用 PVC（持久存储）

适用于生产环境，需要长期保留日志。

**创建 PVC：**
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: comfyui-logs-pvc
  namespace: comfyui-test
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: gp3  # 使用 EBS gp3
```

**在 Deployment 中使用：**
```yaml
volumeMounts:
- name: logs
  mountPath: /tmp/comfyui-logs

volumes:
- name: logs
  persistentVolumeClaim:
    claimName: comfyui-logs-pvc
```

### 方案 3: 使用 CloudWatch Logs（AWS 推荐）

安装 Fluent Bit 或 CloudWatch Agent，自动收集容器日志到 CloudWatch。

**参考：** [AWS EKS Logging](https://docs.aws.amazon.com/eks/latest/userguide/control-plane-logs.html)

---

## 🔧 日志轮转（避免日志过大）

如果日志文件可能很大，建议添加日志轮转：

### 方法 1: 按日期命名

```bash
LOG_FILE="/tmp/comfyui-logs/comfyui_$(date +%Y%m%d_%H%M%S).log"
python -u main.py --listen 0.0.0.0 --port 8188 2>&1 | tee "$LOG_FILE"
```

### 方法 2: 使用 logrotate

在容器内安装 `logrotate` 并配置定期轮转。

### 方法 3: 限制日志文件大小

```bash
# 只保留最后 10000 行
python -u main.py --listen 0.0.0.0 --port 8188 2>&1 | \
  tee >(tail -n 10000 > /tmp/comfyui-logs/comfyui_runtime.log)
```

---

## 🐛 调试技巧

### 查找错误

```bash
# 在 kubectl logs 中查找错误
kubectl logs -n comfyui-test -l app=comfyui-s3-test | grep -i error

# 在日志文件中查找错误
kubectl exec -n comfyui-test $POD_NAME -- \
  grep -i error /tmp/comfyui-logs/comfyui_runtime.log
```

### 查看启动日志

```bash
# 查看 Pod 启动后的前 100 行
kubectl logs -n comfyui-test $POD_NAME --tail=100
```

### 查看特定时间段的日志

```bash
# 查看最近 30 分钟的日志
kubectl logs -n comfyui-test $POD_NAME --since=30m

# 查看最近 2 小时的日志
kubectl logs -n comfyui-test $POD_NAME --since=2h
```

### 监控日志大小

```bash
# 查看日志文件大小
kubectl exec -n comfyui-test $POD_NAME -- \
  du -h /tmp/comfyui-logs/comfyui_runtime.log
```

---

## 📝 常见问题

### Q1: 为什么 kubectl logs 看不到日志？

**A:** 检查以下几点：
1. 确保使用了 `tee` 命令（不是简单的 `>` 重定向）
2. 确保 Python 使用了 `-u` 参数（无缓冲输出）
3. 检查 Pod 是否正在运行：`kubectl get pods -n comfyui-test`

### Q2: 日志文件在哪里？

**A:** 日志文件位于容器内的 `/tmp/comfyui-logs/comfyui_runtime.log`

### Q3: Pod 重启后日志丢失了？

**A:** 默认配置下，日志保存在 `/tmp`（临时目录），Pod 重启后会丢失。如需持久化，请使用 PVC。

### Q4: 如何查看之前 Pod 的日志？

**A:** 使用 `--previous` 参数：
```bash
kubectl logs -n comfyui-test $POD_NAME --previous
```

### Q5: 日志文件太大怎么办？

**A:** 
1. 使用日志轮转（按日期命名）
2. 定期清理旧日志
3. 使用 CloudWatch Logs 等日志聚合服务

---

## 🎯 最佳实践

### 开发/测试环境

```bash
# 使用 kubectl logs 实时查看
kubectl logs -f -n comfyui-test -l app=comfyui-s3-test
```

**优点：**
- ✅ 简单直接
- ✅ 无需额外配置
- ✅ 适合快速调试

### 生产环境

**推荐配置：**
1. ✅ 使用 CloudWatch Logs 或 ELK Stack
2. ✅ 配置日志轮转
3. ✅ 设置日志保留策略
4. ✅ 配置告警（错误日志）

**示例：使用 Fluent Bit 发送到 CloudWatch**
```bash
# 安装 Fluent Bit
kubectl apply -f https://raw.githubusercontent.com/aws-samples/amazon-cloudwatch-container-insights/latest/k8s-deployment-manifest-templates/deployment-mode/daemonset/container-insights-monitoring/fluent-bit/fluent-bit.yaml
```

---

## 📚 相关文档

- [Kubernetes Logging Architecture](https://kubernetes.io/docs/concepts/cluster-administration/logging/)
- [AWS EKS Logging](https://docs.aws.amazon.com/eks/latest/userguide/control-plane-logs.html)
- [Fluent Bit for EKS](https://docs.fluentbit.io/manual/installation/kubernetes)

---

**版本:** 1.0.0  
**最后更新:** 2025-10-12  
**适用于:** ComfyUI S3 部署

