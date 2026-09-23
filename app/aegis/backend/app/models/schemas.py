"""
Division 2 — request/response models for the fake bank + USSD gateway.
Field names deliberately match the Postgres schema from Division 1
(ops/postgres/init/001_schema.sql) so ingestion maps 1:1 into the tables.
"""
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime


# ---------- Bank (WEB channel) ----------

class SessionStartRequest(BaseModel):
    """
    Opens a WEB session BEFORE authentication, so pre-login keystroke telemetry
    has a real sessions row to reference (behavioral_events.session_id is a
    NOT NULL FK). Login then adopts this same session rather than creating a
    second one, keeping one continuous session across login -> transfer.
    """
    device_fingerprint: Optional[str] = None
    ip_type: Optional[str] = None  # HOME_WIFI, MOBILE_DATA, VPN_PROXY, UNKNOWN


class SessionStartResponse(BaseModel):
    session_id: str


class LoginRequest(BaseModel):
    msisdn: str
    pin: str
    device_fingerprint: Optional[str] = None
    ip_type: Optional[str] = None  # HOME_WIFI, MOBILE_DATA, VPN_PROXY, UNKNOWN
    # Session opened by /bank/session/start before the user began typing.
    # Optional so the endpoint still works for direct API calls (Division 7's
    # attack scripts) that don't pre-open a session.
    session_id: Optional[str] = None


class LoginResponse(BaseModel):

    msisdn: str | None = None
    session_id: str
    user_id: str
    full_name: str
    # Division 9A — the consumer app's Home/Profile screens need these on the
    # session object returned at login.
    account_number: Optional[str] = None
    avatar_data_url: Optional[str] = None
    is_freshly_registered: bool = False


class TransferRequest(BaseModel):
    session_id: str
    beneficiary_account: str
    amount: float
    # ---- Division 5 hard-control inputs ----
    # Device identity for the SIM-swap/device-change hard control. If omitted,
    # the scoring layer derives one from the session's device_fingerprint.
    current_imei: Optional[str] = None
    # True while the customer is on a voice call as they confirm (coaching /
    # call+OTP interlock signal).
    call_active: bool = False
    # True when this confirmation is an OTP entry step (call/OTP interlock).
    otp_being_entered: bool = False
    # One-time confirmation token from POST /bank/request-otp. If supplied it is
    # consumed here; a replayed or expired token is a hard block.
    token: Optional[str] = None
    # Division 8B — honeytoken. A CSS-hidden field no human ever sees or fills;
    # a bot that auto-fills every field trips it. Any non-empty value here is an
    # automatic hard BLOCK (near-zero false positive).
    confirm_email_address: Optional[str] = None


class OTPRequestModel(BaseModel):
    """Division 5 — a customer (or attacker) asking for a verification code.
    Feeds the OTP request-rate hard control and issues a one-time token."""
    session_id: str


class OTPRequestResponse(BaseModel):
    token: str
    fallback_channel: str            # SMS_OTP | MANUAL_HOLD_SECONDARY_CHANNEL_REQUIRED
    otp_requests_in_window: int
    rate_anomaly: bool


class TransferResponse(BaseModel):
    transaction_id: str
    status: str  # for Division 2 this is always "recorded" — real ALLOW/CHALLENGE/BLOCK
                 # verdicts come from the decision engine in Division 4/5, not here.
    # Division 4 — the detection loop now fires automatically on every transfer.
    # This carries the risk_score / tier / action / message / latency_ms from
    # POST /score/session/{session_id}. None only if scoring itself errored
    # (the transfer is still recorded regardless — detection never blocks it).
    detection: Optional[Dict[str, Any]] = None


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
