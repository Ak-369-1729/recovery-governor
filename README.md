# 🛡️ Recovery Governor

### Autonomous AI Revenue Recovery Decision Engine with Deterministic Financial Safety Policies
**Razorpay AI Buildathon 2026 — Track 03: AI Revenue Recovery**

> *An AI-powered revenue recovery decision engine that determines **WHEN**, **HOW**, and **WHETHER** to intervene on failed payments, optimizing for incremental revenue recovered while deterministic financial safety policies control every financial action.*

---

## 1. Executive Summary & Problem

Across digital payment ecosystems (UPI, Cards, Mandates, Netbanking), between **12% and 22% of all transaction attempts fail**. While many failures are transient, standard industry recovery methods are blunt and inefficient:
1. **Dumb Immediate Retries**: Most payment systems naively retry failed transactions immediately. For issuer switch downtimes or insufficient funds, retrying immediately has an ~80% failure rate, wasting gateway fees, triggering issuer throttling, and annoying customers.
2. **Hard Decline Violations**: Blind retry engines attempt to charge expired cards, hotlisted/stolen cards, and revoked mandates, triggering card network non-compliance fines and chargeback liability.
3. **Negative Economic Value**: For micro-transactions (e.g. ₹49), the cost of multiple gateway auth fees, risk penalties, and SMS dispatch exceeds the payment's value.
4. **False Attribution**: Existing analytics take 100% causal credit for any payment that settles within 24 hours, ignoring natural customer self-recovery (which accounts for ~5-12% of transient failures).

**Recovery Governor** solves this with a two-tier paradigm:
> **AI proposes. Deterministic code decides. Executor acts. Verifier confirms. Attribution measures. System learns.**

The deterministic Governor is the **single source of financial authority**. Even if an LLM hallucinates or suggests an unsafe retry, the Governor mathematically evaluates economic viability and deterministically enforces safety policies.

---

## 2. Core Architecture

```text
PAYMENT EVENT (UPI / Card / Mandate / Netbanking)
     ↓
CONTEXT ENGINE (History, attempts, cooldown, contact frequency, merchant policy)
     ↓
AI DIAGNOSIS (Gemini 2.5 Flash / Deterministic Fallback Engine)
     ↓
CANDIDATE ACTIONS (Action Catalog: RETRY_30_MIN, SEND_PAYMENT_LINK, STOP, etc.)
     ↓
ERV ENGINE (Net Expected Recovery Value calculation factoring costs & friction)
     ↓
DETERMINISTIC RECOVERY GOVERNOR (8 Financial Safety Gates)
     ↓
EXECUTOR (SimulationAdapter / RazorpayAdapter test mode with idempotency)
     ↓
VERIFIER (SUCCEEDED / FAILED / PENDING / UNKNOWN - never assumes success)
     ↓
ATTRIBUTION (Incremental Causal Lift vs Natural Control Recovery)
     ↓
LEARNING / BAYESIAN UPDATE (Conjugate Beta-Binomial update from verified outcomes)
     ↓
CRYPTOGRAPHIC AUDIT TRAIL (SHA-256 hash chained log)
```

---

## 3. The 8 Deterministic Governor Safety Gates

The Governor is deterministic code that sits between AI suggestions and payment rails. It executes **8 strict safety gates**:

| Gate | Name | Rule & Safety Invariant |
| :--- | :--- | :--- |
| **Gate 1** | **Hard Decline Ban** | Permanent hard declines (`CARD_LOST_STOLEN`, `MANDATE_REVOKED`, `ACCOUNT_CLOSED`, `PERMANENT_DECLINE`) are **permanently banned** from retries, regardless of AI recommendation. |
| **Gate 2** | **Retry Cap** | Hard ceiling on retry attempts (default: 3). Halts retries when exhausted. |
| **Gate 3** | **Cooldown** | Enforces minimum cool-off interval (default: 15 min) between attempts on the same payment method. |
| **Gate 4** | **Customer Contact Cap** | Limits proactive notifications (SMS/WhatsApp/Payment links) to max 2 in 24 hours to eliminate churn. |
| **Gate 5** | **Economic Hurdle** | Only allows actions where $\text{Net ERV} > 0$ and $\text{Net ERV} \ge \text{hurdle}$ (default ₹10). |
| **Gate 6** | **Idempotency** | Prevents duplicate charges by suppressing repeated webhook replay events (`idem_{payment_id}_{event_id}`). |
| **Gate 7** | **Confidence Threshold** | If AI confidence $< 0.50$, flags high uncertainty. High-ticket items escalate to human review; low-ticket items default to `NO_ACTION`. |
| **Gate 8** | **Stopping Rule** | If no candidate satisfies safety gates and economic hurdle, halts recovery with `NO_ACTION` or `STOP`. |

> **"The smartest recovery action can be doing nothing."**

---

## 4. Expected Recovery Value (ERV) Engine

The ERV Engine calculates the exact expected monetary return of every candidate action before authorization:

$$\text{Gross Expected Recovery} = P(\text{recovery} \mid \text{action}, \text{context}) \times \text{Payment Amount}$$

