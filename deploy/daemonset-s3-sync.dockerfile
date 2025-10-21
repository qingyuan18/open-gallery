# Minimal image for DaemonSet S3 sync (awscli + boto3)
# Builds a small Python+Alpine image, installs AWS CLI and boto3

FROM python:3.11-alpine



# Install runtime deps and tools
RUN apk add --no-cache bash curl ca-certificates unzip jq && \
    update-ca-certificates



# Python deps (optional but requested)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir boto3 awscli

# Default workdir
WORKDIR /workspace

# Entrypoint is kept simple. DaemonSet manifest provides command/args.
ENTRYPOINT ["/bin/sh","-lc"]
CMD ["aws --version"]

