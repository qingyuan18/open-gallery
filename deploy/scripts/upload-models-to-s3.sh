#!/bin/bash

# Upload Models to S3 Script for ComfyUI
# This script downloads and uploads all required models to S3 bucket
# Based on the models defined in comfyui-embedded.dockerfile
#
# Usage:
#   ./upload-models-to-s3.sh [OPTIONS]
#
# Options:
#   --bucket <name>       S3 bucket name (required)
#   --region <region>     AWS region (default: us-west-2)
#   --temp-dir <path>     Temporary directory for downloads (default: /tmp/comfyui-models)
#   --parallel <num>      Number of parallel downloads (default: 4)
#   --skip-existing       Skip files that already exist in S3
#   --dry-run             Show what would be uploaded without actually uploading
#   --yes, -y             Skip confirmation prompt (useful for automation/nohup)
#   --help                Show this help message

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
S3_BUCKET=""
AWS_REGION="us-west-2"
TEMP_DIR="/tmp/comfyui-models"
PARALLEL_DOWNLOADS=4
SKIP_EXISTING=false
DRY_RUN=false
AUTO_CONFIRM=false

# Check if required tools are installed
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install AWS CLI first."
        exit 1
    fi
    
    if ! command -v wget &> /dev/null; then
        print_error "wget is not installed. Please install wget first."
        exit 1
    fi
    
    if ! command -v parallel &> /dev/null; then
        print_warn "GNU parallel is not installed. Falling back to sequential downloads."
        PARALLEL_DOWNLOADS=1
    fi
    
    print_info "All prerequisites are met."
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --bucket)
                S3_BUCKET="$2"
                shift 2
                ;;
            --region)
                AWS_REGION="$2"
                shift 2
                ;;
            --temp-dir)
                TEMP_DIR="$2"
                shift 2
                ;;
            --parallel)
                PARALLEL_DOWNLOADS="$2"
                shift 2
                ;;
            --skip-existing)
                SKIP_EXISTING=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
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

    # Validate required parameters
    if [ -z "$S3_BUCKET" ]; then
        print_error "S3 bucket name is required. Use --bucket option."
        show_usage
        exit 1
    fi
}

# Set environment variables
setup_environment() {
    print_info "Setting up environment..."

    # Get AWS account ID for validation
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        print_error "Failed to get AWS account ID. Please check your AWS credentials."
        exit 1
    fi

    print_info "AWS Account ID: $AWS_ACCOUNT_ID"
    print_info "AWS Region: $AWS_REGION"
    print_info "S3 Bucket: $S3_BUCKET"
    print_info "Temp Directory: $TEMP_DIR"
    print_info "Parallel Downloads: $PARALLEL_DOWNLOADS"
    print_info "Skip Existing: $SKIP_EXISTING"
    print_info "Dry Run: $DRY_RUN"
}

# Create temporary directory structure
setup_temp_directory() {
    print_info "Setting up temporary directory structure..."
    
    mkdir -p "$TEMP_DIR"
    mkdir -p "$TEMP_DIR/models/text_encoders"
    mkdir -p "$TEMP_DIR/models/diffusion_models"
    mkdir -p "$TEMP_DIR/models/vae"
    mkdir -p "$TEMP_DIR/models/clip"
    mkdir -p "$TEMP_DIR/models/clip_vision"
    mkdir -p "$TEMP_DIR/models/loras"
    mkdir -p "$TEMP_DIR/models/unet"
    
    print_info "Temporary directory structure created at: $TEMP_DIR"
}

# Check if file exists in S3
check_s3_file_exists() {
    local s3_path="$1"
    aws s3 ls "s3://${S3_BUCKET}/${s3_path}" --region "$AWS_REGION" &> /dev/null
}

