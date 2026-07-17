
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.session_routes import router as session_router

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Adaptive KYC Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router)

try:
    from app.api.kyc_routes import router as kyc_router
    app.include_router(kyc_router)
except ImportError as e:
    print(f"Warning: eKYC/document-verification routes not mounted ({e}). Fraud-scoring endpoint is still available.")


@app.get("/")
def serve_fraud_demo():
    return FileResponse(STATIC_DIR / "fraud_demo.html")


@app.get("/health")
def health_check():
    return {"status": "ok"}