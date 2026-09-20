"""
Division 4E — rules-based fallback engine.

Engages automatically when the ML scoring service raises or is unreachable
(bad/missing model files, a corrupt pkl, an unhandled feature-engineering
error). It must never itself crash the transfer flow, so it depends only on
things that are cheap and almost always available: the transaction amount
(already in Postgres) and the Redis velocity counters from Division 4B.

It deliberately mirrors the decision-engine output contract
(tier / action / message + risk_score + top_features) so callers and the
`decisions` table don't need a second code path — only model_version changes,
to "rules-fallback-v1", so an investigator can see which transfers were
scored while degraded.

Rules (intentionally blunt — this is a safety net, not the detector):
  * amount hard limit           -> block
  * amount soft limit           -> step_up
  * transfer velocity over cap  -> block  (rapid repeated transfers)
  * transfer velocity elevated  -> step_up
  * login velocity over cap     -> step_up (credential stuffing / handoff)
Anything below all thresholds -> allow.
"""
import logging

from app.services import velocity

log = logging.getLogger("aegis.rules_fallback")

# NGN. Chosen to sit well above the Division 3 synthetic "normal" amounts
# (app avg ~15k, ussd avg ~4-8k) so ordinary transfers pass untouched.
AMOUNT_HARD_LIMIT = 200_000
AMOUNT_SOFT_LIMIT = 75_000

TRANSFER_VELOCITY_BLOCK = 6     # transfers/hour
TRANSFER_VELOCITY_STEPUP = 3
LOGIN_VELOCITY_STEPUP = 5       # login attempts/minute


def rules_verdict(user_id: str, channel: str, amount: float) -> dict:
    counters = velocity.snapshot(user_id)
    xfer = counters["transfers_per_hour"]
    logins = counters["login_attempts_per_min"]
    amount = float(amount or 0)

    reasons = []
    tier, action = "low", "allow"

    def escalate(to_tier, to_action, why):
        nonlocal tier, action
        order = {"low": 0, "medium": 1, "high": 2}
        if order[to_tier] > order[tier]:
            tier, action = to_tier, to_action
        reasons.append(why)

    if amount >= AMOUNT_HARD_LIMIT:
        escalate("high", "block", f"amount NGN {amount:,.0f} is over the hard limit")
    elif amount >= AMOUNT_SOFT_LIMIT:
        escalate("medium", "step_up", f"amount NGN {amount:,.0f} is over the review limit")

    if xfer >= TRANSFER_VELOCITY_BLOCK:
        escalate("high", "block", f"{xfer} transfers in the last hour")
    elif xfer >= TRANSFER_VELOCITY_STEPUP:
        escalate("medium", "step_up", f"{xfer} transfers in the last hour")

    if logins >= LOGIN_VELOCITY_STEPUP:
        escalate("medium", "step_up", f"{logins} login attempts in the last minute")

    if tier == "low":
        message = ("Automated checks are running in reduced mode; this transfer "
                   "cleared the fallback velocity and amount limits.")
    else:
        message = ("Scored in reduced mode (ML service unavailable): "
                   + "; ".join(reasons) + ".")

    # top_features shaped like the ML path so the decisions row stays uniform
    top_features = [
        ["transfer_velocity", xfer],
        ["amount", round(amount, 2)],
    ]

    log.warning(
        "rules fallback verdict: user=%s channel=%s amount=%.2f xfer/h=%d login/min=%d -> %s/%s",
        user_id, channel, amount, xfer, logins, tier, action,
    )

    return {
        "tier": tier,
        "action": action,
        "message": message,
        "user_id": str(user_id),
        "channel": channel,
        "risk_score": {"low": 10.0, "medium": 55.0, "high": 90.0}[tier],
        "top_features": top_features,
        "velocity": counters,
        "_model_version": "rules-fallback-v1",
    }
