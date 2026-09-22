"""
Division 5 - Hard Controls Orchestrator.
This is called at the TOP of the scoring flow, BEFORE the ML score from
Division 4. If any hard control fires, its verdict WINS - the ML score
still gets computed (for logging/comparison) but does not override a hard
control's decision. This is the deliberate design: hard controls are
deterministic and take precedence over probabilistic scoring.
"""
from app.services.sim_swap_module import (
    check_sim_swap_and_device, peek_otp_request_rate,
    get_otp_fallback_channel, check_call_otp_interlock,
)
from app.services.identity_correlation import record_correlation_edge, check_device_fraud_ring


AMOUNT_HARD_LIMIT = 200_000   # NGN -> BLOCK (matches rules_fallback.py's constant)
AMOUNT_SOFT_LIMIT = 75_000    # NGN -> STEP-UP (matches rules_fallback.py's constant)


def run_hard_controls(session_id: str, user_id: str, device_fingerprint: str,
                      ip_address: str, current_imei: str, call_active: bool,
                      otp_being_entered: bool, token_status: str = None,
                      honeytoken_tripped: bool = False, amount: float = None) -> dict:
    if amount is not None and amount >= AMOUNT_HARD_LIMIT:
        return {
            'override': True, 'source': 'AMOUNT_CEILING',
            'tier': 'high', 'action': 'block',
            'message': 'This transaction was blocked because the amount exceeds the maximum allowed for a single transfer.',
            'amount': amount,
        }
    if amount is not None and amount >= AMOUNT_SOFT_LIMIT:
        return {
            'override': True, 'source': 'AMOUNT_CEILING',
            'tier': 'medium', 'action': 'step_up',
            'message': 'This transaction requires extra verification because the amount is unusually large.',
            'amount': amount,
        }
    if honeytoken_tripped:
        return {
            "override": True, "source": "HONEYTOKEN",
            "tier": "high", "action": "block",
            "message": ("This transaction was blocked because an automated "
                        "form-filling pattern was detected."),
        }

    if token_status and token_status != "OK":
        return {
            "override": True, "source": "TOKEN_INTEGRITY",
            "tier": "high", "action": "block",
            "message": ("This transaction was blocked because its confirmation "
                        "token had already been used or had expired."),
        }

    swap_verdict = check_sim_swap_and_device(user_id, current_imei)
    swap_reason = swap_verdict.get("reason")
    if swap_verdict.get("override"):
        return {
            "override": True, "source": "SIM_SWAP_MODULE",
            "tier": swap_verdict["tier"], "action": str(swap_verdict["action"]).lower(),
            "message": f"This transaction was blocked because {swap_verdict['message']}.",
            "days_since_swap": swap_verdict.get("days_since_swap"),
        }

    record_correlation_edge(device_fingerprint, ip_address, user_id)
    ring_check = check_device_fraud_ring(device_fingerprint)
    if ring_check["alert"]:
        return {
            "override": True, "source": "IDENTITY_CORRELATION",
            "tier": "high", "action": "block",
            "message": f"This transaction was blocked because {ring_check['message']}.",
            "distinct_accounts": ring_check["distinct_accounts"],
        }

    otp_check = peek_otp_request_rate(user_id)
    if otp_check["anomaly"]:
        return {
            "override": True, "source": "OTP_RATE_ANOMALY",
            "tier": "medium", "action": "step_up",
            "message": f"This transaction requires extra verification because {otp_check['message']}.",
            "otp_request_count": otp_check["count"],
        }

    interlock = check_call_otp_interlock(call_active, otp_being_entered)
    if interlock["elevated"]:
        return {
            "override": True, "source": "CALL_OTP_INTERLOCK",
            "tier": "medium", "action": "step_up",
            "message": f"This transaction requires extra verification because {interlock['message']}.",
        }

    return {
        "override": False,
        "sim_swap_check": swap_reason,
        "days_since_swap": swap_verdict.get("days_since_swap"),
    }