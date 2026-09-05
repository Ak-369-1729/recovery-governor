# 🏗️ Architecture Design Document — Recovery Governor

## 1. Architectural Philosophy

The core architectural invariant of **Recovery Governor** is:
> **AI proposes. Deterministic code decides. Executor acts. Verifier confirms. Attribution measures. System learns.**

Under no circumstances does an LLM possess direct execution authority over financial rails. The LLM acts solely as a **probabilistic context diagnostic advisor**, translating failure codes, telemetry, and customer histories into structured hypotheses and candidate actions. The **Recovery Governor** functions as a deterministic financial firewall that mathematically evaluates viability and enforces regulatory, card scheme, and merchant risk rules.

---

## 2. Component Diagram

```
+---------------------------------------------------------------------------------+
|                                 PAYMENT EVENT                                   |
|                (UPI, Cards, Netbanking, Mandates, Wallets)                      |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                                CONTEXT ENGINE                                   |
|   - Historical recovery probabilities                                           |
|   - Prior retry attempts & last retry timestamp                                 |
|   - Customer contact count (24h window)                                         |
|   - Merchant policy rules (caps, cooldown, hurdle)                              |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                             AI DIAGNOSIS ENGINE                                 |
|   - Primary: Gemini 2.5 Flash via google-genai SDK                              |
|   - Circuit Breaker: DeterministicFallbackEngine on timeout/outage/missing key  |
|   - Output: Strict Pydantic-validated AIDiagnosisOutput                         |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                                  ERV ENGINE                                     |
|   - Net ERV = P(recovery|context) * Amount - Intervention - Risk - Friction     |
|   - Bayesian Beta-Binomial posterior base probability                           |
|   - Diminishing return decay on repeated retries                                |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                        DETERMINISTIC RECOVERY GOVERNOR                          |
|                     [SINGLE SOURCE OF FINANCIAL AUTHORITY]                      |
|                                                                                 |
|   Gate 1: Hard Decline Ban (Permanently blocks stolen cards/revoked mandates)   |
|   Gate 2: Retry Cap (Enforces hard ceiling on attempts)                         |
|   Gate 3: Cooldown (Enforces minimum cool-off duration)                         |
|   Gate 4: Customer Contact Cap (Protects customer relationship from spam)       |
|   Gate 5: Economic Hurdle (Blocks actions with negative or sub-hurdle Net ERV)  |
|   Gate 6: Idempotency (Suppresses duplicate webhook storms)                     |
|   Gate 7: Confidence Threshold (Escalates low-confidence high-value payments)   |
|   Gate 8: Stopping Rule (Explicit NO_ACTION / STOP when intervention unwisely)  |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                                EXECUTOR LAYER                                   |
|   - SimulationAdapter: Deterministic high-speed simulation                      |
|   - RazorpayAdapter: Live test-mode API integration (Payment Links, etc.)       |
|   - Idempotency key tracking: idem_{payment_id}_{event_id}                      |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                              VERIFICATION ENGINE                                |
|   - States: SUCCEEDED, FAILED, PENDING, UNKNOWN                                 |
|   - Invariant: Unverified / ambiguous outcomes NEVER default to success         |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                             ATTRIBUTION ENGINE                                  |
|   - Distinguishes ATTRIBUTED_RECOVERY from NATURAL_RECOVERY                     |
|   - Counterfactual baseline estimation from Control Cohort                      |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                        BAYESIAN LEARNING & AUDIT                                |
|   - Conjugate Beta-Binomial update: Beta(alpha + s, beta + f)                   |
|   - SHA-256 cryptographic audit chain linkage (prev_hash -> hash)               |
+---------------------------------------------------------------------------------+
```

---

## 3. Data Pipeline & Storage Schema

SQLite is configured with **Write-Ahead Logging (WAL)** mode for concurrent reads and serialized writes:
- `payments`: Master record of all failed payment events.
- `payment_events`: Event stream history.
- `decisions`: Immutable record of every Governor decision, including candidate ERVs and policy checks.
- `executions`: Record of executed or suppressed action dispatches.
- `verifications`: Settlement verification states and reconciliation evidence.
- `attributions`: Causal classification (Attributed vs Natural) and net revenue calculation.
- `bayesian_priors`: Persistent learned distribution parameters ($\alpha, \beta, s, f$).
- `audit_logs`: Append-only cryptographic ledger with SHA-256 hash chaining.
- `benchmark_runs`: Persisted 3-way evaluation results.
- `experiments`: Multi-arm A/B/n test results.

---

## 4. Resilience & Fallback Architecture

To ensure high availability, the AI component is wrapped in an active circuit breaker:
1. When `GEMINI_API_KEY` is present and responsive, structured diagnoses are generated in ~600ms.
2. If the API key is missing, network degrades, rate limits are reached, or JSON parsing fails, the system immediately degrades to the `DeterministicFallbackEngine` without throwing an unhandled exception or delaying transactions.
3. Both Gemini and Fallback outputs pass through the identical Pydantic `AIDiagnosisOutput` validation schema, ensuring downstream Governor code operates identically regardless of AI mode.
