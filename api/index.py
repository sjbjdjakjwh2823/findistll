import sys
import os

try:
    from fastapi import FastAPI
    from mangum import Mangum

    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {
            "status": "fastapi_alive", 
            "message": "Dependency install success!",
            "version": "minimal"
        }

    handler = Mangum(app)

except Exception as e:
    import traceback
    error_msg = f"CRITICAL IMPORT ERROR:\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
    print(error_msg)
    
    # Fallback handler to show error in browser
    def handler(event, context):
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/plain"},
            "body": error_msg
        }
