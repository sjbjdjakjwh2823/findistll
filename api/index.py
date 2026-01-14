from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()

@app.get("/api/health")
def health():
    return {"status": "fastapi_alive", "message": "Dependecy installation successful!"}

handler = Mangum(app)
