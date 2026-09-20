"""
Division 7 — Simulator control endpoints.
Division 9's dashboard "Launch Attack" buttons will call these directly.
Building the endpoints now, before the UI exists, means Division 9 only has
to wire buttons to already-working, already-tested logic.
"""
from fastapi import APIRouter, HTTPException

from app.db import get_connection
from simulator.attack_scripts import ATTACK_FUNCTIONS
from simulator.normal_traffic import start_background_traffic, stop_background_traffic

router = APIRouter(prefix="/simulator", tags=["simulator"])


@router.post("/attack/{archetype}")
def launch_attack(archetype: str):
    archetype = archetype.upper()
    if archetype not in ATTACK_FUNCTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown archetype. Valid: {list(ATTACK_FUNCTIONS.keys())}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        result = ATTACK_FUNCTIONS[archetype](cur)
    finally:
        cur.close()
        conn.close()
    return result


@router.post("/normal-traffic/start")
def start_normal_traffic():
    start_background_traffic(get_connection)
    return {"status": "started"}


@router.post("/normal-traffic/stop")
def stop_normal_traffic():
    stop_background_traffic()
    return {"status": "stopped"}


@router.get("/archetypes")
def list_archetypes():
    return {"archetypes": list(ATTACK_FUNCTIONS.keys())}
