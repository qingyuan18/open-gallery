#!/bin/bash

# Open Gallery + ComfyUI EKS Deployment Script
# This script deploys Open Gallery and ComfyUI (S3 mode) to an existing EKS cluster
#
# Usage:
#   ./deploy-to-eks.sh [OPTIONS]
#
# Options:
#   --skip-comfyui         Skip ComfyUI deployment (deploy only open-gallery)
#   --yes, -y              Skip confirmation prompts (for automation/nohup)
#   --help                 Show this help message

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Absolute path to this script directory (independent of current working dir)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

    # Check if kubectl can connect to cluster
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster. Please configure kubectl."
        exit 1
    fi

    print_info "All prerequisites are met."
}

# Parse command line arguments
parse_arguments() {
    SKIP_COMFYUI=false
    AUTO_CONFIRM=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-comfyui)
                SKIP_COMFYUI=true
                shift
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

# Setup environment
setup_environment() {
    print_info "Setting up environment variables..."

    export AWS_REGION=${AWS_REGION:-us-west-2}
    export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    export IMAGE_TAG=${IMAGE_TAG:-latest}
    export ECR_REGISTRY=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

    print_info "AWS Account ID: $AWS_ACCOUNT_ID"
    print_info "AWS Region: $AWS_REGION"
    print_info "ComfyUI Mode: S3 (models mounted from S3)"
    print_info "Skip ComfyUI: $SKIP_COMFYUI"
}

# Update deployment manifests with image URLs
update_deployment_manifests() {
    print_info "Updating deployment manifests with image URLs..."

    cd "${SCRIPT_DIR}/../k8s-manifests"

    # Update open-gallery deployment
    envsubst < open-gallery-deployment.yaml > open-gallery-deployment-temp.yaml

    # Update ComfyUI deployment (S3 mode only)
    if [ "$SKIP_COMFYUI" = false ]; then
        envsubst < comfyui-deployment.yaml > comfyui-deployment-temp.yaml
    fi

    print_info "Deployment manifests updated."
}

# Deploy ConfigMaps
deploy_configmaps() {
    print_info "Deploying ConfigMaps..."

    kubectl apply -f open-gallery-configmap.yaml
    kubectl apply -f comfyui-configmap.yaml

    print_info "ConfigMaps deployed successfully."
}

# Deploy Services
deploy_services() {
    print_info "Deploying Services..."

    kubectl apply -f open-gallery-service.yaml

    if [ "$SKIP_COMFYUI" = false ]; then
        kubectl apply -f comfyui-service.yaml
    fi

    print_info "Services deployed successfully."
}

# Deploy Applications
deploy_applications() {
    print_info "Deploying applications..."

    # Deploy ComfyUI first (if not skipped)
    if [ "$SKIP_COMFYUI" = false ]; then
        print_info "Deploying ComfyUI (S3 mode with models mounted from S3)..."
        kubectl apply -f comfyui-deployment-temp.yaml
    fi

    # Deploy Open Gallery
    print_info "Deploying Open Gallery..."
    kubectl apply -f open-gallery-deployment-temp.yaml

    print_info "Applications deployed successfully."
}

# Wait for deployments
wait_for_deployments() {
    print_info "Waiting for deployments to be ready..."
    print_warn "This may take 5-10 minutes for the first deployment..."

    if [ "$SKIP_COMFYUI" = false ]; then
        print_info "Waiting for ComfyUI..."
        kubectl rollout status deployment/comfyui --timeout=600s
    fi

    print_info "Waiting for Open Gallery..."
    kubectl rollout status deployment/open-gallery --timeout=300s

    print_info "All deployments are ready."
}

# Deploy Ingress
deploy_ingress() {
    print_info "Deploying Ingress..."

    # Ensure IngressClass exists
    kubectl apply -f alb-ingress-class.yaml

    kubectl apply -f open-gallery-ingress.yaml

    print_info "Ingress deployed successfully."
}

