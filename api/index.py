"""
Vercel Serverless Function Entry Point

This file serves as the entry point for Vercel Python Serverless Functions.
It wraps the FastAPI application with Mangum to handle AWS Lambda/Vercel requests.
"""

from mangum import Mangum
from .app import app

# Mangum adapter for AWS Lambda / Vercel Serverless
# lifespan="off" disables ASGI lifespan events (startup/shutdown)
# which are not fully supported in serverless environments
handler = Mangum(app, lifespan="off")
