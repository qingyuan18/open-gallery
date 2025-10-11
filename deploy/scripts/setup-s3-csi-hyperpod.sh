#!/bin/bash

# S3 CSI Driver Setup Script for SageMaker HyperPod EKS
# This script installs and configures the Mountpoint for S3 CSI driver on SageMaker HyperPod
# Key differences from regular EKS:
# 1. Uses EKS add-on instead of Helm installation
# 2. Different service account naming convention (s3-csi-driver-sa)
# 3. Automatic IRSA configuration through add-on
# 4. HyperPod-specific IAM permissions

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Global variables
CLUSTER_NAME=""
AWS_REGION="us-west-2"
S3_BUCKET=""
ADDON_VERSION="v1.10.0-eksbuild.1"  # Latest stable version for HyperPod
AUTO_CONFIRM=false

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --cluster-name)
                CLUSTER_NAME="$2"
                shift 2
                ;;
            --region)
                AWS_REGION="$2"
                shift 2
                ;;
            --bucket)
                S3_BUCKET="$2"
                shift 2
                ;;
            --addon-version)
                ADDON_VERSION="$2"
                shift 2
                ;;
            --yes|-y)
                AUTO_CONFIRM=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Validate required parameters
    if [ -z "$CLUSTER_NAME" ]; then
        print_error "Cluster name is required. Use --cluster-name option."
        show_usage
        exit 1
    fi
    
    if [ -z "$S3_BUCKET" ]; then
        print_error "S3 bucket name is required. Use --bucket option."
        show_usage
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites for SageMaker HyperPod..."
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed."
        exit 1
    fi
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed."
        exit 1
    fi
    
    # Check if cluster is accessible
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot access Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi
    
    # Verify this is a SageMaker HyperPod cluster
    if ! kubectl get nodes -o jsonpath='{.items[0].metadata.labels}' | grep -q "sagemaker.amazonaws.com"; then
        print_warn "This doesn't appear to be a SageMaker HyperPod cluster. Proceeding anyway..."
    fi
    
    print_info "All prerequisites are met."
}

# Setup environment
setup_environment() {
    print_info "Setting up environment variables..."
    
    export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        print_error "Failed to get AWS account ID. Please check your AWS credentials."
        exit 1
    fi
    
    print_info "AWS Account ID: $AWS_ACCOUNT_ID"
    print_info "AWS Region: $AWS_REGION"
    print_info "Cluster Name: $CLUSTER_NAME"
    print_info "S3 Bucket: $S3_BUCKET"
    print_info "Add-on Version: $ADDON_VERSION"
}

# Create IAM policy for S3 access (HyperPod specific)
create_iam_policy() {
    print_info "Creating IAM policy for S3 CSI driver (HyperPod)..."
    
    POLICY_NAME="SageMaker-HyperPod-S3-CSI-Policy"
    POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"
    
    # Check if policy already exists
    if aws iam get-policy --policy-arn ${POLICY_ARN} &> /dev/null; then
        print_info "IAM policy '${POLICY_NAME}' already exists."
    else
        print_info "Creating IAM policy '${POLICY_NAME}'..."
        
        # Create policy document with HyperPod-specific permissions
        cat > /tmp/s3-csi-hyperpod-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation"
            ],
            "Resource": [
                "arn:aws:s3:::${S3_BUCKET}"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::${S3_BUCKET}/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListAllMyBuckets"
            ],
            "Resource": "*"
        }
    ]
}
EOF
        
        aws iam create-policy \
            --policy-name ${POLICY_NAME} \
            --policy-document file:///tmp/s3-csi-hyperpod-policy.json
        
        rm /tmp/s3-csi-hyperpod-policy.json
        print_info "IAM policy created successfully."
    fi
    
    export S3_CSI_POLICY_ARN=${POLICY_ARN}
}

