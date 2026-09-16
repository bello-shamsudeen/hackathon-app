"""
Division 5C — Identity Correlation Engine.
Tracks device fingerprint / IP address against accounts over time. One
account seeing a new device = ignored (that's normal life). One device or
IP touching MULTIPLE accounts in a short window = a fraud-ring signal,
independent of any single session's own risk score.
"""
from datetime import datetime, timedelta

CORRELATION_WINDOW_HOURS = 1
CORRELATION_ACCOUNT_THRESHOLD = 3  # same device/IP touching 3+ DIFFERENT accounts = alert


def record_correlation_edge(device_fingerprint: str, ip_address: str, user_id: str, cur):
    """Call this once per session start."""
    cur.execute(
        """SELECT id FROM correlation_edges
           WHERE device_fingerprint = %s AND user_id = %s""",
        (device_fingerprint, user_id)
    )
    existing = cur.fetchone()
    if existing:
        cur.execute(
            "UPDATE correlation_edges SET last_seen_at = now() WHERE id = %s",
            (existing[0],)
        )
    else:
        cur.execute(
            """INSERT INTO correlation_edges (id, device_fingerprint, ip_address, user_id)
               VALUES (gen_random_uuid(), %s, %s, %s)""",
            (device_fingerprint, ip_address, user_id)
        )


def check_device_fraud_ring(device_fingerprint: str, cur) -> dict:
    """
    The actual fraud-ring check: has this device touched multiple DIFFERENT
    accounts recently? A single account using a device is normal life. Many
    accounts using the same device in a short window is the pattern real
    fraud rings leave behind.
    """
    if not device_fingerprint:
        return {"alert": False, "distinct_accounts": 0}

    cutoff = datetime.utcnow() - timedelta(hours=CORRELATION_WINDOW_HOURS)
    cur.execute(
        """SELECT COUNT(DISTINCT user_id) FROM correlation_edges
           WHERE device_fingerprint = %s AND last_seen_at >= %s""",
        (device_fingerprint, cutoff)
    )
    distinct_accounts = cur.fetchone()[0]

    if distinct_accounts >= CORRELATION_ACCOUNT_THRESHOLD:
        return {
            "alert": True,
            "distinct_accounts": distinct_accounts,
            "message": f"this device has been used on {distinct_accounts} different accounts recently"
        }
    return {"alert": False, "distinct_accounts": distinct_accounts}
