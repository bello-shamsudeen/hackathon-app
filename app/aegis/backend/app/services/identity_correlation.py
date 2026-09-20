"""
Division 5C - Identity Correlation Engine.
Tracks device fingerprint / IP address against accounts over time. One
account seeing a new device = ignored (that's normal life). One device or
IP touching MULTIPLE accounts in a short window = a fraud-ring signal,
independent of any single session's own risk score.
"""
from datetime import datetime, timedelta

from app.services import memory_store

CORRELATION_WINDOW_HOURS = 1
CORRELATION_ACCOUNT_THRESHOLD = 3  # same device/IP touching 3+ DIFFERENT accounts = alert


def record_correlation_edge(device_fingerprint: str, ip_address: str, user_id: str):
    """Call this once per session start."""
    existing = memory_store.find_correlation_edge(device_fingerprint, user_id)
    if existing:
        memory_store.touch_correlation_edge(existing["id"])
    else:
        memory_store.insert_correlation_edge(device_fingerprint, ip_address, user_id)


def check_device_fraud_ring(device_fingerprint: str) -> dict:
    """
    The actual fraud-ring check: has this device touched multiple DIFFERENT
    accounts recently? A single account using a device is normal life. Many
    accounts using the same device in a short window is the pattern real
    fraud rings leave behind.
    """
    if not device_fingerprint:
        return {"alert": False, "distinct_accounts": 0}

    cutoff = datetime.utcnow() - timedelta(hours=CORRELATION_WINDOW_HOURS)
    distinct_accounts = memory_store.count_distinct_accounts_for_device(device_fingerprint, cutoff)

    if distinct_accounts >= CORRELATION_ACCOUNT_THRESHOLD:
        return {
            "alert": True,
            "distinct_accounts": distinct_accounts,
            "message": f"this device has been used on {distinct_accounts} different accounts recently"
        }
    return {"alert": False, "distinct_accounts": distinct_accounts}