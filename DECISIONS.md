# 📐 Architectural Decision Records (ADRs) — Recovery Governor

This document outlines key technical and product architecture decisions made in the engineering of Recovery Governor.

---

## ADR 01: Deterministic Code as the Single Source of Financial Authority

### Context
Large Language Models (LLMs) are probabilistic and generative. Allowing an LLM direct API execution authority introduces severe risks: hallucinated amounts, illegal retries on hotlisted cards, and card scheme fine violations (e.g. Visa/Mastercard excessive retry rules).

### Decision
The system enforces a strict boundary:
- **LLMs suggest hypotheses and candidate actions.**
- **Deterministic Python code evaluates the 8 safety gates and makes the binding execution decision.**

### Consequences
- **Positive**: Zero possibility of an AI hallucination triggering an unauthorized or illegal financial retry.
- **Negative**: The deterministic Governor must anticipate card scheme rules and maintain explicit gate logic.

---

## ADR 02: Zero Node/NPM Runtime Dependency (Vanilla ES6 + Modern CSS)

### Context
Modern web apps often require complex Node/NPM ecosystems, build tools (Webpack/Vite), and heavy runtime node_modules directories, complicating enterprise financial server deployments.

### Decision
Build the web UI using **Pure Vanilla ES6 JavaScript, Semantic HTML5, and Modern CSS Variables**, served directly by FastAPI's static mounting.

### Consequences
- **Positive**:
  - The application starts with a single command (`python -m uvicorn app.main:app`).
  - Zero vulnerability scan flags from transitive npm packages.
  - Extremely fast page load times and minimal memory footprint.
- **Positive**: Responsive, dark-themed Razorpay-inspired fintech design without framework overhead.

---

## ADR 03: SQLite with WAL Mode as Embedded Financial Datastore

### Context
The application requires high-performance local persistence for 5,000+ synthetic payments, decisions, executions, verifications, and cryptographic audit logs without requiring external database servers (Postgres/MySQL) to run demonstrations and benchmarks.

### Decision
Use SQLite with **Write-Ahead Logging (WAL)** mode enabled:
`PRAGMA journal_mode = WAL; PRAGMA synchronous = NORMAL;`

### Consequences
- **Positive**: Zero external database infrastructure setup; 100% self-contained and reproducible.
- **Positive**: Fast concurrent reads during dashboard queries and benchmark runs.

---

## ADR 04: Beta-Binomial Conjugate Model vs Complex Deep Bandit

### Context
The system needs to learn recovery probabilities over time across combinations of `(failure_type, action, channel)`.

### Decision
Implement a **Conjugate Beta-Binomial Bayesian Model**:
- Maintains $\text{Beta}(\alpha + \text{successes}, \beta + \text{failures})$.
- Computes exact posterior means, variances, and 95% Credible Intervals.
- Updates strictly on verified outcomes.

### Consequences
- **Positive**: Mathematically transparent and auditable by financial regulators (no black-box neural networks).
- **Positive**: Naturally incorporates strong domain priors (e.g., temporary issuer recovery windows vs instant retry).
- **Positive**: Extremely fast $O(1)$ computation suitable for real-time payment authorization pipelines.

---

## ADR 05: Explicit UNKNOWN State in Settlement Verification

### Context
When payment gateways return 504 timeouts, ambiguous webhook statuses, or missing callbacks, many legacy retry systems assume either failure (premature retry causing double debit) or success (leaving revenue uncollected).

### Decision
Enforce a first-class **UNKNOWN** verification state. Transactions in the UNKNOWN state:
1. Are never assumed to have succeeded or failed.
2. Are blocked from updating the Bayesian learning model until reconciled.
3. Suppress automated retries until status ambiguity resolves.

### Consequences
- **Positive**: Completely eliminates the risk of double-charging customers during banking gateway timeouts.
