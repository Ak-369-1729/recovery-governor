from fastapi import APIRouter, Query
from typing import Optional, List, Dict, Any
from app.models.repositories import list_audit_logs, verify_audit_chain_integrity

router = APIRouter(prefix="/api/audit", tags=["Audit Trail"])

@router.get("")
def get_audit_trail(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    payment_id: Optional[str] = None
):
    logs = list_audit_logs(limit=limit, offset=offset, payment_id=payment_id)
    return {
        "items": logs,
        "limit": limit,
        "offset": offset
    }

@router.get("/verify")
def verify_audit_chain():
    result = verify_audit_chain_integrity()
    return result
