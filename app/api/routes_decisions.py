from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from app.models.repositories import list_decisions, get_decision_by_id, get_payment
from app.engine.replay import DecisionReplayEngine

router = APIRouter(prefix="/api/decisions", tags=["Decisions"])

@router.get("")
def get_decisions(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    items = list_decisions(limit=limit, offset=offset)
    return {
        "items": items,
        "limit": limit,
        "offset": offset
    }

@router.get("/{decision_id}")
def get_decision(decision_id: str):
    d = get_decision_by_id(decision_id)
    if not d:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
    return d

@router.get("/{payment_id}/replay")
def get_decision_replay(payment_id: str):
    try:
        replay = DecisionReplayEngine.get_or_create_replay(payment_id)
        return replay
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error replaying decision: {str(e)}")

@router.post("/evaluate/{payment_id}")
def evaluate_payment(payment_id: str):
    try:
        replay = DecisionReplayEngine.get_or_create_replay(payment_id)
        return {
            "status": "EVALUATED",
            "decision": replay["decision"],
            "execution": replay["execution"],
            "verification": replay["verification"],
            "attribution": replay["attribution"]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error evaluating payment: {str(e)}")
