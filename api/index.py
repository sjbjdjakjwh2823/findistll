import os
from dotenv import load_dotenv

load_dotenv()

# Vercel entry point - with Startup Error Handling
try:
    from api.app import app
except Exception as e:
    # DEBUG: Deep inspection of the environment
    import sys
    import pkg_resources
    
    debug_info = []
    debug_info.append(f"Python Version: {sys.version}")
    debug_info.append(f"Sys Path: {sys.path}")
    
    try:
        installed = [f"{p.project_name}=={p.version}" for p in pkg_resources.working_set]
        debug_info.append(f"Installed Packages: {', '.join(installed)}")
    except Exception as e:
        debug_info.append(f"Could not list packages: {e}")

    try:
        import google
        debug_info.append(f"Google Package Path: {getattr(google, '__path__', 'No Path')}")
        debug_info.append(f"Google Package File: {getattr(google, '__file__', 'No File')}")
        debug_info.append(f"Google Dir: {dir(google)}")
    except ImportError:
        debug_info.append("Could not import google package")
    except Exception as e:
        debug_info.append(f"Error inspecting google package: {e}")
        
    debug_str = "\n".join(debug_info)
    error_msg = f"CRITICAL STARTUP ERROR:\n{traceback.format_exc()}\n\nDEBUG INFO:\n{debug_str}"
    
    print(error_msg)
    
    app = FastAPI()
    
    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all(path_name: str):
        return JSONResponse(
            status_code=500,
            content={"detail": "Server failed to start.", "error": error_msg}
        )
