import json
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.models.database import get_db

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# ==============================================================================
# Payments Repository
# ==============================================================================
def insert_payment(payment: Dict[str, Any]):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO payments (
                payment_id, merchant_id, customer_id, amount, currency,
                payment_method, failure_type, failure_code, timestamp,
                retry_count, last_retry_at, contact_count, merchant_policy,
                risk_tier, channel, historical_recovery_probability, status,
                natural_recovery_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payment["payment_id"],
            payment["merchant_id"],
            payment["customer_id"],
            payment["amount"],
            payment.get("currency", "INR"),
            payment["payment_method"],
            payment["failure_type"],
            payment["failure_code"],
            payment["timestamp"],
            payment.get("retry_count", 0),
            payment.get("last_retry_at"),
            payment.get("contact_count", 0),
            json.dumps(payment.get("merchant_policy", {})),
            payment.get("risk_tier", "LOW"),
            payment.get("channel", "MOBILE_APP"),
            payment.get("historical_recovery_probability", 0.5),
            payment.get("status", "FAILED"),
            payment.get("natural_recovery_status"),
            payment.get("created_at", utc_now_iso())
        ))

def insert_payments_batch(payments: List[Dict[str, Any]]):
    with get_db() as conn:
        conn.executemany("""
            INSERT OR REPLACE INTO payments (
                payment_id, merchant_id, customer_id, amount, currency,
                payment_method, failure_type, failure_code, timestamp,
                retry_count, last_retry_at, contact_count, merchant_policy,
                risk_tier, channel, historical_recovery_probability, status,
                natural_recovery_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                p["payment_id"],
                p["merchant_id"],
                p["customer_id"],
                p["amount"],
                p.get("currency", "INR"),
                p["payment_method"],
                p["failure_type"],
                p["failure_code"],
                p["timestamp"],
                p.get("retry_count", 0),
                p.get("last_retry_at"),
                p.get("contact_count", 0),
                json.dumps(p.get("merchant_policy", {})),
                p.get("risk_tier", "LOW"),
                p.get("channel", "MOBILE_APP"),
                p.get("historical_recovery_probability", 0.5),
                p.get("status", "FAILED"),
                p.get("natural_recovery_status"),
                p.get("created_at", utc_now_iso())
            )
            for p in payments
        ])

def get_payment(payment_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("merchant_policy"):
            try:
                d["merchant_policy"] = json.loads(d["merchant_policy"])
            except Exception:
                pass
        return d

def list_payments(limit: int = 50, offset: int = 0, status: Optional[str] = None, failure_type: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM payments WHERE 1=1"
    params: List[Any] = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if failure_type:
        query += " AND failure_type = ?"
        params.append(failure_type)
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("merchant_policy"):
                try:
                    d["merchant_policy"] = json.loads(d["merchant_policy"])
                except Exception:
                    pass
            result.append(d)
        return result

def count_payments(status: Optional[str] = None) -> int:
    query = "SELECT COUNT(*) FROM payments"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    with get_db() as conn:
        return conn.execute(query, params).fetchone()[0]

def update_payment_status(payment_id: str, status: str, retry_increment: int = 0, contact_increment: int = 0, last_retry_at: Optional[str] = None):
    with get_db() as conn:
        conn.execute("""
            UPDATE payments 
            SET status = ?, 
                retry_count = retry_count + ?, 
                contact_count = contact_count + ?,
                last_retry_at = COALESCE(?, last_retry_at)
            WHERE payment_id = ?
        """, (status, retry_increment, contact_increment, last_retry_at, payment_id))

# ==============================================================================
# Payment Events Repository
# ==============================================================================
def insert_payment_event(event_id: str, payment_id: str, event_type: str, payload: Dict[str, Any]):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO payment_events (event_id, payment_id, event_type, payload, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (event_id, payment_id, event_type, json.dumps(payload), utc_now_iso()))

def list_events_for_payment(payment_id: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM payment_events WHERE payment_id = ? ORDER BY timestamp ASC", (payment_id,)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d["payload"])
            except Exception:
                pass
            results.append(d)
        return results

# ==============================================================================
# Decisions Repository
# ==============================================================================
def insert_decision(decision: Dict[str, Any]):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO decisions (
                decision_id, payment_id, event_id, ai_diagnosis, ai_confidence,
                ai_mode, candidate_actions, erv_by_action, policy_checks,
                blocked_actions, selected_action, decision_outcome, reason,
                governor_version, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            decision["decision_id"],
            decision["payment_id"],
            decision["event_id"],
            json.dumps(decision.get("ai_diagnosis", {})),
            decision["ai_confidence"],
            decision["ai_mode"],
            json.dumps(decision["candidate_actions"]),
            json.dumps(decision["erv_by_action"]),
            json.dumps(decision["policy_checks"]),
            json.dumps(decision["blocked_actions"]),
            decision["selected_action"],
            decision.get("decision_outcome") or decision.get("decision"),
            decision["reason"],
            decision.get("governor_version", "1.0.0"),
            decision.get("timestamp", utc_now_iso())
        ))

def get_decision_by_id(decision_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        if not row:
            return None
        return _unpack_decision_row(dict(row))

def get_latest_decision_for_payment(payment_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM decisions WHERE payment_id = ? ORDER BY timestamp DESC LIMIT 1", (payment_id,)).fetchone()
        if not row:
            return None
        return _unpack_decision_row(dict(row))

def list_decisions(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [_unpack_decision_row(dict(r)) for r in rows]

def _unpack_decision_row(d: Dict[str, Any]) -> Dict[str, Any]:
    for col in ["ai_diagnosis", "candidate_actions", "erv_by_action", "policy_checks", "blocked_actions"]:
        if d.get(col):
            try:
                d[col] = json.loads(d[col])
            except Exception:
                pass
    return d

# ==============================================================================
# Executions & Verifications Repository
# ==============================================================================
def insert_execution(execution: Dict[str, Any]):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO executions (
                execution_id, decision_id, payment_id, action, adapter_type,
                status, response_payload, idempotency_key, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            execution["execution_id"],
            execution["decision_id"],
            execution["payment_id"],
            execution["action"],
            execution["adapter_type"],
            execution["status"],
            json.dumps(execution.get("response_payload", {})),
            execution["idempotency_key"],
            execution.get("timestamp", utc_now_iso())
        ))

def get_execution_by_idempotency(idempotency_key: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM executions WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["response_payload"] = json.loads(d["response_payload"])
        except Exception:
            pass
        return d

def get_latest_execution_for_payment(payment_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM executions WHERE payment_id = ? ORDER BY timestamp DESC LIMIT 1", (payment_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["response_payload"] = json.loads(d["response_payload"])
        except Exception:
            pass
        return d

def insert_verification(verification: Dict[str, Any]):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO verifications (
                verification_id, execution_id, payment_id, status, evidence, verified_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            verification["verification_id"],
            verification["execution_id"],
            verification["payment_id"],
            verification["status"],
            json.dumps(verification.get("evidence", {})),
            verification.get("verified_at", utc_now_iso())
        ))

def get_latest_verification_for_payment(payment_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM verifications WHERE payment_id = ? ORDER BY verified_at DESC LIMIT 1", (payment_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["evidence"] = json.loads(d["evidence"])
        except Exception:
            pass
        return d

# ==============================================================================
# Attributions Repository
# ==============================================================================
def insert_attribution(attribution: Dict[str, Any]):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO attributions (
                attribution_id, payment_id, category, counterfactual_method,
                recovered_amount, net_recovered_value, cost_breakdown, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            attribution["attribution_id"],
            attribution["payment_id"],
            attribution["category"],
            attribution["counterfactual_method"],
            attribution["recovered_amount"],
            attribution["net_recovered_value"],
            json.dumps(attribution.get("cost_breakdown", {})),
            attribution.get("timestamp", utc_now_iso())
        ))

def get_latest_attribution_for_payment(payment_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM attributions WHERE payment_id = ? ORDER BY timestamp DESC LIMIT 1", (payment_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["cost_breakdown"] = json.loads(d["cost_breakdown"])
        except Exception:
            pass
        return d

# ==============================================================================
# Cryptographic Audit Log Repository
# ==============================================================================
def get_latest_audit_hash() -> str:
    with get_db() as conn:
        row = conn.execute("SELECT hash FROM audit_logs ORDER BY rowid DESC LIMIT 1").fetchone()
        if row and row[0]:
            return row[0]
        # Genesis hash for the initial block
        return "0" * 64

def insert_audit_log(event_type: str, payment_id: str, trace_id: str, payload: Dict[str, Any]) -> str:
    timestamp = utc_now_iso()
    prev_hash = get_latest_audit_hash()
    
    # Calculate SHA-256 hash chaining previous hash + payload + timestamp
    raw_str = f"{prev_hash}|{event_type}|{payment_id}|{trace_id}|{json.dumps(payload, sort_keys=True)}|{timestamp}"
    current_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
    log_id = f"aud_{hashlib.sha256(f'{payment_id}_{timestamp}'.encode()).hexdigest()[:16]}"
    
    with get_db() as conn:
        conn.execute("""
            INSERT INTO audit_logs (log_id, event_type, payment_id, trace_id, payload, prev_hash, hash, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (log_id, event_type, payment_id, trace_id, json.dumps(payload), prev_hash, current_hash, timestamp))
    return log_id

def list_audit_logs(limit: int = 50, offset: int = 0, payment_id: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    if payment_id:
        query += " AND payment_id = ?"
        params.append(payment_id)
    query += " ORDER BY rowid DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d["payload"])
            except Exception:
                pass
            results.append(d)
        return results

def verify_audit_chain_integrity() -> Dict[str, Any]:
    """Verifies that every block in the audit trail has a valid SHA-256 link."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM audit_logs ORDER BY rowid ASC").fetchall()
        
    if not rows:
        return {"total_records": 0, "is_valid": True, "tampered_record_id": None}

    expected_prev_hash = "0" * 64
    for r in rows:
        d = dict(r)
        if d["prev_hash"] != expected_prev_hash:
            return {"total_records": len(rows), "is_valid": False, "tampered_record_id": d["log_id"]}
        
        # Verify recalculation
        raw_str = f"{d['prev_hash']}|{d['event_type']}|{d['payment_id']}|{d['trace_id']}|{json.dumps(json.loads(d['payload']), sort_keys=True)}|{d['timestamp']}"
        calculated_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
        if calculated_hash != d["hash"]:
            return {"total_records": len(rows), "is_valid": False, "tampered_record_id": d["log_id"]}
            
        expected_prev_hash = d["hash"]

    return {"total_records": len(rows), "is_valid": True, "tampered_record_id": None}

# ==============================================================================
# Bayesian Priors Repository
# ==============================================================================
def get_bayesian_record(key: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM bayesian_priors WHERE key = ?", (key,)).fetchone()
        return dict(row) if row else None

def upsert_bayesian_record(key: str, alpha: float, beta: float, successes: int, failures: int):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO bayesian_priors (key, alpha, beta, successes, failures, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (key, alpha, beta, successes, failures, utc_now_iso()))

def get_all_bayesian_records() -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM bayesian_priors ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

# ==============================================================================
# Benchmark & Experiments Repository
# ==============================================================================
def save_benchmark_run(run_id: str, cohort_name: str, sample_size: int, metrics: Dict[str, Any]):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO benchmark_runs (run_id, cohort_name, sample_size, metrics, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (run_id, cohort_name, sample_size, json.dumps(metrics), utc_now_iso()))

def get_latest_benchmark_runs(sample_size: Optional[int] = None) -> Dict[str, Any]:
    with get_db() as conn:
        if sample_size:
            rows = conn.execute("""
                SELECT * FROM benchmark_runs 
                WHERE sample_size = ?
                ORDER BY created_at DESC LIMIT 3
            """, (sample_size,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM benchmark_runs 
                WHERE run_id IN (
                    SELECT run_id FROM benchmark_runs ORDER BY created_at DESC LIMIT 3
                )
            """).fetchall()
        runs = {}
        for r in rows:
            d = dict(r)
            try:
                d["metrics"] = json.loads(d["metrics"])
            except Exception:
                pass
            runs[d["cohort_name"]] = d
        return runs

def save_experiment_run(experiment_id: str, name: str, config: Dict[str, Any], results: Dict[str, Any]):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO experiments (experiment_id, name, config, results, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (experiment_id, name, json.dumps(config), json.dumps(results), utc_now_iso()))

def get_latest_experiments(limit: int = 10) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["config"] = json.loads(d["config"])
                d["results"] = json.loads(d["results"])
            except Exception:
                pass
            results.append(d)
        return results
