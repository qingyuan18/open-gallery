#!/bin/bash
# Build a new AMI based on EKS AL2023 NVIDIA, pre-pulling comfyui-s3-flux:latest
# (which already has Flux models baked into the image) into containerd's
# k8s.io namespace.
#
# Result: a node booted from this AMI has the full ComfyUI image (with Flux
# models) cached locally — no S3 downloads, no NVMe seed copy at boot. The
# pod just mounts an emptyDir or uses /opt/program/models directly inside
# the container.
#
# Source AMI: ami-06c3bbfab4ca9568d  (EKS AL2023 NVIDIA 1.31, 80GiB)
# Output:     ami-XXXX                (~80GiB root, image cached in containerd)
#
# Usage:
#   ./build-flux-image-baked-ami.sh
#
# Prereqs:
#   - comfyui-s3-flux:latest already pushed to ECR
#   - Node IAM profile (passed via IAM_INSTANCE_PROFILE) has ECR pull + SSM
#   - Subnet/SG allow SSM Session Manager (preferred) — public IP via NAT or IGW

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
SOURCE_AMI="${SOURCE_AMI:-ami-06c3bbfab4ca9568d}"
INSTANCE_TYPE="${INSTANCE_TYPE:-c6i.4xlarge}"     # bigger box: faster ECR pull
SUBNET_ID="${SUBNET_ID:-subnet-0be0720f7d356cfe8}" # public subnet (auto IP) in us-east-1b
SG_ID="${SG_ID:-sg-0176fe82167b34c56}"
IAM_INSTANCE_PROFILE="${IAM_INSTANCE_PROFILE:-hp-eks_4377973228388927294}"  # KarpenterNodeRole-hp-eks profile
ROOT_VOLUME_GIB="${ROOT_VOLUME_GIB:-130}"          # large enough to hold the ~39GiB image cache
ROOT_VOLUME_IOPS="${ROOT_VOLUME_IOPS:-6000}"
ROOT_VOLUME_THROUGHPUT_MBPS="${ROOT_VOLUME_THROUGHPUT_MBPS:-500}"
IMAGE_REPO="${IMAGE_REPO:-comfyui-s3-flux}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
NEW_AMI_NAME="${NEW_AMI_NAME:-comfyui-s3-flux-image-baked-al2023-nvidia-1.31-$(date +%Y%m%d-%H%M)}"

ACCT=$(aws sts get-caller-identity --query Account --output text)
ECR_HOST="${ACCT}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_HOST}/${IMAGE_REPO}:${IMAGE_TAG}"

echo "[build-ami] Region=$AWS_REGION Source=$SOURCE_AMI"
echo "[build-ami] Image=$IMAGE_URI"
echo "[build-ami] Output=$NEW_AMI_NAME"

# 1. Launch the bake instance. userData logs into ECR and pre-pulls the image
# into containerd's k8s.io namespace. We touch /opt/.image-pulled when done.
USER_DATA=$(cat <<EOF
#!/bin/bash
set -euxo pipefail
# Make sure containerd is up (it is on the EKS AMI but not started by default).
systemctl start containerd

# Authenticate to ECR
TOKEN=\$(aws ecr get-login-password --region $AWS_REGION)

# Pre-pull into the k8s.io namespace so kubelet sees it as already present.
ctr -n k8s.io images pull \\
    --user "AWS:\$TOKEN" \\
    "$IMAGE_URI"

# Verify
ctr -n k8s.io images ls | grep -F "$IMAGE_URI"

# Marker for the bake watcher
touch /opt/.image-pulled
EOF
)

