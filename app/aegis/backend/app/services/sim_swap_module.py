"""
Division 5B - SIM-Swap / OTP Defense Module.
THIS IS A HARD-RULE LAYER, evaluated ALONGSIDE the ML score, never inside it.
It exists because a fraudster with a correct PIN AND a correct OTP (via SIM
swap) passes every behavioral check - this module is what stops them anyway.

CRITICAL DESIGN RULE (do not simplify away): a device or SIM change ALONE is
NEVER treated as risk. Only device/SIM change IN COMBINATION with a recent
swap, or a first-time pairing, escalates. This directly answers the brief's
explicit warning: "Families share phones and people change SIMs. Neither is
fraud." Simplifying this to "any device change = suspicious" would be wrong
and would violate that requirement.
"""
from datetime import datetime

from app.services import memory_store

OTP_REQUEST_ANOMALY_THRESHOLD = memory_store.OTP_REQUEST_ANOMALY_THRESHOLD


def check_sim_swap_and_device(user_id: str, current_imei: str) -> dict:
    """
    Returns a hard-control verdict. If 'override' is set, the caller (the
    scoring endpoint) should use THIS verdict and skip/override the ML score
    entirely for the swap/device dimension - this is deterministic, not a
    weighted feature.
    """
    row = memory_store.get_telco_state(user_id)

    if not row or (row.get("last_sim_swap_at") is None and row.get("imei") is None):
        # No telco history at all - treat as first-ever pairing, not risk.
        return {"override": False, "reason": None, "days_since_swap": None}

    known_imei = row.get("imei")
    last_swap_at = row.get("last_sim_swap_at")
    # Only claim a device change when we actually have a device identity to
    # compare. USSD sessions (feature phones) carry no fingerprint/IMEI, so a
    # missing current_imei must NOT read as "device changed" - otherwise every
    # post-swap USSD transfer would trip the block on the swap alone, which is
    # exactly the "people change SIMs, that isn't fraud" case the brief forbids.
    device_changed = bool(current_imei) and (known_imei != current_imei)

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
    """
    Rolling OTP request counter, backed by memory_store. This INCREMENTS:
    call it once per *actual* OTP request (the /bank/request-otp endpoint),
    not on every risk check. Returns whether the rolling count has crossed
    the anomaly threshold.
    """
    count = memory_store.record_otp_request(user_id)
    if count >= OTP_REQUEST_ANOMALY_THRESHOLD:
        return {"anomaly": True, "count": count,
                "message": "an unusual number of verification codes were requested in a short time"}
    return {"anomaly": False, "count": count}


def peek_otp_request_rate(user_id: str) -> dict:
    """
    Read-only view of the same counter - does NOT increment. This is what the
    hard-controls orchestrator uses when scoring a transfer, so scoring a
    transaction never inflates the OTP-request count.
    """
    count = memory_store.peek_otp_request_count(user_id)
    if count >= OTP_REQUEST_ANOMALY_THRESHOLD:
        return {"anomaly": True, "count": count,
                "message": "an unusual number of verification codes were requested in a short time"}
    return {"anomaly": False, "count": count}


def get_otp_fallback_channel(user_id: str, sim_swap_verdict: dict) -> str:
    """
    THIS IS THE KEY DESIGN DECISION: if a SIM swap was recently flagged, do
    NOT send another OTP to that same (now-compromised) number - the
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