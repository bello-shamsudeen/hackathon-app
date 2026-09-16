"""
Division 2 — request/response models for the fake bank + USSD gateway.
Field names deliberately match the Postgres schema from Division 1
(ops/postgres/init/001_schema.sql) so ingestion maps 1:1 into the tables.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ---------- Bank (WEB channel) ----------

class LoginRequest(BaseModel):
    msisdn: str
    pin: str
    device_fingerprint: Optional[str] = None
    ip_type: Optional[str] = None  # HOME_WIFI, MOBILE_DATA, VPN_PROXY, UNKNOWN


class LoginResponse(BaseModel):
    session_id: str
    user_id: str
    full_name: str


class TransferRequest(BaseModel):
    session_id: str
    beneficiary_account: str
    amount: float


class TransferResponse(BaseModel):
    transaction_id: str
    status: str  # for Division 2 this is always "recorded" — real ALLOW/CHALLENGE/BLOCK
                 # verdicts come from the decision engine in Division 4/5, not here.


# ---------- Behavioral telemetry (WEB channel) ----------

class BehaviorEvent(BaseModel):
    session_id: str
    event_type: str  # KEYDOWN, KEYUP, PASTE, BACKSPACE, MOUSEMOVE, NAV, CALL_STATE
    key_dwell_ms: Optional[int] = None
    key_flight_ms: Optional[int] = None
    is_paste: bool = False
    backspace_count: int = 0
    nav_screen: Optional[str] = None
    cursor_smoothness_score: Optional[float] = None
    call_active: bool = False


class BehaviorBatch(BaseModel):
    events: List[BehaviorEvent]


# ---------- USSD (protocol-accurate) ----------

class USSDRequest(BaseModel):
    """
    Mirrors the real aggregator->bank POST contract used by Africa's Talking
    and most Nigerian USSD aggregators. 'text' is the FULL accumulated string
    of every key the user has pressed this session, joined by '*'.
    e.g. after dialing, selecting "2", then "08012345678": text = "2*08012345678"
    """
    sessionId: str
    phoneNumber: str
    serviceCode: str
    text: str
