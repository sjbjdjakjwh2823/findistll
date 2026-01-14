from mangum import Mangum
import sys
import os

try:
    from .app import app
    # Disable lifespan temporarily to isolate startup crashes
    handler = Mangum(app, lifespan="off") 
except Exception as e:
    import traceback
    error_trace = traceback.format_exc()
    
    def handler(event, context):
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/plain"},
            "body": f"Init Error:\n{error_trace}\n\nPath: {sys.path}\nCWD: {os.getcwd()}"
        }
