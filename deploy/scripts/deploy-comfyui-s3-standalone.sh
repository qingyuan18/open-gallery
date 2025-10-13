#!/bin/bash

# ComfyUI-S3 Standalone Deployment Script for EKS
# This script builds and deploys ComfyUI-S3 for quick testing
# Usage: ./deploy-comfyui-s3-standalone.sh [OPTIONS]
#
# Features:
# - Builds and pushes ComfyUI-S3 Docker image
# - Deploys to dedicated test namespace
# - Sets up S3 PVC for models
# - Provides port-forward command for testing

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

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Global variables
AWS_REGION="us-west-2"
S3_BUCKET="comfyui-models-bucket-687912291502"
SKIP_BUILD=false
SKIP_S3_SETUP=false
NO_S3_MOUNT=false  # New option to deploy without S3 mount
GPU_NODE_TYPE="ml.g6e.2xlarge"
AUTO_CONFIRM=false

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --region)
                AWS_REGION="$2"
                shift 2
                ;;
            --bucket)
                S3_BUCKET="$2"
                shift 2
                ;;
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --skip-s3-setup)
                SKIP_S3_SETUP=true
                shift
                ;;
            --no-s3-mount)
                NO_S3_MOUNT=true
                shift
                ;;
            --gpu-node-type)
                GPU_NODE_TYPE="$2"
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
}

# Check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed."
        exit 1
    fi
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed."
        exit 1
    fi
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed."
        exit 1
    fi
    
    # Check kubectl connection
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi
    
    print_info "All prerequisites met."
}

# Setup environment
setup_environment() {
    print_step "Setting up environment..."
    
    export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        print_error "Failed to get AWS account ID. Please check your AWS credentials."
        exit 1
    fi
    
    export ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    export IMAGE_NAME="comfyui-s3"
    export IMAGE_TAG="test-$(date +%Y%m%d-%H%M%S)"
    export FULL_IMAGE="${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    
    print_info "AWS Account ID: $AWS_ACCOUNT_ID"
    print_info "AWS Region: $AWS_REGION"
    if [ "$NO_S3_MOUNT" = false ]; then
        print_info "S3 Bucket: $S3_BUCKET"
    else
        print_warn "S3 Mount: DISABLED (testing mode)"
    fi
    print_info "Image: $FULL_IMAGE"
    print_info "GPU Node Type: $GPU_NODE_TYPE"
}

# Build and push Docker image
build_and_push_image() {
    if [ "$SKIP_BUILD" = true ]; then
        print_warn "Skipping Docker build (--skip-build flag set)"
        # Use latest tag instead
        export FULL_IMAGE="${ECR_REGISTRY}/${IMAGE_NAME}:latest"
        return 0
    fi
    
    print_step "Building and pushing ComfyUI-S3 Docker image..."
    
    # Navigate to project root
    cd "$(dirname "$0")/../.."
    
    # Create ECR repository if it doesn't exist
    print_info "Checking ECR repository..."
    if ! aws ecr describe-repositories --repository-names ${IMAGE_NAME} --region ${AWS_REGION} &> /dev/null; then
        print_info "Creating ECR repository: ${IMAGE_NAME}"
        aws ecr create-repository \
            --repository-name ${IMAGE_NAME} \
            --region ${AWS_REGION} \
            --image-scanning-configuration scanOnPush=true
    fi
    
    # Authenticate Docker to ECR
    print_info "Authenticating Docker to ECR..."
    aws ecr get-login-password --region ${AWS_REGION} | \
        docker login --username AWS --password-stdin ${ECR_REGISTRY}
    
    # Build image
    print_info "Building Docker image (this may take 5-10 minutes)..."
    docker build \
        -f deploy/comfyui-s3.dockerfile \
        -t ${IMAGE_NAME}:${IMAGE_TAG} \
        -t ${IMAGE_NAME}:latest \
        --progress=plain \
        .
    
    # Tag for ECR
    print_info "Tagging image for ECR..."
    docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${FULL_IMAGE}
    docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_REGISTRY}/${IMAGE_NAME}:latest
    
    # Push to ECR
    print_info "Pushing image to ECR..."
    docker push ${FULL_IMAGE}
    docker push ${ECR_REGISTRY}/${IMAGE_NAME}:latest
    
    print_info "Image pushed successfully: ${FULL_IMAGE}"
}

