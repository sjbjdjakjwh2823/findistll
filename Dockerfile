# Multi-stage Dockerfile for FinDistill with Cloudflare Tunnel
# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app
# Copy the frontend folder into the build context (root of context -> /app/frontend)
COPY frontend ./frontend
# Move into frontend dir to run build
WORKDIR /app/frontend
# Install dependencies
RUN npm ci
# Build Next.js
RUN npm run build

# Stage 2: Backend & Runtime
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

# Copy Backend Code
COPY . /app

# Copy Frontend Build from Stage 1
COPY --from=frontend-builder /app/frontend/out /app/frontend/out

# Make startup script executable and fix line endings
RUN dos2unix scripts/start_with_tunnel.sh && chmod +x scripts/start_with_tunnel.sh

# Expose the port (Required for HF Health Checks)
EXPOSE 7860

# Run the wrapper script that launches both App and Tunnel
CMD ["./scripts/start_with_tunnel.sh"]
