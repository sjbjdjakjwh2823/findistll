import sys
import os

# Vercel entry point - with Startup Error Handling
try:
    from api.app import app
except Exception as e:
    # If imports fail (common in serverless), create a dummy app to display the error
    import traceback
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    
    error_msg = f"CRITICAL STARTUP ERROR:\n{traceback.format_exc()}"
    print(error_msg)
    
    app = FastAPI()
    
    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all(path_name: str):
        return PlainTextResponse(
            status_code=500,
            content=f"Server failed to start.\n\n{error_msg}"
        )
