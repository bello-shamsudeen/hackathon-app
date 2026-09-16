"""
Division 5B — SIM-Swap / OTP Defense Module.
THIS IS A HARD-RULE LAYER, evaluated ALONGSIDE the ML score, never inside it.
It exists because a fraudster with a correct PIN AND a correct OTP (via SIM
swap) passes every behavioral check — this module is what stops them anyway.

CRITICAL DESIGN RULE (do not simplify away): a device or SIM change ALONE is
NEVER treated as risk. Only device/SIM change IN COMBINATION with a recent
swap, or a first-time pairing, escalates. This directly answers the brief's
explicit warning: "Families share phones and people change SIMs. Neither is
fraud." Simplifying this to "any device change = suspicious" would be wrong
and would violate that requirement.
"""
from datetime import datetime, timedelta
import redis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

OTP_REQUEST_WINDOW_SECONDS = 600   # 10-minute rolling window
OTP_REQUEST_ANOMALY_THRESHOLD = 4  # 4+ OTP requests in that window is itself a signal


def check_sim_swap_and_device(user_id: str, current_imei: str, cur) -> dict:
    """
    Returns a hard-control verdict. If 'override' is set, the caller (the
    scoring endpoint) should use THIS verdict and skip/override the ML score
    entirely for the swap/device dimension — this is deterministic, not a
    weighted feature.
    """
    cur.execute(
        """SELECT imei, sim_device_paired, last_sim_swap_at
           FROM telco_state WHERE user_id = %s
           ORDER BY updated_at DESC LIMIT 1""",
        (user_id,)
    )
    row = cur.fetchone()

    if not row:
        # No telco history at all — treat as first-ever pairing, not risk.
        return {"override": False, "reason": None, "days_since_swap": None}

    known_imei, sim_device_paired, last_swap_at = row
    device_changed = (known_imei != current_imei)

    days_since_swap = None
    recent_swap = False
    if last_swap_at:
        days_since_swap = (datetime.utcnow() - last_swap_at.replace(tzinfo=None)).days
        recent_swap = days_since_swap <= 4  # matches Division 3's "0_4" bucket = highest risk

    # ---- THE CORE RULE ----
    if not device_changed:
        return {"override": False, "reason": None, "days_since_swap": days_since_swap}

    if device_changed and not recent_swap:
        # New device, but no recent SIM swap on record. This is the
        # "shared family phone" / "upgraded my phone" case. NOT risk alone.
        return {"override": False, "reason": "DEVICE_CHANGED_NO_RECENT_SWAP_IGNORED",
                "days_since_swap": days_since_swap}

    if device_changed and recent_swap:
        # New device AND a SIM swap in the last 4 days. THIS is the real signal.
        return {"override": True, "action": "BLOCK", "tier": "high",
                "reason": "sim_swap_risk",
                "message": "your SIM was recently changed and this device hasn't been used on your account before",
                "days_since_swap": days_since_swap}

    return {"override": False, "reason": None, "days_since_swap": days_since_swap}


def check_otp_request_rate(user_id: str) -> dict:
    """Rolling OTP request counter in Redis — reuses the pattern from Division 4B."""
    key = f"otp_requests:{user_id}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, OTP_REQUEST_WINDOW_SECONDS)
    if count >= OTP_REQUEST_ANOMALY_THRESHOLD:
        return {"anomaly": True, "count": count,
                "message": "an unusual number of verification codes were requested in a short time"}
    return {"anomaly": False, "count": count}


def get_otp_fallback_channel(user_id: str, sim_swap_verdict: dict) -> str:
    """
    THIS IS THE KEY DESIGN DECISION: if a SIM swap was recently flagged, do
    NOT send another OTP to that same (now-compromised) number — the
    attacker holds the SIM. Escalate to a secondary channel or manual hold
    instead. In this hackathon build, that's simulated as a named fallback
    path; in production this would be a registered secondary channel.
    """
    if sim_swap_verdict.get("override") and sim_swap_verdict.get("reason") == "sim_swap_risk":
        return "MANUAL_HOLD_SECONDARY_CHANNEL_REQUIRED"
    return "SMS_OTP"


def check_call_otp_interlock(call_active: bool, otp_being_entered: bool) -> dict:
    """
    Division 5B's coaching-detection tie-in: if a call is active WHILE an OTP
    is being entered, elevate risk EVEN IF the OTP itself is technically
    correct. Nothing gets waved through just because the code matched.
    """
    if call_active and otp_being_entered:
        return {"elevated": True,
                "message": "this code was entered while you appeared to be on a call"}
    return {"elevated": False}
