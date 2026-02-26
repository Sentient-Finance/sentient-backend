from fastapi import FastAPI

app = FastAPI(title="sentient-backend-api", version="0.1.0")


@app.get("/health")
def health():
    return {"ok": True, "service": "api"}


@app.get("/ready")
def ready():
    return {"ok": True, "service": "api", "ready": True}
