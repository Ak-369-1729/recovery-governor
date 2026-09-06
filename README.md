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

## 9. Recovery Sandbox & Progressive Autonomy (Phase-2)

The **Recovery Sandbox** extends Recovery Governor into an interactive proving ground where AI models, recovery policies, and chaos scenarios are rigorously evaluated under strict deterministic governance.

```text
                    RECOVERY GOVERNOR
                           │
              ┌────────────┴────────────┐
              │                         │
       RECOVERY SANDBOX            EXISTING FLOWS
              │                         │
      ┌───────┼────────┐                │
      │       │        │                │
   Single  Portfolio  What-If           │
   Event   Simulation                   │
      │       │        │                │
      └───────┼────────┘                │
              ↓                         │
       Strategy Arena                   │
              ↓                         │
       Chaos / Shadow                   │
              ↓                         │
      Readiness Evaluation              │
              ↓                         │
    Constrained Autonomy                │
              │                         │
              └──────────┬──────────────┘
                         ↓
                 DETERMINISTIC
                    GOVERNOR
                         ↓
                     EXECUTOR
                         ↓
                    VERIFIER
                         ↓
                   ATTRIBUTION
                         ↓
                    LEARNING
```

### The Architectural Invariant
```text
AI
 ↓
Deterministic Recovery Governor
 ↓
Allowed Bounded Action
 ↓
Executor
```
> **Invariant**: AI proposes. Deterministic Governor decides. Direct financial execution by AI is permanently forbidden across all autonomy levels.

### 5 Architectural Upgrades
1. **Dynamic Action Catalog (Patch 1)**: What-If Simulator dynamically queries `ActionType` / `ACTION_CATALOG` to evaluate all candidate actions without hardcoded counts.
2. **Recovery AI Readiness Score (Patch 2)**: A deterministic, mathematically reproducible 0–100 score across 5 core dimensions:
   - **Safety Rate (30 pts)**: Zero tolerance for hard decline retries or card scheme rule violations.
   - **Economic Efficiency (25 pts)**: Ratio of Net ERV to gross recovery, preventing fee burning.
   - **Fallback Reliability (15 pts)**: Zero downtime under LLM failure; deterministic rules take over seamlessly.
   - **Decision Accuracy & Calibration (15 pts)**: Brier calibration score between predicted probabilities and verified outcomes.
   - **Verification & Attribution Quality (15 pts)**: Strict causal attribution; distinguishes natural settlement from interventions.
3. **Constrained Autonomy (Patch 3)**:
   - Autonomy progresses from `LEVEL_0_OBSERVE`, `LEVEL_1_RECOMMEND`, `LEVEL_2_SHADOW`, `LEVEL_3_GOVERNED_EXECUTION`, to `LEVEL_4_CONSTRAINED_AUTONOMOUS`.
   - **Even at Level 4**, the AI remains bounded by the 8 deterministic safety gates. The Governor retains exclusive financial authority.
4. **Single Event (Mode A) & Portfolio Simulation (Mode B) (Patch 4)**:
   - **Mode A (Single Event)**: 10-step full forensic pipeline trace (Scenario → Diagnosis → Candidate Actions → What-If ERV → Governor Gates → Execution → Verification → Attribution → Bayesian Learning).
   - **Mode B (Portfolio Simulation)**: Scalable multi-strategy tournament across synthetic populations (100, 1,000, 5,000, 10,000, 50,000) comparing `CONTROL`, `NAIVE_BASELINE`, `FIXED_DELAY_2H`, `ADAPTIVE`, and `GOVERNOR`. Fully reproducible using deterministic seeds.
5. **Counterfactual Replay (Patch 5)**:
   - Replays the actual executed strategy side-by-side with 3 simulated counterfactual trajectories:
     - **Counterfactual A**: Control (Do Nothing — measure baseline natural recovery without merchant cost)
     - **Counterfactual B**: Naive Baseline (Immediate blind retry — exposes burnt fees & regulatory violations)
     - **Counterfactual C**: Alternative Governor Policy (e.g. 2-Hour window or Payment Link)
   - Every counterfactual is explicitly labeled with **`SIMULATED COUNTERFACTUAL`** to preserve causal integrity.