$$\text{Net ERV} = \text{Gross Expected Recovery} - \text{Intervention Cost} - \text{Risk Cost} - \text{Customer Friction Cost}$$

### Concrete Example
```text
Payment Amount (UPI)             ₹4,999.00
Recovery Probability (30-min)        64.0%
Expected Gross Recovery          ₹3,199.36

Intervention Fee (Gateway)           ₹5.00
Expected Risk Cost                   ₹4.00
Customer Friction Cost               ₹0.00
------------------------------------------
Net Expected Recovery Value (ERV) ₹3,190.36  ➔ [APPROVED: Viable & Profitable]
```

Contrast with a micro-transaction (₹49.00):
```text
Payment Amount (UPI)                ₹49.00
Recovery Probability                 15.0%
Expected Gross Recovery              ₹7.35

Intervention Fee (Gateway)           ₹5.00
Expected Risk Cost                   ₹4.00
Customer Friction Cost              ₹25.00
------------------------------------------
Net Expected Recovery Value (ERV)  -₹26.65  ➔ [BLOCKED: Gate 5 Negative ERV]
```

---

## 5. Bayesian Recovery Model (Beta-Binomial Learning)

The system maintains a conjugate Bayesian Beta-Binomial distribution for each `(failure_type, action, channel)` tuple:

$$\text{Prior}: \theta \sim \text{Beta}(\alpha, \beta)$$
$$\text{Posterior}: \theta \mid (s, f) \sim \text{Beta}(\alpha + s, \beta + f)$$
$$\text{Expected Probability}: \mathbb{E}[\theta] = \frac{\alpha + s}{\alpha + \beta + s + f}$$

- **Strict Invariant**: Only **verified** outcomes (`SUCCEEDED` or `FAILED`) update priors. Ambiguous or `UNKNOWN` outcomes never contaminate the model.
- Includes 95% Credible Intervals and variance tracking to quantify recovery uncertainty.

---

## 6. Causal Recovery Attribution

Recovery Governor differentiates between:
1. **ATTRIBUTED_RECOVERY**: Direct incremental recovery produced by the Governor's action.
2. **NATURAL_RECOVERY**: Transactions that self-resolve naturally (estimated via the Control cohort counterfactual).
3. **UNKNOWN**: Transactions with ambiguous settlement states (e.g. gateway timeout 504).
4. **FAILED_RECOVERY**: Interventions attempted where the transaction remained unrecovered.

$$\text{Net Incremental Revenue} = \text{Attributed Recovered Volume} - \text{Total Costs}$$

---

## 7. Three-Way Controlled Benchmark Results

Evaluated on **5,000 synthetic failed payment events** (seed: 42, representing ₹1.20 Crore of volume):

| Metric | CONTROL (No Intervention) | BASELINE (Naive Immediate Retry) | RECOVERY GOVERNOR | Governor Advantage |
| :--- | :--- | :--- | :--- | :--- |
| **Gross Volume Analyzed** | ₹11,976,164.42 | ₹11,976,164.42 | ₹11,976,164.42 | Identical Dataset |
| **Gross Revenue Recovered** | ₹659,658.60 | ₹3,402,789.93 | **₹5,758,242.25** | **+₹2,355,452.32 (+69.2%)** |
| **Recovery Rate** | 5.51% (Natural) | 28.41% | **48.08%** | **+19.67% absolute lift** |
| **Interventions Dispatched** | 0 | 5,000 (100% blind) | 4,454 (Selective) | 546 wasteful actions saved |
| **Intervention & Risk Costs** | ₹0.00 | ₹75,000.00 | ₹77,181.00 | Targeted cost allocation |
| **Unsafe Actions Blocked** | 0 | 0 (Violated card schemes) | **432 (100% Protected)** | Zero penalty risk |
| **Net Recovery Value** | ₹659,658.60 | ₹3,327,789.93 | **₹5,681,061.25** | **+₹2,353,271.32 (+70.7% net)** |

*Note: Data is synthetic evaluation data generated with fixed seed for full reproducibility.*

---

## 8. Chaos Engineering Laboratory (5 Scenarios)

The Chaos Lab tests the Governor under hostile and degraded operating conditions:
1. **Adversarial AI Prohibited Retry**: An LLM hallucinating or aggressively proposing retry on `MANDATE_REVOKED` is intercepted and blocked by Gate 1.
2. **Webhook Replay Storm**: 5 simultaneous duplicate failure events burst within milliseconds; 1 executes, 4 are suppressed by Gate 6 Idempotency.
3. **Gemini Outage Circuit Breaker**: Total LLM outage (503 / network timeout) gracefully falls back to the Deterministic Fallback Engine with 0 downtime.
4. **Negative ERV Economic Suppression**: Micro-payments where fees exceed expected returns trigger Gate 5 & Gate 8 `NO_ACTION`.
5. **Max Retry Cap Enforcement**: Payments with 3 prior attempts trigger Gate 2 `STOP`.

---

## 9. Quickstart & Installation

### Prerequisites
- Python 3.10+ (Tested on Python 3.14)
- **Zero Node/NPM dependencies** (Pure ES6 JavaScript frontend)

