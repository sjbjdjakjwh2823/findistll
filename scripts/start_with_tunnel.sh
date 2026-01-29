#!/bin/bash

# 1. Start the FastAPI/Next.js Server in the background
echo "Starting Application Server (Uvicorn)..."
# Use 0.0.0.0 so HF health checks pass (port 7860)
uvicorn api.app:app --host 0.0.0.0 --port 7860 &
APP_PID=$!

# Wait for the service to be ready (Port 7860)
echo "Waiting for service to bind port 7860..."
MAX_RETRIES=60 # Wait up to 60 seconds (extended for DB migration)
COUNT=0
while ! curl -s http://localhost:7860/api/health > /dev/null; do
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Timeout waiting for app to start on port 7860."
        echo "Check logs for potential DB connection errors."
        # Don't exit, just proceed to keep container alive for debugging
        break
    fi
    echo "Waiting for app... ($COUNT/$MAX_RETRIES)"
    sleep 1
    COUNT=$((COUNT+1))
done
echo "App appears to be running!"

# 2. Keep Alive & Self-Ping Loop
# This ensures the container stays running and prevents HF 48h inactivity pause.
echo "Service is running. Entering keep-alive loop..."

# Define the Space URL (Direct Docker Space URL)
SPACE_URL="https://sdkfsklf-preciso-f108bab9.hf.space"

while true; do
    # Check if App is still running
    if ! kill -0 $APP_PID 2>/dev/null; then
        echo "CRITICAL: Application Server (uvicorn) died! Restarting..."
        uvicorn api.app:app --host 0.0.0.0 --port 7860 &
        APP_PID=$!
    fi
    
    # Self-Ping to prevent inactivity pause
    # We use the HF_TOKEN if available to authenticate against the private space
    if [ ! -z "$HF_TOKEN" ]; then
        echo "Sending keep-alive ping to $SPACE_URL..."
        curl -s -o /dev/null -H "Authorization: Bearer $HF_TOKEN" $SPACE_URL/api/health || echo "Ping failed"
    else
        # Fallback for public spaces or local health check
        curl -s -o /dev/null http://localhost:7860/api/health || echo "Local health check failed"
    fi
    
    sleep 300 # Ping every 5 minutes
done
