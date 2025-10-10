#!/bin/bash

# S3 CSI Driver Setup Script for EKS
# This script installs and configures the Mountpoint for S3 CSI driver
# Supports both EKS Pod Identity (recommended) and IRSA (legacy)
#
# Usage:
#   ./setup-s3-csi.sh [OPTIONS]
#
# Options:
#   --cluster-name <name>     EKS cluster name (required)
#   --bucket <name>           S3 bucket name (required)
#   --region <region>         AWS region (default: us-west-2)
#   --use-pod-identity        Use EKS Pod Identity (recommended, default)
#   --use-irsa                Use IRSA (legacy method)
#   --help                    Show this help message

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

# Global variables
CLUSTER_NAME=""
S3_BUCKET=""
AWS_REGION="us-west-2"
USE_POD_IDENTITY=true  # Default to Pod Identity

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --cluster-name)
                CLUSTER_NAME="$2"
                shift 2
                ;;
            --bucket)
                S3_BUCKET="$2"
                shift 2
                ;;
            --region)
                AWS_REGION="$2"
                shift 2
                ;;
            --use-pod-identity)
                USE_POD_IDENTITY=true
                shift
                ;;
            --use-irsa)
                USE_POD_IDENTITY=false
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
    print_info "Checking prerequisites..."

    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed."
        exit 1
    fi

    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed."
        exit 1
    fi

    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot access Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi

    # Check EKS version for Pod Identity
    if [ "$USE_POD_IDENTITY" = true ]; then
        K8S_VERSION=$(kubectl version --short 2>/dev/null | grep 'Server Version' | awk '{print $3}' | sed 's/v//' | cut -d. -f1,2)
        MAJOR=$(echo $K8S_VERSION | cut -d. -f1)
        MINOR=$(echo $K8S_VERSION | cut -d. -f2)

        if [ "$MAJOR" -lt 1 ] || ([ "$MAJOR" -eq 1 ] && [ "$MINOR" -lt 24 ]); then
            print_warn "EKS Pod Identity requires Kubernetes 1.24+. Current version: $K8S_VERSION"
            print_warn "Falling back to IRSA method..."
            USE_POD_IDENTITY=false
        fi
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
    print_info "Auth Method: $([ "$USE_POD_IDENTITY" = true ] && echo "Pod Identity (recommended)" || echo "IRSA (legacy)")"
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

        # Create policy document
        cat > /tmp/s3-csi-policy.json << EOF
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
                "s3:DeleteObject",
                "s3:AbortMultipartUpload"
            ],
            "Resource": [
                "arn:aws:s3:::${S3_BUCKET}/*"
            ]
        }
    ]
}
EOF

        aws iam create-policy \
            --policy-name ${POLICY_NAME} \
            --policy-document file:///tmp/s3-csi-policy.json

        rm /tmp/s3-csi-policy.json
        print_info "IAM policy created successfully."
    fi

    export S3_CSI_POLICY_ARN=${POLICY_ARN}
}

# Create IAM role with Pod Identity trust policy
create_iam_role_pod_identity() {
    print_info "Creating IAM role for Pod Identity..."

    ROLE_NAME="ComfyUI-S3-CSI-Role"
    ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"

    # Check if role already exists
    if aws iam get-role --role-name ${ROLE_NAME} &> /dev/null 2>&1; then
        print_info "IAM role '${ROLE_NAME}' already exists."
    else
        print_info "Creating IAM role '${ROLE_NAME}' with Pod Identity trust policy..."

        # Create trust policy for Pod Identity
        cat > /tmp/pod-identity-trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "pods.eks.amazonaws.com"
            },
            "Action": [
                "sts:AssumeRole",
                "sts:TagSession"
            ]
        }
    ]
}
EOF

        aws iam create-role \
            --role-name ${ROLE_NAME} \
            --assume-role-policy-document file:///tmp/pod-identity-trust-policy.json \
            --description "IAM role for S3 CSI driver using EKS Pod Identity"

        rm /tmp/pod-identity-trust-policy.json
        print_info "IAM role created successfully."
    fi

    # Attach policy to role
    print_info "Attaching policy to role..."
    aws iam attach-role-policy \
        --role-name ${ROLE_NAME} \
        --policy-arn ${S3_CSI_POLICY_ARN}

    export S3_CSI_ROLE_ARN=${ROLE_ARN}
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

# Create Pod Identity association
create_pod_identity_association() {
    print_info "Creating EKS Pod Identity association..."

    # Check if association already exists
    EXISTING_ASSOC=$(aws eks list-pod-identity-associations \
        --cluster-name ${CLUSTER_NAME} \
        --namespace kube-system \
        --service-account s3-csi-driver-sa \
        --region ${AWS_REGION} \
        --query 'associations[0].associationId' \
        --output text 2>/dev/null || echo "")

    if [ -n "$EXISTING_ASSOC" ] && [ "$EXISTING_ASSOC" != "None" ]; then
        print_info "Pod Identity association already exists: $EXISTING_ASSOC"
    else
        print_info "Creating new Pod Identity association..."

        aws eks create-pod-identity-association \
            --cluster-name ${CLUSTER_NAME} \
            --namespace kube-system \
            --service-account s3-csi-driver-sa \
            --role-arn ${S3_CSI_ROLE_ARN} \
            --region ${AWS_REGION}

        print_info "Pod Identity association created successfully."
    fi
}