6. **Emergency Global Kill Switch (Gate 0)**:
   - Instantaneous global thread-safe circuit breaker. When tripped, Gate 0 intercepts 100% of candidate actions, halts financial execution, and logs exposure prevented to the SHA-256 audit ledger.

---

## 10. Phase 3 & 3.1 Hardening: Predict → Prevent → Recover → Prove

In Phase 3.1, Recovery Governor evolved from a purely reactive post-failure engine into a unified revenue recovery intelligence layer that operates across the full payment lifecycle:

```text
PAYMENT ATTEMPT
      ↓
FAILURE PREDICTOR (Simulated Failure-Risk Estimate, Zero Future Leakage)
      ↓
PREDICTION + CONFIDENCE (Simulated Probability, Contributing Factors)
      ↓
PREDICTION EVALUATION (Brier Score & 5-Bin Reliability Tracking)
      ↓
PREVENTION CANDIDATES (Alternate Path, Cooldown Delay, User Notification)
      ↓
DETERMINISTIC RECOVERY GOVERNOR (5 Pre-Flight Safety Gates)
      ↓
BOUNDED ACTION (Approved / Suppressed / No Action)
      ↓
EXECUTOR (Simulation / Proposed SDK Adapter)
      ↓
VERIFIER (Confirmed Settlement / Timeout / Terminal Failure)
      ↓
ACTUAL OUTCOME
      ↓
CONSERVATIVE ATTRIBUTION (Prevented Failure vs Natural Success vs Unknown)
      ↓
PREDICTION ERROR / MODEL EVALUATION (Residual Bias & Feedback Loop)
      ↓
LEARNING / READINESS (Bayesian Priors & Empirical AI Readiness Score)
```

> **The Central Invariant**:
> **AI proposes → Deterministic Governor decides → Bounded action executes → Verifier confirms → Attribution measures → System learns.**
> The Predictor and LLM **NEVER** have financial authority.

### The 4 Hardening Pillars

#### 1. Removal of Unsupported "Calibrated" Claims
- Replaced all unverified "calibrated" terminology with honest descriptors: **simulated failure probability**, **deterministic failure-risk estimate**, and **Prediction Reliability**.
- The UI, API, schemas, and documentation transparently identify synthetic predictions as simulation-derived.

#### 2. Deterministic Prediction Evaluation Engine (`app/engine/prediction_evaluation.py`)
- Evaluates predictions against synthetic ground-truth outcomes with strictly **zero future outcome leakage**.
- **Classification Metrics**:
  - True Positive (TP), True Negative (TN), False Positive (FP), False Negative (FN)
  - Precision: $\frac{\text{TP}}{\text{TP} + \text{FP}}$
  - Recall: $\frac{\text{TP}}{\text{TP} + \text{FN}}$
  - F1 Score: $2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$
  - False Positive Rate: $\frac{\text{FP}}{\text{FP} + \text{TN}}$
  - Accuracy: $\frac{\text{TP} + \text{TN}}{\text{Total}}$
  - Returns `"N/A"` safely when samples are insufficient — never `null`, `NaN`, or `undefined`.
- **Probability Quality & Brier Score**:
  $$\text{Brier Score} = \frac{1}{N} \sum_{i=1}^N (\hat{p}_i - y_i)^2$$
  where $\hat{p}_i$ is the simulated failure probability and $y_i \in \{0, 1\}$ is the actual outcome (1 = failed, 0 = succeeded). Lower is better.
- **5-Bin Prediction Reliability Curve**:
  Evaluates reliability across $[0.0-0.2], [0.2-0.4], [0.4-0.6], [0.6-0.8], [0.8-1.0]$ buckets, displaying Sample Count, Predicted Average, Actual Failure Rate, and Prediction Error (Bias).

