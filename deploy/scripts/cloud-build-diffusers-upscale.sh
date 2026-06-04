#!/bin/bash
# Cloud-side Docker build for diffusers-upscale:latest.
# Mirrors cloud-build-comfyui-flux.sh — spawns a same-region EC2 instance,
# embeds the Dockerfile as base64 in userData, builds & pushes to ECR.
#
# Why a separate script: we want to keep the comfyui-s3-flux pipeline pristine.
# This image has its own ECR repo, its own AMI bake, and its own k8s manifests.
#
# Usage:
#   ./cloud-build-diffusers-upscale.sh

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-c6i.4xlarge}"
SUBNET_ID="${SUBNET_ID:-subnet-0be0720f7d356cfe8}"
SG_ID="${SG_ID:-sg-0176fe82167b34c56}"
IAM_INSTANCE_PROFILE="${IAM_INSTANCE_PROFILE:-hp-eks_4377973228388927294}"
DISK_GIB="${DISK_GIB:-100}"
IMAGE_REPO="${IMAGE_REPO:-diffusers-upscale}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DOCKERFILE_PATH="${DOCKERFILE_PATH:-$(cd "$(dirname "$0")/.." && pwd)/diffusers-upscale.dockerfile}"

AMI_PARAM="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
SOURCE_AMI=$(aws ssm get-parameter --region "$AWS_REGION" --name "$AMI_PARAM" --query 'Parameter.Value' --output text)

ACCT=$(aws sts get-caller-identity --query Account --output text)
ECR_HOST="${ACCT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

[ -f "$DOCKERFILE_PATH" ] || { echo "ERROR: Dockerfile not found: $DOCKERFILE_PATH"; exit 1; }

echo "[cloud-build] Region=$AWS_REGION SourceAMI=$SOURCE_AMI"
echo "[cloud-build] InstanceType=$INSTANCE_TYPE Disk=${DISK_GIB}GiB"
echo "[cloud-build] Output: $ECR_HOST/$IMAGE_REPO:$IMAGE_TAG"
echo "[cloud-build] Dockerfile: $DOCKERFILE_PATH"

aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$IMAGE_REPO" >/dev/null 2>&1 \
  || aws ecr create-repository --region "$AWS_REGION" --repository-name "$IMAGE_REPO" >/dev/null
echo "[cloud-build] ECR repo ready: $IMAGE_REPO"

DOCKERFILE_B64=$(base64 < "$DOCKERFILE_PATH" | tr -d '\n')

USER_DATA=$(cat <<EOF
#!/bin/bash
set -euxo pipefail
exec > >(tee /var/log/build.log | logger -t build) 2>&1

echo "[\$(date +%H:%M:%S)] installing docker"
dnf install -y docker
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{ "mtu": 1500 }
JSON
systemctl start docker
systemctl enable docker

mkdir -p /root/build
cd /root/build

echo "$DOCKERFILE_B64" | base64 -d > Dockerfile

echo "[\$(date +%H:%M:%S)] ECR login"
aws ecr get-login-password --region $AWS_REGION \\
  | docker login --username AWS --password-stdin $ECR_HOST

echo "[\$(date +%H:%M:%S)] docker build"
docker build \\
  -f Dockerfile \\
  -t $ECR_HOST/$IMAGE_REPO:$IMAGE_TAG \\
  .

echo "[\$(date +%H:%M:%S)] docker push"
docker push $ECR_HOST/$IMAGE_REPO:$IMAGE_TAG

echo "[\$(date +%H:%M:%S)] BUILD_PUSH_DONE"
touch /opt/.build-done
EOF
)

INSTANCE_ID=$(aws ec2 run-instances \
  --region "$AWS_REGION" \
  --image-id "$SOURCE_AMI" \
  --instance-type "$INSTANCE_TYPE" \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_ID" \
  --iam-instance-profile "Name=$IAM_INSTANCE_PROFILE" \
  --block-device-mappings "[{\"DeviceName\":\"/dev/xvda\",\"Ebs\":{\"VolumeSize\":$DISK_GIB,\"VolumeType\":\"gp3\",\"Iops\":6000,\"Throughput\":500,\"DeleteOnTermination\":true}}]" \
  --user-data "$USER_DATA" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=cloud-build-$IMAGE_REPO}]" \
  --query 'Instances[0].InstanceId' --output text)
echo "[cloud-build] Build instance: $INSTANCE_ID"
trap "echo '[cloud-build] Terminating build instance...'; aws ec2 terminate-instances --region $AWS_REGION --instance-ids $INSTANCE_ID >/dev/null 2>&1 || true" EXIT

aws ec2 wait instance-running --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
echo "[cloud-build] Instance running; polling build status via SSM..."

DEADLINE=$((SECONDS + 3600))
DONE=false
while [ $SECONDS -lt $DEADLINE ]; do
  CMD_ID=$(aws ssm send-command \
    --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=["if [ -f /opt/.build-done ]; then echo BUILD_OK; else echo BUILD_NOT_DONE; tail -8 /var/log/build.log 2>/dev/null | sed s/^/  /; fi"]' \
    --query 'Command.CommandId' --output text 2>/dev/null) || { sleep 15; continue; }
  sleep 5
  OUT=$(aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'StandardOutputContent' --output text 2>/dev/null || echo "")
  echo "[cloud-build] poll @ +${SECONDS}s:"
  echo "$OUT" | sed 's/^/    /' | head -10
  if echo "$OUT" | grep -qw BUILD_OK; then
    DONE=true; break
  fi
  sleep 25
done
[ "$DONE" = true ] || { echo "[cloud-build] ERROR: build timed out"; exit 1; }

echo ""
echo "============================================================"
echo "  Image pushed: $ECR_HOST/$IMAGE_REPO:$IMAGE_TAG"
echo "============================================================"
echo ""
echo "Next: bake the AMI"
echo "    ./deploy/scripts/build-diffusers-upscale-ami.sh"
