"""
Division 5A — Token Integrity Service.
Every session gets a one-time-use token ID (jti). Once consumed, it's burned
in Redis forever. Reusing an old token is caught DETERMINISTICALLY — this is
a hard control, not a probability, and it's what actually stops OTP/session
replay attacks regardless of what the ML model thinks.
"""
import uuid
import redis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

TOKEN_TTL_SECONDS = 300  # a token is valid for 5 minutes before it expires unused


def issue_token(session_id: str) -> str:
    """Called at the start of a sensitive action (e.g. OTP verification, transfer confirm)."""
    jti = str(uuid.uuid4())
    r.setex(f"token:issued:{jti}", TOKEN_TTL_SECONDS, session_id)
    return jti


def consume_token(jti: str) -> dict:
    """
    Called when the token is actually used. Returns whether this was a fresh,
    valid use or a replay. This function is intentionally atomic (GETDEL) so
    two near-simultaneous requests can't both succeed.
    """
    session_id = r.getdel(f"token:issued:{jti}")
    if session_id is None:
        return {"valid": False, "reason": "TOKEN_REPLAYED_OR_EXPIRED", "session_id": None}
    return {"valid": True, "reason": None, "session_id": session_id}