#### 3. Prevention Economics & Conservative Attribution
- **Conservative Attribution Categories**:
  - `PREVENTED_FAILURE`: Simulation provides counterfactual evidence that the intervention converted a failure to a success.
  - `NATURAL_SUCCESS`: Payment succeeded without requiring intervention.
  - `FAILED_PREVENTION`: Intervention was executed but the attempt still failed.
  - `UNKNOWN_PREVENTION`: Causal impact cannot be conclusively verified (prefers honesty over inflated claims).
- **Prevention Economics Metrics**:
  - Total payment attempts, high-risk predictions, approved preventive candidates, failures prevented, unnecessary interventions, prevented GMV, intervention cost, and net preventive economic value.

#### 4. Simulated Network Health Engine with Deterministic Seeds (`app/engine/network_health.py`)
- **Deterministic Scenario Presets**:
  - `NORMAL`: Healthy baseline across all payment rails.
  - `SBI_DEGRADED`: SBI UPI degradation scenario (e.g. 43.0 health, 380ms latency, 14.5% timeout rate).
  - `ICICI_DEGRADED`: Transient ICICI Netbanking degradation.
  - `MULTI_RAIL_DEGRADATION`: Systemic multi-rail network stress.
  - `UPI_OUTAGE`: Major UPI gateway outage requiring alternate payment methods.
  - `CARD_DEGRADATION`: 3D-Secure ACS server degradation.
  - `RECOVERY`: Upward recovery trajectory.
- **Repeatable Random Seeds**: Given the same scenario + seed (e.g. `seed=42`), telemetry outputs are mathematically identical.
- **7-Step Temporal Degradation Timeline**: Models health across time ($T-15\text{m}$ to $T+15\text{m}$), demonstrating how changing expected recovery value dynamically guides the Governor.
- **Honest Disclaimers**: Explicitly disclaims live Razorpay production routing authority; values are benchmark simulation presets.

---

## 11. Quickstart & Installation

### Prerequisites
- Python 3.10+ (Tested on Python 3.14)
- **Zero Node/NPM dependencies** (Pure ES6 JavaScript frontend)

