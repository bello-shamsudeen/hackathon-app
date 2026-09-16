"""
Division 5 — Hard Controls Orchestrator.
This is called at the TOP of the scoring flow, BEFORE the ML score from
Division 4. If any hard control fires, its verdict WINS — the ML score
still gets computed (for logging/comparison) but does not override a hard
control's decision. This is the deliberate design: hard controls are
deterministic and take precedence over probabilistic scoring.
"""
from app.services.sim_swap_module import (
    check_sim_swap_and_device, check_otp_request_rate,
    get_otp_fallback_channel, check_call_otp_interlock
)
from app.services.identity_correlation import record_correlation_edge, check_device_fraud_ring


def run_hard_controls(session_id: str, user_id: str, device_fingerprint: str,
                       ip_address: str, current_imei: str, call_active: bool,
                       otp_being_entered: bool, cur) -> dict:
    """
    Returns {"override": bool, ...verdict fields...} if a hard control fires,
    or {"override": False} if the ML score should decide normally.
    Checks run in order; the FIRST one to fire wins (they're deliberately
    ordered from most to least severe).
    """
    # 1. SIM-swap + device change combination (the strongest, most specific check)
    swap_verdict = check_sim_swap_and_device(user_id, current_imei, cur)
    if swap_verdict.get("override"):
        return {
            "override": True, "source": "SIM_SWAP_MODULE",
            "tier": swap_verdict["tier"], "action": swap_verdict["action"],
            "message": f"This transaction was blocked because {swap_verdict['message']}.",
        }

    # 2. Identity correlation — fraud ring detection
    record_correlation_edge(device_fingerprint, ip_address, user_id, cur)
    ring_check = check_device_fraud_ring(device_fingerprint, cur)
    if ring_check["alert"]:
        return {
            "override": True, "source": "IDENTITY_CORRELATION",
            "tier": "high", "action": "block",
            "message": f"This transaction was blocked because {ring_check['message']}.",
        }

    # 3. OTP request-rate anomaly
    otp_check = check_otp_request_rate(user_id)
    if otp_check["anomaly"]:
        return {
            "override": True, "source": "OTP_RATE_ANOMALY",
            "tier": "medium", "action": "step_up",
            "message": f"This transaction requires extra verification because {otp_check['message']}.",
        }

    # 4. Call/OTP interlock — coaching detection
    interlock = check_call_otp_interlock(call_active, otp_being_entered)
    if interlock["elevated"]:
        return {
            "override": True, "source": "CALL_OTP_INTERLOCK",
            "tier": "medium", "action": "step_up",
            "message": f"This transaction requires extra verification because {interlock['message']}.",
        }

    return {"override": False, "days_since_swap": swap_verdict.get("days_since_swap")}