# Create IAM role for service account (HyperPod specific)
create_irsa() {
    print_info "Creating IAM role for service account (IRSA) for HyperPod..."
    
    # Note: Service account name is s3-csi-driver-sa (not s3-csi-controller-sa)
    SERVICE_ACCOUNT_NAME="s3-csi-driver-sa"
    ROLE_NAME="SageMaker-HyperPod-S3-CSI-Role"
    
    # Check if service account already exists
    if kubectl get sa ${SERVICE_ACCOUNT_NAME} -n kube-system &> /dev/null; then
        print_warn "Service account '${SERVICE_ACCOUNT_NAME}' already exists."
        
        # Get existing role ARN
        ROLE_ARN=$(kubectl get sa ${SERVICE_ACCOUNT_NAME} -n kube-system -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}' 2>/dev/null || echo "")
        
        if [ -n "$ROLE_ARN" ]; then
            print_info "Using existing IRSA role: $ROLE_ARN"
            export S3_CSI_ROLE_ARN="$ROLE_ARN"
            return 0
        fi
    fi
    
    print_info "Creating IRSA for S3 CSI driver..."
    
    # Create IRSA using eksctl (recommended for HyperPod)
    eksctl create iamserviceaccount \
        --name ${SERVICE_ACCOUNT_NAME} \
        --namespace kube-system \
        --cluster ${CLUSTER_NAME} \
        --region ${AWS_REGION} \
        --attach-policy-arn ${S3_CSI_POLICY_ARN} \
        --approve \
        --override-existing-serviceaccounts
    
    # Get the created role ARN
    ROLE_ARN=$(kubectl get sa ${SERVICE_ACCOUNT_NAME} -n kube-system -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}')
    export S3_CSI_ROLE_ARN="$ROLE_ARN"
    
    print_info "IRSA created successfully: $ROLE_ARN"
}

# Install S3 CSI driver using EKS add-on (HyperPod method)
install_s3_csi_addon() {
    print_info "Installing Mountpoint for S3 CSI driver as EKS add-on..."
    
    # Check if add-on already exists
    if aws eks describe-addon \
        --cluster-name ${CLUSTER_NAME} \
        --addon-name aws-mountpoint-s3-csi-driver \
        --region ${AWS_REGION} &> /dev/null; then
        
        print_warn "S3 CSI add-on already exists. Updating..."
        
        # Update existing add-on
        aws eks update-addon \
            --cluster-name ${CLUSTER_NAME} \
            --addon-name aws-mountpoint-s3-csi-driver \
            --addon-version ${ADDON_VERSION} \
            --service-account-role-arn ${S3_CSI_ROLE_ARN} \
            --region ${AWS_REGION} \
            --resolve-conflicts OVERWRITE
    else
        print_info "Creating S3 CSI add-on..."
        
        # Create new add-on
        aws eks create-addon \
            --cluster-name ${CLUSTER_NAME} \
            --addon-name aws-mountpoint-s3-csi-driver \
            --addon-version ${ADDON_VERSION} \
            --service-account-role-arn ${S3_CSI_ROLE_ARN} \
            --region ${AWS_REGION} \
            --resolve-conflicts OVERWRITE
    fi
    
    print_info "Waiting for S3 CSI add-on to be active..."
    aws eks wait addon-active \
        --cluster-name ${CLUSTER_NAME} \
        --addon-name aws-mountpoint-s3-csi-driver \
        --region ${AWS_REGION}
    
    print_info "S3 CSI add-on installed successfully."
}

