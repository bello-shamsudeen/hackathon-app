"""
Division 5 — regression tests. The single most important thing to protect
here is: a device or SIM change ALONE must NEVER trigger an override. This
is a named hackathon brief requirement, and it's exactly the kind of rule
that gets silently broken by a future "helpful" simplification.

These tests use fake cursor objects (no real DB needed) so they can run
fast and often. Real end-to-end proof still happens against the live DB
separately (see the Claude Code prompt).
"""
from datetime import datetime, timedelta


class FakeCursor:
    """Minimal fake cursor — returns pre-set fetchone() results in sequence."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return self.responses.pop(0) if self.responses else None


def test_device_change_alone_is_ignored():
    from sim_swap_module import check_sim_swap_and_device
    # known_imei different from current, but last_sim_swap_at is old (60 days ago)
    cur = FakeCursor([("OLD-IMEI-123", True, datetime.utcnow() - timedelta(days=60))])
    result = check_sim_swap_and_device("user1", "NEW-IMEI-456", cur)
    assert result["override"] is False, f"FAIL: device change alone triggered an override: {result}"
    print("PASS: device change alone (no recent swap) correctly ignored")


def test_device_change_plus_recent_swap_blocks():
    from sim_swap_module import check_sim_swap_and_device
    cur = FakeCursor([("OLD-IMEI-123", True, datetime.utcnow() - timedelta(days=1))])
    result = check_sim_swap_and_device("user1", "NEW-IMEI-456", cur)
    assert result["override"] is True and result["action"] == "BLOCK", f"FAIL: should have blocked: {result}"
    print("PASS: device change + recent SIM swap correctly blocks")


def test_same_device_never_flags():
    from sim_swap_module import check_sim_swap_and_device
    cur = FakeCursor([("SAME-IMEI", True, datetime.utcnow() - timedelta(days=1))])
    result = check_sim_swap_and_device("user1", "SAME-IMEI", cur)
    assert result["override"] is False, f"FAIL: same device should never flag: {result}"
    print("PASS: unchanged device never flags, even with a recent swap on record")


def test_otp_rate_anomaly():
    from sim_swap_module import check_otp_request_rate
    # Note: this test requires a real (or fake) Redis — run against the real
    # local Redis container for genuine proof; this is a smoke test only.
    for i in range(5):
        result = check_otp_request_rate("test_user_otp_rate")
    assert result["anomaly"] is True, f"FAIL: should have flagged after 4+ requests: {result}"
    print("PASS: OTP request-rate anomaly correctly triggers after threshold")


if __name__ == "__main__":
    all_pass = True
    for test_fn in [test_device_change_alone_is_ignored, test_device_change_plus_recent_swap_blocks,
                     test_same_device_never_flags, test_otp_rate_anomaly]:
        try:
            test_fn()
        except AssertionError as e:
            print(f"FAIL: {test_fn.__name__}: {e}")
            all_pass = False
        except Exception as e:
            print(f"ERROR running {test_fn.__name__} (may need real Redis running): {e}")
            all_pass = False
    print("\n" + ("ALL PASS" if all_pass else "SOME FAILED — DO NOT PROCEED TO DIVISION 6"))
