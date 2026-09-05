import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.database import init_db
from app.engine.synthetic_data import ensure_synthetic_data_seeded
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_payments import router as payments_router
from app.api.routes_decisions import router as decisions_router
from app.api.routes_benchmark import router as benchmark_router
from app.api.routes_experiments import router as experiments_router
from app.api.routes_chaos import router as chaos_router
from app.api.routes_audit import router as audit_router
from app.api.routes_demo import router as demo_router

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize SQLite WAL database and guarantee 5,000 synthetic records
    init_db()
    ensure_synthetic_data_seeded(5000)
    yield
    # Shutdown

app = FastAPI(
    title="Recovery Governor",
    description="AI Revenue Recovery Decision Engine — Razorpay AI Buildathon 2026 Track 03",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(dashboard_router)
app.include_router(payments_router)
app.include_router(decisions_router)
app.include_router(benchmark_router)
app.include_router(experiments_router)
app.include_router(chaos_router)
app.include_router(audit_router)
app.include_router(demo_router)

# Health endpoints
@app.get("/health")
@app.get("/api/health")
def health_check():
    return {
        "status": "HEALTHY",
        "service": "Recovery Governor",
        "version": settings.version,
        "ai_provider": "GEMINI" if settings.has_gemini else "DETERMINISTIC_FALLBACK",
        "razorpay_adapter": "LIVE_TEST_MODE" if settings.has_razorpay else "SIMULATION",
        "database": "SQLite WAL"
    }

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def serve_index():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"status": "Frontend loading..."})
