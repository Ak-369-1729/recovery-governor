from fastapi import APIRouter, Query
from typing import Dict, Any
from app.engine.benchmark import BenchmarkEngine
from app.models.repositories import get_latest_benchmark_runs

router = APIRouter(prefix="/api/benchmark", tags=["Benchmark"])

@router.get("")
def get_benchmark_results():
    runs = get_latest_benchmark_runs(sample_size=5000)
    if not runs or len(runs) < 3:
        # Run benchmark automatically if not yet executed
        results = BenchmarkEngine.run_benchmark(sample_size=5000)
        return {
            "status": "FRESHLY_EXECUTED",
            "cohorts": {k: v.model_dump() for k, v in results.items()}
        }
    return {
        "status": "CACHED",
        "cohorts": {k: v["metrics"] for k, v in runs.items()}
    }

@router.post("/run")
def run_benchmark(sample_size: int = Query(5000, ge=100, le=5000)):
    results = BenchmarkEngine.run_benchmark(sample_size=sample_size)
    return {
        "status": "COMPLETED",
        "sample_size": sample_size,
        "cohorts": {k: v.model_dump() for k, v in results.items()}
    }
