#!/bin/bash
# Cloud-side Docker build for comfyui-s3-flux:latest.
# Spawns a temporary EC2 instance in the same region as ECR, embeds the
# Dockerfile as a heredoc into userData, builds the image and pushes it to
# ECR, then terminates.
#
# Why: building a ~39 GiB image on a Mac is impractical (slow qemu emulation
# for x86_64, slow internet for the 22 GiB S3 download + 39 GiB ECR push).
# Same-region EC2 finishes in ~10-20 min and costs <$0.50.
#
# Usage:
#   ./cloud-build-comfyui-flux.sh

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-c6i.4xlarge}"      # 16 vCPU, 32 GiB RAM, 12.5 Gbps
SUBNET_ID="${SUBNET_ID:-subnet-0be0720f7d356cfe8}" # public subnet in us-east-1b
SG_ID="${SG_ID:-sg-0176fe82167b34c56}"
IAM_INSTANCE_PROFILE="${IAM_INSTANCE_PROFILE:-hp-eks_4377973228388927294}"
DISK_GIB="${DISK_GIB:-200}"                        # docker layers + image cache need elbow room
IMAGE_REPO="${IMAGE_REPO:-comfyui-s3-flux}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DOCKERFILE_PATH="${DOCKERFILE_PATH:-$(cd "$(dirname "$0")/.." && pwd)/comfyui-s3-flux.dockerfile}"

# Latest Amazon Linux 2023 AMI (x86_64) — has aws-cli, ssm-agent, dnf
AMI_PARAM="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
SOURCE_AMI=$(aws ssm get-parameter --region "$AWS_REGION" --name "$AMI_PARAM" --query 'Parameter.Value' --output text)

ACCT=$(aws sts get-caller-identity --query Account --output text)
ECR_HOST="${ACCT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

[ -f "$DOCKERFILE_PATH" ] || { echo "ERROR: Dockerfile not found: $DOCKERFILE_PATH"; exit 1; }

echo "[cloud-build] Region=$AWS_REGION SourceAMI=$SOURCE_AMI"
echo "[cloud-build] InstanceType=$INSTANCE_TYPE Disk=${DISK_GIB}GiB"
echo "[cloud-build] Output: $ECR_HOST/$IMAGE_REPO:$IMAGE_TAG"
echo "[cloud-build] Dockerfile: $DOCKERFILE_PATH"

# Make sure the ECR repo exists
aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$IMAGE_REPO" >/dev/null 2>&1 \
  || aws ecr create-repository --region "$AWS_REGION" --repository-name "$IMAGE_REPO" >/dev/null
echo "[cloud-build] ECR repo ready: $IMAGE_REPO"

# Read Dockerfile content and base64-encode (avoids quoting hell in userData).
DOCKERFILE_B64=$(base64 < "$DOCKERFILE_PATH" | tr -d '\n')

USER_DATA=$(cat <<EOF
#!/bin/bash
set -euxo pipefail
exec > >(tee /var/log/build.log | logger -t build) 2>&1

echo "[\$(date +%H:%M:%S)] installing docker"
dnf install -y docker
# Cap docker0 bridge MTU at 1500 — EC2 ENA defaults to 9001 (jumbo), which
# breaks container egress to PMTU-locked sites (Ubuntu apt mirrors etc.).
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{ "mtu": 1500 }
JSON
systemctl start docker
systemctl enable docker

mkdir -p /root/build
cd /root/build

# Decode Dockerfile from base64
echo "$DOCKERFILE_B64" | base64 -d > Dockerfile

echo "[\$(date +%H:%M:%S)] ECR login"
aws ecr get-login-password --region $AWS_REGION \\
  | docker login --username AWS --password-stdin $ECR_HOST

echo "[\$(date +%H:%M:%S)] docker build"
docker build \\
  -f Dockerfile \\
  --build-arg AWS_REGION=$AWS_REGION \\
  --build-arg MODELS_S3_BUCKET=comfyui-models-bucket-${ACCT} \\
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
echo "    ./deploy/scripts/build-flux-image-baked-ami.sh"
