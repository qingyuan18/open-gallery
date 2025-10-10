# ComfyUI Dockerfile - S3 Mount Version
# This version expects models to be mounted from S3 at runtime
# Image size: ~5-10GB (much smaller)
# Use this for: Production deployments with S3 CSI driver

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

# Install basic dependencies
RUN pip install --no-cache-dir fastapi uvicorn sagemaker
RUN pip install sagemaker-ssh-helper
RUN curl -L https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz | tar -xz && mv s5cmd /opt/program/

ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE
ENV PATH="/opt/program:${PATH}"

####install ComfyUI
COPY ComfyUI /opt/program
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
# INSTALL CUSTOM NODES SECTION
# Models will be mounted from S3 at runtime
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
RUN pip3 install pydantic
RUN pip install loguru
RUN pip install typer_config
RUN pip install --no-deps diffusers
RUN pip install omegaconf

#### Install layer style dependencies
RUN mkdir -p /opt/program/web/extensions/dzNodes
RUN pip install --no-cache-dir --force-reinstall pillow
RUN pip install opencv-fixer==0.2.5
RUN python -c "from opencv_fixer import AutoFix; AutoFix()"
RUN pip install --no-deps protobuf==3.20.3
RUN pip install --no-deps mediapipe
RUN pip install --no-deps segment_anything
RUN pip install addict
RUN pip install yapf
RUN pip install openai

#### Install PaddleOCR dependencies
RUN pip install paddlepaddle-gpu==2.6.2
RUN pip install paddleocr==2.10.0

#### Install SageAttention (optional performance optimization)
RUN git clone https://github.com/thu-ml/SageAttention.git /tmp/SageAttention && \
    cd /tmp/SageAttention && \
    pip install -e . && \
    cd / && rm -rf /tmp/SageAttention

#### Upgrade torch/torchvision/cuda dependencies
RUN pip install -U --forece-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

###############################################################################
# S3 MODEL MOUNTING CONFIGURATION
###############################################################################
# Models will be mounted from S3 at the following paths:
# - /opt/program/models/diffusion_models/ -> s3://bucket/models/wan/, s3://bucket/models/flux/
# - /opt/program/models/loras/ -> s3://bucket/models/wan/
# - /opt/program/models/vae/ -> s3://bucket/models/flux/
# - /opt/program/models/clip/ -> s3://bucket/models/flux/
# - /opt/program/models/text_encoders/ -> s3://bucket/models/wan/
#
# See k8s-manifests/comfyui-deployment-s3.yaml for volume mount configuration

#####start comfyui
RUN chmod 755 /opt/program
RUN chmod 755 /opt/program/serve
WORKDIR /opt/program

