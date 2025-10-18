#!/usr/bin/env bash
set -euo pipefail

# Sync S3 models/files into EFS via Kubernetes Jobs that mount the EFS PVCs.
# Requirements:
# - EFS CSI installed; PVCs created: comfyui-models-pvc-efs, open-gallery-files-pvc-efs (default names)
# - A ServiceAccount with S3 read permissions (default: open-gallery-sa via Pod Identity)
# - kubectl and AWS CLI configured
#
# Usage examples:
#   ./s3-to-efs-sync.sh --region us-west-2 \
#       --models-bucket comfyui-models-bucket-123456789012 \
#       --models-prefix models/ \
#       --files-bucket open-gallery-files-bucket-123456789012
#
# Flags:
#   --region <aws-region>
#   --namespace <k8s-namespace>        (default: default)
#   --sa <service-account>              (default: open-gallery-sa)
#   --models-bucket <bucket-name>       (optional; if set will run models sync Job)
#   --models-prefix <prefix>            (default: models/)
#   --models-pvc <pvc-name>             (default: comfyui-models-pvc-efs)
#   --models-dest <path>                (default: /mnt/efs/models)
#   --files-bucket <bucket-name>        (optional; if set will run files sync Job)
#   --files-prefix <prefix>             (default: "")
#   --files-pvc <pvc-name>              (default: open-gallery-files-pvc-efs)
#   --files-dest <path>                 (default: /mnt/efs/files)
#
# This script will apply short-lived Jobs and wait for completion.

REGION=""
NAMESPACE="default"
SERVICE_ACCOUNT="open-gallery-sa"
MODELS_BUCKET=""
MODELS_PREFIX="models/"
MODELS_PVC="comfyui-models-pvc-efs"
MODELS_DEST="/mnt/efs/models"
FILES_BUCKET=""
FILES_PREFIX=""
FILES_PVC="open-gallery-files-pvc-efs"
FILES_DEST="/mnt/efs/files"

print_info() { echo -e "[INFO] $1"; }
print_err()  { echo -e "[ERROR] $1" >&2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2;;
    --namespace) NAMESPACE="$2"; shift 2;;
    --sa) SERVICE_ACCOUNT="$2"; shift 2;;
    --models-bucket) MODELS_BUCKET="$2"; shift 2;;
    --models-prefix) MODELS_PREFIX="$2"; shift 2;;
    --models-pvc) MODELS_PVC="$2"; shift 2;;
    --models-dest) MODELS_DEST="$2"; shift 2;;
    --files-bucket) FILES_BUCKET="$2"; shift 2;;
    --files-prefix) FILES_PREFIX="$2"; shift 2;;
    --files-pvc) FILES_PVC="$2"; shift 2;;
    --files-dest) FILES_DEST="$2"; shift 2;;
    *) print_err "Unknown argument: $1"; exit 1;;
  esac
done

if [[ -z "$REGION" ]]; then
  print_err "--region is required"
  exit 1
fi

run_job() {
  local NAME="$1"; shift
  local PVC="$1"; shift
  local SRC="$1"; shift
  local DEST="$1"; shift

  print_info "Applying sync job: ${NAME} (PVC=${PVC})"
  cat <<EOF | kubectl apply -n "$NAMESPACE" -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: ${NAME}
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: ${SERVICE_ACCOUNT}
      containers:
      - name: aws-cli
        image: public.ecr.aws/aws-cli/aws-cli:2.15.35
        imagePullPolicy: IfNotPresent
        env:
        - name: AWS_REGION
          value: ${REGION}
        command: ["/bin/sh","-lc"]
        args:
        - |
          set -euo pipefail
          echo "Syncing from ${SRC} to ${DEST}"
          mkdir -p ${DEST}
          aws s3 sync "${SRC}" "${DEST}" --region "${REGION}" --delete
        volumeMounts:
        - name: efs
          mountPath: /mnt/efs
      volumes:
      - name: efs
        persistentVolumeClaim:
          claimName: ${PVC}
EOF

  print_info "Waiting for job/${NAME} to complete..."
  kubectl wait --for=condition=complete job/${NAME} -n "$NAMESPACE" --timeout=3600s
  print_info "Job ${NAME} completed. Cleaning up..."
  kubectl delete job/${NAME} -n "$NAMESPACE" --ignore-not-found
}

# Run models sync if bucket provided
if [[ -n "$MODELS_BUCKET" ]]; then
  run_job "sync-models-to-efs" "$MODELS_PVC" "s3://${MODELS_BUCKET}/${MODELS_PREFIX}" "$MODELS_DEST"
else
  print_info "Skipping models sync (no --models-bucket provided)"
fi

# Run files sync if bucket provided
if [[ -n "$FILES_BUCKET" ]]; then
  run_job "sync-files-to-efs" "$FILES_PVC" "s3://${FILES_BUCKET}/${FILES_PREFIX}" "$FILES_DEST"
else
  print_info "Skipping files sync (no --files-bucket provided)"
fi

print_info "All requested sync jobs finished."