# Wait for ALB
wait_for_alb() {
    print_info "Waiting for ALB to be provisioned..."
    print_warn "This may take 2-3 minutes..."

    # Wait for ingress to get an address
    for i in {1..60}; do
        ALB_URL=$(kubectl get ingress open-gallery-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
        if [ ! -z "$ALB_URL" ]; then
            print_info "ALB provisioned successfully."
            export ALB_URL
            return 0
        fi
        sleep 5
    done

    print_warn "ALB provisioning is taking longer than expected. Check AWS console for details."
}

# Tag ALB security groups so the controller can manage inbound rules
# Some users provide a pre-existing SG via annotations; ALB Controller only manages SGs tagged with the cluster key
# We infer the cluster tag from the ALB itself and apply it to attached SGs
tag_alb_security_groups() {
    print_info "Tagging ALB security groups for cluster ownership (if needed)..."

    if [ -z "$ALB_URL" ]; then
        print_warn "ALB URL not available, skipping SG tagging."
        return 0
    fi

    # Resolve ALB ARN from DNSName
    LB_ARN=$(aws elbv2 describe-load-balancers \
        --region "$AWS_REGION" \
        --query "LoadBalancers[?DNSName=='${ALB_URL}'].LoadBalancerArn" \
        --output text 2>/dev/null)

    if [ -z "$LB_ARN" ] || [ "$LB_ARN" = "None" ]; then
        print_warn "Could not resolve ALB ARN from DNSName '$ALB_URL'. Skipping SG tagging."
        return 0
    fi

    # Get the cluster tag key from the ALB itself (kubernetes.io/cluster/<name>)
    CLUSTER_TAG_KEY=$(aws elbv2 describe-tags \
        --region "$AWS_REGION" \
        --resource-arns "$LB_ARN" \
        --query "TagDescriptions[0].Tags[?starts_with(Key, 'kubernetes.io/cluster/')].Key" \
        --output text 2>/dev/null)

    if [ -z "$CLUSTER_TAG_KEY" ] || [ "$CLUSTER_TAG_KEY" = "None" ]; then
        print_warn "ALB does not have a kubernetes.io/cluster/* tag. Skipping SG tagging."
        return 0
    fi

    # Fetch Security Group IDs attached to the ALB
    SG_IDS=$(aws elbv2 describe-load-balancers \
        --region "$AWS_REGION" \
        --load-balancer-arns "$LB_ARN" \
        --query "LoadBalancers[0].SecurityGroups" \
        --output text 2>/dev/null)

    if [ -z "$SG_IDS" ] || [ "$SG_IDS" = "None" ]; then
        print_warn "No security groups associated with ALB. Skipping SG tagging."
        return 0
    fi

    for SG in $SG_IDS; do
        print_info "Ensuring tag '$CLUSTER_TAG_KEY=owned' on security group $SG"
        aws ec2 create-tags \
            --region "$AWS_REGION" \
            --resources "$SG" \
            --tags Key="$CLUSTER_TAG_KEY",Value="owned" >/dev/null 2>&1 || true
    done

    print_success "Security group tagging step completed."
}


# Optional: Deploy HPA
deploy_hpa() {
    if [ "$AUTO_CONFIRM" = false ] && [ -t 0 ]; then
        read -p "Do you want to deploy Horizontal Pod Autoscaler? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Deploying HPA..."
            kubectl apply -f comfyui-hpa.yaml
            print_info "HPA deployed successfully."
        fi
    elif [ "$AUTO_CONFIRM" = true ]; then
        print_info "Auto-confirm: Skipping HPA deployment"
    else
        print_info "Skipping HPA deployment."
    fi
}

# Verify deployment
verify_deployment() {
    print_info "Verifying deployment..."

    echo ""
    print_info "Open Gallery Pods:"
    kubectl get pods -l app=open-gallery

    if [ "$SKIP_COMFYUI" = false ]; then
        echo ""
        print_info "ComfyUI Pods:"
        kubectl get pods -l app=comfyui
    fi

    echo ""
    print_info "Services:"
    kubectl get svc open-gallery-service
    if [ "$SKIP_COMFYUI" = false ]; then
        kubectl get svc comfyui-service
    fi

    echo ""
    print_info "Ingress:"
    kubectl get ingress open-gallery-ingress

    echo ""
    print_info "Deployments:"
    kubectl get deployment open-gallery
    if [ "$SKIP_COMFYUI" = false ]; then
        kubectl get deployment comfyui
    fi
}

# Display logs
display_logs() {
    if [ "$AUTO_CONFIRM" = false ] && [ -t 0 ]; then
        read -p "Do you want to view pod logs? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Which logs do you want to view?"
            echo "1) Open Gallery"
            if [ "$SKIP_COMFYUI" = false ]; then
                echo "2) ComfyUI"
            fi
            read -p "Enter choice: " choice

            if [ "$choice" == "1" ]; then
                POD_NAME=$(kubectl get pods -l app=open-gallery -o jsonpath='{.items[0].metadata.name}')
                print_info "Displaying logs for Open Gallery pod: $POD_NAME"
                kubectl logs -f $POD_NAME
            elif [ "$choice" == "2" ] && [ "$SKIP_COMFYUI" = false ]; then
                POD_NAME=$(kubectl get pods -l app=comfyui -o jsonpath='{.items[0].metadata.name}')
                print_info "Displaying logs for ComfyUI pod: $POD_NAME"
                kubectl logs -f $POD_NAME
            fi
        fi
    else
        print_info "Skipping log display (non-interactive mode or auto-confirm)"
    fi
}

# Display summary
display_summary() {
    echo ""
    print_info "========================================="
    print_info "Deployment Summary"
    print_info "========================================="

    OG_POD=$(kubectl get pods -l app=open-gallery -o jsonpath='{.items[0].metadata.name}')
    OG_STATUS=$(kubectl get pods -l app=open-gallery -o jsonpath='{.items[0].status.phase}')

    print_info "Open Gallery Pod: $OG_POD"
    print_info "Open Gallery Status: $OG_STATUS"

    if [ "$SKIP_COMFYUI" = false ]; then
        COMFY_POD=$(kubectl get pods -l app=comfyui -o jsonpath='{.items[0].metadata.name}')
        COMFY_STATUS=$(kubectl get pods -l app=comfyui -o jsonpath='{.items[0].status.phase}')
        print_info "ComfyUI Pod: $COMFY_POD"
        print_info "ComfyUI Status: $COMFY_STATUS"
        print_info "ComfyUI Mode: S3 (models mounted from S3)"
    fi

    if [ ! -z "$ALB_URL" ]; then
        print_info "Application URL: http://${ALB_URL}"
    else
        print_warn "ALB URL not available yet. Run: kubectl get ingress open-gallery-ingress"
    fi

    # Get ComfyUI internal endpoint
    COMFYUI_ENDPOINT=$(kubectl get svc comfyui-service -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "N/A")
    if [ "$COMFYUI_ENDPOINT" != "N/A" ]; then
        print_info "ComfyUI Internal Endpoint: http://${COMFYUI_ENDPOINT}:8188"
    fi

    print_info "========================================="
    echo ""
    print_info "Useful commands:"
    echo "  View pods:           kubectl get pods"
    echo "  View Open Gallery:   kubectl logs -f $OG_POD"
    if [ "$SKIP_COMFYUI" = false ]; then
        echo "  View ComfyUI logs:   kubectl logs -f $COMFY_POD"
    fi
    echo "  Get ALB URL:         kubectl get ingress open-gallery-ingress"
    echo "  Port forward (OG):   kubectl port-forward svc/open-gallery-service 8080:80"
    if [ "$SKIP_COMFYUI" = false ]; then
        echo "  Port forward (ComfyUI): kubectl port-forward svc/comfyui-service 8188:8188"
    fi
    echo "  Scale Open Gallery:  kubectl scale deployment open-gallery --replicas=3"
    echo ""
}

# Cleanup temporary files
cleanup() {
    print_info "Cleaning up temporary files..."
    cd "${SCRIPT_DIR}/../k8s-manifests" 2>/dev/null || return 0
    rm -f open-gallery-deployment-temp.yaml
    rm -f comfyui-deployment-temp.yaml
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Deploy Open Gallery and ComfyUI (S3 mode) to existing EKS cluster"
    echo ""
    echo "Options:"
    echo "  --skip-comfyui         Skip ComfyUI deployment (deploy only Open Gallery)"
    echo "  --yes, -y              Skip confirmation prompts (for automation)"
    echo "  --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                              # Deploy Open Gallery + ComfyUI (S3 mode)"
    echo "  $0 --skip-comfyui               # Deploy only Open Gallery"
    echo "  $0 --yes                        # Deploy with auto-confirm"
    echo ""
    echo "Note: ComfyUI uses S3 mode only. Models are mounted from S3 bucket."
    echo "      Make sure S3 CSI driver is installed and PV/PVC are configured."
    echo ""
}

# Main execution
main() {
    print_info "Starting deployment to EKS..."

    parse_arguments "$@"
    check_prerequisites
    setup_environment
    update_deployment_manifests
    deploy_configmaps
    deploy_services
    deploy_applications
    wait_for_deployments
    deploy_ingress
    wait_for_alb
    tag_alb_security_groups
    deploy_hpa
    verify_deployment
    display_summary
    display_logs
    cleanup

    print_info "Deployment completed successfully!"
}

# Trap errors and cleanup
trap cleanup EXIT

# Run main function
main "$@"

