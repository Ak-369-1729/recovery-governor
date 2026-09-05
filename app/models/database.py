import sqlite3
from contextlib import contextmanager
from typing import Generator
from app.config import settings

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.db_path), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode and performance optimizations
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = OFF;")
    return conn

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            merchant_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'INR',
            payment_method TEXT NOT NULL,
            failure_type TEXT NOT NULL,
            failure_code TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            retry_count INTEGER DEFAULT 0,
            last_retry_at TEXT,
            contact_count INTEGER DEFAULT 0,
            merchant_policy TEXT,
            risk_tier TEXT DEFAULT 'LOW',
            channel TEXT DEFAULT 'MOBILE_APP',
            historical_recovery_probability REAL DEFAULT 0.5,
            status TEXT DEFAULT 'FAILED',
            natural_recovery_status TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
        CREATE INDEX IF NOT EXISTS idx_payments_failure_type ON payments(failure_type);
        CREATE INDEX IF NOT EXISTS idx_payments_timestamp ON payments(timestamp);

        CREATE TABLE IF NOT EXISTS payment_events (
            event_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (payment_id) REFERENCES payments(payment_id)
        );

        CREATE INDEX IF NOT EXISTS idx_events_payment ON payment_events(payment_id);

        CREATE TABLE IF NOT EXISTS decisions (
            decision_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            ai_diagnosis TEXT NOT NULL,
            ai_confidence REAL NOT NULL,
            ai_mode TEXT NOT NULL,
            candidate_actions TEXT NOT NULL,
            erv_by_action TEXT NOT NULL,
            policy_checks TEXT NOT NULL,
            blocked_actions TEXT NOT NULL,
            selected_action TEXT NOT NULL,
            decision_outcome TEXT NOT NULL,
            reason TEXT NOT NULL,
            governor_version TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (payment_id) REFERENCES payments(payment_id)
        );

        CREATE INDEX IF NOT EXISTS idx_decisions_payment ON decisions(payment_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_action ON decisions(selected_action);

        CREATE TABLE IF NOT EXISTS executions (
            execution_id TEXT PRIMARY KEY,
            decision_id TEXT NOT NULL,
            payment_id TEXT NOT NULL,
            action TEXT NOT NULL,
            adapter_type TEXT NOT NULL,
            status TEXT NOT NULL,
            response_payload TEXT NOT NULL,
            idempotency_key TEXT UNIQUE NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
            FOREIGN KEY (decision_id) REFERENCES decisions(decision_id)
        );

        CREATE INDEX IF NOT EXISTS idx_executions_payment ON executions(payment_id);
        CREATE INDEX IF NOT EXISTS idx_executions_idempotency ON executions(idempotency_key);

        CREATE TABLE IF NOT EXISTS verifications (
            verification_id TEXT PRIMARY KEY,
            execution_id TEXT NOT NULL,
            payment_id TEXT NOT NULL,
            status TEXT NOT NULL,
            evidence TEXT NOT NULL,
            verified_at TEXT NOT NULL,
            FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
            FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
        );

        CREATE INDEX IF NOT EXISTS idx_verifications_payment ON verifications(payment_id);

        CREATE TABLE IF NOT EXISTS attributions (
            attribution_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            category TEXT NOT NULL,
            counterfactual_method TEXT NOT NULL,
            recovered_amount REAL NOT NULL,
            net_recovered_value REAL NOT NULL,
            cost_breakdown TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (payment_id) REFERENCES payments(payment_id)
        );

        CREATE INDEX IF NOT EXISTS idx_attributions_payment ON attributions(payment_id);

        CREATE TABLE IF NOT EXISTS bayesian_priors (
            key TEXT PRIMARY KEY,
            alpha REAL NOT NULL,
            beta REAL NOT NULL,
            successes INTEGER DEFAULT 0,
            failures INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            payment_id TEXT NOT NULL,
            trace_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            hash TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_audit_payment ON audit_logs(payment_id);
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);

        CREATE TABLE IF NOT EXISTS benchmark_runs (
            run_id TEXT PRIMARY KEY,
            cohort_name TEXT NOT NULL,
            sample_size INTEGER NOT NULL,
            metrics TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            config TEXT NOT NULL,
            results TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
