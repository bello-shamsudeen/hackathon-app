"""
Division 8G — Live Metrics Service.
Computes REAL catch rate, false-positive rate, and latency percentiles from
actual decisions in the database — never hardcoded. This powers the honesty
dashboard (Division 9).

Ground truth for live traffic comes from the device_fingerprint naming
convention already established by Division 7's scripts:
  - Attack scripts use fingerprints starting with "ATTACKER-" or similar
  - Normal traffic uses "KNOWN-DEVICE" / "legit-dev-<user_id>"
This is an honest, disclosed convention — not real-world ground truth, but a
legitimate way to measure ourselves against our OWN known-labeled simulated
traffic, exactly as Division 3's synthetic data does for offline metrics.
"""
from app.db import get_connection

ATTACKER_FINGERPRINT_PREFIXES = ("ATTACKER-",)
NORMAL_FINGERPRINT_PREFIXES = ("KNOWN-DEVICE", "legit-dev-")


def _classify_fingerprint(fp: str) -> str:
    if not fp:
        return "unknown"
    if any(fp.startswith(p) for p in ATTACKER_FINGERPRINT_PREFIXES):
        return "attack"
    if any(fp.startswith(p) for p in NORMAL_FINGERPRINT_PREFIXES):
        return "normal"
    return "unknown"


def compute_live_metrics() -> dict:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """SELECT s.device_fingerprint, d.verdict, d.latency_ms
           FROM decisions d
           JOIN sessions s ON s.id = d.session_id
           WHERE s.device_fingerprint IS NOT NULL"""
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    tp = fp = tn = fn = 0
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
            fp += 1
        elif ground_truth == "normal" and not flagged:
            tn += 1

    total_labeled = tp + fp + tn + fn
    latencies.sort()

    def percentile(data, p):
        if not data:
            return None
        idx = min(len(data) - 1, int(len(data) * p / 100))
        return data[idx]

    return {
        "total_decisions_seen": len(rows),
        "total_labeled_for_metrics": total_labeled,
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn},
        "catch_rate_recall": round(tp / (tp + fn), 4) if (tp + fn) > 0 else None,
        "false_positive_rate": round(fp / (fp + tn), 4) if (fp + tn) > 0 else None,
        "precision": round(tp / (tp + fp), 4) if (tp + fp) > 0 else None,
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "latency_max_ms": max(latencies) if latencies else None,
        "note": "Ground truth is derived from our own simulator's device_fingerprint "
                "naming convention (disclosed), not independently verified real-world labels.",
    }
