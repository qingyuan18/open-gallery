# ComfyUI Dockerfile - Embedded Models Version
# This version includes all models embedded in the Docker image
# Image size: ~50-100GB
# Use this for: Development, testing, or when S3 access is not available

FROM nvcr.io/nvidia/pytorch:23.05-py3

# Create directory structure
RUN mkdir -p /opt/program
RUN mkdir -p /opt/program/models/text_encoders/
RUN mkdir -p /opt/program/models/diffusion_models/
RUN mkdir -p /opt/program/models/vae/
RUN mkdir -p /opt/program/models/clip/
RUN mkdir -p /opt/program/models/clip_vision/
RUN mkdir -p /opt/program/models/loras/
RUN mkdir -p /opt/program/models/unet/
RUN mkdir -p /opt/program/custom_nodes/
RUN chmod -R 777 /opt/program

# Install git and basic dependencies
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi uvicorn sagemaker
RUN pip install sagemaker-ssh-helper
RUN curl -L https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz | tar -xz && mv s5cmd /opt/program/

ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE
ENV PATH="/opt/program:${PATH}"

####install ComfyUI
# Clone ComfyUI from official repository
WORKDIR /opt/program
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /tmp/comfyui && \
    cp -r /tmp/comfyui/* /opt/program/ && \
    rm -rf /tmp/comfyui

RUN pip install -r /opt/program/requirements.txt

# Install core dependencies
RUN pip install -U xformers==0.0.27 --no-deps
RUN pip install scikit-image
RUN pip install imageio_ffmpeg
RUN pip install wget
RUN pip install retry
RUN pip install blend_modes
RUN pip install transparent_background
RUN pip install GitPython

# Install system packages
RUN apt-get update && apt-get install -y ffmpeg libgl1-mesa-glx

###############################################################################
# DOWNLOAD MODELS SECTION
###############################################################################

### Text Encoders ###
# UMT5 encoders for Wan Video
RUN wget https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors \
    -O /opt/program/models/text_encoders/umt5-xxl-enc-bf16.safetensors

RUN wget https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-fp8_e4m3fn.safetensors \
    -O /opt/program/models/text_encoders/umt5-xxl-enc-fp8_e4m3fn.safetensors

RUN wget https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
    -O /opt/program/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors

### CLIP Models ###
# CLIP for Wan Video
RUN wget https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/open-clip-xlm-roberta-large-vit-huge-14_fp16.safetensors \
    -O /opt/program/models/clip/open-clip-xlm-roberta-large-vit-huge-14_fp16.safetensors

# CLIP for FLUX
RUN wget https://huggingface.co/openai/clip-vit-large-patch14/resolve/main/model.safetensors \
    -O /opt/program/models/clip/clip_l.safetensors

# T5XXL for FLUX
RUN wget https://huggingface.co/fmoraes2k/t5xxl_fp8_e4m3fn.safetensors/resolve/main/t5xxl_fp8_e4m3fn.safetensors \
    -O /opt/program/models/clip/t5xxl_fp8_e4m3fn.safetensors

# Qwen CLIP
RUN wget https://huggingface.co/Qwen/Qwen2.5-VL-7B/resolve/main/model.safetensors \
    -O /opt/program/models/clip/qwen_2.5_vl_7b_fp8_scaled.safetensors || echo "Qwen CLIP model download failed, will use S3 fallback"

### Diffusion Models ###
# Wan Video 2.1 models
RUN wget https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-I2V-14B-720P_fp8_e4m3fn.safetensors \
    -O /opt/program/models/diffusion_models/Wan2_1-I2V-14B-720P_fp8_e4m3fn.safetensors

RUN wget https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-T2V-14B_fp8_e4m3fn.safetensors \
    -O /opt/program/models/diffusion_models/Wan2_1-T2V-14B_fp8_e4m3fn.safetensors

# Wan Video 2.2 Animate model
RUN wget https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors \
    -O /opt/program/models/diffusion_models/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors || echo "Wan 2.2 Animate model download failed, will use S3 fallback"

# Wan Video 2.2 Inpaint models
RUN wget https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_fun_inpaint_high_noise_14B_fp8_scaled.safetensors \
    -O /opt/program/models/diffusion_models/wan2.2_fun_inpaint_high_noise_14B_fp8_scaled.safetensors

RUN wget https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_fun_inpaint_low_noise_14B_fp8_scaled.safetensors \
    -O /opt/program/models/diffusion_models/wan2.2_fun_inpaint_low_noise_14B_fp8_scaled.safetensors

# FLUX Kontext model
RUN wget https://huggingface.co/Comfy-Org/flux1-kontext-dev_ComfyUI/resolve/main/split_files/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors \
    -O /opt/program/models/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors

# FLUX Dev UNET
RUN wget https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8-unet.safetensors \
    -O /opt/program/models/diffusion_models/flux1-dev-fp8-unet.safetensors || echo "FLUX dev unet download failed, will use S3 fallback"

# Qwen Image Edit model
RUN wget https://huggingface.co/Qwen/Qwen-Image-Edit/resolve/main/qwen_image_edit_2509_fp8_e4m3fn.safetensors \
    -O /opt/program/models/diffusion_models/qwen_image_edit_2509_fp8_e4m3fn.safetensors || echo "Qwen Image Edit model download failed, will use S3 fallback"

### VAE Models ###
# Wan Video VAE models
RUN wget https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors \
    -O /opt/program/models/vae/Wan2_1_VAE_bf16.safetensors

RUN wget https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors \
    -O /opt/program/models/vae/wan2.2_vae.safetensors

RUN wget https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors \
    -O /opt/program/models/vae/wan_2.1_vae.safetensors

RUN wget https://huggingface.co/alibaba-pai/Wan2.2-Fun-A14B-InP/resolve/main/Wan2.1_VAE.pth \
    -O /opt/program/models/vae/Wan2_1_VAE_fp32.safetensors

# FLUX VAE
RUN wget https://huggingface.co/modelzpalace/ae.safetensors/resolve/main/ae.safetensors \
    -O /opt/program/models/vae/ae.safetensors

# Qwen Image VAE
RUN wget https://huggingface.co/Qwen/Qwen-Image/resolve/main/qwen_image_vae.safetensors \
    -O /opt/program/models/vae/qwen_image_vae.safetensors || echo "Qwen Image VAE download failed, will use S3 fallback"

### LoRA Models ###
# Qwen Image Lightning LoRA
RUN wget https://huggingface.co/Qwen/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.1.safetensors \
    -O /opt/program/models/loras/Qwen-Image-Lightning-8steps-V1.1.safetensors || echo "Qwen Lightning LoRA download failed, will use S3 fallback"

# Wan Video 2.1 LoRAs
RUN wget https://huggingface.co/Wan-AI/Wan2.1-T2V-14B-FusionX/resolve/main/Wan2.1_T2V_14B_FusionX_LoRA.safetensors \
    -O /opt/program/models/loras/Wan2.1_T2V_14B_FusionX_LoRA.safetensors || echo "Wan 2.1 FusionX LoRA download failed, will use S3 fallback"

RUN wget https://huggingface.co/lightx2v/Wan2.1-Lightning/resolve/main/Wan21_I2V_14B_lightx2v_cfg_step_distill_lora_rank64.safetensors \
    -O /opt/program/models/loras/Wan21_I2V_14B_lightx2v_cfg_step_distill_lora_rank64.safetensors || echo "Wan 2.1 Lightning LoRA download failed, will use S3 fallback"

# Wan Video 2.2 LoRAs
RUN wget https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/relighting_lora.ckpt \
    -O /opt/program/models/loras/relighting_lora.ckpt

RUN wget https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors \
    -O /opt/program/models/loras/Wan2.2_I2V_14B_lightx2v_lora_high.safetensors

RUN wget https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors \
    -O /opt/program/models/loras/Wan2.2_I2V_14B_lightx2v_lora_low.safetensors

RUN wget https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors \
    -O /opt/program/models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors

RUN wget https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors \
    -O /opt/program/models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors

###############################################################################
# INSTALL CUSTOM NODES SECTION
###############################################################################

### Core Custom Nodes ###
# ComfyUI Manager
RUN git clone https://github.com/ltdrdata/ComfyUI-Manager.git /opt/program/custom_nodes/ComfyUI-Manager && \
    cd /opt/program/custom_nodes/ComfyUI-Manager && \
    pip install -r requirements.txt

# WAS Node Suite
RUN git clone https://github.com/WASasquatch/was-node-suite-comfyui /opt/program/custom_nodes/was-node-suite-comfyui

# Tooling Nodes
RUN git clone https://github.com/Acly/comfyui-tooling-nodes.git /opt/program/custom_nodes/comfyui-tooling-nodes

### Video Generation Nodes ###
# Wan Video Wrapper
RUN git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git /opt/program/custom_nodes/ComfyUI-WanVideoWrapper && \
    cd /opt/program/custom_nodes/ComfyUI-WanVideoWrapper && \
    pip install -r requirements.txt

### Image Editing Nodes ###
# Qwen Edit Utils
RUN git clone https://github.com/lrzjason/Comfyui-QwenEditUtils /opt/program/custom_nodes/Comfyui-QwenEditUtils

# Layer Style (latest branch)
RUN git clone -b latest https://github.com/qingyuan18/ComfyUI_LayerStyle.git /opt/program/custom_nodes/ComfyUI_LayerStyle && \
    cd /opt/program/custom_nodes/ComfyUI_LayerStyle && \
    pip install -r requirements.txt

# Layer Style Advance
RUN git clone https://github.com/chflame163/ComfyUI_LayerStyle_Advance.git /opt/program/custom_nodes/ComfyUI_LayerStyle_Advance && \
    cd /opt/program/custom_nodes/ComfyUI_LayerStyle_Advance && \
    pip install -r requirements.txt

### Utility Nodes ###
# Easy Use
RUN git clone https://github.com/yolain/ComfyUI-Easy-Use.git /opt/program/custom_nodes/ComfyUI-Easy-Use && \
    cd /opt/program/custom_nodes/ComfyUI-Easy-Use && \
    pip install -r requirements.txt

# Amazon Bedrock LLM Node
RUN git clone https://github.com/qingyuan18/comfyui-llm-node-for-amazon-bedrock.git /opt/program/custom_nodes/comfyui-llm-node-for-amazon-bedrock

###############################################################################
# INSTALL ADDITIONAL DEPENDENCIES
###############################################################################

#### Install http/socket client (for uvicorn web server)
RUN pip3 install websocket-client
# Pin pydantic and typing_extensions to avoid ImportError: 'Sentinel'
RUN pip3 install "pydantic>=2.7,<3" "typing_extensions>=4.12.2"
RUN pip install loguru
RUN pip install typer_config
RUN pip install --no-deps diffusers
RUN pip install omegaconf

#### Install layer style dependencies
RUN mkdir -p /opt/program/web/extensions/dzNodes
RUN pip install --no-cache-dir --force-reinstall pillow
RUN pip install --no-deps protobuf==3.20.3
RUN pip install --no-deps mediapipe
RUN pip install --no-deps segment_anything
RUN pip install addict
RUN pip install yapf
RUN pip install openai

#### Install PaddleOCR dependencies
RUN pip install paddlepaddle-gpu==2.6.2
RUN pip install paddleocr==2.10.0

#### Upgrade torch/torchvision/cuda dependencies FIRST (before OpenCV)
RUN pip install -U torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

#### Install SageAttention (optional performance optimization)
# Use non-editable install to avoid pip 25.0 deprecation warning
RUN git clone https://github.com/thu-ml/SageAttention.git /tmp/SageAttention && \
    cd /tmp/SageAttention && \
    pip install --no-build-isolation . && \
    cd / && rm -rf /tmp/SageAttention

# Install OpenCV compatible with NumPy 2.x LAST to avoid being overwritten
# (4.10.0+ supports NumPy 2.x)
# Uninstall any existing opencv packages first to avoid conflicts
RUN pip uninstall -y opencv opencv-python opencv-python-headless opencv-contrib-python || true
RUN pip install --no-cache-dir --force-reinstall opencv-python-headless==4.12.0.88

###############################################################################
# S3 MODEL MOUNTING SUPPORT (Optional)
###############################################################################
# When using S3 PV/PVC for model storage, models will be mounted at runtime
# The following directories can be overridden by S3 mounts:
# - /opt/program/models/diffusion_models/
# - /opt/program/models/loras/
# - /opt/program/models/vae/
# - /opt/program/models/clip/
# See deployment guide for S3 CSI driver setup instructions

#####start comfyui
RUN chmod 755 /opt/program
RUN chmod 755 /opt/program/serve
WORKDIR /opt/program

