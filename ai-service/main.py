"""
main.py — NSE Scheduler AI Microservice (FastAPI entry point)

Internal service — not exposed to the public internet.
All estimation traffic routes: Client → Nginx → Node.js (authenticated) → this service.

Phase 1: Deterministic estimation engine (Modes 1 & 2)
Phase 2: LangChain agent layer for dynamic efficiency inference,
         labor density conflict detection, and ceiling delta compensation.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.estimate import router as estimate_router

app = FastAPI(
    title="NSE Scheduler — Estimation Microservice",
    description=(
        "Internal FastAPI service implementing the NSE Estimation Brain. "
        "Exposes POST /api/v1/estimate for deterministic labor and schedule calculations. "
        "Phase 2 will add LangChain-powered efficiency inference from historical project data."
    ),
    version="1.0.0",
    # Disable Redoc — keep only /docs (Swagger UI) for internal dev use
    redoc_url=None,
)

# CORS locked to internal Docker network only — no public origin needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://backend:5000", "http://localhost:5000"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

# Mount routers
app.include_router(estimate_router, prefix="/api/v1")


@app.get("/health", include_in_schema=False)
async def health() -> dict:
    """Docker health check endpoint."""
    return {"status": "ok", "service": "estimation-engine"}
