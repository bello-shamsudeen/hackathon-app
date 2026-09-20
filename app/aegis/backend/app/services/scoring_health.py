"""
Division 4E — scoring-mode health state.

A tiny in-process record of whether the last scoring attempt used the ML
models ("ml") or had to fall back to the rules engine ("degraded"). The
frontend polls this (via GET /score/health) to decide whether to show a
"degraded mode" banner — Division 9 builds the actual banner; for now the
backend just has to report the mode honestly.

Self-healing: every successful ML score calls mark_ml(), so once the models
are reachable again the mode flips back to "ml" on the next transfer with no
restart.
"""
import time
import threading

_lock = threading.Lock()
_state = {
    "mode": "ml",            # "ml" | "degraded"
    "last_error": None,      # str | None
    "since": None,           # epoch seconds the current mode started
    "degraded_count": 0,     # how many times we've fallen back since boot
}


def mark_ml() -> None:
    with _lock:
        if _state["mode"] != "ml":
            _state["mode"] = "ml"
            _state["last_error"] = None
            _state["since"] = time.time()


def mark_degraded(error: str) -> None:
    with _lock:
        if _state["mode"] != "degraded":
            _state["since"] = time.time()
        _state["mode"] = "degraded"
        _state["last_error"] = error
        _state["degraded_count"] += 1


def get_state() -> dict:
    with _lock:
        s = dict(_state)
    s["healthy"] = s["mode"] == "ml"
    return s