# Download a single model file
download_model() {
    local url="$1"
    local local_path="$2"
    local s3_path="$3"

    print_info "Processing: $(basename "$local_path")"

    # Check if file already exists in S3 and skip if requested
    if [ "$SKIP_EXISTING" = true ] && check_s3_file_exists "$s3_path"; then
        print_info "Skipping $(basename "$local_path") - already exists in S3"
        return 0
    fi

    # Check if file already exists locally
    if [ -f "$local_path" ]; then
        print_info "File already exists locally: $(basename "$local_path")"
    else
        print_info "Downloading: $(basename "$local_path")"
        wget -q --show-progress --timeout=300 --tries=3 "$url" -O "$local_path"
        local download_result=$?
        if [ $download_result -ne 0 ]; then
            print_error "Failed to download: $url (exit code: $download_result)"
            return 1
        fi
    fi

    # Upload to S3 (unless dry run)
    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would upload: $local_path -> s3://${S3_BUCKET}/${s3_path}"
    else
        print_info "Uploading to S3: $(basename "$local_path")"
        aws s3 cp "$local_path" "s3://${S3_BUCKET}/${s3_path}" --region "$AWS_REGION"
        local upload_result=$?
        if [ $upload_result -ne 0 ]; then
            print_error "Failed to upload: $local_path (exit code: $upload_result)"
            return 1
        fi
        print_debug "Successfully uploaded: $(basename "$local_path")"
    fi

    # Clean up local file to save space (only the individual file, not the directory)
    if [ "$DRY_RUN" = false ] && [ -f "$local_path" ]; then
        rm -f "$local_path" 2>/dev/null || print_warn "Failed to clean up local file: $local_path"
        print_debug "Cleaned up local file: $local_path"
    fi

    print_debug "download_model completed successfully for: $(basename "$local_path")"
    return 0
}

# Define all models to download and upload
define_models() {
    # Clear any existing model definitions
    unset MODEL_URLS
    unset LOCAL_PATHS  
    unset S3_PATHS
    
    declare -g -a MODEL_URLS
    declare -g -a LOCAL_PATHS
    declare -g -a S3_PATHS
    
    # Text Encoders
    MODEL_URLS+=("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/text_encoders/umt5_xxl_fp16.safetensors")
    S3_PATHS+=("models/text_encoders/umt5-xxl-enc-bf16.safetensors")

    MODEL_URLS+=("https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/text_encoders/t5xxl_fp8_e4m3fn.safetensors")
    S3_PATHS+=("models/text_encoders/t5xxl_fp8_e4m3fn.safetensors")

    # CLIP Models
    MODEL_URLS+=("https://huggingface.co/openai/clip-vit-large-patch14/resolve/main/model.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/clip/clip_l.safetensors")
    S3_PATHS+=("models/clip/clip_l.safetensors")


    MODEL_URLS+=("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/clip/qwen_2.5_vl_7b_fp8_scaled.safetensors")
    S3_PATHS+=("models/clip/qwen_2.5_vl_7b_fp8_scaled.safetensors")
    

    # Diffusion Models
    MODEL_URLS+=("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_14B_fp8_e4m3fn.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/diffusion_models/wan2.1_t2v_14B_fp8_e4m3fn.safetensors")
    S3_PATHS+=("models/diffusion_models/wan2.1_t2v_14B_fp8_e4m3fn.safetensors")

    MODEL_URLS+=("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors")
    S3_PATHS+=("models/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors")

    MODEL_URLS+=("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors")
    S3_PATHS+=("models/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors")
    

    MODEL_URLS+=("https://huggingface.co/Comfy-Org/flux1-kontext-dev_ComfyUI/resolve/main/split_files/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors")
    S3_PATHS+=("models/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors")

    MODEL_URLS+=("https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/diffusion_models/flux1-dev-fp8.safetensors")
    S3_PATHS+=("models/diffusion_models/flux1-dev-fp8.safetensors")

    MODEL_URLS+=("https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2509_fp8_e4m3fn.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/diffusion_models/qwen_image_edit_2509_fp8_e4m3fn.safetensors")
    S3_PATHS+=("models/diffusion_models/qwen_image_edit_2509_fp8_e4m3fn.safetensors")

    # VAE Models
    MODEL_URLS+=("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/vae/Wan2_1_VAE_bf16.safetensors")
    S3_PATHS+=("models/vae/Wan2_1_VAE_bf16.safetensors")

    MODEL_URLS+=("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/vae/wan2.2_vae.safetensors")
    S3_PATHS+=("models/vae/wan2.2_vae.safetensors")

    MODEL_URLS+=("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/vae/wan_2.1_vae.safetensors")
    S3_PATHS+=("models/vae/wan_2.1_vae.safetensors")

    MODEL_URLS+=("https://huggingface.co/alibaba-pai/Wan2.2-Fun-A14B-InP/resolve/main/Wan2.1_VAE.pth")
    LOCAL_PATHS+=("$TEMP_DIR/models/vae/Wan2_1_VAE_fp32.safetensors")
    S3_PATHS+=("models/vae/Wan2_1_VAE_fp32.safetensors")

    MODEL_URLS+=("https://huggingface.co/modelzpalace/ae.safetensors/resolve/main/ae.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/vae/ae.safetensors")
    S3_PATHS+=("models/vae/ae.safetensors")

    MODEL_URLS+=("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/vae/qwen_image_vae.safetensors")
    S3_PATHS+=("models/vae/qwen_image_vae.safetensors")

    # LoRA Models
    MODEL_URLS+=("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.1.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/loras/Qwen-Image-Lightning-8steps-V1.1.safetensors")
    S3_PATHS+=("models/loras/Qwen-Image-Lightning-8steps-V1.1.safetensors")

    MODEL_URLS+=("https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/loras/Wan2.2_I2V_14B_lightx2v_lora_high.safetensors")
    S3_PATHS+=("models/loras/Wan2.2_I2V_14B_lightx2v_lora_high.safetensors")

    MODEL_URLS+=("https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/loras/Wan2.2_I2V_14B_lightx2v_lora_low.safetensors")
    S3_PATHS+=("models/loras/Wan2.2_I2V_14B_lightx2v_lora_low.safetensors")

    MODEL_URLS+=("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors")
    S3_PATHS+=("models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors")

    MODEL_URLS+=("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors")
    LOCAL_PATHS+=("$TEMP_DIR/models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors")
    S3_PATHS+=("models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors")
}

