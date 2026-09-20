"""
Division 4B — Redis velocity layer.

Rolling per-user counters that the detection core (and Division 5's hard
controls) read as a cheap, model-independent signal:

  * login attempts   — per rolling 60s window
  * transfers        — per rolling 3600s window
  * OTP requests     — per rolling window (default 3600s), reused by Division 5

Login and transfer counters are fixed-bucket INCRs (key carries the bucket
number, TTL a little over one window so a stale bucket can't linger). The OTP
counter is a true sliding window (sorted set keyed by timestamp) because
Division 5 needs "how many OTP requests in the last N seconds" precisely, not
bucketed.

Everything here fails soft: if Redis is unreachable (or was never configured
for this deployment) the increment helpers still return a best-effort number
and `snapshot()` returns zeros, so a Redis outage or absence degrades the
velocity signal rather than breaking a transfer.
"""
import os
import time
import logging

import redis

log = logging.getLogger("aegis.velocity")

LOGIN_WINDOW_SEC = 60
TRANSFER_WINDOW_SEC = 3600
OTP_WINDOW_SEC = 3600

_client = None


def get_client():
    """Return a Redis client, or None if Redis isn't configured for this
    deployment. Deliberately does NOT attempt a connection in the None case —
    this architecture dropped Redis, so falling through to a real connect
    attempt against an unconfigured/default host just burns ~4s per call
    until it times out."""
    global _client
    if _client is not None:
        return _client
    raw = os.environ.get("REDIS_URL")
    if not raw:
        return None
    if "localhost" in raw or "127.0.0.1" in raw or "//redis" in raw or "@redis" in raw:
        return None
    _client = redis.Redis.from_url(raw, decode_responses=True)
    return _client


# ---------------------------------------------------------------- fixed bucket

def _bucket_incr(kind: str, user_id: str, window_sec: int) -> int:
    """INCR the current time-bucket for (kind, user) and return the new count."""
    r = get_client()
    if r is None:
        return 0
    try:
        bucket = int(time.time() // window_sec)
        key = f"vel:{kind}:{user_id}:{bucket}"
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_sec * 2)
        count, _ = pipe.execute()
        return int(count)
    except redis.RedisError as exc:  # noqa: BLE001 — velocity must not break the flow
        log.warning("velocity %s incr failed for %s: %s", kind, user_id, exc)
        return 0


def _bucket_get(kind: str, user_id: str, window_sec: int) -> int:
    r = get_client()
    if r is None:
        return 0
    try:
        bucket = int(time.time() // window_sec)
        val = r.get(f"vel:{kind}:{user_id}:{bucket}")
        return int(val) if val is not None else 0
    except redis.RedisError as exc:  # noqa: BLE001
        log.warning("velocity %s get failed for %s: %s", kind, user_id, exc)
        return 0


# --------------------------------------------------------------- sliding window

def _sliding_incr(kind: str, user_id: str, window_sec: int) -> int:
    """Record one event now in a per-user sorted set, prune anything older than
    the window, return how many remain (i.e. the count in the last window_sec)."""
    r = get_client()
    if r is None:
        return 0
    try:
        now = time.time()
        key = f"vel:{kind}:{user_id}"
        pipe = r.pipeline()
        pipe.zadd(key, {f"{now:.6f}": now})
        pipe.zremrangebyscore(key, 0, now - window_sec)
        pipe.zcard(key)
        pipe.expire(key, window_sec * 2)
        _, _, count, _ = pipe.execute()
        return int(count)
    except redis.RedisError as exc:  # noqa: BLE001
        log.warning("velocity %s sliding incr failed for %s: %s", kind, user_id, exc)
        return 0


def _sliding_get(kind: str, user_id: str, window_sec: int) -> int:
    r = get_client()
    if r is None:
        return 0
    try:
        now = time.time()
        key = f"vel:{kind}:{user_id}"
        r.zremrangebyscore(key, 0, now - window_sec)
        return int(r.zcard(key))
    except redis.RedisError as exc:  # noqa: BLE001
        log.warning("velocity %s sliding get failed for %s: %s", kind, user_id, exc)
        return 0


# --------------------------------------------------------------------- public

def record_login_attempt(user_id: str) -> int:
    return _bucket_incr("login", str(user_id), LOGIN_WINDOW_SEC)


def record_transfer(user_id: str) -> int:
    return _bucket_incr("transfer", str(user_id), TRANSFER_WINDOW_SEC)


def record_otp_request(user_id: str) -> int:
    """Division 5 will call this from the OTP-issue path; exposed now so the
    counter and its window are defined in one place."""
    return _sliding_incr("otp", str(user_id), OTP_WINDOW_SEC)


def snapshot(user_id: str) -> dict:
    """Read-only current counters for a user — used by feature engineering and
    the rules fallback. Never increments."""
    uid = str(user_id)
    return {
        "login_attempts_per_min": _bucket_get("login", uid, LOGIN_WINDOW_SEC),
        "transfers_per_hour": _bucket_get("transfer", uid, TRANSFER_WINDOW_SEC),
        "otp_requests_in_window": _sliding_get("otp", uid, OTP_WINDOW_SEC),
    }