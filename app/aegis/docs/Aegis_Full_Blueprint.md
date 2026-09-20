# AEGIS — Full Combined Blueprint
### Track A1: Spotting Account Takeover From Behaviour (ICSC Hackathon)

---

## 1. The Problem, Restated Precisely

Nigerian bank accounts are protected by a **secret** (PIN, password, OTP), not by verification of the **person**. Once the secret is entered correctly, the system assumes the real owner is present — even if the secret was phished, bought, or read aloud to a scammer over a phone call.

Banks already collect behavioral data that could catch this but don't use it. The rules that do exist (flag large/first-time transfers) are blunt: they block honest customers doing something unusual (rent, hospital bill) and miss patient fraudsters who stay under the threshold.

### The five hard constraints (every feature below must respect these)
1. Decision must happen in **under 1 second**, live, mid-transaction.
2. Many users are on **USSD/feature phones** — no app, no JS, no rich sensors.
3. Real fraud is **rare and arrives late** — can't rely on lots of labeled fraud data.
4. **False positives have real human cost** — blocking a genuine transfer isn't harmless.
5. **Shared phones and SIM swaps are normal**, not inherently fraud — device/SIM change alone is a weak signal that needs context.

---

## 2. System Architecture (Full)

```
┌────────────────────────────────────────────────────────────────────┐
│ FRONTEND (React + Tailwind)                                         │
│  - Live transaction feed, risk dashboard, analyst/SOC console        │
│  - USSD text-menu simulator (separate interface)                     │
└───────────────────────────────┬──────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────┐
│ EDGE / GATEWAY LAYER                                                  │
│  - Reverse proxy, TLS, rate limiting                                  │
│  - Honeytoken fields, basic WAF rules                                 │
└───────────────────────────────┬──────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────┐
│ BACKEND (FastAPI, Python)                                             │
│  ├─ Session/Behavior Ingestion API (app + USSD gateway)                │
│  ├─ Feature Engineering Layer (behavioral + telco-simulated fields)    │
│  ├─ Redis — real-time velocity counters & session state                │
│  ├─ SIM-Swap / OTP Defense Module                                      │
│  ├─ Identity Correlation Engine                                        │
│  ├─ ML Scoring Service (Isolation Forest + XGBoost)                    │
│  ├─ Explainability Module (SHAP → plain-English sentence)              │
│  ├─ Token Integrity Service (JWT/OTP replay prevention)                │
│  ├─ Rules Fallback Engine (offline/degraded mode)                      │
│  ├─ Attack Simulator Module                                            │
│  └─ Network Sensor Bridge (Zeek/Suricata log ingestion)                │
└───────────────────────────────┬──────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────┐
│ CORRELATION / SIEM LAYER (Wazuh or ELK)                               │
│  - Unifies app logs, auth events, Suricata alerts, decision log        │
└───────────────────────────────┬──────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────┐
│ DATA LAYER                                                            │
│  - PostgreSQL: sessions, decisions, hash-chained audit log             │
│  - Synthetic dataset generator (documented generation logic)           │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. Full Feature List — Each Mapped to the Exact Problem It Solves

### A. The Fake Bank + USSD Simulator
**What it is:** A pretend banking site (login, dashboard, send-money) AND a separate text-menu USSD-style interface.
**Solves:** *"Many customers use USSD or feature phones, so there is no app collecting signals."* Without this, half the brief is unaddressed.

---

### B. Behavioral Signal Set (App/Web Users) — Expanded

| Signal | What it catches |
|---|---|
| Typing speed on PIN entry | Baseline anomaly detector |
| Typed vs pasted detection | Credential-stuffing / autofill bots |
| **Typing rhythm** (dwell/flight time between specific keys) | Harder-to-fake identity signal than raw speed |
| **Backspace/retry pattern** | Sudden "perfect" entry from a usually-fumbling user is itself suspicious |
| **Navigation path through app** | Scripted attacks skip the normal browsing pattern and go straight to transfer |
| **Touch/cursor movement quality** | Bots move in unnaturally straight/instant lines; humans don't |
| **Simultaneous phone call during session** *(coaching/scam-call detection)* | Catches the "victim being talked through the transfer live by a scammer" pattern — a completely different signature from both a normal user and a bot: long hesitation, re-reading behavior, active call flag if permission allows |
| Time-of-day vs personal history | Off-hours activity for this specific user |
| Transaction amount vs personal average | Unusual amount for this specific user |
| **New beneficiary + amount novelty (compound)** | First-time recipient + unusual amount together is stronger than either alone |
| **Dormant-account reactivation** | Sudden activity after months of inactivity |
| Session velocity (login → transfer speed) | Bots move faster than humans |
| **IP/network type** (home WiFi vs fresh mobile data vs VPN/proxy) | Sudden jump to proxy/VPN is a red flag |
| **Impossible travel** (location vs last session, vs time elapsed) | Physically implausible session jumps |

**Solves:** *"Banks already collect signals that could tell them more... almost none of this is used."* This is the direct, literal answer to that complaint — and the phone-call signal specifically answers *"fraudsters... talk victims into reading the code out over the phone."*

---

### C. USSD-Specific Solution Stack (the part that actually solves it, not just simulates a menu)

USSD has no JavaScript, no device fingerprinting, no keystroke-level data. The solution has to come from the **gateway/telco layer**, not the app layer:

| Signal | What it catches |
|---|---|
| Menu-to-menu timing at the gateway | Even without keystrokes, every menu selection is a timestamped request — hesitation/pace still measurable and comparable to this user's USSD history |
| Habitual USSD path | Does this user always check balance first, or go straight to transfer? Automated USSD fraud tends to skip straight to the money path |
| Session retry/timeout pattern | Faster-than-human retries across multiple 180-second timeouts is a signal |
| **Telco-side signals (simulated for hackathon, honestly labeled as such):** SIM-device (IMEI) pairing, current cell tower/region, recent SIM-swap flag | This is the actual unlock for USSD users — the network already knows what the handset can't tell your app |

**Solves:** *"A sensible answer for USSD and feature phone users, even if it is a different one."* — different mechanism (telco/gateway-side, not device-side), but equally real protection. **Explicit honesty note for judges:** telco data is simulated for the demo; production version would need an MNO data-sharing integration.

---

### D. OTP / SIM-Swap Defense Module (dedicated subsystem — deterministic, not probabilistic)

This exists because a fraudster with a correct PIN *and* a correct OTP (via SIM swap) will pass every behavioral check that only watches typing patterns. This module is a **hard rule layer**, sitting alongside the ML score, not inside it:

1. **SIM-swap flag check** — before any OTP-gated action, check (simulated telco field): has this number had a SIM swap in the last X hours? If yes → automatic CHALLENGE/BLOCK regardless of behavioral score.
2. **Device-SIM pairing mismatch, with context:**
   - New device alone = weak signal (ignore/low weight)
   - New device + recent SIM swap = strong signal
   - New device + first-time SIM on this account = strong signal
   - This is the direct fix for *"Families share phones and people change SIMs. Neither is fraud"* — the system never punishes a raw device/SIM change, only the *combination* that indicates compromise.
3. **OTP request-rate anomaly** — multiple OTP requests in a short window for one account, independent of any transaction.
4. **Out-of-band fallback when SIM-swap flag is active** — do NOT just send another OTP to a number flagged as recently swapped (the fraudster has it). Fall back to a registered secondary channel or manual hold instead. This is the detail that shows you understand *why* SMS-OTP alone fails in a SIM-swap scenario.
5. **Live-call / coaching flag feeds into this module too** — if the behavioral signal in section B (simultaneous call, hesitation, re-reading) fires *at the same time* as an OTP is being entered, that combination is treated as elevated risk even if the OTP itself is technically valid and untouched. This is the module ensuring "OTP was technically correct" never means "assume it's safe" — nothing here gets skipped just because the code matched.

**Solves:** Directly answers the brief's opening line — *"Fraudsters phish them, buy them, or talk victims into reading the code out over the phone... the system checks the secret, not the human being."* This module is what makes the system check something beyond the secret.

---

### E. Identity Correlation Engine
**What it is:** Tracks whether the same device fingerprint or IP touches multiple *different* accounts in a short window — a sign of an organized fraud ring, not one confused customer.
**Solves:** Gives you a *safe* way to use device/IP signals without punishing the normal shared-phone/SIM-swap behavior the brief explicitly protects. One account, new device = ignored. One device, five accounts = real alert.

---

### F. ML Scoring Pipeline
- **Isolation Forest** (unsupervised) — learns "normal" without needing labeled fraud, because *"real fraud examples are rare, arrive late."*
- **XGBoost** (supervised) — layered in once labeled synthetic attack data exists, for sharper scoring.
- **Output:** risk score 0–100 → ALLOW / **CHALLENGE** / BLOCK.
- The CHALLENGE middle tier directly answers *"blocking a genuine transfer is not harmless"* — ambiguous cases get a second check, not an outright block.

---

### G. Explainability (SHAP → Plain-English Sentence)
**What it is:** Converts model weights into: *"Flagged because: new device (high), 3x normal transfer amount (medium), rapid session (low)."*
**Solves:** *"A plain sentence explaining each decision, of the kind a bank could give a customer who asks why their transfer was stopped."* Named explicitly in the brief — not optional.

---

### H. Token Integrity Service
**What it is:** One-time-use session tickets (JWT with a `jti`); once used, dead forever. Reuse = instant deterministic block.
**Solves:** OTP/session replay attacks — a hard control, not a guess, complementing the SIM-swap module.

---

### I. Redis Velocity Layer
**What it is:** Sub-millisecond in-memory counters for login attempts, transfer frequency, etc., instead of slow database queries.
**Solves:** *"The decision must happen in under a second, inside a live transfer."* Makes the speed requirement architecturally true, not just claimed.

---

### J. Rules Fallback Engine (Offline/Degraded Mode)
**What it is:** Simple velocity-cap/amount-limit rules that take over automatically if the ML service goes down.
**Solves:** Realism/robustness — demoing "we killed the ML service and the system didn't fail open or crash" is a maturity signal judges specifically probe for.

---

### K. Attack Simulator
**What it is:** Scripts that generate real attacker sessions against your own fake bank: credential stuffing, OTP replay, slow-drift fraud (small amounts increasing over time), impossible travel/device swap.
**Solves:** *"Proof that it catches takeovers without flooding the bank with false alarms. Show both numbers."* The slow-drift attacker specifically answers *"blunt rules... miss patient criminals who stay just under the limit."*

---

### L. Hash-Chained Audit Log
**What it is:** Every decision row cryptographically links to the previous one — tampering with history becomes detectable.
**Solves:** Supports the trust story underneath the whole track — a decision that blocked someone's rent needs to be provably honest when reviewed later.

---

### M. SIEM Correlation Layer (Wazuh/ELK)
**What it is:** One timeline view combining app logs, Suricata/network alerts, and the decision log.
**Solves:** Lets you *prove*, live, that an attack was caught by multiple independent signals at once — not a single fragile model.

---

### N. Honeytokens
**What it is:** Invisible form fields real humans never fill; bots that auto-fill everything often do.
**Solves:** A near-zero-false-positive signal for scripted/bot attacks — directly supports the "don't flood the bank with false alarms" requirement.

---

### O. Edge/Gateway (Rate Limiting, Basic WAF)
**What it is:** Front-door filtering of obviously scripted traffic before it reaches the core pipeline.
**Solves:** Reduces load on the <1s decision path; demonstrates defense-in-depth rather than one layer catching everything.

---

### P. Self-Pentest Artifact (OWASP ZAP baseline scan)
**What it is:** A one-time scan of your own fake bank, kept as a report/slide.
**Solves:** Shows you tested your own attack surface before asking judges to trust your detection layer — legitimate, defensive, self-contained (not offensive tooling aimed at anything outside your own sandbox).

---

## 4. Complete Requirement → Solution Map

| Brief requirement | Feature(s) answering it |
|---|---|
| Decision under 1 second | Redis velocity layer, edge filtering, Token Integrity Service |
| USSD/feature phone users, no app signals | USSD simulator + gateway-timing + simulated telco signals |
| Fraud rare, arrives late | Isolation Forest (unsupervised baseline) |
| Blocking genuine transfers is harmful | CHALLENGE tier, honeytokens (low false-positive bot signal) |
| Shared phones/SIM swaps ≠ fraud alone | Identity Correlation Engine + SIM-swap contextual logic (device change alone = ignored) |
| OTP can be phished/bought/read aloud | SIM-Swap/OTP Defense Module, live-call/coaching behavioral signal |
| Synthetic dataset, generation documented | Attack Simulator + Dataset Generator with written methodology |
| Model scores live | ML Scoring Service (Isolation Forest + XGBoost) |
| Show catch rate AND false-positive rate honestly | Metrics dashboard, SIEM correlation view |
| Plain sentence explaining each decision | SHAP → sentence generator |
| Sensible, different answer for USSD users | Full USSD-specific stack (Section C) |

---

## 5. Data Schema — Fields to Capture (for dataset generator + live pipeline)

**Behavioral (app/web):** keystroke dwell/flight times, backspace count, paste-event flag, nav-path sequence, cursor movement metrics, call-active flag, session duration, time-of-day, tx amount, beneficiary novelty, account dormancy flag, IP type (home/mobile/VPN), geo-coordinates + timestamp (for impossible-travel calc).

**USSD:** menu-selection timestamps, path sequence, retry count, timeout count, session length.

**Telco (simulated):** IMEI, SIM-device pairing status, last SIM-swap timestamp, current cell region, OTP request count (rolling window).

**System/security:** device fingerprint hash, JWT `jti` usage log, honeytoken-filled flag, Suricata alert tags, hash-chain value per decision row.

---

## 6. Honesty Notes (state these explicitly to judges — this builds credibility, not weakness)
- Telco-side data (SIM-swap timestamps, IMEI pairing, cell location) is **simulated** for this hackathon; production would require an MNO data-sharing integration.
- Synthetic dataset generation logic will be fully documented and shown, not black-boxed.
- The demo will show at least one attack type the system does **not** catch well, with an explanation and next steps — not just wins.

---

*This document is the single source of truth for the Aegis build. Next step (on request): translate this into the judge-facing pitch/presentation structure.*
