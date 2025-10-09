# Open Gallery Application Dockerfile
# Multi-stage build for React frontend + Python backend

###############################################################################
# Stage 1: Build React Frontend
###############################################################################
FROM node:18-alpine AS frontend-builder

WORKDIR /app/react

# Copy package files
COPY react/package*.json ./

# Install dependencies
RUN npm ci

# Copy React source code
COPY react/ ./

# Build React app
RUN npm run build

###############################################################################
# Stage 2: Python Backend
###############################################################################
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements
COPY server/requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY server/ ./server/

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/react/dist ./react/dist

# Create user_data directory for config and database
RUN mkdir -p /app/user_data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV UI_DIST_DIR=/app/react/dist
ENV DEVELOPMENT_MODE=false

# Expose port
EXPOSE 57988

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:57988/ || exit 1

# Start the application
WORKDIR /app/server
CMD ["python", "main.py", "--port", "57988"]

