# ComfyUI Dockerfile - S3 mount + Flux models baked-in version
#
# Same as comfyui-s3.dockerfile but with the Flux test model set pre-downloaded
# into /opt/program/models/<subtype>/ so the container is fully self-contained.
# Pair with an AMI that pre-pulls this image into containerd k8s.io namespace
# (no NVMe seed copy needed at boot).
#
# Image size: ~17 GiB (base) + ~22 GiB (flux models) ≈ 39 GiB
# ECR push will take a while; pull on a fresh node also slow unless pre-staged in AMI.

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

# Install git and basic dependencies.
# Build SG only allows :443 outbound, so rewrite apt sources from http:// to
# https:// (Ubuntu mirrors support HTTPS) and use the AWS regional mirror so
# traffic stays inside the VPC.
RUN for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do \
      [ -f "$f" ] && sed -i \
        -e 's|http://archive.ubuntu.com|https://us-east-1.ec2.archive.ubuntu.com|g' \
        -e 's|http://security.ubuntu.com|https://us-east-1.ec2.archive.ubuntu.com|g' \
        -e 's|http://us-east-1.ec2.archive.ubuntu.com|https://us-east-1.ec2.archive.ubuntu.com|g' \
        "$f" || true; \
    done \
 && echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/99retries \
 && apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg git ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
RUN curl -L https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz | tar -xz && mv s5cmd /opt/program/

ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE
ENV PATH="/opt/program:${PATH}"
ENV export TORCH_CUDA_ARCH_LIST="8.9"
ENV export FORCE_CUDA=1

####install ComfyUI
WORKDIR /opt/program
# Pin to a known-good commit. ComfyUI HEAD added comfy/ldm/lightricks/vae/audio_vae.py
# which unconditionally imports torchaudio at startup; that pulls a libcudart.so.13
# dependency our CUDA 12.x base image can't satisfy, leading to CrashLoopBackOff.
# This commit predates that change and is what comfyui-s3:latest was built from.
ARG COMFYUI_COMMIT=v0.3.64
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /tmp/comfyui && \
    cd /tmp/comfyui && git checkout ${COMFYUI_COMMIT} && cd / && \
    cp -r /tmp/comfyui/. /opt/program/ && \
    rm -rf /tmp/comfyui

RUN pip install -r /opt/program/requirements.txt

RUN pip install wget
RUN pip install retry

###############################################################################
# CUSTOM NODES
###############################################################################

RUN git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git /opt/program/custom_nodes/comfyui_controlnet_aux

RUN git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git /opt/program/custom_nodes/ComfyUI-Custom-Scripts

RUN git clone https://github.com/crystian/ComfyUI-Crystools /opt/program/custom_nodes/ComfyUI-Crystools && \
    cd /opt/program/custom_nodes/ComfyUI-Crystools && \
    pip install -r requirements.txt

RUN git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git /opt/program/custom_nodes/ComfyUI-VideoHelperSuite

RUN git clone https://github.com/kijai/ComfyUI-KJNodes.git /opt/program/custom_nodes/ComfyUI-KJNodes

RUN git clone https://github.com/ltdrdata/ComfyUI-Manager.git /opt/program/custom_nodes/ComfyUI-Manager && \
    cd /opt/program/custom_nodes/ComfyUI-Manager && \
    pip install -r requirements.txt

RUN git clone https://github.com/WASasquatch/was-node-suite-comfyui /opt/program/custom_nodes/was-node-suite-comfyui

RUN git clone https://github.com/Acly/comfyui-tooling-nodes.git /opt/program/custom_nodes/comfyui-tooling-nodes

RUN git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git /opt/program/custom_nodes/ComfyUI-WanVideoWrapper && \
    cd /opt/program/custom_nodes/ComfyUI-WanVideoWrapper && \
    pip install -r requirements.txt

RUN git clone https://github.com/lrzjason/Comfyui-QwenEditUtils /opt/program/custom_nodes/Comfyui-QwenEditUtils

RUN git clone -b latest https://github.com/qingyuan18/ComfyUI_LayerStyle.git /opt/program/custom_nodes/ComfyUI_LayerStyle && \
    cd /opt/program/custom_nodes/ComfyUI_LayerStyle && \
    pip install -r requirements.txt

RUN git clone https://github.com/chflame163/ComfyUI_LayerStyle_Advance.git /opt/program/custom_nodes/ComfyUI_LayerStyle_Advance && \
    cd /opt/program/custom_nodes/ComfyUI_LayerStyle_Advance && \
    pip install -r requirements.txt

RUN git clone https://github.com/yolain/ComfyUI-Easy-Use.git /opt/program/custom_nodes/ComfyUI-Easy-Use && \
    cd /opt/program/custom_nodes/ComfyUI-Easy-Use && \
    pip install -r requirements.txt

