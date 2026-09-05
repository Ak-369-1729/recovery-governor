import json
import logging
from typing import Dict, Any, Tuple
from app.config import settings
from app.models.enums import AIMode
from app.models.schemas import AIDiagnosisOutput
from app.engine.fallback import DeterministicFallbackEngine

logger = logging.getLogger("recovery_governor.diagnosis")

class AIDiagnosisEngine:
    """
    AI Diagnosis Engine: Integrates Gemini AI for contextual payment failure diagnosis.
    Strictly constrained: AI outputs structured diagnosis and candidate actions;
    it has ZERO execution authority. Falls back gracefully to DeterministicFallbackEngine.
    """

    @classmethod
    def diagnose(cls, payment: Dict[str, Any]) -> Tuple[AIDiagnosisOutput, AIMode]:
        if not settings.has_gemini:
            return DeterministicFallbackEngine.diagnose(payment), AIMode.DETERMINISTIC_FALLBACK

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.gemini_api_key)
            
            prompt = f"""
You are an expert payment systems recovery AI at Razorpay.
Analyze the following failed payment event and provide structured failure etiology diagnosis, confidence, and candidate recovery actions.

Payment Context:
- Payment ID: {payment.get('payment_id')}
- Amount: ₹{payment.get('amount')} {payment.get('currency', 'INR')}
- Payment Method: {payment.get('payment_method')}
- Failure Type: {payment.get('failure_type')}
- Failure Code: {payment.get('failure_code')}
- Current Retry Count: {payment.get('retry_count', 0)}
- Contact Count: {payment.get('contact_count', 0)}
- Risk Tier: {payment.get('risk_tier', 'LOW')}
- Channel: {payment.get('channel', 'MOBILE_APP')}

Action Catalog Available:
- RETRY_NOW: Immediate automated retry
- RETRY_30_MIN: Scheduled retry after 30 min
- RETRY_2_HOURS: Scheduled retry after 2 hours
- RETRY_NEXT_DAY: Scheduled retry next morning
- SEND_PAYMENT_LINK: Outbound multi-rail link
- SEND_REMINDER: Gentle notification
- REQUEST_CUSTOMER_ACTION: Update card / mandate
- HUMAN_ESCALATION: Ops manual review
- NO_ACTION: Do not intervene
- STOP: Terminate all recovery

Output strict JSON conforming to this schema:
{{
  "diagnosis": "<Concise diagnostic explanation of why the payment failed>",
  "confidence": <float between 0.1 and 1.0>,
  "candidate_actions": [
    {{
      "action": "<ONE_OF_ACTION_CATALOG>",
      "reason": "<Specific reason why this action is suitable>"
    }}
  ],
  "risk_flags": ["<Optional risk flags>"]
}}
"""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )

            response_text = response.text.strip()
            # Parse JSON and validate with Pydantic
            parsed_json = json.loads(response_text)
            validated_output = AIDiagnosisOutput.model_validate(parsed_json)
            
            logger.info("Successfully received Gemini AI diagnosis for %s", payment.get("payment_id"))
            return validated_output, AIMode.GEMINI

        except Exception as e:
            logger.warning("Gemini AI diagnosis failed or timed out (%s). Using Deterministic Fallback Engine.", str(e))
            return DeterministicFallbackEngine.diagnose(payment), AIMode.DETERMINISTIC_FALLBACK
