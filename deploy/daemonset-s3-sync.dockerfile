# Minimal image for DaemonSet S3 sync (s5cmd + boto3)
# Builds a small Python+Alpine image, installs s5cmd binary and boto3

FROM python:3.11-alpine

ARG S5CMD_VERSION=2.2.2

# Install runtime deps and tools
RUN apk add --no-cache bash curl ca-certificates unzip jq && \
    update-ca-certificates

# Install s5cmd (static binary)
RUN set -euo pipefail && \
    ARCH="Linux-64bit" && \
    URL="https://github.com/peak/s5cmd/releases/download/v${S5CMD_VERSION}/s5cmd_${S5CMD_VERSION}_${ARCH}.tar.gz" && \
    echo "Downloading s5cmd from: ${URL}" && \
    curl -fsSL "$URL" -o /tmp/s5cmd.tgz && \
    tar -xzf /tmp/s5cmd.tgz -C /tmp && \
    install -m 0755 /tmp/s5cmd /usr/local/bin/s5cmd && \
    rm -rf /tmp/s5cmd* && \
    s5cmd version

# Python deps (optional but requested)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir boto3

# Default workdir
WORKDIR /workspace

# Entrypoint is kept simple. DaemonSet manifest provides command/args.
ENTRYPOINT ["/bin/sh","-lc"]
CMD ["s5cmd --help"]

