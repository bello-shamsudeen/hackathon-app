"""
Division 8G - Live Metrics Service.
Computes REAL catch rate, false-positive rate, and latency percentiles from
actual decisions in the in-memory store - never hardcoded. This powers the
honesty dashboard (Division 9).

Ground truth for live traffic comes from the device_fingerprint naming
convention already established by Division 7's scripts:
  - Attack scripts use fingerprints starting with "ATTACKER-" or similar
  - Normal traffic uses "legit-dev-<user_id>"
This is an honest, disclosed convention - not real-world ground truth, but a
legitimate way to measure ourselves against our OWN known-labeled simulated
traffic, exactly as Division 3's synthetic data does for offline metrics.
"""
from datetime import datetime, timedelta

from app.services.memory_store import SESSIONS, DECISIONS

# Division 7's simulator labels its traffic by device_fingerprint prefix.
# ALL six attack archetypes use "ATTACKER-*"; the normal-traffic generator
# uses "legit-dev-<user_id>". (The stale "KNOWN-DEVICE" prefix that two attack
# archetypes and the pre-fix normal generator both used is intentionally NOT
# listed - those rows fall through to "unknown" and are excluded rather than
# mislabelled.)
ATTACKER_FINGERPRINT_PREFIXES = ("ATTACKER-",)
NORMAL_FINGERPRINT_PREFIXES = ("legit-dev-",)


def _classify_fingerprint(fp: str) -> str:
    if not fp:
        return "unknown"
    if any(fp.startswith(p) for p in ATTACKER_FINGERPRINT_PREFIXES):
        return "attack"
    if any(fp.startswith(p) for p in NORMAL_FINGERPRINT_PREFIXES):
        return "normal"
    return "unknown"


def compute_live_metrics(since_minutes: int = None) -> dict:
    """
    since_minutes: if given, only decisions from the last N minutes are
    counted (useful to score a single fresh simulator run without historical
    noise from earlier divisions). One decision per session (the latest).
    """
    decisions = DECISIONS
    if since_minutes is not None:
        cutoff = datetime.utcnow() - timedelta(minutes=since_minutes)
        decisions = [d for d in decisions if d["decided_at"] > cutoff]

    # Latest decision per session_id (mirrors SQL's DISTINCT ON ... ORDER BY decided_at DESC)
    latest_by_session = {}
    for d in decisions:
        sid = d["session_id"]
        if sid not in latest_by_session or d["decided_at"] > latest_by_session[sid]["decided_at"]:
            latest_by_session[sid] = d

    rows = []
    for sid, d in latest_by_session.items():
        session = SESSIONS.get(sid)
        if session is None:
            continue
        fp = session.get("device_fingerprint")
        if not fp:
            continue
        rows.append((fp, d["verdict"], d["latency_ms"]))

    tp = fp_ = tn = fn = 0
    latencies = []

    for fingerprint, verdict, latency_ms in rows:
        if latency_ms is not None:
            latencies.append(latency_ms)
        ground_truth = _classify_fingerprint(fingerprint)
        flagged = verdict in ("BLOCK", "CHALLENGE")

        if ground_truth == "attack" and flagged:
            tp += 1
        elif ground_truth == "attack" and not flagged:
            fn += 1
        elif ground_truth == "normal" and flagged:
            fp_ += 1
        elif ground_truth == "normal" and not flagged:
            tn += 1

    total_labeled = tp + fp_ + tn + fn
    latencies.sort()

    def percentile(data, p):
        if not data:
            return None
        idx = min(len(data) - 1, int(len(data) * p / 100))
        return data[idx]

    return {
        "total_decisions_seen": len(rows),
        "total_labeled_for_metrics": total_labeled,
        "confusion_matrix": {"true_positive": tp, "false_positive": fp_, "true_negative": tn, "false_negative": fn},
        "catch_rate_recall": round(tp / (tp + fn), 4) if (tp + fn) > 0 else None,
        "false_positive_rate": round(fp_ / (fp_ + tn), 4) if (fp_ + tn) > 0 else None,
        "precision": round(tp / (tp + fp_), 4) if (tp + fp_) > 0 else None,
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "latency_max_ms": max(latencies) if latencies else None,
        "note": "Ground truth is derived from our own simulator's device_fingerprint "
                "naming convention (disclosed), not independently verified real-world labels.",
    }