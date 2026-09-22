"""
Division 2 - persistent store. Dual-backend persistence:

- PostgreSQL when the DATABASE_URL environment variable is set. Render's
  free web tier has an EPHEMERAL filesystem - aegis.db would be wiped on
  every restart, redeploy, or free-tier spin-down, silently destroying the
  real login/persistence feature. Render's free Postgres (a separate
  service that survives web-service restarts) is therefore the production
  store. DATABASE_URL may also live in <repo root>/app/.env (loaded below).
- SQLite at <repo root>/aegis.db otherwise (local development, unchanged
  from the previous version of this file).

All table/column names and all function names/signatures are IDENTICAL
across backends; only the connection layer differs: _conn() picks the
driver, and _run() translates '?' placeholders to psycopg2's '%s' when on
Postgres. Rows are dict-like in both cases (sqlite3.Row / DictRow).

Timestamps are stored as ISO-8601 text and are ALWAYS converted back into
real Python datetime objects on read - several call sites
(feature_engineering.py's SIM-swap day-count math, USSD's hour extraction)
call datetime methods directly on these fields, so returning raw strings
would be a silent, hard-to-diagnose runtime crash.

_conn() is a CONTEXT MANAGER, not a plain function, and every function
below uses "with _conn() as conn:" - this guarantees the connection is
closed even if the code inside raises (e.g. a UNIQUE-constraint violation
on duplicate registration). Without this guarantee, a single failed write
leaks an open connection; on Postgres an aborted transaction also rolls
back when the connection closes.

.env loading: <repo root>/app/.env (then <repo root>/.env) is read at
import time and any key not already present in os.environ is set from it.
Real environment variables always win over the file.
"""
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", "..", ".."))
DB_PATH = os.path.join(_REPO_ROOT, "aegis.db")

# Division 5B - rolling OTP request count considered anomalous (used by
# sim_swap_module.py). 3+ requests in the rolling window matches the same
# industry-standard OTP/PIN retry threshold already used for the USSD
# session_retry_deviation feature elsewhere in this project.
OTP_REQUEST_ANOMALY_THRESHOLD = 3


def _load_env_file() -> None:
    for rel in ("app/.env", ".env"):
        path = os.path.join(_REPO_ROOT, rel)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ.setdefault(key, value)
        except OSError:
            pass


_load_env_file()

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
_IS_PG = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")

if _IS_PG:
    import psycopg2
    import psycopg2.extras
    # Render's dashboard shows the URL with the postgres:// scheme; libpq
    # accepts it, but normalise to postgresql:// for clarity.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]


@contextmanager
def _conn():
    if _IS_PG:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
    else:
        # Default (rollback-journal) mode, not WAL: WAL requires proper
        # shared-memory-mapped file locking, which cloud-synced folders
        # (OneDrive, Dropbox, Google Drive) and some container/network
        # filesystems handle unreliably - this repo lives in OneDrive, so
        # WAL risked intermittent "database is locked" errors, including
        # live during a demo. A timeout lets a transient lock (e.g.
        # OneDrive briefly touching the file) retry instead of failing
        # immediately.
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _run(conn, sql, params=()):
    """Run one statement on either backend. '?' placeholders are translated
    to psycopg2's '%s' when on Postgres. Returns the cursor; rows are
    dict-like (and positionally indexable) in both backends."""
    cur = conn.cursor()
    if _IS_PG:
        sql = sql.replace("?", "%s")
    cur.execute(sql, params)
    return cur


def _now() -> datetime:
    return datetime.utcnow()


def _gen_id() -> str:
    return str(uuid.uuid4())


def _to_iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


def _from_iso(s) -> datetime | None:
    return datetime.fromisoformat(s) if s is not None else None


def hash_pin(pin: str) -> str:
    """Real hashing (sha256, no salt) - a deliberate, documented simplification
    for a hackathon demo; production would use bcrypt/argon2 with a per-user
    salt. Never store or compare the raw PIN anywhere."""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def verify_pin(user: dict, pin: str) -> bool:
    return bool(user) and user.get("pin_hash") == hash_pin(pin)


