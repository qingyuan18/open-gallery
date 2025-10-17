#!/bin/bash

#############################################################################
# Setup Open Gallery Pod Identity for EKS
# 
# This script configures EKS Pod Identity for the Open Gallery application
# to access AWS services (DynamoDB, S3, Bedrock) without hardcoded credentials.
#
# Prerequisites:
# - AWS CLI configured with appropriate permissions
# - kubectl configured to access the EKS cluster
# - EKS cluster with Pod Identity enabled (EKS 1.24+)
#
# Usage:
#   ./setup-open-gallery-pod-identity.sh --cluster-name <name> [--region <region>]
#
#############################################################################

set -e

# Default values
AWS_REGION="us-west-2"
CLUSTER_NAME=""
NAMESPACE="default"
SERVICE_ACCOUNT_NAME="open-gallery-sa"
IAM_ROLE_NAME="OpenGalleryAppRole"
IAM_POLICY_NAME="OpenGalleryAppPolicy"

# Print functions
print_info() {
    echo "[INFO] $1"
}

print_success() {
    echo "[SUCCESS] $1"
}

print_warn() {
    echo "[WARNING] $1"
}

print_error() {
    echo "[ERROR] $1"
}

print_header() {
    echo ""
    echo "==========================================================="
    echo "  $1"
    echo "==========================================================="
    echo ""
}

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
        print_error "Cluster name is required"
        show_usage
        exit 1
    fi
}

show_usage() {
    cat << EOF
Usage: $0 --cluster-name <name> [OPTIONS]

Setup EKS Pod Identity for Open Gallery application.

Required Arguments:
  --cluster-name <name>    EKS cluster name

Optional Arguments:
  --region <region>        AWS region (default: us-west-2)
  --help                   Show this help message

Example:
  $0 --cluster-name hp-eks-03 --region us-west-2

EOF
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install it first."
        exit 1
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        print_error "jq is not installed. Please install it first."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials are not configured. Please run 'aws configure'."
        exit 1
    fi

    # Check kubectl cluster access
    if ! kubectl cluster-info &> /dev/null; then
        print_error "kubectl is not connected to a cluster. Please configure kubectl."
        exit 1
    fi

    print_success "All prerequisites met"
}

# Setup environment
setup_environment() {
    print_info "Setting up environment variables..."

    export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        print_error "Failed to get AWS account ID. Please check your AWS credentials."
        exit 1
    fi

    export IAM_POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${IAM_POLICY_NAME}"
    export IAM_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${IAM_ROLE_NAME}"

    print_info "AWS Account ID: $AWS_ACCOUNT_ID"
    print_info "AWS Region: $AWS_REGION"
    print_info "Cluster Name: $CLUSTER_NAME"
    print_info "Namespace: $NAMESPACE"
    print_info "ServiceAccount: $SERVICE_ACCOUNT_NAME"
    print_info "IAM Role: $IAM_ROLE_NAME"
    print_info "IAM Policy: $IAM_POLICY_NAME"
}

# Create IAM policy
create_iam_policy() {
    print_header "Creating IAM Policy"

    # Navigate to k8s-manifests directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    POLICY_FILE="${SCRIPT_DIR}/../k8s-manifests/open-gallery-iam-policy.json"

    if [ ! -f "$POLICY_FILE" ]; then
        print_error "Policy file not found: $POLICY_FILE"
        exit 1
    fi

    # Check if policy already exists
    if aws iam get-policy --policy-arn ${IAM_POLICY_ARN} &> /dev/null; then
        print_warn "IAM policy '${IAM_POLICY_NAME}' already exists."
        print_info "Updating policy with new version..."
        
        # Create a new policy version
        aws iam create-policy-version \
            --policy-arn ${IAM_POLICY_ARN} \
            --policy-document file://${POLICY_FILE} \
            --set-as-default
        
        print_success "IAM policy updated successfully"
    else
        print_info "Creating IAM policy '${IAM_POLICY_NAME}'..."
        
        aws iam create-policy \
            --policy-name ${IAM_POLICY_NAME} \
            --policy-document file://${POLICY_FILE} \
            --description "Policy for Open Gallery application to access DynamoDB, S3, and Bedrock"
        
        print_success "IAM policy created successfully"
    fi

    print_info "Policy ARN: ${IAM_POLICY_ARN}"
}