# Setup S3 PVC in test namespace
setup_s3_pvc() {
    if [ "$NO_S3_MOUNT" = true ]; then
        print_warn "Skipping S3 mount (--no-s3-mount flag set)"
        print_info "ComfyUI will start without models - for testing only"
        return 0
    fi

    if [ "$SKIP_S3_SETUP" = true ]; then
        print_warn "Skipping S3 PVC setup (--skip-s3-setup flag set)"
        return 0
    fi

    print_step "Setting up S3 PVC for models..."

    # Ensure namespace exists first
    kubectl create namespace comfyui-test --dry-run=client -o yaml | kubectl apply -f -

    # Create PV and PVC for test namespace
    cat > /tmp/comfyui-s3-test-pvc.yaml << EOF
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: comfyui-models-pv-test
spec:
  capacity:
    storage: 1000Gi
  accessModes:
    - ReadOnlyMany
  mountOptions:
    - allow-delete
    - region ${AWS_REGION}
    - prefix models/
  csi:
    driver: s3.csi.aws.com
    volumeHandle: ${S3_BUCKET}
    volumeAttributes:
      bucketName: ${S3_BUCKET}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: comfyui-models-pvc
  namespace: comfyui-test
spec:
  accessModes:
    - ReadOnlyMany
  storageClassName: ""
  resources:
    requests:
      storage: 1000Gi
  volumeName: comfyui-models-pv-test
EOF

    kubectl apply -f /tmp/comfyui-s3-test-pvc.yaml
    rm /tmp/comfyui-s3-test-pvc.yaml

    # Wait for PVC to be bound
    print_info "Waiting for PVC to be bound..."
    for i in {1..30}; do
        PVC_STATUS=$(kubectl get pvc -n comfyui-test comfyui-models-pvc -o jsonpath='{.status.phase}' 2>/dev/null || echo "NotFound")
        if [ "$PVC_STATUS" = "Bound" ]; then
            print_info "PVC bound successfully"
            return 0
        fi
        echo -n "."
        sleep 2
    done

    print_warn "PVC not bound yet, but continuing deployment..."
    print_info "Check PVC status with: kubectl get pvc -n comfyui-test"
}

# Deploy ComfyUI-S3
deploy_comfyui() {
    print_step "Deploying ComfyUI-S3 to EKS..."

    # Navigate to k8s-manifests directory
    cd "$(dirname "$0")/../k8s-manifests"

    # Create temporary deployment file with image replaced
    if [ "$NO_S3_MOUNT" = true ]; then
        print_info "Creating deployment without S3 mount..."
        # Remove volume and volumeMounts sections
        cat comfyui-s3-standalone.yaml | \
            sed "s|PLACEHOLDER_IMAGE|${FULL_IMAGE}|g" | \
            sed "s|node.kubernetes.io/instance-type: g5.xlarge|node.kubernetes.io/instance-type: ${GPU_NODE_TYPE}|g" | \
            sed '/volumeMounts:/,/readOnly: true/d' | \
            sed '/volumes:/,/claimName: comfyui-models-pvc/d' > /tmp/comfyui-s3-deploy.yaml
    else
        cat comfyui-s3-standalone.yaml | \
            sed "s|PLACEHOLDER_IMAGE|${FULL_IMAGE}|g" | \
            sed "s|node.kubernetes.io/instance-type: g5.xlarge|node.kubernetes.io/instance-type: ${GPU_NODE_TYPE}|g" > /tmp/comfyui-s3-deploy.yaml
    fi

    # Apply deployment
    kubectl apply -f /tmp/comfyui-s3-deploy.yaml
    rm /tmp/comfyui-s3-deploy.yaml

    print_info "Deployment created successfully"
}

# Wait for pod to be ready
wait_for_pod() {
    print_step "Waiting for ComfyUI pod to be ready..."

    print_info "This may take up to 30 minutes for the pod to start..."

    # Wait for pod to exist (30 minutes = 900 iterations * 2 seconds)
    for i in {1..900}; do
        if kubectl get pods -n comfyui-test -l app=comfyui-s3-test &> /dev/null; then
            break
        fi
        sleep 2
    done

    # Wait for pod to be ready (with timeout of 30 minutes = 1800 seconds)
    kubectl wait --for=condition=ready pod \
        -l app=comfyui-s3-test \
        -n comfyui-test \
        --timeout=1800s || {
        print_error "Pod failed to become ready. Checking logs..."
        POD_NAME=$(kubectl get pods -n comfyui-test -l app=comfyui-s3-test -o jsonpath='{.items[0].metadata.name}')
        kubectl logs -n comfyui-test $POD_NAME --tail=50
        exit 1
    }

    print_info "Pod is ready!"
}