RUN git clone https://github.com/qingyuan18/comfyui-llm-node-for-amazon-bedrock.git /opt/program/custom_nodes/comfyui-llm-node-for-amazon-bedrock

RUN git clone https://github.com/jaimitoes/ComfyUI_Wan2_1_lora_trainer.git /opt/program/customer_nodes/ComfyUI_Wan2_1_lora_trainer
RUN git clone https://github.com/kijai/ComfyUI-FluxTrainer.git /opt/program/customer_nodes/ComfyUI-FluxTrainer
RUN git clone https://github.com/aidenli/ComfyUI_NYJY.git /opt/program/customer_nodes/ComfyUI_NYJY
RUN git clone https://github.com/kijai/ComfyUI-Florence2.git /opt/program/customer_nodes/ComfyUI-Florence2
RUN git clone https://github.com/No-22-Github/ComfyUI_SaveImageCustom.git /opt/program/customer_nodes/ComfyUI_SaveImageCustom
RUN git clone https://github.com/pythongosssss/ComfyUI-WD14-Tagger.git /opt/program/customer_nodes/ComfyUI-WD14-Tagger
RUN git clone https://github.com/alexgenovese/ComfyUI_HF_Servelress_Inference.git /opt/program/customer_nodes/ComfyUI_HF_Servelress_Inference
RUN git clone https://github.com/cubiq/ComfyUI_essentials.git /opt/program/customer_nodes/ComfyUI_essentials

###############################################################################
# DEPENDENCIES
###############################################################################

RUN pip install "pydantic>=2.7,<3" "typing_extensions>=4.12.2"

RUN export TORCH_CUDA_ARCH_LIST="8.9" && export FORCE_CUDA=1 && git clone https://github.com/thu-ml/SageAttention.git /tmp/SageAttention && \
    cd /tmp/SageAttention && \
    git checkout 2aecfa89c777ec46c4eaaab66082f188a1e00ae4 && \
    pip install --no-build-isolation . && \
    cd / && rm -rf /tmp/SageAttention

RUN pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python
RUN rm -rf /usr/local/lib/python3.12/dist-packages/cv2*
RUN rm -rf /usr/local/lib/python3.12/dist-packages/opencv*
RUN pip install --no-cache-dir opencv-python==4.12.0.88

###############################################################################
# BAKE FLUX MODELS INTO THE IMAGE
#
# This is the key difference vs comfyui-s3.dockerfile. Each model lands in the
# subdirectory ComfyUI expects, so the running container needs zero extra
# mounts to serve Flux workflows.
#
# Build prerequisites:
#   - The Docker daemon's host must have AWS credentials available so the
#     `aws s3 cp` calls below succeed. Use BuildKit secrets or pre-pull the
#     bucket to a local cache; for simplicity here we rely on `aws` CLI
#     reading $HOME/.aws/credentials inherited via the build environment.
#   - The buildx builder must be `--driver docker-container` if you need
#     secrets; otherwise use the classic builder with credentials in env.
#
# Production note: this fattens the image to ~39 GiB. ECR storage cost goes
# up, and `docker push` / `pull` time scales accordingly. AMI-side image
# pre-pull is REQUIRED for fast cold start (covered in the bake-AMI script).
###############################################################################

ARG MODELS_S3_BUCKET=comfyui-models-bucket-687912291502
ARG AWS_REGION=us-east-1

# awscli is needed at build-time for the s3 cp commands. Keep it for runtime
# too in case future workflows want to pull additional assets (this is also
# how the existing comfyui-s3 image stays consistent).
RUN pip install --no-cache-dir awscli

# Bake the Flux test set. Layer is large but stable: subsequent builds that
# don't change the model URIs reuse the cached layer.
RUN aws s3 cp s3://${MODELS_S3_BUCKET}/models/diffusion_models/flux1-dev-fp8.safetensors /opt/program/models/diffusion_models/flux1-dev-fp8.safetensors --region ${AWS_REGION} \
 && aws s3 cp s3://${MODELS_S3_BUCKET}/models/text_encoders/t5xxl_fp8_e4m3fn.safetensors /opt/program/models/text_encoders/t5xxl_fp8_e4m3fn.safetensors --region ${AWS_REGION} \
 && aws s3 cp s3://${MODELS_S3_BUCKET}/models/clip/clip_l.safetensors /opt/program/models/clip/clip_l.safetensors --region ${AWS_REGION} \
 && aws s3 cp s3://${MODELS_S3_BUCKET}/models/vae/ae.safetensors /opt/program/models/vae/ae.safetensors --region ${AWS_REGION}

###############################################################################
# Final config
###############################################################################

RUN chmod 755 /opt/program
WORKDIR /opt/program
