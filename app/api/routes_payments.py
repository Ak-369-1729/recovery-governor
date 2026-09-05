from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from app.models.repositories import list_payments, get_payment, count_payments
from app.engine.synthetic_data import ensure_synthetic_data_seeded, SYNTHETIC_DATASET_SIZE

router = APIRouter(prefix="/api/payments", tags=["Payments"])

@router.get("")
def get_payments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    failure_type: Optional[str] = None,
):
    ensure_synthetic_data_seeded()
    payments = list_payments(limit=limit, offset=offset, status=status, failure_type=failure_type)
    total = count_payments(status=status)
    return {
        "items": payments,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.get("/{payment_id}")
def get_payment_detail(payment_id: str):
    p = get_payment(payment_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    return p

@router.post("/seed")
def seed_payments(target_count: int = Query(SYNTHETIC_DATASET_SIZE, ge=100, le=10000)):
    count = ensure_synthetic_data_seeded(target_count)
    return {
        "status": "SUCCESS",
        "total_seeded": count,
        "message": f"Successfully ensured {count} synthetic failed payments in SQLite database."
    }