# Display summary and next steps
display_summary() {
    echo ""
    print_info "========================================="
    print_info "ComfyUI-S3 Deployment Summary"
    print_info "========================================="
    print_info "Namespace: comfyui-test"
    print_info "Image: ${FULL_IMAGE}"
    if [ "$NO_S3_MOUNT" = false ]; then
        print_info "S3 Bucket: ${S3_BUCKET}"
    else
        print_warn "S3 Mount: DISABLED"
        print_warn "ComfyUI started without models (testing mode)"
    fi

    POD_NAME=$(kubectl get pods -n comfyui-test -l app=comfyui-s3-test -o jsonpath='{.items[0].metadata.name}')
    print_info "Pod Name: ${POD_NAME}"
    print_info "========================================="
    echo ""

    if [ "$NO_S3_MOUNT" = true ]; then
        print_warn "⚠️  Testing Mode: ComfyUI deployed without S3 models"
        print_info "This is useful for testing Docker build and pod startup"
        print_info "ComfyUI will start but won't have any models loaded"
        echo ""
    fi

    print_info "🎉 Deployment completed successfully!"
    echo ""
    print_info "Next steps:"
    echo ""
    echo "  1. Port-forward to access ComfyUI:"
    echo "     ${BLUE}kubectl port-forward -n comfyui-test ${POD_NAME} 8188:8188${NC}"
    echo ""
    echo "  2. Open in browser:"
    echo "     ${BLUE}http://localhost:8188${NC}"
    echo ""
    echo "  3. Check pod logs:"
    echo "     ${BLUE}kubectl logs -n comfyui-test ${POD_NAME} -f${NC}"
    echo ""
    echo "  4. Check pod status:"
    echo "     ${BLUE}kubectl get pods -n comfyui-test${NC}"
    echo ""
    echo "  5. Delete deployment when done:"
    echo "     ${BLUE}kubectl delete namespace comfyui-test${NC}"
    echo ""
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Build and deploy ComfyUI-S3 for standalone testing on EKS"
    echo ""
    echo "Options:"
    echo "  --region <region>         AWS region (default: us-west-2)"
    echo "  --bucket <name>           S3 bucket name (default: comfyui-models-bucket-687912291502)"
    echo "  --gpu-node-type <type>    GPU node instance type (default: g5.xlarge)"
    echo "  --skip-build              Skip Docker build, use existing latest image"
    echo "  --skip-s3-setup           Skip S3 PVC setup (assumes already configured)"
    echo "  --no-s3-mount             Deploy without S3 mount (for testing build only)"
    echo "  --yes, -y                 Skip confirmation prompt (for automation/nohup)"
    echo "  --help                    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Full deployment with S3"
    echo "  $0 --no-s3-mount                      # Test build without S3 models"
    echo "  $0 --skip-build                       # Use existing image"
    echo "  $0 --bucket my-bucket                 # Use different S3 bucket"
    echo "  $0 --gpu-node-type g5.2xlarge         # Use larger GPU instance"
    echo "  $0 --yes                              # Auto-confirm (for nohup)"
    echo ""
    echo "For background execution with nohup:"
    echo "  nohup $0 --yes > deploy.log 2>&1 &"
    echo ""
    echo "Testing without S3 models:"
    echo "  $0 --no-s3-mount                      # Build and deploy, no models"
    echo "  # ComfyUI will start but won't have models loaded"
    echo "  # Useful for testing Docker build and basic pod startup"
    echo ""
    echo "Prerequisites:"
    echo "  • EKS cluster with GPU nodes"
    echo "  • kubectl configured for your cluster"
    echo "  • AWS CLI configured"
    echo "  • Docker installed"
    echo ""
    echo "Optional (for S3 mount):"
    echo "  • S3 CSI driver installed"
    echo "  • Models uploaded to S3 bucket"
    echo ""
}

# Main execution
main() {
    print_info "Starting ComfyUI-S3 Standalone Deployment..."
    echo ""

    parse_arguments "$@"
    check_prerequisites
    setup_environment

    # Confirm with user unless auto-confirm
    if [ "$AUTO_CONFIRM" = false ]; then
        echo ""
        print_warn "This will deploy ComfyUI-S3 to namespace 'comfyui-test'"
        # Check if stdin is available (not running in nohup/background)
        if [ -t 0 ]; then
            read -p "Continue? (y/N): " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_info "Deployment cancelled."
                exit 0
            fi
        else
            print_warn "Running in non-interactive mode (stdin not available)"
            print_warn "Use --yes or -y flag to auto-confirm, or run interactively"
            print_error "Cannot proceed without confirmation"
            exit 1
        fi
    else
        print_info "Auto-confirm enabled, proceeding with deployment..."
    fi

    build_and_push_image
    setup_s3_pvc
    deploy_comfyui
    wait_for_pod
    display_summary

    print_info "All done! 🚀"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
