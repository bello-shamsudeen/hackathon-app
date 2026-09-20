"""Division 2 — In-memory store, drop-in replacement for Postgres during demo."""

import uuid
from datetime import datetime, timedelta

USERS: dict[str, dict] = {}
SESSIONS: dict[str, dict] = {}
TRANSACTIONS: list[dict] = []
BEHAVIORAL_EVENTS: list[dict] = []
TELCO_STATE: dict[str, dict] = {}
AUDIT_LOG: list[dict] = []
CORRELATION_EDGES: list[dict] = []
USSD_EVENTS: list[dict] = []
OTP_REQUESTS: dict[str, list[float]] = {}

OTP_REQUEST_WINDOW_SECONDS = 600
OTP_REQUEST_ANOMALY_THRESHOLD = 4

_seed_users = [
    {"id": 1, "full_name": "Demo User", "msisdn": "08012345678"},
    {"id": 2, "full_name": "Test User", "msisdn": "08098765432"},
]
for _u in _seed_users:
    USERS[_u["msisdn"]] = _u
    TELCO_STATE[str(_u["id"])] = {"imei": None, "sim_device_paired": None, "last_sim_swap_at": None}


def get_user_by_id(user_id: str) -> dict | None:
    """Return the user dict for the given user ID, or None if unknown."""
    for user in USERS.values():
        if str(user["id"]) == user_id:
            return user
    return None


def create_user(full_name: str, msisdn: str, account_number: str, nin: str, bvn: str, avatar_data_url: str | None = None) -> dict:
    """Create a new user and return the user dict."""
    user_id = len(USERS) + 1
    user = {
        "id": user_id,
        "full_name": full_name,
        "msisdn": msisdn,
        "account_number": account_number,
        "nin": nin,
        "bvn": bvn,
        "avatar_data_url": avatar_data_url,
        "is_freshly_registered": True,
        "account_created_at": _now(),
    }
    USERS[msisdn] = user
    TELCO_STATE[str(user_id)] = {"imei": None, "sim_device_paired": None, "last_sim_swap_at": None}
    return user


def get_transactions_for_user(user_id: str) -> list[dict]:
    """Return all transactions for a user, sorted by requested_at descending."""
    user_txns = [t for t in TRANSACTIONS if t["user_id"] == user_id]
    return sorted(user_txns, key=lambda t: t["requested_at"], reverse=True)


def _now() -> datetime:
    return datetime.utcnow()


def _gen_id() -> str:
    return str(uuid.uuid4())


def get_user_by_msisdn(msisdn: str) -> dict | None:
    return USERS.get(msisdn)


def create_session(user_id: str, channel: str, device_fingerprint: str, ip_address: str = None) -> str:
    session_id = _gen_id()
    SESSIONS[session_id] = {
        "id": session_id, "user_id": user_id, "channel": channel,
        "device_fingerprint": device_fingerprint, "ip_address": ip_address,
        "started_at": _now(),
    }
    return session_id


def get_session(session_id: str) -> dict | None:
    return SESSIONS.get(session_id)


def count_sessions_for_user(user_id: str) -> int:
    return sum(1 for s in SESSIONS.values() if s["user_id"] == user_id)


def log_transaction(session_id: str, user_id: str, beneficiary_account: str,
                    amount: float) -> str:
    prior_count = sum(
        1 for t in TRANSACTIONS
        if t["user_id"] == user_id and t["beneficiary_account"] == beneficiary_account
    )
    transaction_id = _gen_id()
    TRANSACTIONS.append({
        "id": transaction_id, "session_id": session_id, "user_id": user_id,
        "beneficiary_account": beneficiary_account,
        "beneficiary_is_novel": prior_count == 0,
        "amount": amount, "requested_at": _now(),
    })
    return transaction_id


def log_behavioral_events(events: list[dict]) -> None:
    for event in events:
        if "id" not in event:
            event["id"] = _gen_id()
        if "recorded_at" not in event:
            event["recorded_at"] = _now()
        BEHAVIORAL_EVENTS.append(event)


def get_behavioral_events_for_session(session_id: str) -> list[dict]:
    return sorted(
        [e for e in BEHAVIORAL_EVENTS if e["session_id"] == session_id],
        key=lambda e: e["recorded_at"],
    )


