import os
from dotenv import load_dotenv

load_dotenv()

# Vercel entry point - with Startup Error Handling
try:
    from api.app import app
except Exception as e:
    # Minimal error handler without pkg_resources
    import sys
    import traceback
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    error_msg = f"STARTUP ERROR (HANDLER v2):\n{traceback.format_exc()}"
    print(error_msg)
    
    app = FastAPI()
    
    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
    async def catch_all(path_name: str):
        return JSONResponse(
            status_code=500,
            content={"detail": "Server failed to start.", "error": error_msg}
        )
