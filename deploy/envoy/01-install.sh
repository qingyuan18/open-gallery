#!/usr/bin/env bash
# Install Gateway API CRDs + Envoy Gateway controller.
# Idempotent: rerun is safe.
set -euo pipefail

EG_VERSION="v1.2.1"

# Envoy Gateway helm chart bundles its own copy of the Gateway API CRDs.
# If you previously kubectl-applied the upstream CRDs, helm will conflict on
# field ownership. Adopt them into the helm release first (or remove if absent).
echo "==> Adopting Gateway API CRDs into helm if present"
for crd in gatewayclasses.gateway.networking.k8s.io \
           gateways.gateway.networking.k8s.io \
           grpcroutes.gateway.networking.k8s.io \
           httproutes.gateway.networking.k8s.io \
           referencegrants.gateway.networking.k8s.io; do
  if kubectl get crd "$crd" >/dev/null 2>&1; then
    kubectl annotate --overwrite crd "$crd" \
      meta.helm.sh/release-name=eg \
      meta.helm.sh/release-namespace=envoy-gateway-system >/dev/null
    kubectl label --overwrite crd "$crd" \
      app.kubernetes.io/managed-by=Helm >/dev/null
  fi
done

echo "==> Installing Envoy Gateway controller ($EG_VERSION)"
helm upgrade --install eg \
  oci://docker.io/envoyproxy/gateway-helm \
  --version "$EG_VERSION" \
  -n envoy-gateway-system \
  --create-namespace \
  --wait --timeout 5m

echo "==> Waiting for envoy-gateway controller pods"
kubectl wait --for=condition=Available deploy/envoy-gateway -n envoy-gateway-system --timeout=180s

echo "==> Done. Controller status:"
kubectl get pods -n envoy-gateway-system
