"""
API Routes for Merchant Policy Configuration.
"""

from typing import List
from fastapi import APIRouter, Query
from app.models.schemas import MerchantPolicyConfig
from app.engine.merchant_policy import MerchantPolicyManager

router = APIRouter(prefix="/api/merchant", tags=["Merchant Policy"])

@router.get("/policy", response_model=MerchantPolicyConfig)
def get_merchant_policy(merchant_id: str = Query(default="mer_demo_razorpay")):
    """Retrieves policy configuration for a merchant."""
    return MerchantPolicyManager.get_policy(merchant_id)

@router.post("/policy", response_model=MerchantPolicyConfig)
def update_merchant_policy(config: MerchantPolicyConfig):
    """
    Updates policy configuration for a merchant.
    Note: override_global_safety cannot override Governor safety invariants.
    """
    return MerchantPolicyManager.update_policy(config)

@router.get("/policies", response_model=List[MerchantPolicyConfig])
def list_merchant_policies():
    """Lists all configured merchant policies."""
    return MerchantPolicyManager.list_policies()