### Installation
```bash
git clone https://github.com/Ak-369-1729/recovery-governor.git
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
**41 automated test cases** validate:
- 8 Deterministic Governor safety gates + Gate 0 Hardware Kill Switch
- ERV engine & Bayesian learner
- What-If simulator, Strategy Arena, Recovery AI Readiness Score, and Counterfactual Replay
- Failure Predictor (deterministic predictions, no outcome leakage, probability bounds)
- Prediction Evaluation Engine (Precision, Recall, F1, FPR, Brier score, 5-bin reliability, safe `"N/A"`)
- Simulated Network Health Engine (scenario presets, seed reproducibility, 7-step timeline)
- Preventive Governor Evaluation (ERV hurdle, merchant policy immunity, kill switch)
- Conservative Prevention Attribution & Unified 13-Stage Lifecycle

---

## 12. AI & Razorpay Configuration

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

## 13. Project Structure

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
│   │   ├── routes_chaos.py      # Resilience chaos runners
│   │   ├── routes_audit.py      # Cryptographic audit logs and verification
│   │   ├── routes_demo.py       # 2-minute live demo orchestration
│   │   ├── routes_sandbox.py    # Sandbox, What-If, Arena, Readiness, Kill-Switch APIs
│   │   ├── routes_prediction.py # Prediction evaluation, metrics, reliability curve, history
│   │   ├── routes_network.py    # Simulated network health & temporal timeline APIs
│   │   ├── routes_lifecycle.py  # 13-stage unified payment lifecycle orchestration
│   │   └── routes_merchant_policy.py # Merchant policy configuration
│   │
│   ├── engine/                  # Core Algorithmic Engines
│   │   ├── governor.py          # Deterministic Recovery Governor (8 Gates + Pre-Gate 0 Kill Switch)
│   │   ├── erv.py               # Expected Recovery Value (ERV) Engine
│   │   ├── bayesian.py          # Conjugate Beta-Binomial Bayesian Model
│   │   ├── diagnosis.py         # Gemini AI Diagnosis Engine
│   │   ├── fallback.py          # Deterministic Fallback Diagnosis Engine
│   │   ├── executor.py          # Simulation & Razorpay Test Adapters
│   │   ├── verifier.py          # Settlement Verifier (Succeeded/Failed/Unknown)
│   │   ├── attribution.py       # Causal Incremental Recovery & Prevention Attribution
│   │   ├── predictor.py         # Pre-flight Failure Predictor (No future leakage)
│   │   ├── prediction_evaluation.py # Brier score, F1, 5-bin reliability breakdown
│   │   ├── network_health.py    # Scenario-driven simulated network health with seeds
│   │   ├── merchant_policy.py   # Merchant policy manager with global safety immunity
│   │   ├── lifecycle.py         # Unified 13-stage payment lifecycle engine
│   │   ├── synthetic_data.py    # 5,000 reproducible synthetic dataset generator
│   │   ├── benchmark.py         # Control / Baseline / Governor benchmark
│   │   ├── experiments.py       # A/B/n strategy testing
│   │   ├── chaos.py             # Resilience chaos laboratory
│   │   ├── replay.py            # Chronological decision replay pipeline
│   │   └── sandbox.py           # What-If, Arena, Readiness, Autonomy Engine
│   │
│   ├── models/                  # Data Architecture
│   │   ├── database.py          # SQLite WAL mode initialization
│   │   ├── enums.py             # Failure taxonomy, action catalog & autonomy levels
│   │   ├── schemas.py           # Strict Pydantic v2 schemas
│   │   └── repositories.py      # Data access layer & SHA-256 audit chaining
│   │
│   └── static/                  # Vanilla ES6 UI (Zero Node/NPM)
│       ├── index.html           # Single-page interface with Payment Intelligence view
│       ├── css/app.css          # Dark fintech Razorpay-inspired styling
│       └── js/                  # View controllers
│           ├── app.js           # Router & navigation
│           ├── intelligence.js  # Payment Intelligence & Lifecycle view controller
│           ├── dashboard.js     # Overview metrics
│           ├── payments.js      # Recovery queue
│           ├── replay.js        # Decision replay
│           ├── benchmark.js     # 3-way benchmark
│           ├── experiments.js   # A/B/n experiments
│           ├── chaos.js         # Chaos lab
│           ├── audit.js         # Cryptographic audit
│           └── sandbox.js       # Recovery Sandbox view controller
│
├── tests/                       # Automated Test Suite (41 test cases)
│   ├── test_governor.py
│   ├── test_erv.py
│   ├── test_bayesian.py
│   ├── test_audit.py
│   ├── test_benchmark.py
│   ├── test_experiments.py
│   ├── test_chaos.py
│   ├── test_sandbox_phase2.py
│   └── test_phase3.py           # Phase 3 & 3.1 Hardening test suite
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

## 14. Known Limitations & Technical Disclosures

### Technical Disclosures
1. **Simulated Network Health**: Telemetry values (e.g. SBI health = 43.0) are scenario-driven simulation presets for benchmark stress testing, NOT live production feeds. In production, this engine would ingest verified PSP status webhooks.
2. **Proposed Merchant SDK Integration**: Actions like `RECOMMEND_ALTERNATE_PAYMENT_PATH` provide client-side payment routing recommendations to the checkout UI, rather than internal Razorpay production rail overrides.
3. **Conservative Prevention Attribution**: When causal evidence is insufficient to verify that an intervention altered the outcome, the system conservatively records `UNKNOWN_PREVENTION` rather than overstating lift.
4. **Parameterization**: Currently parameterized for INR (`₹`) transactions and Indian payment methods (UPI, Cards, e-Mandates, Netbanking).
5. **Real Customer PII**: The dataset is 100% synthetic for privacy and PCI-DSS compliance.

---

## 15. License
Independent Prototype built for the **Razorpay AI Buildathon 2026 Track 03: AI Revenue Recovery**.
Not an official Razorpay product. Released under the Apache 2.0 License.

