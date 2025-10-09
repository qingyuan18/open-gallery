#!/bin/bash

# S3 CSI Driver Setup Script for EKS
# This script installs and configures the Mountpoint for S3 CSI driver

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed."
        exit 1
    fi
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed."
        exit 1
    fi
    
    if ! command -v helm &> /dev/null; then
        print_error "Helm is not installed."
        exit 1
    fi
    
    print_info "All prerequisites are met."
}

# Setup environment
setup_environment() {
    print_info "Setting up environment variables..."
    
    export AWS_REGION=${AWS_REGION:-us-west-2}
    export CLUSTER_NAME=${CLUSTER_NAME:-comfyui-cluster}
    export S3_BUCKET=${S3_BUCKET:-salunchbucket}
    export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    
    print_info "AWS Account ID: $AWS_ACCOUNT_ID"
    print_info "AWS Region: $AWS_REGION"
    print_info "Cluster Name: $CLUSTER_NAME"
    print_info "S3 Bucket: $S3_BUCKET"
}

# Create IAM policy for S3 access
create_iam_policy() {
    print_info "Creating IAM policy for S3 CSI driver..."
    
    POLICY_NAME="ComfyUI-S3-CSI-Policy"
    POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"
    
    # Check if policy already exists
    if aws iam get-policy --policy-arn ${POLICY_ARN} &> /dev/null; then
        print_info "IAM policy '${POLICY_NAME}' already exists."
    else
        print_info "Creating IAM policy '${POLICY_NAME}'..."
        
        # Navigate to k8s-manifests directory
        cd "$(dirname "$0")/../k8s-manifests"
        
        aws iam create-policy \
            --policy-name ${POLICY_NAME} \
            --policy-document file://s3-csi-policy.json
        
        print_info "IAM policy created successfully."
    fi
    
    export S3_CSI_POLICY_ARN=${POLICY_ARN}
}

# Create IAM role for service account
create_irsa() {
    print_info "Creating IAM role for service account (IRSA)..."
    
    # Check if service account already exists
    if kubectl get sa s3-csi-driver-sa -n kube-system &> /dev/null; then
        print_warn "Service account 's3-csi-driver-sa' already exists. Skipping IRSA creation."
    else
        print_info "Creating IRSA for S3 CSI driver..."
        
        eksctl create iamserviceaccount \
            --name s3-csi-driver-sa \
            --namespace kube-system \
            --cluster ${CLUSTER_NAME} \
            --region ${AWS_REGION} \
            --attach-policy-arn ${S3_CSI_POLICY_ARN} \
            --approve \
            --override-existing-serviceaccounts
        
        print_info "IRSA created successfully."
    fi
}

# Install S3 CSI driver
install_s3_csi_driver() {
    print_info "Installing Mountpoint for S3 CSI driver..."
    
    # Add Helm repository
    helm repo add aws-mountpoint-s3-csi-driver https://awslabs.github.io/mountpoint-s3-csi-driver
    helm repo update
    
    # Get the service account role ARN
    SA_ROLE_ARN=$(kubectl get sa s3-csi-driver-sa -n kube-system -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}')
    
    if [ -z "$SA_ROLE_ARN" ]; then
        print_error "Failed to get service account role ARN."
        exit 1
    fi
    
    print_info "Service Account Role ARN: $SA_ROLE_ARN"
    
    # Install or upgrade the driver
    helm upgrade --install aws-mountpoint-s3-csi-driver \
        aws-mountpoint-s3-csi-driver/aws-mountpoint-s3-csi-driver \
        --namespace kube-system \
        --set node.serviceAccount.annotations."eks\.amazonaws\.com/role-arn"="${SA_ROLE_ARN}"
    
    print_info "S3 CSI driver installed successfully."
}

# Verify installation
verify_installation() {
    print_info "Verifying S3 CSI driver installation..."
    
    # Wait for pods to be ready
    print_info "Waiting for S3 CSI driver pods to be ready..."
    kubectl wait --for=condition=ready pod \
        -l app.kubernetes.io/name=aws-mountpoint-s3-csi-driver \
        -n kube-system \
        --timeout=300s
    
    # Check driver pods
    print_info "S3 CSI driver pods:"
    kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-mountpoint-s3-csi-driver
    
    print_info "S3 CSI driver installation verified."
}

# Create PV and PVC
create_pv_pvc() {
    print_info "Creating PersistentVolume and PersistentVolumeClaim..."
    
    # Navigate to k8s-manifests directory
    cd "$(dirname "$0")/../k8s-manifests"
    
    # Apply PV and PVC
    kubectl apply -f s3-pv-pvc.yaml
    
    # Wait for PVC to be bound
    print_info "Waiting for PVC to be bound..."
    sleep 5
    
    # Check PV and PVC status
    print_info "PersistentVolume status:"
    kubectl get pv comfyui-models-pv
    
    print_info "PersistentVolumeClaim status:"
    kubectl get pvc comfyui-models-pvc
    
    print_info "PV and PVC created successfully."
}

# Test S3 mount
test_s3_mount() {
    print_info "Testing S3 mount with a test pod..."
    
    # Create a test pod
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: s3-test-pod
  namespace: default
spec:
  containers:
  - name: test
    image: busybox
    command: ['sh', '-c', 'ls -la /mnt/s3 && sleep 3600']
    volumeMounts:
    - name: s3-volume
      mountPath: /mnt/s3
      readOnly: true
  volumes:
  - name: s3-volume
    persistentVolumeClaim:
      claimName: comfyui-models-pvc
EOF
    
    # Wait for pod to be ready
    print_info "Waiting for test pod to be ready..."
    kubectl wait --for=condition=ready pod s3-test-pod --timeout=120s
    
    # Check logs
    print_info "Test pod logs:"
    kubectl logs s3-test-pod
    
    # Cleanup test pod
    print_info "Cleaning up test pod..."
    kubectl delete pod s3-test-pod
    
    print_info "S3 mount test completed successfully."
}

# Display summary
display_summary() {
    echo ""
    print_info "========================================="
    print_info "S3 CSI Driver Setup Summary"
    print_info "========================================="
    print_info "IAM Policy ARN: ${S3_CSI_POLICY_ARN}"
    print_info "S3 Bucket: ${S3_BUCKET}"
    print_info "PV Name: comfyui-models-pv"
    print_info "PVC Name: comfyui-models-pvc"
    print_info "========================================="
    echo ""
    print_info "Next steps:"
    echo "  1. Upload models to S3 bucket: s3://${S3_BUCKET}/models/"
    echo "  2. Uncomment volume mounts in k8s-manifests/comfyui-deployment.yaml"
    echo "  3. Deploy ComfyUI: kubectl apply -f k8s-manifests/comfyui-deployment.yaml"
    echo ""
}

# Main execution
main() {
    print_info "Starting S3 CSI driver setup..."
    
    check_prerequisites
    setup_environment
    create_iam_policy
    create_irsa
    install_s3_csi_driver
    verify_installation
    create_pv_pvc
    
    # Optional: Test S3 mount
    read -p "Do you want to test S3 mount with a test pod? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        test_s3_mount
    fi
    
    display_summary
    
    print_info "S3 CSI driver setup completed successfully!"
}

# Run main function
main