# Create IAM role with Pod Identity trust policy
create_iam_role() {
    print_header "Creating IAM Role for Pod Identity"

    # Check if role already exists
    if aws iam get-role --role-name ${IAM_ROLE_NAME} &> /dev/null 2>&1; then
        print_warn "IAM role '${IAM_ROLE_NAME}' already exists."
        
        # Update trust policy to ensure it's correct
        print_info "Updating trust policy..."
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
        
        aws iam update-assume-role-policy \
            --role-name ${IAM_ROLE_NAME} \
            --policy-document file:///tmp/pod-identity-trust-policy.json
        
        rm /tmp/pod-identity-trust-policy.json
        print_success "Trust policy updated"
    else
        print_info "Creating IAM role '${IAM_ROLE_NAME}' with Pod Identity trust policy..."

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
            --role-name ${IAM_ROLE_NAME} \
            --assume-role-policy-document file:///tmp/pod-identity-trust-policy.json \
            --description "Role for Open Gallery pods to access AWS services via EKS Pod Identity"

        rm /tmp/pod-identity-trust-policy.json
        print_success "IAM role created successfully"
    fi

    # Attach policy to role
    print_info "Attaching policy to role..."
    aws iam attach-role-policy \
        --role-name ${IAM_ROLE_NAME} \
        --policy-arn ${IAM_POLICY_ARN} || true

    print_success "Policy attached to role"
    print_info "Role ARN: ${IAM_ROLE_ARN}"
}

# Create Kubernetes ServiceAccount
create_service_account() {
    print_header "Creating Kubernetes ServiceAccount"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SA_FILE="${SCRIPT_DIR}/../k8s-manifests/open-gallery-serviceaccount.yaml"

    if [ ! -f "$SA_FILE" ]; then
        print_error "ServiceAccount file not found: $SA_FILE"
        exit 1
    fi

    # Check if ServiceAccount already exists
    if kubectl get sa ${SERVICE_ACCOUNT_NAME} -n ${NAMESPACE} &> /dev/null; then
        print_warn "ServiceAccount '${SERVICE_ACCOUNT_NAME}' already exists in namespace '${NAMESPACE}'"
        print_info "Applying configuration to ensure it's up to date..."
    else
        print_info "Creating ServiceAccount '${SERVICE_ACCOUNT_NAME}' in namespace '${NAMESPACE}'..."
    fi

    kubectl apply -f ${SA_FILE}
    print_success "ServiceAccount created/updated successfully"
}

# Create Pod Identity Association
create_pod_identity_association() {
    print_header "Creating EKS Pod Identity Association"

    # Check if association already exists
    print_info "Checking for existing Pod Identity associations..."
    
    EXISTING_ASSOCIATIONS=$(aws eks list-pod-identity-associations \
        --cluster-name ${CLUSTER_NAME} \
        --namespace ${NAMESPACE} \
        --service-account ${SERVICE_ACCOUNT_NAME} \
        --region ${AWS_REGION} \
        --query 'associations[*].associationId' \
        --output text 2>/dev/null || echo "")

    if [ -n "$EXISTING_ASSOCIATIONS" ]; then
        print_warn "Pod Identity association(s) already exist for this ServiceAccount"
        
        for ASSOC_ID in $EXISTING_ASSOCIATIONS; do
            print_info "Deleting existing association: $ASSOC_ID"
            aws eks delete-pod-identity-association \
                --cluster-name ${CLUSTER_NAME} \
                --association-id ${ASSOC_ID} \
                --region ${AWS_REGION}
        done
        
        print_info "Waiting for deletion to complete..."
        sleep 5
    fi

    print_info "Creating new Pod Identity association..."
    
    ASSOCIATION_ID=$(aws eks create-pod-identity-association \
        --cluster-name ${CLUSTER_NAME} \
        --namespace ${NAMESPACE} \
        --service-account ${SERVICE_ACCOUNT_NAME} \
        --role-arn ${IAM_ROLE_ARN} \
        --region ${AWS_REGION} \
        --query 'association.associationId' \
        --output text)

    print_success "Pod Identity association created successfully"
    print_info "Association ID: ${ASSOCIATION_ID}"
}

