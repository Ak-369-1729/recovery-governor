# 🔒 Security & Compliance Specification — Recovery Governor

Recovery Governor is engineered with zero-trust architectural boundaries tailored for enterprise fintech payment recovery infrastructure.

---

## 1. Zero Direct AI Execution Authority

The foundational security posture is:
**The Large Language Model is an untrusted advisory component.**
- The LLM cannot directly call payment gateways.
- The LLM cannot initiate credit, debit, refund, or retry calls.
- The LLM cannot alter financial limits, retry caps, or merchant safety thresholds.
- All AI responses must strictly conform to Pydantic v2 schemas (`AIDiagnosisOutput`). Any schema failure or malformed payload triggers an immediate fallback to the rule-based `DeterministicFallbackEngine`.

---

## 2. Hard Decline Scheme Protection (Gate 1)

Card schemes (Visa, Mastercard, RuPay) and payment networks (NPCI) impose strict fines for repeated retries on permanent decline reason codes.
Recovery Governor enforces an unbypassable hard decline ban for:
- `CARD_LOST_STOLEN` (Reason code 41/43)
- `MANDATE_REVOKED` (Customer cancelled mandate)
- `ACCOUNT_CLOSED` (Account dormant or closed)
- `PERMANENT_DECLINE` (Suspected fraud / Do Not Honor)

Even if an AI model or merchant webhook suggests retrying, Gate 1 intercepts and halts recovery with `STOP`.

---

## 3. Idempotency & Double-Debit Prevention (Gate 6)

To protect against duplicate webhook storms, network retry storms, or replay attacks:
1. Every action generates an idempotency key: `idem_{payment_id}_{event_id}`.
2. The `executions` table enforces a `UNIQUE` constraint on `idempotency_key`.
3. If an identical event is re-delivered, Gate 6 intercepts the event and returns `DecisionOutcome.SUPPRESS` without calling external banking APIs.

---

## 4. Cryptographic Audit Chain (SHA-256)

Every payment decision, execution, and verification event generates an immutable audit record:
- Each block records `prev_hash`, `timestamp`, `event_type`, `payment_id`, and `payload`.
- The current block's hash is computed via:
  $$\text{hash} = \text{SHA-256}(\text{prev\_hash} \parallel \text{event\_type} \parallel \text{payment\_id} \parallel \text{trace\_id} \parallel \text{payload} \parallel \text{timestamp})$$
- The audit log can be verified in $O(N)$ time via `/api/audit/verify` to detect any manual tampering or database record corruption.

---

## 5. Credential Isolation & Environment Security

- API keys (`GEMINI_API_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`) are read strictly from server-side environment variables or `.env`.
- API keys are **never serialized** to API response schemas or frontend client bundles.
- If credentials are absent, the application functions in 100% Simulation Mode without crashing or leaking stack traces.
- `.env` and `.db` files are included in `.gitignore` to prevent credential exposure.

---

## 6. Synthetic Data Integrity & PCI-DSS Safety

- **Zero Real Customer Data**: All 5,000 failed payment records are synthetic.
- **Zero Real Card/BIN/IFSC Information**: No real credit card PANs, CVVs, expiration dates, or bank account numbers are processed or stored.
- All identifiers are synthetic format-valid strings (`pay_syn_...`, `cust_syn_...`).