### Installation
```bash
git clone <repo-url>
cd recovery-governor
pip install -r requirements.txt
```

### Running the Application
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open **`http://127.0.0.1:8000/`** in your browser.

The database initializes automatically with SQLite in WAL mode and populates the 5,000 reproducible synthetic payments.

### Running Automated Tests
```bash
python -m pytest tests/ -v
```
All 19 tests validate the Governor gates, ERV engine, Bayesian learner, and chaos scenarios.

---

## 10. AI & Razorpay Configuration

The application runs completely out-of-the-box in **Deterministic Fallback + Simulation Mode** with zero external credentials required.

To optionally activate live Gemini LLM diagnosis or Razorpay test-mode API:
Create `.env` based on `.env.example`:
```env
# Optional Gemini AI API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Optional Razorpay Test Mode Credentials
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```
- If `GEMINI_API_KEY` is provided, live diagnosis uses `gemini-2.5-flash` with strict structured output.
- If missing or rate-limited, the system falls back seamlessly to the Deterministic Fallback Engine.

---

## 11. Project Structure

```text
recovery-governor/
│
├── app/
│   ├── main.py                  # FastAPI assembly, lifespan, static mounting
│   ├── config.py                # Environment and policy configuration
│   │
│   ├── api/                     # REST API Endpoints
│   │   ├── routes_dashboard.py  # Live metrics and taxonomy distributions
│   │   ├── routes_payments.py   # Recovery queue and payment details
│   │   ├── routes_decisions.py  # Decisions and Decision Replay
│   │   ├── routes_benchmark.py  # 3-Way benchmark runner
│   │   ├── routes_experiments.py# 4-Arm strategy experiment
│   │   ├── routes_chaos.py      # 5 Chaos scenario runners
│   │   ├── routes_audit.py      # Cryptographic audit logs and verification
│   │   └── routes_demo.py       # 2-minute live demo orchestration
│   │
│   ├── engine/                  # Core Algorithmic Engines
│   │   ├── governor.py          # Deterministic Recovery Governor (8 Gates)
│   │   ├── erv.py               # Expected Recovery Value (ERV) Engine
│   │   ├── bayesian.py          # Conjugate Beta-Binomial Bayesian Model
│   │   ├── diagnosis.py         # Gemini AI Diagnosis Engine
│   │   ├── fallback.py          # Deterministic Fallback Diagnosis Engine
│   │   ├── executor.py          # Simulation & Razorpay Test Adapters
│   │   ├── verifier.py          # Settlement Verifier (Succeeded/Failed/Unknown)
│   │   ├── attribution.py       # Causal Incremental Recovery Attribution
│   │   ├── synthetic_data.py    # 5,000 reproducible synthetic dataset generator
│   │   ├── benchmark.py         # Control / Baseline / Governor benchmark
│   │   ├── experiments.py       # A/B/n strategy testing
│   │   ├── chaos.py             # Resilience chaos laboratory
│   │   └── replay.py            # Chronological decision replay pipeline
│   │
│   ├── models/                  # Data Architecture
│   │   ├── database.py          # SQLite WAL mode initialization
│   │   ├── enums.py             # Failure taxonomy and action catalog
│   │   ├── schemas.py           # Strict Pydantic v2 schemas
│   │   └── repositories.py      # Data access layer & SHA-256 audit chaining
│   │
│   └── static/                  # Vanilla ES6 UI (Zero Node/NPM)
│       ├── index.html           # Single-page interface
│       ├── css/app.css          # Dark fintech Razorpay-inspired styling
│       └── js/                  # View controllers
│           ├── app.js
│           ├── dashboard.js
│           ├── payments.js
│           ├── replay.js
│           ├── benchmark.js
│           ├── experiments.js
│           ├── chaos.js
│           └── audit.js
│
├── tests/                       # Automated Test Suite (19 test cases)
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── ARCHITECTURE.md
├── DECISIONS.md
├── EVALUATION.md
├── DEMO.md
└── SECURITY.md
```

---

## 12. Known Limitations & Roadmap

### Limitations
1. **Network settlement delay**: In production, banking clearing cycles (NACH/e-Mandate) take up to 24-48 hours. In the prototype, these settlement windows are simulated or accelerated.
2. **Multi-currency**: Currently calibrated for INR (`₹`) transactions and Indian payment methods (UPI, Rupay/Visa/Mastercard, e-Mandates, Netbanking).
3. **Real Customer PII**: The dataset is 100% synthetic for privacy and PCI-DSS safety.

### Roadmap
- Reinforcement Learning with Human Feedback (RLHF) for high-ticket human escalation triage.
- Cross-merchant shared issuer health telemetry (detecting bank switch downtime before retries occur).
- Dynamic payment rail failover (e.g. auto-switching from HDFC UPI handle to ICICI handle during NPCI switch degradation).

---

## 13. License
Independent Prototype built for the **Razorpay AI Buildathon 2026 Track 03: AI Revenue Recovery**.
Not an official Razorpay product. Released under the Apache 2.0 License.
