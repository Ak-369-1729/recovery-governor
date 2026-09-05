from fastapi import APIRouter, Query
from typing import Dict, Any
from app.engine.experiments import ExperimentEngine
from app.models.repositories import get_latest_experiments

router = APIRouter(prefix="/api/experiments", tags=["Experiments"])

@router.get("")
def get_experiments():
    exps = get_latest_experiments(limit=5)
    if not exps:
        res = ExperimentEngine.run_experiment(sample_per_arm=500)
        return {
            "status": "FRESHLY_EXECUTED",
            "latest_experiment": res
        }
    return {
        "status": "CACHED",
        "latest_experiment": exps[0]["results"],
        "history": exps
    }

@router.post("/run")
def run_experiment(sample_per_arm: int = Query(500, ge=50, le=1250)):
    results = ExperimentEngine.run_experiment(sample_per_arm=sample_per_arm)
    return {
        "status": "COMPLETED",
        "results": results
    }
