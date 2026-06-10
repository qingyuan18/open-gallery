# Envoy Gateway 前置层（diffusers-upscale）

在不修改现有 KEDA / Karpenter / Deployment / Service 的前提下，给 `default/diffusers-upscale` 前面叠一层 Envoy Gateway，做 **LeastRequest 负载分发** + **集群级中央队列**。

## 设计

```
Client (kubectl port-forward)
   ↓ HTTP :80
Envoy Gateway pod (diffusers-lb ns)         ← 新增
   ├ LeastRequest（挑 in-flight 最少的 endpoint）
   ├ maxParallelRequests=10 (在途上限)
   └ maxPendingRequests=10 (中央队列上限，超过即 503)
   ↓
Service default/diffusers-upscale (不变)
   ↓
Pod diffusers-upscale-* (KEDA 0~10 副本，不变)
   ├ container: diffusers (FastAPI :8000)
   └ sidecar:   queue-metrics → CloudWatch QueuePending → KEDA → HPA → Karpenter
```

不动的部分：
- `deploy/k8s-manifests/diffusers-upscale-*.yaml`
- `deploy/k8s-manifests/karpenter-*.yaml`
- `deploy/k8s-manifests/diffusers-upscale-keda-scaledobject.yaml`
- `deploy/scripts/*`、`deploy/diffusers-upscale.dockerfile`

## 文件

| 文件 | 内容 |
|---|---|
| `01-install.sh` | 装 Gateway API CRDs (v1.2.1) + Envoy Gateway controller (helm) |
| `02-namespace.yaml` | 新 ns `diffusers-lb` |
| `03-gateway.yaml` | GatewayClass + Gateway + EnvoyProxy（envoyService=ClusterIP）|
| `04-httproute.yaml` | HTTPRoute + ReferenceGrant（跨 ns 引用 `default/diffusers-upscale`）|
| `05-backendtrafficpolicy.yaml` | LeastRequest + maxParallel=10 + maxPending=10 + active HC `/healthz` |
| `99-test.sh` | port-forward 到 Envoy svc 跑冒烟 / 并发压测 |

## 部署

```bash
cd deploy/envoy

# 1. 装 controller (一次性)
bash 01-install.sh

# 2. apply 业务 manifests
kubectl apply -f 02-namespace.yaml
kubectl apply -f 03-gateway.yaml
kubectl apply -f 04-httproute.yaml
kubectl apply -f 05-backendtrafficpolicy.yaml

# 3. 等 envoy data-plane pod 起来（~30s）
kubectl wait --for=condition=Programmed gateway/diffusers-gw -n diffusers-lb --timeout=180s
kubectl get pods -n diffusers-lb
```

## 测试

```bash
# 单个 /upscale (会触发 KEDA 扩第一个 pod，全冷启动 ~80s)
bash 99-test.sh

# 25 并发，观察中央队列行为
bash 99-test.sh load 25
# 预期：前 10 个 200 (在途)、接着 10 个 200 (排队后再发)、5 个 503 (overflow)
```

## 回滚

```bash
kubectl delete -f 05-backendtrafficpolicy.yaml -f 04-httproute.yaml -f 03-gateway.yaml -f 02-namespace.yaml
# 可选：删 controller
helm uninstall eg -n envoy-gateway-system
```

老入口 `default/diffusers-upscale` Service 完全没动，删除 envoy 层后立刻退回原状。

## 已知点

- Envoy 健康检查走 `/healthz`，pod 加载 pipeline 中返回 503 → 自动从 LB 池摘掉，加载完返 200 → 自动加回。
- KEDA 仍然只读 sidecar 推的 CW `QueuePending`，跟 Envoy 无关。Envoy 中央队列里排队的请求**不算 pending**（pod 还没收到），这是有意为之 — 让 KEDA 只对真实压力扩缩，避免抖动。
- 第一次请求会触发 KEDA 扩出 pod（冷启动 ~65s），跟现状一样；Envoy 在没 healthy endpoint 时会立刻返 503，需要等第一个 pod ready 再压测。
