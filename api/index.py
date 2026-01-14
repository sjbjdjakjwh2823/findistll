from fastapi import FastAPI
from mangum import Mangum

# Minimal dummy app to allow Vercel to start without heavy dependencies
app = FastAPI()

@app.get("/api/health")
def health():
    return {"status": "alive_minimal", "message": "It works!"}

handler = Mangum(app)
