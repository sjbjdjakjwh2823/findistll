import os
from dotenv import load_dotenv

load_dotenv()

# Vercel entry point - with Startup Error Handling
try:
    from api.app import app
except Exception as e:
    # Minimal, safe error handler
    import sys
    import traceback
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    debug_info = []
    debug_info.append(f"Python Version: {sys.version}")
    debug_info.append(f"Sys Path: {sys.path[:5]}")  # Limit path output
    
    # Try to list installed packages safely
    try:
        import subprocess
        result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=freeze"], 
                              capture_output=True, text=True, timeout=10)
        debug_info.append(f"Packages: {result.stdout[:1000]}")
    except Exception as pkg_err:
        debug_info.append(f"Could not list packages: {pkg_err}")

    # Try to inspect google package
    try:
        import google
        debug_info.append(f"Google Path: {getattr(google, '__path__', 'N/A')}")
        debug_info.append(f"Google Dir: {dir(google)}")
    except Exception as g_err:
        debug_info.append(f"Google import error: {g_err}")
        
    debug_str = "\n".join(debug_info)
    error_msg = f"STARTUP ERROR:\n{traceback.format_exc()}\n\nDEBUG:\n{debug_str}"
    
    print(error_msg)
    
    app = FastAPI()
    
    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
    async def catch_all(path_name: str):
        return JSONResponse(
            status_code=500,
            content={"detail": "Server failed to start.", "error": error_msg}
        )
