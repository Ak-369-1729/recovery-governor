from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from app.engine.chaos import ChaosLabEngine

router = APIRouter(prefix="/api/chaos", tags=["Chaos Lab"])

SCENARIOS = [
    {
        "id": "prohibited_retry",
        "title": "Adversarial AI Prohibited Retry Interception",
        "description": "Simulates rogue/hallucinated AI proposing immediate retry on a revoked mandate. Tests Gate 1 Hard Decline Ban.",
        "expected_gate": "GATE_1_HARD_DECLINE_BAN",
        "expected_outcome": "BLOCKED -> STOP"
    },
    {
        "id": "webhook_replay_storm",
        "title": "Webhook Replay Storm Idempotency Guard",
        "description": "Bursts 5 identical failure events in rapid succession. Tests Gate 6 Idempotency to prevent duplicate charges.",
        "expected_gate": "GATE_6_IDEMPOTENCY",
        "expected_outcome": "1 EXECUTED, 4 SUPPRESSED"
    },
    {
        "id": "gemini_outage",
        "title": "Gemini AI Outage Circuit Breaker",
        "description": "Simulates total LLM unavailability (503 Service Outage), verifying automatic degradation to deterministic fallback engine.",
        "expected_gate": "DETERMINISTIC_FALLBACK_CIRCUIT",
        "expected_outcome": "SAFE_EXECUTION_ZERO_DOWNTIME"
    },
    {
        "id": "negative_erv",
        "title": "Negative ERV Economic Suppression",
        "description": "Presents a ₹49 micro-payment where auth fees and risk exceed expected recovery value. Tests Gate 5 Economic Hurdle.",
        "expected_gate": "GATE_5_ECONOMIC_HURDLE",
        "expected_outcome": "NO_ACTION (Stopping Rule)"
    },
    {
        "id": "retry_cap",
        "title": "Max Retry Cap Enforcement",
        "description": "Simulates payment that has already undergone 3 failed retries. Tests Gate 2 Retry Cap.",
        "expected_gate": "GATE_2_RETRY_CAP",
        "expected_outcome": "STOP (Max Retries Exhausted)"
    }
]

@router.get("/scenarios")
def get_chaos_scenarios():
    return SCENARIOS

@router.post("/run/{scenario_id}")
def run_chaos_scenario(scenario_id: str):
    try:
        res = ChaosLabEngine.run_scenario(scenario_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chaos simulation error: {str(e)}")
