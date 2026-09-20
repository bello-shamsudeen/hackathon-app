"""
Division 8E - Hash-Chained Audit Log.
Every decision row gets a hash of (its own data + the previous row's hash).
Tampering with any past row breaks the chain from that point forward -
this is detectable, not theoretical. This is the "verify -> green, tamper ->
verify -> red" demo moment.
"""
import hashlib
import json

from app.services import memory_store


def _row_hash(row_data: dict, prev_hash: str) -> str:
    payload = json.dumps(row_data, sort_keys=True, default=str) + (prev_hash or "GENESIS")
    return hashlib.sha256(payload.encode()).hexdigest()


def append_audit_row(decision_id: str, row_data: dict) -> str:
    """Call this right after inserting a decision row."""
    prev_hash = memory_store.get_last_audit_hash()
    new_hash = _row_hash(row_data, prev_hash)
    memory_store.insert_audit_row(decision_id, row_data, prev_hash, new_hash)
    return new_hash


def verify_chain() -> dict:
    """
    Walks the ENTIRE chain from the beginning, recomputing each hash and
    comparing it to what's stored. Returns the first break found, if any.
    """
    rows = memory_store.get_audit_chain()

    expected_prev = None
    for row in rows:
        row_id = row["id"]
        decision_id = row["decision_id"]
        row_data = row["row_data"]
        stored_prev_hash = row["prev_hash"]
        stored_row_hash = row["row_hash"]

        if stored_prev_hash != expected_prev:
            return {"valid": False, "broken_at_row": row_id, "decision_id": str(decision_id),
                    "reason": "prev_hash does not match the actual previous row's hash"}

        recomputed = _row_hash(row_data, stored_prev_hash)
        if recomputed != stored_row_hash:
            return {"valid": False, "broken_at_row": row_id, "decision_id": str(decision_id),
                    "reason": "row_hash does not match recomputed hash - row_data was altered"}

        expected_prev = stored_row_hash

    return {"valid": True, "rows_verified": len(rows)}