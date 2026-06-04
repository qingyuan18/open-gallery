#!/bin/bash
# Build a new AMI that bakes Flux test models into the EBS root.
#
# Source AMI: ami-0612079d793ce76d8  (EKS AL2023 + NVIDIA + comfyui-s3 image pre-pulled, 80GiB)
# Output:     ami-XXXX                (same + ~22GiB Flux models under /opt/comfyui-models-seed, 130GiB)
#
# At node boot, userData mounts the instance-store NVMe and copies seed -> /opt/dlami/nvme/comfyui-models
# so the comfyui-nvme-prewarm DaemonSet is no longer needed.
#
# Usage:
#   ./build-flux-preloaded-ami.sh
#
# Prereqs:
#   - AWS CLI configured for the target account (us-east-1)
#   - SSH key pair name + a subnet/SG that allows SSM Session Manager (preferred) or SSH
#   - Models exist in s3://comfyui-models-bucket-687912291502/

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
SOURCE_AMI="${SOURCE_AMI:-ami-0612079d793ce76d8}"
INSTANCE_TYPE="${INSTANCE_TYPE:-c6i.2xlarge}"     # cheap, only used for baking; EBS bandwidth is what matters
SUBNET_ID="${SUBNET_ID:-subnet-02a0c90865eb51a75}"
SG_ID="${SG_ID:-sg-0176fe82167b34c56}"
IAM_INSTANCE_PROFILE="${IAM_INSTANCE_PROFILE:-AmazonSSMInstanceProfile}"  # must allow SSM + S3 read of models bucket
ROOT_VOLUME_GIB="${ROOT_VOLUME_GIB:-130}"
ROOT_VOLUME_IOPS="${ROOT_VOLUME_IOPS:-6000}"
ROOT_VOLUME_THROUGHPUT_MBPS="${ROOT_VOLUME_THROUGHPUT_MBPS:-500}"
S3_MODELS_BUCKET="${S3_MODELS_BUCKET:-comfyui-models-bucket-687912291502}"
SEED_DIR="/opt/comfyui-models-seed"
NEW_AMI_NAME="${NEW_AMI_NAME:-comfyui-s3-flux-preloaded-al2023-nvidia-1.31-$(date +%Y%m%d-%H%M)}"

# Which model files to bake into the AMI. Keep this list small to control AMI size.
MODELS=(
  "models/diffusion_models/flux1-dev-fp8.safetensors"
  "models/text_encoders/t5xxl_fp8_e4m3fn.safetensors"
  "models/clip/clip_l.safetensors"
  "models/vae/ae.safetensors"
)

echo "[build-ami] Region=$AWS_REGION Source=$SOURCE_AMI Output name=$NEW_AMI_NAME"

# 1. Launch a baking instance with an enlarged root volume.
USER_DATA=$(cat <<EOF
#!/bin/bash
set -euxo pipefail
mkdir -p $SEED_DIR
$(for m in "${MODELS[@]}"; do
  d=$(dirname "$m")
  echo "mkdir -p $SEED_DIR/$d"
  echo "aws s3 cp s3://$S3_MODELS_BUCKET/$m $SEED_DIR/$m --region $AWS_REGION"
done)
# Mark seed ready for the bake-watcher.
touch $SEED_DIR/.ready
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
echo "[build-ami] Instance running, waiting for S3 download to finish..."

# 2. Poll for the seed-ready marker via SSM (no SSH key required).
# Allow up to 30 minutes for ~22GiB download.
DEADLINE=$((SECONDS + 1800))
READY=false
while [ $SECONDS -lt $DEADLINE ]; do
  CMD_ID=$(aws ssm send-command \
    --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=[\"if [ -f $SEED_DIR/.ready ]; then du -sh $SEED_DIR; echo SEED_READY_OK; else echo SEED_NOT_READY_YET; ls -la $SEED_DIR 2>/dev/null | tail -5; fi\"]" \
    --query 'Command.CommandId' --output text 2>/dev/null) || { sleep 10; continue; }
  sleep 5
  OUT=$(aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'StandardOutputContent' --output text 2>/dev/null || echo "")
  echo "[build-ami] poll @ +${SECONDS}s:"
  echo "$OUT" | sed 's/^/    /'
  if echo "$OUT" | grep -qw SEED_READY_OK; then
    READY=true; break
  fi
  sleep 20
done
[ "$READY" = true ] || { echo "[build-ami] ERROR: seed not ready after 30 min"; exit 1; }

# 3. Stop instance and create AMI.
echo "[build-ami] Stopping instance for clean snapshot..."
aws ec2 stop-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID" >/dev/null
aws ec2 wait instance-stopped --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"

NEW_AMI_ID=$(aws ec2 create-image \
  --region "$AWS_REGION" \
  --instance-id "$INSTANCE_ID" \
  --name "$NEW_AMI_NAME" \
  --description "EKS AL2023 GPU + comfyui-s3 + flux test models pre-staged at $SEED_DIR" \
  --tag-specifications "ResourceType=image,Tags=[{Key=purpose,Value=karpenter-comfyui-flux-preloaded}]" \
  --query 'ImageId' --output text)
echo "[build-ami] Creating AMI: $NEW_AMI_ID"

aws ec2 wait image-available --region "$AWS_REGION" --image-ids "$NEW_AMI_ID"
echo "[build-ami] AMI available"

# 4. Enable Fast Snapshot Restore on the new root snapshot.
SNAP_ID=$(aws ec2 describe-images --region "$AWS_REGION" --image-ids "$NEW_AMI_ID" \
  --query 'Images[0].BlockDeviceMappings[0].Ebs.SnapshotId' --output text)
echo "[build-ami] Enabling FSR on snapshot $SNAP_ID..."
AZ=$(aws ec2 describe-subnets --region "$AWS_REGION" --subnet-ids "$SUBNET_ID" \
  --query 'Subnets[0].AvailabilityZone' --output text)
aws ec2 enable-fast-snapshot-restores \
  --region "$AWS_REGION" \
  --availability-zones "$AZ" \
  --source-snapshot-ids "$SNAP_ID" >/dev/null
echo "[build-ami] FSR enable requested for AZ=$AZ. Activation takes ~60 min/TiB."

cat <<EOF

============================================================
  New AMI: $NEW_AMI_ID
  Snapshot: $SNAP_ID  (FSR enabling on $AZ)
  Root size: ${ROOT_VOLUME_GIB}GiB
  Seed path on AMI: $SEED_DIR
============================================================

Next steps:
  1. Update deploy/k8s-manifests/karpenter-ec2nodeclass-gpu.yaml:
       amiSelectorTerms[0].id  -> $NEW_AMI_ID
       blockDeviceMappings[0].ebs.volumeSize -> ${ROOT_VOLUME_GIB}Gi
     The userData copy block is already in place (cp seed -> NVMe).
  2. kubectl apply -f deploy/k8s-manifests/karpenter-ec2nodeclass-gpu.yaml
  3. (Optional) kubectl delete daemonset comfyui-nvme-prewarm
  4. ./deploy/scripts/test-keda-karpenter-scaling-simple.sh
EOF
