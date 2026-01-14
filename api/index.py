"""
Vercel Serverless Function Entry Point (Debug Mode)
"""
import sys
import traceback

try:
    from mangum import Mangum
    from .app import app
    
    # Enable lifespan for auto-migration
    handler = Mangum(app, lifespan="on")
    
except Exception as e:
    # Capture import errors and return as basic HTTP response
    error_msg = f"Critical Import Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
    print(error_msg)
    
    def handler(event, context):
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/plain"},
            "body": error_msg
        }
