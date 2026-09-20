"""
AEGIS Backend - Division 1 skeleton.
This is intentionally minimal: it proves the stack boots and connects to
Postgres + Redis. Divisions 2-8 will add routers into app/routers/.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
import os

# Division 8A - lightweight edge rate limiting. `slowapi` is the declared
# dependency; we use its bundled `limits` engine directly in a path-scoped
# middleware (no Nginx container needed for the hackathon).
from slowapi import Limiter
from slowapi.util import get_remote_address
from limits import parse as _parse_rate
from limits.storage import MemoryStorage as _RLMemoryStorage
from limits.strategies import MovingWindowRateLimiter as _RLMovingWindow

from app.routers import bank, behavior, ussd, score, profile

app = FastAPI(title="Aegis", version="0.1.0")

# slowapi limiter registered on app.state (used by any future @limiter.limit
# route decorators); the middleware below is the active enforcement path.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

_RL_STORAGE = _RLMemoryStorage()
_RL = _RLMovingWindow(_RL_STORAGE)
_RL_RATE = _parse_rate("60/minute")
_RL_PREFIXES = ("/bank", "/ussd")
# Internal service-to-service calls (the Division 7 simulator runs inside this
# container and hits localhost) are exempt - the limiter guards the external edge.
_RL_EXEMPT_IPS = {"127.0.0.1", "::1", "testclient"}


@app.middleware("http")
async def edge_rate_limiter(request: Request, call_next):
    """Division 8A - 60 requests/minute per client IP on /bank and /ussd."""
    if request.url.path.startswith(_RL_PREFIXES):
        client_ip = request.client.host if request.client else "unknown"
        if client_ip not in _RL_EXEMPT_IPS and not _RL.hit(_RL_RATE, "edge", client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded: 60 requests/minute per IP "
                                   "on /bank and /ussd (Division 8A edge limiter)",
                         "client_ip": client_ip},
            )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in Division 8A (edge/gateway hardening)
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bank.router)
app.include_router(behavior.router)
app.include_router(ussd.router)
app.include_router(score.router)
# app.include_router(copilot.router)            # Division 6C - AI analyst copilot
# app.include_router(incident_report.router)    # Division 6D - AI incident report
# app.include_router(simulator.router)          # Division 7  - attack simulator
# app.include_router(secops.router)             # Division 8  - security ops (audit chain, metrics, honeytoken)
app.include_router(profile.router)            # Division 9A - registration, profile, transaction history


@app.on_event("startup")
def _warm_scoring_models():
    """Division 4/6 - pre-load the trained models and the SHAP explainers so
    the first live transfer doesn't pay the cold-load cost."""
    from app.services.scoring import warm_models
    warm_models()
    try:
        from app.services.explainability import _get_explainer
        for ch in ("app", "ussd"):
            _get_explainer(ch)
    except Exception as exc:  # noqa: BLE001 - explainer warmup is best-effort
        import logging
        logging.getLogger("aegis.startup").warning("SHAP explainer warmup skipped: %s", exc)


@app.get("/health")
def health():
    """
    Confirms the API process is up. Postgres and Redis were both deliberately
    dropped from this architecture during the pivot to the in-memory store
    (memory_store.py) - this endpoint reflects that intentionally, rather than
    attempting live connections to services that were never meant to be here
    for this build.
    """
    return {
        "api": "ok",
        "postgres": "not used (pivoted to in-memory store)",
        "redis": "not used (pivoted to in-memory store; velocity counters fail soft)",
    }


@app.get("/")
def root():
    return {"service": "aegis-backend", "status": "running"}

# Division 5 will add:
#   app.include_router(hard_controls_router)