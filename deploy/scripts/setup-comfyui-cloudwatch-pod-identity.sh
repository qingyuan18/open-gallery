#!/bin/bash

#############################################################################
# Setup ComfyUI CloudWatch Pod Identity for EKS
# - Grants the comfyui ServiceAccount permission to PutMetricData (CloudWatch)
# - Creates EKS Pod Identity association for comfyui-sa
#
# Prerequisites:
# - AWS CLI and kubectl installed and configured
# - EKS cluster with Pod Identity enabled (EKS >= 1.24)
#
# Usage:
#   ./setup-comfyui-cloudwatch-pod-identity.sh --cluster-name <name> [--region us-west-2]
#############################################################################

set -euo pipefail

AWS_REGION="us-west-2"
CLUSTER_NAME=""
NAMESPACE="default"
SERVICE_ACCOUNT_NAME="comfyui-sa"
IAM_ROLE_NAME="ComfyUICloudWatchRole"
IAM_POLICY_NAME="ComfyUICloudWatchPutMetricPolicy"

print() { echo "[INFO] $*"; }
error() { echo "[ERROR] $*" >&2; }

usage() {
  cat <<EOF
Usage: $0 --cluster-name <name> [--region <region>]

Creates IAM policy+role for CloudWatch PutMetricData and associates it to SA ${SERVICE_ACCOUNT_NAME} via EKS Pod Identity.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster-name) CLUSTER_NAME="$2"; shift 2;;
    --region) AWS_REGION="$2"; shift 2;;
    --help|-h) usage; exit 0;;
    *) error "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$CLUSTER_NAME" ]]; then
  error "--cluster-name is required"
  usage
  exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${IAM_POLICY_NAME}"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${IAM_ROLE_NAME}"

print "Account: $ACCOUNT_ID, Region: $AWS_REGION, Cluster: $CLUSTER_NAME"

# 1) Ensure ServiceAccount exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_DIR="${SCRIPT_DIR}/../k8s-manifests"

kubectl apply -f "${MANIFEST_DIR}/comfyui-serviceaccount.yaml"

# 2) Create/Update IAM Policy (PutMetricData for namespace ComfyUI)
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
  print "IAM policy exists: $POLICY_ARN (updating default version)"
  aws iam create-policy-version \
    --policy-arn "$POLICY_ARN" \
    --policy-document file://"${MANIFEST_DIR}/comfyui-cloudwatch-iam-policy.json" \
    --set-as-default >/dev/null
else
  print "Creating IAM policy: $IAM_POLICY_NAME"
  aws iam create-policy \
    --policy-name "$IAM_POLICY_NAME" \
    --policy-document file://"${MANIFEST_DIR}/comfyui-cloudwatch-iam-policy.json" \
    --description "Allow ComfyUI sidecar to PutMetricData into CloudWatch" >/dev/null
fi

# 3) Create or update IAM Role for Pod Identity
TRUST_JSON=$(cat <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "pods.eks.amazonaws.com"},
      "Action": ["sts:AssumeRole", "sts:TagSession"]
    }
  ]
}
JSON
)

if aws iam get-role --role-name "$IAM_ROLE_NAME" >/dev/null 2>&1; then
  print "IAM role exists: $ROLE_ARN (updating trust policy and attaching policy)"
  aws iam update-assume-role-policy \
    --role-name "$IAM_ROLE_NAME" \
    --policy-document "$TRUST_JSON" >/dev/null
else
  print "Creating IAM role: $IAM_ROLE_NAME"
  aws iam create-role \
    --role-name "$IAM_ROLE_NAME" \
    --assume-role-policy-document "$TRUST_JSON" \
    --description "Role for comfyui-sa to write CloudWatch custom metrics" >/dev/null
fi

# Attach policy to role (idempotent)
aws iam attach-role-policy \
  --role-name "$IAM_ROLE_NAME" \
  --policy-arn "$POLICY_ARN" >/dev/null 2>&1 || true

# 4) Create Pod Identity association
# Delete existing association(s) first for idempotency
ASSOC_IDS=$(aws eks list-pod-identity-associations \
  --cluster-name "$CLUSTER_NAME" \
  --namespace "$NAMESPACE" \
  --service-account "$SERVICE_ACCOUNT_NAME" \
  --region "$AWS_REGION" \
  --query 'associations[*].associationId' \
  --output text 2>/dev/null || true)
if [[ -n "$ASSOC_IDS" && "$ASSOC_IDS" != "None" ]]; then
  for AID in $ASSOC_IDS; do
    print "Deleting existing association: $AID"
    aws eks delete-pod-identity-association \
      --cluster-name "$CLUSTER_NAME" \
      --association-id "$AID" \
      --region "$AWS_REGION" >/dev/null
  done
fi

print "Creating Pod Identity association for SA ${SERVICE_ACCOUNT_NAME} -> ${ROLE_ARN}"
aws eks create-pod-identity-association \
  --cluster-name "$CLUSTER_NAME" \
  --namespace "$NAMESPACE" \
  --service-account "$SERVICE_ACCOUNT_NAME" \
  --role-arn "$ROLE_ARN" \
  --region "$AWS_REGION" >/dev/null

print "Done. Verify with: aws eks list-pod-identity-associations --cluster-name $CLUSTER_NAME --namespace $NAMESPACE --service-account $SERVICE_ACCOUNT_NAME --region $AWS_REGION"