# Verify installation
verify_installation() {
    print_info "Verifying S3 CSI driver installation..."
    
    # Check add-on status
    print_info "Add-on status:"
    aws eks describe-addon \
        --cluster-name ${CLUSTER_NAME} \
        --addon-name aws-mountpoint-s3-csi-driver \
        --region ${AWS_REGION} \
        --query 'addon.{Name:addonName,Version:addonVersion,Status:status,Health:health.issues}' \
        --output table
    
    # Wait for pods to be ready
    print_info "Waiting for S3 CSI driver pods to be ready..."
    kubectl wait --for=condition=ready pod \
        -l app.kubernetes.io/name=aws-mountpoint-s3-csi-driver \
        -n kube-system \
        --timeout=300s
    
    # Check driver pods
    print_info "S3 CSI driver pods:"
    kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-mountpoint-s3-csi-driver
    
    # Check CSI driver
    print_info "CSI drivers:"
    kubectl get csidriver s3.csi.aws.com
    
    print_info "S3 CSI driver installation verified."
}

# Create PV and PVC for HyperPod
create_pv_pvc() {
    print_info "Creating PersistentVolume and PersistentVolumeClaim for HyperPod..."

    # Create PV manifest
    cat > /tmp/s3-pv-hyperpod.yaml << EOF
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: comfyui-models-pv-hyperpod
spec:
  capacity:
    storage: 1000Gi  # Arbitrary value for S3
  accessModes:
    - ReadOnlyMany
  mountOptions:
    - allow-delete
    - region ${AWS_REGION}
    - cache /tmp/s3-cache
    - max-cache-size 10737418240  # 10GB cache
  csi:
    driver: s3.csi.aws.com
    volumeHandle: ${S3_BUCKET}
    volumeAttributes:
      bucketName: ${S3_BUCKET}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: comfyui-models-pvc-hyperpod
  namespace: default
spec:
  accessModes:
    - ReadOnlyMany
  storageClassName: ""
  resources:
    requests:
      storage: 1000Gi
  volumeName: comfyui-models-pv-hyperpod
EOF

    # Apply PV and PVC
    kubectl apply -f /tmp/s3-pv-hyperpod.yaml
    rm /tmp/s3-pv-hyperpod.yaml

    # Wait for PVC to be bound
    print_info "Waiting for PVC to be bound..."
    sleep 5

    # Check PV and PVC status
    print_info "PersistentVolume status:"
    kubectl get pv comfyui-models-pv-hyperpod

    print_info "PersistentVolumeClaim status:"
    kubectl get pvc comfyui-models-pvc-hyperpod

    print_info "PV and PVC created successfully."
}

# Test S3 mount on HyperPod
test_s3_mount() {
    print_info "Testing S3 mount with a test pod on HyperPod..."

    # Create a test pod with HyperPod-compatible configuration
    cat > /tmp/s3-test-pod-hyperpod.yaml << EOF
apiVersion: v1
kind: Pod
metadata:
  name: s3-test-pod-hyperpod
  namespace: default
spec:
  # Use HyperPod worker nodes
  nodeSelector:
    node.kubernetes.io/instance-type: "ml.m5.large"  # Adjust as needed
  containers:
  - name: test
    image: busybox
    command: ['sh', '-c', 'echo "Testing S3 mount on HyperPod..."; ls -la /mnt/s3; echo "Contents of models directory:"; ls -la /mnt/s3/models/ || echo "No models directory found"; sleep 3600']
    volumeMounts:
    - name: s3-volume
      mountPath: /mnt/s3
      readOnly: true
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:
        memory: "256Mi"
        cpu: "200m"
  volumes:
  - name: s3-volume
    persistentVolumeClaim:
      claimName: comfyui-models-pvc-hyperpod
  restartPolicy: Never
EOF

    kubectl apply -f /tmp/s3-test-pod-hyperpod.yaml
    rm /tmp/s3-test-pod-hyperpod.yaml

    # Wait for pod to be ready
    print_info "Waiting for test pod to be ready..."
    kubectl wait --for=condition=ready pod s3-test-pod-hyperpod --timeout=120s

    # Check logs
    print_info "Test pod logs:"
    kubectl logs s3-test-pod-hyperpod

    # Cleanup test pod
    print_info "Cleaning up test pod..."
    kubectl delete pod s3-test-pod-hyperpod

    print_info "S3 mount test completed successfully."
}

