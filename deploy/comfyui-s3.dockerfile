# ComfyUI Dockerfile - S3 Mount Version
# This version expects models to be mounted from S3 at runtime
# Image size: ~5-10GB (much smaller)
# Use this for: Production deployments with S3 CSI driver

#FROM nvcr.io/nvidia/pytorch:25.03-py3
FROM nvcr.io/nvidia/pytorch:24.12-py3

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
RUN apt-get update && apt-get install -y ffmpeg git
#RUN pip install --no-cache-dir fastapi uvicorn sagemaker
#RUN pip install sagemaker-ssh-helper
RUN curl -L https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz | tar -xz && mv s5cmd /opt/program/

ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE
ENV PATH="/opt/program:${PATH}"
# Compile CUDA extensions for NVIDIA L40S (Ada, SM 8.9) at build time
# This avoids GPU detection at build and ensures wheels work in k8s pods
ENV export TORCH_CUDA_ARCH_LIST="8.9"
ENV export FORCE_CUDA=1

####install ComfyUI
# Clone ComfyUI from official repository
WORKDIR /opt/program
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /tmp/comfyui && \
    cp -r /tmp/comfyui/* /opt/program/ && \
    rm -rf /tmp/comfyui

RUN pip install -r /opt/program/requirements.txt

# Install core dependencies
RUN pip install wget
RUN pip install retry



###############################################################################
# INSTALL CUSTOM NODES SECTION
# Models will be mounted from S3 at runtime
###############################################################################

### Core Custom Nodes ###
RUN git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git /opt/program/custom_nodes/comfyui_controlnet_aux

RUN git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git /opt/program/custom_nodes/ComfyUI-Custom-Scripts

RUN git clone https://github.com/crystian/ComfyUI-Crystools /opt/program/custom_nodes/ComfyUI-Crystools && \
    cd /opt/program/custom_nodes/ComfyUI-Crystools && \
    pip install -r requirements.txt

# video suite
RUN git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git /opt/program/custom_nodes/ComfyUI-VideoHelperSuite

# KJ node
RUN git clone https://github.com/kijai/ComfyUI-KJNodes.git /opt/program/custom_nodes/ComfyUI-KJNodes

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


# flux & wan trainer node
RUN git clone https://github.com/jaimitoes/ComfyUI_Wan2_1_lora_trainer.git /opt/program/custom_nodes/ComfyUI_Wan2_1_lora_trainer
RUN git clone https://github.com/kijai/ComfyUI-FluxTrainer.git /opt/program/custom_nodes/ComfyUI-FluxTrainer && \
    cd /opt/program/custom_nodes/ComfyUI-FluxTrainer && \
    pip install -r requirements.txt
RUN git clone https://github.com/aidenli/ComfyUI_NYJY.git /opt/program/custom_nodes/ComfyUI_NYJY && \
    cd /opt/program/custom_nodes/ComfyUI_NYJY && \
    pip install -r requirements.txt
RUN git clone https://github.com/kijai/ComfyUI-Florence2.git /opt/program/custom_nodes/ComfyUI-Florence2 && \
    cd /opt/program/custom_nodes/ComfyUI-Florence2 && \
    pip install -r requirements.txt
RUN git clone https://github.com/No-22-Github/ComfyUI_SaveImageCustom.git /opt/program/custom_nodes/ComfyUI_SaveImageCustom
RUN git clone https://github.com/pythongosssss/ComfyUI-WD14-Tagger.git /opt/program/custom_nodes/ComfyUI-WD14-Tagger
RUN git clone https://github.com/alexgenovese/ComfyUI_HF_Servelress_Inference.git /opt/program/custom_nodes/ComfyUI_HF_Servelress_Inference
RUN git clone https://github.com/cubiq/ComfyUI_essentials.git /opt/program/custom_nodes/ComfyUI_essentials && \
    cd /opt/program/custom_nodes/ComfyUI_essentials && \
    pip install -r requirements.txt


# 

###############################################################################
# INSTALL ADDITIONAL DEPENDENCIES
###############################################################################

#### Install http/socket client (for uvicorn web server)
#RUN pip install websocket-client
# Pin pydantic and typing_extensions to avoid ImportError: 'Sentinel'
RUN pip install "pydantic>=2.7,<3" "typing_extensions>=4.12.2"
#RUN pip install --no-deps diffusers


#### Install layer style dependencies
#RUN pip install addict
#RUN pip install yapf
#RUN pip install openai

#### Upgrade torch/torchvision/cuda dependencies FIRST (before OpenCV)
#RUN pip install -U --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128



# legacy flash attn lib
# Install ninja for faster compilation
RUN pip install ninja

# Install flash-attention with verbose output
RUN pip uninstall -y flash_attn
RUN git clone -b v2.0.1 https://github.com/Dao-AILab/flash-attention.git /tmp/flash-attention && \
    cd /tmp/flash-attention && \
    MAX_JOBS=4 python setup.py install --verbose && \
    cd / && rm -rf /tmp/flash-attention

#### Install SageAttention (optional performance optimization)
# Use non-editable install to avoid pip 25.0 deprecation warning
RUN export TORCH_CUDA_ARCH_LIST="8.9" && export FORCE_CUDA=1 && git clone https://github.com/thu-ml/SageAttention.git /tmp/SageAttention && \
    cd /tmp/SageAttention && \
    git checkout 2aecfa89c777ec46c4eaaab66082f188a1e00ae4 && \
    pip install --no-build-isolation . && \
    cd / && rm -rf /tmp/SageAttention

# Install OpenCV compatible with NumPy 2.x LAST to avoid being overwritten
# (4.10.0+ supports NumPy 2.x)
# Uninstall any existing opencv packages first to avoid conflicts
RUN pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python
RUN rm -rf /usr/local/lib/python3.12/dist-packages/cv2*
RUN rm -rf /usr/local/lib/python3.12/dist-packages/opencv*
RUN pip install --no-cache-dir opencv-python==4.12.0.88
#RUN pip install numpy==1.26.4




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
WORKDIR /opt/program