# Process all models
process_models() {
    print_info "Starting model processing..."

    local total_models=${#MODEL_URLS[@]}
    local failed_downloads=0
    local successful_uploads=0

    print_info "Total models to process: $total_models"

    # Process models sequentially or in parallel
    if [ "$PARALLEL_DOWNLOADS" -gt 1 ] && command -v parallel &> /dev/null; then
        print_info "Processing models in parallel (max $PARALLEL_DOWNLOADS concurrent downloads)..."

        # Create a temporary file for parallel processing
        local temp_script=$(mktemp)
        cat > "$temp_script" << 'EOF'
#!/bin/bash
source "$(dirname "$0")/upload-models-to-s3.sh"
download_model "$1" "$2" "$3"
EOF
        chmod +x "$temp_script"

        # Export functions for parallel
        export -f download_model check_s3_file_exists print_info print_error print_debug
        export S3_BUCKET AWS_REGION DRY_RUN SKIP_EXISTING

        # Process in parallel
        for i in "${!MODEL_URLS[@]}"; do
            echo "${MODEL_URLS[$i]} ${LOCAL_PATHS[$i]} ${S3_PATHS[$i]}"
        done | parallel -j "$PARALLEL_DOWNLOADS" --colsep ' ' "$temp_script" {1} {2} {3}

        rm "$temp_script"
    else
        print_info "Processing models sequentially..."

        for i in "${!MODEL_URLS[@]}"; do
            local current=$((i + 1))
            print_info "========================================="
            print_info "Processing model $current/$total_models"
            print_info "========================================="

            download_model "${MODEL_URLS[$i]}" "${LOCAL_PATHS[$i]}" "${S3_PATHS[$i]}"
            local result=$?

            if [ $result -eq 0 ]; then
                ((successful_uploads++))
                print_info "✓ Model $current/$total_models completed successfully"
            else
                ((failed_downloads++))
                print_error "✗ Failed to process model: $(basename "${LOCAL_PATHS[$i]}")"
            fi

            print_debug "Continuing to next model..."
        done

        print_info "========================================="
        print_info "All models processed"
        print_info "========================================="
    fi

    print_info "Model processing completed."
    print_info "Successful uploads: $successful_uploads"
    if [ $failed_downloads -gt 0 ]; then
        print_warn "Failed downloads: $failed_downloads"
    fi
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

# Display summary of what will be uploaded
display_summary() {
    print_info "========================================="
    print_info "Upload Summary"
    print_info "========================================="
    print_info "S3 Bucket: $S3_BUCKET"
    print_info "AWS Region: $AWS_REGION"
    print_info "Total Models: ${#MODEL_URLS[@]}"
    print_info "Temp Directory: $TEMP_DIR"

    if [ "$DRY_RUN" = true ]; then
        print_warn "DRY RUN MODE - No files will be uploaded"
    fi

    if [ "$SKIP_EXISTING" = true ]; then
        print_info "Skip existing files: Enabled"
    fi

    echo ""
    print_info "Model categories:"
    print_info "  - Text Encoders: $(echo "${S3_PATHS[@]}" | tr ' ' '\n' | grep -c "models/wan/umt5\|models/flux/t5xxl")"
    print_info "  - CLIP Models: $(echo "${S3_PATHS[@]}" | tr ' ' '\n' | grep -c "clip")"
    print_info "  - Diffusion Models: $(echo "${S3_PATHS[@]}" | tr ' ' '\n' | grep -c "diffusion_models\|unet\|flux1-dev\|qwen_image_edit")"
    print_info "  - VAE Models: $(echo "${S3_PATHS[@]}" | tr ' ' '\n' | grep -c "vae")"
    print_info "  - LoRA Models: $(echo "${S3_PATHS[@]}" | tr ' ' '\n' | grep -c "loras")"
    print_info "========================================="
    echo ""
}

# Cleanup function - only called at the very end
cleanup() {
    # Only cleanup if we're actually exiting
    if [ -d "$TEMP_DIR" ] && [ "$TEMP_DIR" != "/" ]; then
        print_info "Cleaning up temporary directory: $TEMP_DIR"
        rm -rf "$TEMP_DIR" 2>/dev/null || true
        print_info "Temporary directory cleaned up"
    fi
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Download and upload ComfyUI models to S3 bucket"
    echo ""
    echo "Options:"
    echo "  --bucket <name>       S3 bucket name (required)"
    echo "  --region <region>     AWS region (default: us-west-2)"
    echo "  --temp-dir <path>     Temporary directory for downloads (default: /tmp/comfyui-models)"
    echo "  --parallel <num>      Number of parallel downloads (default: 4)"
    echo "  --skip-existing       Skip files that already exist in S3"
    echo "  --dry-run             Show what would be uploaded without actually uploading"
    echo "  --yes, -y             Skip confirmation prompt (for automation/nohup)"
    echo "  --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --bucket my-comfyui-models                    # Upload all models"
    echo "  $0 --bucket my-bucket --skip-existing            # Skip existing files"
    echo "  $0 --bucket my-bucket --dry-run                  # Preview what would be uploaded"
    echo "  $0 --bucket my-bucket --parallel 8               # Use 8 parallel downloads"
    echo "  $0 --bucket my-bucket --yes                      # Auto-confirm (for nohup)"
    echo ""
    echo "For background execution with nohup:"
    echo "  nohup $0 --bucket my-bucket --yes > upload.log 2>&1 &"
    echo ""
    echo "Note: This script will download ~50-100GB of models and upload them to S3."
    echo "      Make sure you have sufficient disk space and network bandwidth."
    echo ""
}

# Main execution
main() {
    print_info "Starting ComfyUI Models S3 Upload Process..."

    # Set up trap for cleanup
    trap cleanup EXIT

    parse_arguments "$@"
    check_prerequisites
    setup_environment
    verify_s3_access
    setup_temp_directory
    define_models
    display_summary

    # Ask for confirmation unless dry run or auto-confirm
    if [ "$DRY_RUN" = false ] && [ "$AUTO_CONFIRM" = false ]; then
        echo ""
        # Check if stdin is available (not running in nohup/background)
        if [ -t 0 ]; then
            read -p "Do you want to proceed with downloading and uploading ${#MODEL_URLS[@]} models? (y/N): " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_info "Operation cancelled by user."
                exit 0
            fi
        else
            print_warn "Running in non-interactive mode (stdin not available)"
            print_warn "Use --yes or -y flag to auto-confirm, or run interactively"
            print_error "Cannot proceed without confirmation"
            exit 1
        fi
    elif [ "$AUTO_CONFIRM" = true ]; then
        print_info "Auto-confirm enabled, proceeding with upload..."
    fi

    # Process all models
    process_models

    print_info "========================================="
    print_info "Upload Process Completed Successfully!"
    print_info "========================================="

    if [ "$DRY_RUN" = false ]; then
        print_info "All models have been uploaded to: s3://${S3_BUCKET}/"
        print_info ""
        print_info "Next steps:"
        print_info "  1. Update your S3 PV/PVC configuration to use bucket: $S3_BUCKET"
        print_info "  2. Deploy ComfyUI with S3 mount: ./scripts/deploy-to-eks.sh --app comfyui-s3"
        print_info "  3. Verify models are accessible in the ComfyUI pods"
    else
        print_info "Dry run completed. Use --dry-run=false to actually upload the models."
    fi

    echo ""
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