# Verify S3 bucket access
verify_s3_access() {
    print_info "Verifying S3 bucket access..."

    # Check if bucket exists and is accessible
    if ! aws s3 ls "s3://${S3_BUCKET}/" --region "$AWS_REGION" &> /dev/null; then
        print_error "Cannot access S3 bucket: $S3_BUCKET"
        print_error "Please check:"
        print_error "  1. Bucket exists"
        print_error "  2. AWS credentials are configured"
        print_error "  3. You have read/write permissions to the bucket"
        exit 1
    fi

    print_info "S3 bucket access verified."
}

# Display summary
display_summary() {
    echo ""
    print_info "========================================="
    print_info "SageMaker HyperPod S3 CSI Setup Summary"
    print_info "========================================="
    print_info "Cluster Name: ${CLUSTER_NAME}"
    print_info "IAM Policy ARN: ${S3_CSI_POLICY_ARN}"
    print_info "IAM Role ARN: ${S3_CSI_ROLE_ARN}"
    print_info "S3 Bucket: ${S3_BUCKET}"
    print_info "Add-on Version: ${ADDON_VERSION}"
    print_info "PV Name: comfyui-models-pv-hyperpod"
    print_info "PVC Name: comfyui-models-pvc-hyperpod"
    print_info "========================================="
    echo ""
    print_info "Key differences from regular EKS:"
    print_info "  ✓ Uses EKS add-on instead of Helm"
    print_info "  ✓ Service account: s3-csi-driver-sa"
    print_info "  ✓ Automatic IRSA configuration"
    print_info "  ✓ HyperPod-optimized mount options"
    echo ""
    print_info "Next steps:"
    echo "  1. Upload models to S3: ./scripts/upload-models-to-s3.sh --bucket ${S3_BUCKET}"
    echo "  2. Update ComfyUI deployment to use: comfyui-models-pvc-hyperpod"
    echo "  3. Deploy ComfyUI: kubectl apply -f k8s-manifests/comfyui-deployment.yaml"
    echo ""
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Install and configure S3 CSI driver for SageMaker HyperPod EKS cluster"
    echo ""
    echo "Options:"
    echo "  --cluster-name <name>     SageMaker HyperPod cluster name (required)"
    echo "  --bucket <name>           S3 bucket name (required)"
    echo "  --region <region>         AWS region (default: us-west-2)"
    echo "  --addon-version <version> S3 CSI add-on version (default: v1.10.0-eksbuild.1)"
    echo "  --help                    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --cluster-name my-hyperpod-cluster --bucket my-models-bucket"
    echo "  $0 --cluster-name hyperpod --bucket models --region us-east-1"
    echo ""
    echo "Key differences from regular EKS:"
    echo "  • Uses EKS add-on instead of Helm installation"
    echo "  • Service account naming: s3-csi-driver-sa"
    echo "  • Automatic IRSA configuration through add-on"
    echo "  • HyperPod-specific IAM permissions and mount options"
    echo ""
}

# Main execution
main() {
    print_info "Starting S3 CSI driver setup for SageMaker HyperPod..."

    parse_arguments "$@"
    check_prerequisites
    setup_environment
    verify_s3_access
    create_iam_policy
    create_irsa
    install_s3_csi_addon
    verify_installation
    create_pv_pvc

    # Optional: Test S3 mount
    if [ "$AUTO_CONFIRM" = false ] && [ -t 0 ]; then
        echo ""
        read -p "Do you want to test S3 mount with a test pod? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            test_s3_mount
        fi
    elif [ "$AUTO_CONFIRM" = true ]; then
        print_info "Auto-confirm: Skipping S3 mount test"
    else
        print_info "Skipping S3 mount test (non-interactive mode)"
    fi

    display_summary

    print_info "SageMaker HyperPod S3 CSI driver setup completed successfully!"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