# Install S3 CSI driver as EKS add-on
install_s3_csi_addon() {
    print_info "Installing Mountpoint for S3 CSI driver as EKS add-on..."

    # Check if add-on already exists
    if aws eks describe-addon \
        --cluster-name ${CLUSTER_NAME} \
        --addon-name aws-mountpoint-s3-csi-driver \
        --region ${AWS_REGION} &> /dev/null; then

        print_warn "S3 CSI add-on already exists. Updating..."

        # Update existing add-on
        if [ "$USE_POD_IDENTITY" = true ]; then
            # For Pod Identity, no service account role ARN needed
            aws eks update-addon \
                --cluster-name ${CLUSTER_NAME} \
                --addon-name aws-mountpoint-s3-csi-driver \
                --region ${AWS_REGION} \
                --resolve-conflicts OVERWRITE
        else
            # For IRSA, specify service account role ARN
            aws eks update-addon \
                --cluster-name ${CLUSTER_NAME} \
                --addon-name aws-mountpoint-s3-csi-driver \
                --service-account-role-arn ${S3_CSI_ROLE_ARN} \
                --region ${AWS_REGION} \
                --resolve-conflicts OVERWRITE
        fi
    else
        print_info "Creating S3 CSI add-on..."

        # Create new add-on
        if [ "$USE_POD_IDENTITY" = true ]; then
            # For Pod Identity, no service account role ARN needed in add-on
            aws eks create-addon \
                --cluster-name ${CLUSTER_NAME} \
                --addon-name aws-mountpoint-s3-csi-driver \
                --region ${AWS_REGION} \
                --resolve-conflicts OVERWRITE
        else
            # For IRSA, specify service account role ARN
            aws eks create-addon \
                --cluster-name ${CLUSTER_NAME} \
                --addon-name aws-mountpoint-s3-csi-driver \
                --service-account-role-arn ${S3_CSI_ROLE_ARN} \
                --region ${AWS_REGION} \
                --resolve-conflicts OVERWRITE
        fi
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
    print_info "Cluster Name: ${CLUSTER_NAME}"
    print_info "Auth Method: $([ "$USE_POD_IDENTITY" = true ] && echo "Pod Identity" || echo "IRSA")"
    print_info "IAM Policy ARN: ${S3_CSI_POLICY_ARN}"
    print_info "IAM Role ARN: ${S3_CSI_ROLE_ARN}"
    print_info "S3 Bucket: ${S3_BUCKET}"
    print_info "PV Name: comfyui-models-pv"
    print_info "PVC Name: comfyui-models-pvc"
    print_info "========================================="
    echo ""
    if [ "$USE_POD_IDENTITY" = true ]; then
        print_info "✅ Using EKS Pod Identity (recommended)"
        print_info "   • Simpler configuration"
        print_info "   • Better scalability"
        print_info "   • Cross-cluster role reuse"
    else
        print_info "⚠️  Using IRSA (legacy method)"
        print_info "   • Consider migrating to Pod Identity"
    fi
    echo ""
    print_info "Next steps:"
    echo "  1. Upload models: ./scripts/upload-models-to-s3.sh --bucket ${S3_BUCKET}"
    echo "  2. Update k8s-manifests/s3-pv-pvc.yaml with bucket name"
    echo "  3. Deploy ComfyUI: ./scripts/deploy-to-eks.sh --comfyui-mode s3"
    echo ""
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Install and configure S3 CSI driver for EKS cluster"
    echo ""
    echo "Options:"
    echo "  --cluster-name <name>     EKS cluster name (required)"
    echo "  --bucket <name>           S3 bucket name (required)"
    echo "  --region <region>         AWS region (default: us-west-2)"
    echo "  --use-pod-identity        Use EKS Pod Identity (recommended, default)"
    echo "  --use-irsa                Use IRSA (legacy method)"
    echo "  --help                    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --cluster-name my-cluster --bucket my-bucket"
    echo "  $0 --cluster-name my-cluster --bucket my-bucket --use-pod-identity"
    echo "  $0 --cluster-name my-cluster --bucket my-bucket --use-irsa"
    echo ""
    echo "Authentication Methods:"
    echo "  • Pod Identity (recommended): Simpler, more scalable, requires EKS 1.24+"
    echo "  • IRSA (legacy): Uses OIDC, more complex, works with older EKS versions"
    echo ""
}

# Main execution
main() {
    print_info "Starting S3 CSI driver setup..."

    parse_arguments "$@"
    check_prerequisites
    setup_environment
    create_iam_policy

    if [ "$USE_POD_IDENTITY" = true ]; then
        print_info "Using EKS Pod Identity (recommended method)"
        create_iam_role_pod_identity
        install_s3_csi_addon
        create_pod_identity_association
    else
        print_info "Using IRSA (legacy method)"
        create_irsa
        install_s3_csi_addon
    fi

    verify_installation
    create_pv_pvc

    # Optional: Test S3 mount
    echo ""
    read -p "Do you want to test S3 mount with a test pod? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        test_s3_mount
    fi

    display_summary

    print_info "S3 CSI driver setup completed successfully!"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

