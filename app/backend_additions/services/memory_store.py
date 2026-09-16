"""Division 2 — In-memory store, drop-in replacement for Postgres during demo."""

import uuid
from datetime import datetime, timedelta

USERS: dict[str, dict] = {}
SESSIONS: dict[str, dict] = {}
TRANSACTIONS: list[dict] = []
BEHAVIORAL_EVENTS: list[dict] = []
TELCO_STATE: dict[str, dict] = {}

_seed_users = [
    {"id": 1, "full_name": "Demo User", "msisdn": "08012345678"},
    {"id": 2, "full_name": "Test User", "msisdn": "08098765432"},
]
for _u in _seed_users:
    USERS[_u["msisdn"]] = _u
    TELCO_STATE[str(_u["id"])] = {"last_sim_swap_at": None}


def _now() -> datetime:
    return datetime.utcnow()


def _gen_id() -> str:
    return str(uuid.uuid4())


def get_user_by_msisdn(msisdn: str) -> dict | None:
    return USERS.get(msisdn)


def create_session(user_id: str, channel: str, device_fingerprint: str) -> str:
    session_id = _gen_id()
    SESSIONS[session_id] = {
        "id": session_id, "user_id": user_id, "channel": channel,
        "device_fingerprint": device_fingerprint, "started_at": _now(),
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
if __name__ == "__main__":
    print("=" * 60)
    print("memory_store self-test")
    print("=" * 60)

    user = get_user_by_msisdn("08012345678")
    print(f"[1] get_user_by_msisdn: {user}")
    assert user is not None and user["full_name"] == "Demo User"
    user_id = str(user["id"])

    unknown = get_user_by_msisdn("00000000000")
    print(f"[2] get_user_by_msisdn (unknown): {unknown}")
    assert unknown is None

    sid = create_session(user_id, "WEB", "DEMO-DEVICE-001")
    print(f"\n[3] create_session: {sid}")
    assert sid in SESSIONS

    sess = get_session(sid)
    print(f"[4] get_session: {sess}")
    assert sess is not None and sess["user_id"] == user_id

    count = count_sessions_for_user(user_id)
    print(f"[5] count_sessions_for_user: {count}")
    assert count >= 1

    events = [
        {"session_id": sid, "event_type": "KEYDOWN", "key_dwell_ms": 120,
         "key_flight_ms": 45, "is_paste": False, "backspace_count": 0,
         "nav_screen": "login", "cursor_smoothness_score": 0.95,
         "call_active": False},
        {"session_id": sid, "event_type": "NAV", "key_dwell_ms": 0,
         "key_flight_ms": 0, "is_paste": False, "backspace_count": 0,
         "nav_screen": "dashboard", "cursor_smoothness_score": 0.92,
         "call_active": False},
        {"session_id": sid, "event_type": "PASTE", "key_dwell_ms": 300,
         "key_flight_ms": 10, "is_paste": True, "backspace_count": 2,
         "nav_screen": "confirm", "cursor_smoothness_score": 0.88,
         "call_active": False},
    ]
    log_behavioral_events(events)
    print(f"\n[6] log_behavioral_events: logged {len(events)} events")

    retrieved = get_behavioral_events_for_session(sid)
    print(f"[7] get_behavioral_events_for_session: {len(retrieved)} events")
    for e in retrieved:
        print(f"    nav_screen={e['nav_screen']!r:16s} "
              f"recorded_at={e['recorded_at']}")
    assert len(retrieved) == 3
    assert [e["nav_screen"] for e in retrieved] == \
        ["login", "dashboard", "confirm"]

    txn_id = log_transaction(sid, user_id, "2002002002", 45000.00)
    txn = get_transaction_for_session(sid)
    print(f"\n[8] log_transaction (first): {txn_id}")
    print(f"    get_transaction_for_session: {txn}")
    assert txn is not None and txn["beneficiary_is_novel"] is True

    txn_id2 = log_transaction(sid, user_id, "2002002002", 12000.00)
    txn2 = get_transaction_for_session(sid)
    print(f"\n[9] log_transaction (repeat): {txn_id2}")
    print(f"    get_transaction_for_session: {txn2}")
    assert txn2 is not None and txn2["beneficiary_is_novel"] is False
    assert txn2["id"] != txn_id

    print(f"\n[10] get_sim_swap_bucket for {user_id}: "
          f"{get_sim_swap_bucket(user_id)}")
    assert get_sim_swap_bucket(user_id) == "OVER_30"

    print(f"    get_sim_swap_bucket for unknown: "
          f"{get_sim_swap_bucket('99999')}")
    assert get_sim_swap_bucket("99999") == "OVER_30"

    print("\n" + "=" * 60)
    print("All self-test assertions passed")
    print("=" * 60)