def get_transaction_for_session(session_id: str) -> dict | None:
    matches = [t for t in TRANSACTIONS if t["session_id"] == session_id]
    if not matches:
        return None
    return max(matches, key=lambda t: t["requested_at"])


def get_sim_swap_bucket(user_id: str) -> str:
    state = TELCO_STATE.get(user_id)
    if state is None:
        return "OVER_30"
    last_swap = state.get("last_sim_swap_at")
    if last_swap is None:
        return "OVER_30"
    delta = _now() - last_swap
    if delta <= timedelta(days=4):
        return "0_4"
    if delta <= timedelta(days=14):
        return "5_14"
    if delta <= timedelta(days=30):
        return "15_30"
    return "OVER_30"


def get_telco_state(user_id: str) -> dict | None:
    return TELCO_STATE.get(user_id)


def log_ussd_event(session_id: str, retry_count: int, timeout_count: int) -> None:
    USSD_EVENTS.append({
        "session_id": session_id, "retry_count": retry_count,
        "timeout_count": timeout_count, "recorded_at": _now(),
    })


def get_ussd_events_for_session(session_id: str) -> list[dict]:
    return sorted(
        [e for e in USSD_EVENTS if e["session_id"] == session_id],
        key=lambda e: e["recorded_at"],
    )


def get_last_audit_hash() -> str | None:
    if not AUDIT_LOG:
        return None
    return AUDIT_LOG[-1]["row_hash"]


def insert_audit_row(decision_id: str, row_data: dict, prev_hash: str, row_hash: str) -> None:
    AUDIT_LOG.append({
        "id": len(AUDIT_LOG) + 1, "decision_id": decision_id, "row_data": row_data,
        "prev_hash": prev_hash, "row_hash": row_hash, "created_at": _now(),
    })


def get_audit_chain() -> list[dict]:
    return list(AUDIT_LOG)


def find_correlation_edge(device_fingerprint: str, user_id: str) -> dict | None:
    for e in CORRELATION_EDGES:
        if e["device_fingerprint"] == device_fingerprint and e["user_id"] == user_id:
            return e
    return None


def touch_correlation_edge(edge_id: str) -> None:
    for e in CORRELATION_EDGES:
        if e["id"] == edge_id:
            e["last_seen_at"] = _now()
            return


def insert_correlation_edge(device_fingerprint: str, ip_address: str, user_id: str) -> None:
    CORRELATION_EDGES.append({
        "id": _gen_id(), "device_fingerprint": device_fingerprint,
        "ip_address": ip_address, "user_id": user_id, "last_seen_at": _now(),
    })


def count_distinct_accounts_for_device(device_fingerprint: str, cutoff: datetime) -> int:
    return len({
        e["user_id"] for e in CORRELATION_EDGES
        if e["device_fingerprint"] == device_fingerprint and e["last_seen_at"] >= cutoff
    })


def peek_otp_request_count(user_id: str) -> int:
    now = _now().timestamp()
    cutoff = now - OTP_REQUEST_WINDOW_SECONDS
    times = [t for t in OTP_REQUESTS.get(user_id, []) if t >= cutoff]
    OTP_REQUESTS[user_id] = times
    return len(times)


def record_otp_request(user_id: str) -> int:
    now = _now().timestamp()
    OTP_REQUESTS.setdefault(user_id, []).append(now)
    return peek_otp_request_count(user_id)


DECISIONS: list[dict] = []


def log_decision(session_id: str, transaction_id: str | None, risk_score: float,
                 verdict: str, triggered_rules: list | None, feature_contributions: dict,
                 explanation_customer: str, explanation_analyst: str,
                 model_version: str, latency_ms: float) -> str:
    """Append a decision record so it can be inspected later (Division 9)."""
    decision_id = _gen_id()
    DECISIONS.append({
        "id": decision_id,
        "session_id": session_id,
        "transaction_id": transaction_id,
        "risk_score": risk_score,
        "verdict": verdict,
        "triggered_rules": triggered_rules,
        "feature_contributions": feature_contributions,
        "explanation_customer": explanation_customer,
        "explanation_analyst": explanation_analyst,
        "model_version": model_version,
        "latency_ms": latency_ms,
        "decided_at": _now(),
    })
    return decision_id