# Verify setup
verify_setup() {
    print_header "Verifying Setup"

    # Check IAM policy
    print_info "Checking IAM policy..."
    if aws iam get-policy --policy-arn ${IAM_POLICY_ARN} &> /dev/null; then
        print_success "IAM policy exists"
    else
        print_error "IAM policy not found"
        return 1
    fi

    # Check IAM role
    print_info "Checking IAM role..."
    if aws iam get-role --role-name ${IAM_ROLE_NAME} &> /dev/null; then
        print_success "IAM role exists"
    else
        print_error "IAM role not found"
        return 1
    fi

    # Check ServiceAccount
    print_info "Checking Kubernetes ServiceAccount..."
    if kubectl get sa ${SERVICE_ACCOUNT_NAME} -n ${NAMESPACE} &> /dev/null; then
        print_success "ServiceAccount exists"
    else
        print_error "ServiceAccount not found"
        return 1
    fi

    # Check Pod Identity association
    print_info "Checking Pod Identity association..."
    ASSOC_COUNT=$(aws eks list-pod-identity-associations \
        --cluster-name ${CLUSTER_NAME} \
        --namespace ${NAMESPACE} \
        --service-account ${SERVICE_ACCOUNT_NAME} \
        --region ${AWS_REGION} \
        --query 'length(associations)' \
        --output text 2>/dev/null || echo "0")

    if [ "$ASSOC_COUNT" -gt 0 ]; then
        print_success "Pod Identity association exists"
    else
        print_error "Pod Identity association not found"
        return 1
    fi

    print_success "All components verified successfully!"
}

# Print next steps
print_next_steps() {
    print_header "Setup Complete!"

    cat << EOF
${GREEN}✓${NC} Open Gallery Pod Identity has been configured successfully!

${BLUE}Next Steps:${NC}

1. ${YELLOW}Deploy/Update Open Gallery:${NC}
   cd deploy
   kubectl apply -f k8s-manifests/open-gallery-serviceaccount.yaml
   kubectl apply -f k8s-manifests/open-gallery-deployment.yaml

2. ${YELLOW}Restart the deployment to apply changes:${NC}
   kubectl rollout restart deployment/open-gallery -n ${NAMESPACE}

3. ${YELLOW}Verify the Pod is using the ServiceAccount:${NC}
   kubectl get pods -l app=open-gallery -n ${NAMESPACE} -o yaml | grep serviceAccountName

4. ${YELLOW}Check Pod logs for successful AWS authentication:${NC}
   kubectl logs -f deployment/open-gallery -n ${NAMESPACE}

5. ${YELLOW}Test DynamoDB access from within the Pod:${NC}
   POD=\$(kubectl get pods -l app=open-gallery -n ${NAMESPACE} -o jsonpath='{.items[0].metadata.name}')
   kubectl exec -it \$POD -- python3 -c "import boto3; print(boto3.client('dynamodb', region_name='${AWS_REGION}').list_tables())"

${BLUE}Resources Created:${NC}
  • IAM Policy: ${IAM_POLICY_ARN}
  • IAM Role: ${IAM_ROLE_ARN}
  • ServiceAccount: ${NAMESPACE}/${SERVICE_ACCOUNT_NAME}
  • Pod Identity Association: Linked to cluster ${CLUSTER_NAME}

${BLUE}Permissions Granted:${NC}
  • DynamoDB: Full access to jaaz-* tables
  • S3: Read/write access to open-gallery-files-bucket-687912291502
  • Bedrock: Model invocation permissions

${YELLOW}Note:${NC} Pods must be restarted after ServiceAccount changes to receive AWS credentials.

EOF
}

# Main execution
main() {
    print_header "Open Gallery Pod Identity Setup"

    parse_arguments "$@"
    check_prerequisites
    setup_environment
    create_iam_policy
    create_iam_role
    create_service_account
    create_pod_identity_association
    verify_setup
    print_next_steps
}

# Run main function
main "$@"

