# 🎬 2-Minute Live Product Demonstration Guide — Recovery Governor

This guide provides a rapid 2-minute walkthrough for hackathon judges and technical evaluators.

---

## Step 1: Start the Application

```powershell
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open **`http://127.0.0.1:8000/`** in your web browser.

---

## Step 2: Overview Dashboard (30 Seconds)
1. Notice the top metrics:
   - **Revenue at Risk**: ~₹1.20 Crore across 5,000 synthetic transactions.
   - **Incrementally Recovered**: Demonstrates verified causal lift.
   - **Unsafe Actions Blocked**: 432 permanent declines stopped by Gate 1.
2. Scroll to the **Failed Payment Etiology Matrix**:
   - Observe how failures are categorized into temporary issuer glitches, network timeouts, expired instruments, and hard declines.
3. Review the **Bayesian Recovery Model** table:
   - See the dynamic Beta(α, β) distributions that learn recovery probabilities exclusively from verified settlements.

---

## Step 3: Run the 3-Scenario Guided Demo (45 Seconds)
Click **Live Demo** (`#demo`) in the sidebar, and click **▶ Run All 3 Scenarios**:

1. **Scenario 1: Intelligent Recovery of High-Value Failure**
   - A ₹4,999 UPI transaction fails due to issuer switch downtime.
   - Immediate retry would fail. Governor computes Net ERV of ₹3,156 for `RETRY_30_MIN`, authorizes it, and successfully recovers the full ₹4,999.
2. **Scenario 2: Single Source of Authority (Gate 1 Hard Decline Ban)**
   - AI proposes immediate retry on a ₹12,500 recurring mandate with `MANDATE_REVOKED`.
   - The deterministic Governor overrides and blocks the AI's proposal: retrying revoked mandates violates card scheme rules. Recovery is halted with `STOP`.
3. **Scenario 3: The Smartest Action is Doing Nothing (Negative ERV)**
   - A ₹49 micro-transaction fails for insufficient funds.
   - Intervention fees + friction cost = ₹25, while gross expected return is only ₹4.20 (Net ERV = -₹20.80).
   - Governor enforces Gate 5 & Gate 8 Stopping Rule: `NO_ACTION`.

---

## Step 4: Decision Replay & 8-Stage Audit Trace (30 Seconds)
1. Click **Decision Replay** (`#replay`) in the sidebar.
2. Enter `pay_syn_00001` (or pick any payment from the Recovery Queue).
3. Walk through the 8 chronological stages:
   - **Stage 1**: Raw Payment Event
   - **Stage 2**: Payment Context & Profile
   - **Stage 3**: AI Failure Etiology Diagnosis
   - **Stage 4**: Expected Recovery Value (ERV) Math Breakdown
   - **Stage 5**: Deterministic Safety Gate Evaluation (all 8 gates)
   - **Stage 6**: Action Dispatch via Executor
   - **Stage 7**: Settlement Verification
   - **Stage 8**: Causal Revenue Attribution

---

## Step 5: Chaos Lab & Cryptographic Audit Trail (15 Seconds)
1. Click **Chaos Lab** (`#chaos`):
   - Click **Trigger Scenario Now** on *Adversarial AI Prohibited Retry Interception*.
   - Watch the backend intercept the rogue proposal and output a green **PASSED** verdict.
2. Click **Audit Trail** (`#audit`):
   - Inspect the chronologically chained records with SHA-256 hashes.
   - Click **Verify Hash Chain Integrity** to verify the cryptographic links across every block.