_DDL = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        msisdn TEXT UNIQUE NOT NULL,
        pin_hash TEXT,
        account_number TEXT,
        nin TEXT,
        bvn TEXT,
        avatar_data_url TEXT,
        is_freshly_registered INTEGER DEFAULT 0,
        balance REAL NOT NULL DEFAULT 500000,
        blocked_until TEXT,
        account_created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS telco_state (
        user_id TEXT PRIMARY KEY,
        imei TEXT,
        sim_device_paired INTEGER,
        last_sim_swap_at TEXT
    );
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        channel TEXT,
        device_fingerprint TEXT,
        ip_address TEXT,
        started_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        session_id TEXT,
        user_id TEXT,
        beneficiary_account TEXT,
        beneficiary_is_novel INTEGER,
        amount REAL,
        requested_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS behavioral_events (
        id TEXT PRIMARY KEY,
        session_id TEXT,
        event_type TEXT,
        key_dwell_ms INTEGER,
        key_flight_ms INTEGER,
        is_paste INTEGER,
        backspace_count INTEGER,
        nav_screen TEXT,
        cursor_smoothness_score REAL,
        call_active INTEGER,
        recorded_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ussd_events (
        id TEXT PRIMARY KEY,
        session_id TEXT,
        retry_count INTEGER,
        timeout_count INTEGER,
        recorded_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_id TEXT,
        row_data TEXT,
        prev_hash TEXT,
        row_hash TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS correlation_edges (
        id TEXT PRIMARY KEY,
        device_fingerprint TEXT,
        ip_address TEXT,
        user_id TEXT,
        last_seen_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS otp_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        requested_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS decisions (
        id TEXT PRIMARY KEY,
        session_id TEXT,
        transaction_id TEXT,
        risk_score REAL,
        verdict TEXT,
        triggered_rules TEXT,
        feature_contributions TEXT,
        explanation_customer TEXT,
        explanation_analyst TEXT,
        model_version TEXT,
        latency_ms REAL,
        decided_at TEXT NOT NULL
    );
"""


def _init_db():
    # SQLite uses AUTOINCREMENT; Postgres uses SERIAL. Everything else in
    # the DDL is valid in both dialects, so one string + one substitution.
    ddl = _DDL.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY") if _IS_PG else _DDL
    with _conn() as conn:
        cur = conn.cursor()
        if _IS_PG:
            # psycopg2 has no executescript; a parameterless execute may
            # carry multiple statements.
            cur.execute(ddl)
        else:
            cur.executescript(ddl)
        conn.commit()

        row = _run(conn, "SELECT COUNT(*) FROM users").fetchone()
        if row[0] == 0:
            demo_pin_hash = hash_pin("1234")
            seed_users = [
                ("Demo User", "08012345678", demo_pin_hash),
                ("Test User", "08098765432", demo_pin_hash),
            ]
            now_iso = _to_iso(_now())
            for full_name, msisdn, pin_hash in seed_users:
                if _IS_PG:
                    new_cur = _run(conn,
                        "INSERT INTO users (full_name, msisdn, pin_hash, is_freshly_registered, account_created_at) "
                        "VALUES (?, ?, ?, 0, ?) RETURNING id",
                        (full_name, msisdn, pin_hash, now_iso))
                    user_id = new_cur.fetchone()[0]
                else:
                    new_cur = _run(conn,
                        "INSERT INTO users (full_name, msisdn, pin_hash, is_freshly_registered, account_created_at) "
                        "VALUES (?, ?, ?, 0, ?)",
                        (full_name, msisdn, pin_hash, now_iso))
                    user_id = new_cur.lastrowid
                _run(conn,
                    "INSERT INTO telco_state (user_id, imei, sim_device_paired, last_sim_swap_at) VALUES (?, NULL, NULL, NULL)",
                    (str(user_id),))
            conn.commit()


_init_db()


def _migrate() -> None:
    """Idempotent column migrations for EXISTING databases (local SQLite and
    production Postgres alike): CREATE TABLE IF NOT EXISTS in _DDL is a no-op
    against tables that already exist, so new columns on `users` must be added
    here. Safe on every boot - once the column exists the check finds it and
    does nothing."""
    with _conn() as conn:
        if _IS_PG:
            cols = {r[0] for r in _run(conn,
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'users'").fetchall()}
        else:
            cols = {r[1] for r in _run(conn, "PRAGMA table_info(users)").fetchall()}
        if "balance" not in cols:
            _run(conn, "ALTER TABLE users ADD COLUMN balance REAL NOT NULL DEFAULT 500000")
        if "blocked_until" not in cols:
            _run(conn, "ALTER TABLE users ADD COLUMN blocked_until TEXT")
        conn.commit()


import datetime as _dt


def get_blocked_until(user_id) -> str | None:
    with _conn() as conn:
        row = _run(conn, "SELECT blocked_until FROM users WHERE id = ?", (str(user_id),)).fetchone()
    return row[0] if row and row[0] else None


def is_blocked(user_id) -> tuple:
    """(blocked, blocked_until_iso). The check runs off the server's clock -
    no endpoint ever writes NULL to blocked_until, so the only way out of a
    block is the timer expiring on its own."""
    until = get_blocked_until(user_id)
    if not until:
        return False, None
    try:
        expired = _dt.datetime.utcnow() >= _dt.datetime.fromisoformat(str(until))
    except (TypeError, ValueError):
        return False, None
    return (not expired), until


def set_blocked(user_id, blocked_until: str) -> None:
    with _conn() as conn:
        _run(conn, "UPDATE users SET blocked_until = ? WHERE id = ?", (blocked_until, str(user_id)))
        conn.commit()


def get_balance(user_id) -> float:
    with _conn() as conn:
        row = _run(conn, "SELECT balance FROM users WHERE id = ?", (str(user_id),)).fetchone()
    return float(row[0]) if row else 0.0


def debit_balance(user_id, amount: float) -> bool:
    """Atomic debit: the balance >= ? guard plus the rowcount check means two
    simultaneous transfers cannot overdraw the account - one of them affects
    0 rows and returns False."""
    with _conn() as conn:
        cur = _run(conn,
            "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
            (float(amount), str(user_id), float(amount)))
        conn.commit()
        return cur.rowcount > 0


_migrate()


def get_user_by_id(user_id: str) -> dict | None:
    with _conn() as conn:
        row = _run(conn, "SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    user = dict(row)
    user["account_created_at"] = _from_iso(user["account_created_at"])
    user["is_freshly_registered"] = bool(user["is_freshly_registered"])
    return user


def get_user_by_msisdn(msisdn: str) -> dict | None:
    with _conn() as conn:
        row = _run(conn, "SELECT * FROM users WHERE msisdn = ?", (msisdn,)).fetchone()
    if not row:
        return None
    user = dict(row)
    user["account_created_at"] = _from_iso(user["account_created_at"])
    user["is_freshly_registered"] = bool(user["is_freshly_registered"])
    return user


def create_user(full_name: str, msisdn: str, account_number: str, nin: str, bvn: str,
                pin: str, avatar_data_url: str | None = None) -> dict:
    now_iso = _to_iso(_now())
    with _conn() as conn:
        if _IS_PG:
            cur = _run(conn,
                "INSERT INTO users (full_name, msisdn, pin_hash, account_number, nin, bvn, avatar_data_url, "
                "is_freshly_registered, account_created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?) RETURNING id",
                (full_name, msisdn, hash_pin(pin), account_number, nin, bvn, avatar_data_url, now_iso))
            user_id = cur.fetchone()[0]
        else:
            cur = _run(conn,
                "INSERT INTO users (full_name, msisdn, pin_hash, account_number, nin, bvn, avatar_data_url, "
                "is_freshly_registered, account_created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (full_name, msisdn, hash_pin(pin), account_number, nin, bvn, avatar_data_url, now_iso))
            user_id = cur.lastrowid
        _run(conn,
            "INSERT INTO telco_state (user_id, imei, sim_device_paired, last_sim_swap_at) VALUES (?, NULL, NULL, NULL)",
            (str(user_id),))
        conn.commit()
    return {
        "id": user_id, "full_name": full_name, "msisdn": msisdn,
        "account_number": account_number, "nin": nin, "bvn": bvn,
        "avatar_data_url": avatar_data_url, "is_freshly_registered": True,
        "account_created_at": _from_iso(now_iso),
    }


def clear_freshly_registered(user_id: str) -> None:
    """Called once, on a user's first successful login after registration.
    is_freshly_registered is set to 1 only at INSERT time in create_user()
    and was never being cleared - meaning every login for that user kept
    reporting True forever, not just the first one. This flips it to 0 so
    the flag (and the frontend's cold-start hint it drives) only fires once."""
    with _conn() as conn:
        _run(conn, "UPDATE users SET is_freshly_registered = 0 WHERE id = ?", (user_id,))
        conn.commit()


def create_session(user_id: str, channel: str, device_fingerprint: str, ip_address: str = None) -> str:
    session_id = _gen_id()
    with _conn() as conn:
        _run(conn,
            "INSERT INTO sessions (id, user_id, channel, device_fingerprint, ip_address, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, user_id, channel, device_fingerprint, ip_address, _to_iso(_now())))
        conn.commit()
    return session_id


def get_session(session_id: str) -> dict | None:
    with _conn() as conn:
        row = _run(conn, "SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return None
    s = dict(row)
    s["started_at"] = _from_iso(s["started_at"])
    return s


def count_sessions_for_user(user_id: str) -> int:
    with _conn() as conn:
        row = _run(conn, "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)).fetchone()
    return row[0]


def log_transaction(session_id: str, user_id: str, beneficiary_account: str, amount: float) -> str:
    transaction_id = _gen_id()
    with _conn() as conn:
        prior_row = _run(conn,
            "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND beneficiary_account = ?",
            (user_id, beneficiary_account)).fetchone()
        prior_count = prior_row[0]
        _run(conn,
            "INSERT INTO transactions (id, session_id, user_id, beneficiary_account, beneficiary_is_novel, amount, requested_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (transaction_id, session_id, user_id, beneficiary_account, 1 if prior_count == 0 else 0,
             amount, _to_iso(_now())))
        conn.commit()
    return transaction_id


def get_transactions_for_user(user_id: str) -> list[dict]:
    with _conn() as conn:
        rows = _run(conn, "SELECT * FROM transactions WHERE user_id = ?", (user_id,)).fetchall()
    out = []
    for r in rows:
        t = dict(r)
        t["requested_at"] = _from_iso(t["requested_at"])
        t["beneficiary_is_novel"] = bool(t["beneficiary_is_novel"])
        out.append(t)
    return sorted(out, key=lambda t: t["requested_at"], reverse=True)


def get_transaction_for_session(session_id: str) -> dict | None:
    with _conn() as conn:
        rows = _run(conn, "SELECT * FROM transactions WHERE session_id = ?", (session_id,)).fetchall()
    if not rows:
        return None
    out = []
    for r in rows:
        t = dict(r)
        t["requested_at"] = _from_iso(t["requested_at"])
        t["beneficiary_is_novel"] = bool(t["beneficiary_is_novel"])
        out.append(t)
    return max(out, key=lambda t: t["requested_at"])


def log_behavioral_events(events: list[dict]) -> None:
    with _conn() as conn:
        for event in events:
            eid = event.get("id") or _gen_id()
            recorded_at = event.get("recorded_at") or _now()
            _run(conn,
                "INSERT INTO behavioral_events (id, session_id, event_type, key_dwell_ms, key_flight_ms, "
                "is_paste, backspace_count, nav_screen, cursor_smoothness_score, call_active, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (eid, event.get("session_id"), event.get("event_type"), event.get("key_dwell_ms"),
                 event.get("key_flight_ms"), 1 if event.get("is_paste") else 0,
                 event.get("backspace_count", 0), event.get("nav_screen"),
                 event.get("cursor_smoothness_score"), 1 if event.get("call_active") else 0,
                 _to_iso(recorded_at)))
        conn.commit()


def get_behavioral_events_for_session(session_id: str) -> list[dict]:
    with _conn() as conn:
        rows = _run(conn, "SELECT * FROM behavioral_events WHERE session_id = ?", (session_id,)).fetchall()
    out = []
    for r in rows:
        e = dict(r)
        e["recorded_at"] = _from_iso(e["recorded_at"])
        e["is_paste"] = bool(e["is_paste"])
        e["call_active"] = bool(e["call_active"])
        out.append(e)
    return sorted(out, key=lambda e: e["recorded_at"])


def get_sim_swap_bucket(user_id: str) -> str:
    state = get_telco_state(user_id)
    if not state or not state.get("last_sim_swap_at"):
        return "OVER_30"
    delta = _now() - state["last_sim_swap_at"]
    if delta <= timedelta(days=4):
        return "0_4"
    if delta <= timedelta(days=14):
        return "5_14"
    if delta <= timedelta(days=30):
        return "15_30"
    return "OVER_30"


def get_telco_state(user_id: str) -> dict | None:
    with _conn() as conn:
        row = _run(conn, "SELECT * FROM telco_state WHERE user_id = ?", (str(user_id),)).fetchone()
    if not row:
        return None
    s = dict(row)
    s["last_sim_swap_at"] = _from_iso(s["last_sim_swap_at"])
    s["sim_device_paired"] = bool(s["sim_device_paired"]) if s["sim_device_paired"] is not None else None
    return s


def set_telco_state(user_id: str, imei: str = None, sim_device_paired: bool = None,
                    last_sim_swap_at: datetime = None, _swap_explicitly_set: bool = True) -> None:
    """Upsert - used by registration (fresh telco row) and by the SIM-swap
    self-report question at login (setting last_sim_swap_at to now on
    'yes'). last_sim_swap_at=None is a VALID, meaningful value (no swap on
    record) - it is always written, not skipped, so this never silently
    keeps a stale value. COALESCE works identically in SQLite and Postgres.
    """
    uid = str(user_id)
    with _conn() as conn:
        existing = _run(conn, "SELECT user_id FROM telco_state WHERE user_id = ?", (uid,)).fetchone()
        swap_iso = _to_iso(last_sim_swap_at)
        paired_val = 1 if sim_device_paired else (0 if sim_device_paired is False else None)
        if existing:
            _run(conn,
                "UPDATE telco_state SET imei = COALESCE(?, imei), "
                "sim_device_paired = COALESCE(?, sim_device_paired), "
                "last_sim_swap_at = ? WHERE user_id = ?",
                (imei, paired_val, swap_iso, uid))
        else:
            _run(conn,
                "INSERT INTO telco_state (user_id, imei, sim_device_paired, last_sim_swap_at) VALUES (?, ?, ?, ?)",
                (uid, imei, paired_val, swap_iso))
        conn.commit()


def log_ussd_event(session_id: str, retry_count: int, timeout_count: int) -> None:
    with _conn() as conn:
        _run(conn,
            "INSERT INTO ussd_events (id, session_id, retry_count, timeout_count, recorded_at) VALUES (?, ?, ?, ?, ?)",
            (_gen_id(), session_id, retry_count, timeout_count, _to_iso(_now())))
        conn.commit()


def get_ussd_events_for_session(session_id: str) -> list[dict]:
    with _conn() as conn:
        rows = _run(conn, "SELECT * FROM ussd_events WHERE session_id = ?", (session_id,)).fetchall()
    out = []
    for r in rows:
        e = dict(r)
        e["recorded_at"] = _from_iso(e["recorded_at"])
        out.append(e)
    return sorted(out, key=lambda e: e["recorded_at"])


def get_last_audit_hash() -> str | None:
    with _conn() as conn:
        row = _run(conn, "SELECT row_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None


def insert_audit_row(decision_id: str, row_data: dict, prev_hash: str, row_hash: str) -> None:
    with _conn() as conn:
        _run(conn,
            "INSERT INTO audit_log (decision_id, row_data, prev_hash, row_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (decision_id, json.dumps(row_data), prev_hash, row_hash, _to_iso(_now())))
        conn.commit()


def get_audit_chain() -> list[dict]:
    with _conn() as conn:
        rows = _run(conn, "SELECT * FROM audit_log ORDER BY id ASC").fetchall()
    out = []
    for r in rows:
        a = dict(r)
        a["row_data"] = json.loads(a["row_data"]) if a["row_data"] else None
        a["created_at"] = _from_iso(a["created_at"])
        out.append(a)
    return out


def find_correlation_edge(device_fingerprint: str, user_id: str) -> dict | None:
    with _conn() as conn:
        row = _run(conn,
            "SELECT * FROM correlation_edges WHERE device_fingerprint = ? AND user_id = ?",
            (device_fingerprint, user_id)).fetchone()
    if not row:
        return None
    e = dict(row)
    e["last_seen_at"] = _from_iso(e["last_seen_at"])
    return e


def touch_correlation_edge(edge_id: str) -> None:
    with _conn() as conn:
        _run(conn, "UPDATE correlation_edges SET last_seen_at = ? WHERE id = ?", (_to_iso(_now()), edge_id))
        conn.commit()


def insert_correlation_edge(device_fingerprint: str, ip_address: str, user_id: str) -> None:
    with _conn() as conn:
        _run(conn,
            "INSERT INTO correlation_edges (id, device_fingerprint, ip_address, user_id, last_seen_at) VALUES (?, ?, ?, ?, ?)",
            (_gen_id(), device_fingerprint, ip_address, user_id, _to_iso(_now())))
        conn.commit()


def count_distinct_accounts_for_device(device_fingerprint: str, cutoff: datetime) -> int:
    with _conn() as conn:
        rows = _run(conn,
            "SELECT user_id, last_seen_at FROM correlation_edges WHERE device_fingerprint = ?",
            (device_fingerprint,)).fetchall()
    return len({r["user_id"] for r in rows if _from_iso(r["last_seen_at"]) >= cutoff})


def peek_otp_request_count(user_id: str) -> int:
    cutoff = _now().timestamp() - 600
    with _conn() as conn:
        row = _run(conn,
            "SELECT COUNT(*) FROM otp_requests WHERE user_id = ? AND requested_at >= ?",
            (user_id, cutoff)).fetchone()
    return row[0]


def record_otp_request(user_id: str) -> int:
    with _conn() as conn:
        _run(conn, "INSERT INTO otp_requests (user_id, requested_at) VALUES (?, ?)", (user_id, _now().timestamp()))
        conn.commit()
    return peek_otp_request_count(user_id)


def log_decision(session_id: str, transaction_id: str | None, risk_score: float,
                 verdict: str, triggered_rules: list | None, feature_contributions: dict,
                 explanation_customer: str, explanation_analyst: str,
                 model_version: str, latency_ms: float) -> str:
    decision_id = _gen_id()
    with _conn() as conn:
        _run(conn,
            "INSERT INTO decisions (id, session_id, transaction_id, risk_score, verdict, triggered_rules, "
            "feature_contributions, explanation_customer, explanation_analyst, model_version, latency_ms, decided_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (decision_id, session_id, transaction_id, risk_score, verdict,
             json.dumps(triggered_rules) if triggered_rules else None,
             json.dumps(feature_contributions), explanation_customer, explanation_analyst,
             model_version, latency_ms, _to_iso(_now())))
        conn.commit()
    return decision_id


def get_latest_decision_for_transaction(transaction_id: str) -> dict | None:
    """Added for profile.py's transaction history, which previously scanned
    the raw in-memory DECISIONS list directly - not possible once decisions
    live in a real database, so this is the real function call it uses."""
    with _conn() as conn:
        row = _run(conn,
            "SELECT * FROM decisions WHERE transaction_id = ? ORDER BY decided_at DESC LIMIT 1",
            (transaction_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["decided_at"] = _from_iso(d["decided_at"])
    d["triggered_rules"] = json.loads(d["triggered_rules"]) if d["triggered_rules"] else None
    d["feature_contributions"] = json.loads(d["feature_contributions"]) if d["feature_contributions"] else None
    return d