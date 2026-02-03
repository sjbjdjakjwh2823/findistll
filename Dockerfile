# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set set shell to bash
SHELL ["/bin/bash", "-c"]

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app

# Create app directory
WORKDIR $APP_HOME

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    zlib1g-dev \
    libjpeg-dev \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user and switch to it
RUN useradd -m preciso
USER preciso

# Copy project files
COPY --chown=preciso:preciso . .

# Expose the application port
EXPOSE 8004

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