INSTANCE_ID=$(aws ec2 run-instances \
  --region "$AWS_REGION" \
  --image-id "$SOURCE_AMI" \
  --instance-type "$INSTANCE_TYPE" \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_ID" \
  --iam-instance-profile "Name=$IAM_INSTANCE_PROFILE" \
  --block-device-mappings "[{\"DeviceName\":\"/dev/xvda\",\"Ebs\":{\"VolumeSize\":$ROOT_VOLUME_GIB,\"VolumeType\":\"gp3\",\"Iops\":$ROOT_VOLUME_IOPS,\"Throughput\":$ROOT_VOLUME_THROUGHPUT_MBPS,\"DeleteOnTermination\":true}}]" \
  --user-data "$USER_DATA" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=ami-bake-$NEW_AMI_NAME}]" \
  --query 'Instances[0].InstanceId' --output text)
echo "[build-ami] Bake instance: $INSTANCE_ID"
trap "echo '[build-ami] Cleaning up...'; aws ec2 terminate-instances --region $AWS_REGION --instance-ids $INSTANCE_ID >/dev/null 2>&1 || true" EXIT

aws ec2 wait instance-running --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
echo "[build-ami] Instance running; waiting for image pre-pull..."

# 2. Poll for /opt/.image-pulled via SSM. Allow up to 30 min for ~39GiB pull.
DEADLINE=$((SECONDS + 1800))
READY=false
while [ $SECONDS -lt $DEADLINE ]; do
  CMD_ID=$(aws ssm send-command \
    --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=[\"if [ -f /opt/.image-pulled ]; then ctr -n k8s.io images ls | grep -F '$IMAGE_URI' | head -1; echo IMAGE_READY_OK; else echo IMAGE_NOT_READY_YET; ls /var/log/cloud-init-output.log 2>/dev/null; tail -10 /var/log/cloud-init-output.log 2>/dev/null | sed 's/^/  /'; fi\"]" \
    --query 'Command.CommandId' --output text 2>/dev/null) || { sleep 10; continue; }
  sleep 5
  OUT=$(aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'StandardOutputContent' --output text 2>/dev/null || echo "")
  echo "[build-ami] poll @ +${SECONDS}s:"
  echo "$OUT" | sed 's/^/    /' | head -8
  if echo "$OUT" | grep -qw IMAGE_READY_OK; then
    READY=true; break
  fi
  sleep 20
done
[ "$READY" = true ] || { echo "[build-ami] ERROR: image not pulled after 30 min"; exit 1; }

# 3. Stop instance for clean snapshot.
echo "[build-ami] Stopping instance for clean snapshot..."
aws ec2 stop-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID" >/dev/null
aws ec2 wait instance-stopped --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"

# 4. Create AMI.
NEW_AMI_ID=$(aws ec2 create-image \
  --region "$AWS_REGION" \
  --instance-id "$INSTANCE_ID" \
  --name "$NEW_AMI_NAME" \
  --description "EKS AL2023 NVIDIA + comfyui-s3-flux:$IMAGE_TAG (Flux models inside image, no NVMe seed)" \
  --tag-specifications "ResourceType=image,Tags=[{Key=purpose,Value=karpenter-comfyui-flux-image-baked}]" \
  --query 'ImageId' --output text)
echo "[build-ami] Creating AMI: $NEW_AMI_ID"

aws ec2 wait image-available --region "$AWS_REGION" --image-ids "$NEW_AMI_ID" || \
  echo "[build-ami] WARN: image-available wait timed out (default 10 min); AMI may still be pending — re-check manually"

aws ec2 describe-images --region "$AWS_REGION" --image-ids "$NEW_AMI_ID" \
  --query 'Images[0].State' --output text

# 5. Enable FSR on the new root snapshot.
SNAP_ID=$(aws ec2 describe-images --region "$AWS_REGION" --image-ids "$NEW_AMI_ID" \
  --query 'Images[0].BlockDeviceMappings[0].Ebs.SnapshotId' --output text)
echo "[build-ami] New snapshot: $SNAP_ID"
AZ=$(aws ec2 describe-subnets --region "$AWS_REGION" --subnet-ids "$SUBNET_ID" \
  --query 'Subnets[0].AvailabilityZone' --output text)

echo "[build-ami] Enabling FSR for snap=$SNAP_ID AZ=$AZ ..."
aws ec2 enable-fast-snapshot-restores \
  --region "$AWS_REGION" \
  --availability-zones "$AZ" \
  --source-snapshot-ids "$SNAP_ID" \
  --output json 2>&1 | head -20 || true

cat <<EOF

============================================================
  New AMI: $NEW_AMI_ID
  Snapshot: $SNAP_ID  (FSR enabling on $AZ)
  Root size: ${ROOT_VOLUME_GIB}GiB
  Image baked: $IMAGE_URI (containerd k8s.io namespace)
  At pod start: image is locally cached, no S3 / EBS-seed needed
============================================================

Next steps:
  1. Update deploy/k8s-manifests/karpenter-ec2nodeclass-gpu.yaml:
       amiSelectorTerms[0].id  -> $NEW_AMI_ID
       blockDeviceMappings[0].ebs.volumeSize -> ${ROOT_VOLUME_GIB}Gi
       Remove userData seed-copy block (no longer needed; just keep NVMe mount).
  2. Update deploy/k8s-manifests/comfyui-deployment.yaml image to comfyui-s3-flux:latest.
  3. kubectl apply -f deploy/k8s-manifests/karpenter-ec2nodeclass-gpu.yaml
                   -f deploy/k8s-manifests/comfyui-deployment.yaml
  4. Wait for FSR enabled, then run scale-out test.
EOF
