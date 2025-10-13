#!/bin/bash

# Docker Build and Push Script for Open Gallery and ComfyUI
# This script builds Docker images and pushes them to Amazon ECR
#
# Usage:
#   ./build-and-push.sh [OPTIONS]
#
# Options:
#   --app <name>          Application to build: open-gallery, comfyui-s3, all (default: all)
#   --tag <tag>           Image tag (default: latest)
#   --region <region>     AWS region (default: us-west-2)
#   --help                Show this help message

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

# Check if required tools are installed
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install AWS CLI first."
        exit 1
    fi
    
    print_info "All prerequisites are met."
}

# Parse command line arguments
parse_arguments() {
    APP_TO_BUILD="all"
    IMAGE_TAG="latest"
    AWS_REGION="us-west-2"

    while [[ $# -gt 0 ]]; do
        case $1 in
            --app)
                APP_TO_BUILD="$2"
                shift 2
                ;;
            --tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            --region)
                AWS_REGION="$2"
                shift 2
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

    # Validate app name
    if [[ ! "$APP_TO_BUILD" =~ ^(open-gallery|comfyui-s3|all)$ ]]; then
        print_error "Invalid app name: $APP_TO_BUILD"
        print_error "Valid options: open-gallery, comfyui-s3, all"
        exit 1
    fi
}

# Set environment variables
setup_environment() {
    print_info "Setting up environment variables..."

    # Get AWS account ID
    export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        print_error "Failed to get AWS account ID. Please check your AWS credentials."
        exit 1
    fi

    export ECR_REGISTRY=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

    print_info "AWS Account ID: $AWS_ACCOUNT_ID"
    print_info "AWS Region: $AWS_REGION"
    print_info "Image Tag: $IMAGE_TAG"
    print_info "App to Build: $APP_TO_BUILD"
}

# Create ECR repository if it doesn't exist
create_ecr_repo() {
    local repo_name=$1
    print_info "Checking if ECR repository '${repo_name}' exists..."

    if aws ecr describe-repositories --repository-names ${repo_name} --region ${AWS_REGION} &> /dev/null; then
        print_info "ECR repository '${repo_name}' already exists."
    else
        print_info "Creating ECR repository '${repo_name}'..."
        aws ecr create-repository \
            --repository-name ${repo_name} \
            --region ${AWS_REGION} \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256
        print_info "ECR repository '${repo_name}' created successfully."
    fi
}

# Authenticate Docker to ECR
authenticate_docker() {
    print_info "Authenticating Docker to ECR..."
    
    aws ecr get-login-password --region ${AWS_REGION} | \
        docker login --username AWS --password-stdin ${ECR_REGISTRY}
    
    if [ $? -eq 0 ]; then
        print_info "Docker authentication successful."
    else
        print_error "Docker authentication failed."
        exit 1
    fi
}

# Build Docker image
build_image() {
    local app_name=$1
    local dockerfile=$2
    local repo_name=$3
    local context_dir=$4

    print_info "Building ${app_name} Docker image..."

    if [ "$app_name" == "comfyui-s3" ]; then
        print_info "Building ComfyUI S3 version (models will be mounted from S3 at runtime)..."
    fi

    # Navigate to appropriate directory
    cd "$(dirname "$0")/.."

    # Build the image
    docker build \
        -f ${dockerfile} \
        -t ${repo_name}:${IMAGE_TAG} \
        -t ${repo_name}:latest \
        --progress=plain \
        ${context_dir}

    if [ $? -eq 0 ]; then
        print_info "${app_name} Docker image built successfully."
    else
        print_error "${app_name} Docker build failed."
        exit 1
    fi
}

# Tag image for ECR
tag_image() {
    local repo_name=$1
    print_info "Tagging ${repo_name} image for ECR..."

    docker tag ${repo_name}:${IMAGE_TAG} ${ECR_REGISTRY}/${repo_name}:${IMAGE_TAG}
    docker tag ${repo_name}:${IMAGE_TAG} ${ECR_REGISTRY}/${repo_name}:latest

    print_info "Image tagged successfully."
}

# Push image to ECR
push_image() {
    local repo_name=$1
    print_info "Pushing ${repo_name} image to ECR..."

    docker push ${ECR_REGISTRY}/${repo_name}:${IMAGE_TAG}
    docker push ${ECR_REGISTRY}/${repo_name}:latest

    if [ $? -eq 0 ]; then
        print_info "${repo_name} image pushed successfully."
    else
        print_error "${repo_name} image push failed."
        exit 1
    fi
}

# Build and push a single app
build_and_push_app() {
    local app_name=$1
    local dockerfile=$2
    local repo_name=$3
    local context_dir=$4

    print_info "========================================="
    print_info "Building and pushing: ${app_name}"
    print_info "========================================="

    create_ecr_repo ${repo_name}
    build_image ${app_name} ${dockerfile} ${repo_name} ${context_dir}
    tag_image ${repo_name}
    push_image ${repo_name}

    echo ""
}

# Display summary
display_summary() {
    echo ""
    print_info "========================================="
    print_info "Build and Push Summary"
    print_info "========================================="

    if [ "$APP_TO_BUILD" == "all" ] || [ "$APP_TO_BUILD" == "open-gallery" ]; then
        print_info "Open Gallery: ${ECR_REGISTRY}/open-gallery:${IMAGE_TAG}"
    fi

    if [ "$APP_TO_BUILD" == "all" ] || [ "$APP_TO_BUILD" == "comfyui-s3" ]; then
        print_info "ComfyUI (S3): ${ECR_REGISTRY}/comfyui-s3:${IMAGE_TAG}"
    fi

    print_info "========================================="
    echo ""
    print_info "Next steps:"
    echo "  1. Deploy to EKS using: ./scripts/deploy-to-eks.sh"
    echo "  2. Or manually: kubectl apply -f k8s-manifests/"
    echo ""
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Build and push Docker images to Amazon ECR"
    echo ""
    echo "Options:"
    echo "  --app <name>      Application to build (default: all)"
    echo "                    Options: open-gallery, comfyui-s3, all"
    echo "  --tag <tag>       Image tag (default: latest)"
    echo "  --region <region> AWS region (default: us-west-2)"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Build all images"
    echo "  $0 --app open-gallery                 # Build only open-gallery"
    echo "  $0 --app comfyui-s3                   # Build ComfyUI S3 version"
    echo "  $0 --app comfyui-s3 --tag v1.0        # Build ComfyUI S3 with tag v1.0"
    echo ""
    echo "Note: ComfyUI uses S3 mode only. Models are mounted from S3 at runtime."
    echo ""
}

# Main execution
main() {
    print_info "Starting Docker build and push process..."

    parse_arguments "$@"
    check_prerequisites
    setup_environment
    authenticate_docker

    # Navigate to project root
    cd "$(dirname "$0")/../.."
    PROJECT_ROOT=$(pwd)

    # Build based on selection
    if [ "$APP_TO_BUILD" == "all" ] || [ "$APP_TO_BUILD" == "open-gallery" ]; then
        build_and_push_app "open-gallery" \
            "deploy/open-gallery.dockerfile" \
            "open-gallery" \
            "."
    fi

    if [ "$APP_TO_BUILD" == "all" ] || [ "$APP_TO_BUILD" == "comfyui-s3" ]; then
        build_and_push_app "comfyui-s3" \
            "deploy/comfyui-s3.dockerfile" \
            "comfyui-s3" \
            "."
    fi

    display_summary

    print_info "Process completed successfully!"
}

# Run main function
main "$@"

