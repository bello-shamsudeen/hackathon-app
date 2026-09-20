# AEGIS — FINAL BUILD PLAN
### Division-by-division execution order · ICSC Hackathon, Track A1
*Companion to `Aegis_Full_Blueprint.md` — that document is WHAT and WHY. This document is WHAT WE BUILD, IN WHAT ORDER, WITH WHAT.*

---

## 0. Ground Rules For This Build

**Rule 1 — Nothing is built that doesn't appear in the demo.** Every division below ends with a named "demo moment." If a component has no demo moment, it doesn't get built.

**Rule 2 — Everything is demo data, and we say so loudly.** We cannot and should not pull real people's banking behaviour. The entire platform runs on synthetic data we generate and document. This is not a weakness — the brief *explicitly asks* for a synthetic dataset with documented generation logic. We lean into it: *"every number on this screen came from data we generated, and here is exactly how we generated it."* That is a stronger position than a team vaguely implying real data.

**Rule 3 — 100% free / free-tier tooling.** Full stack listed in Appendix A. No paid dependency anywhere in the critical path.

**Rule 4 — Build order is dependency-driven.** You cannot train a model before you have data. You cannot generate data before you know the schema. The order below is not arbitrary.

---

# THE NINE DIVISIONS

```
DIV 1  Foundation & Schema          ──┐
DIV 2  The Bank + USSD Gateway        ├─ nothing works without these
DIV 3  Synthetic Data Engine        ──┘
DIV 4  Detection Core (ML + Redis)   ─── the brain
DIV 5  Hard Controls (SIM/OTP/Token) ─── the part ML can't do
DIV 6  AI Explainability Layer       ─── the differentiator
DIV 7  Attack Simulator              ─── proves the numbers
DIV 8  Security Ops / SOC Backend    ─── the "high-tech" layer
DIV 9  Frontend, Console & Demo      ─── what the judges actually see
```

---

## DIVISION 1 — Foundation & Schema
**Build first. Everything downstream depends on the shape of this data.**

### What we build
- Monorepo structure: `/backend` (FastAPI), `/frontend` (React+Vite), `/ml` (training + models), `/simulator` (attack scripts), `/data` (generator + datasets), `/ops` (docker, sensor configs)
- `docker-compose.yml` bringing up: Postgres, Redis, FastAPI, frontend dev server — one command, whole stack. **This matters for the demo**: "one command, entire platform." Judges notice.
- Postgres schema — the full field list from the blueprint:
  - `users` — profile, historical baselines (typical hours, typical amount, typical devices)
  - `sessions` — channel (WEB/USSD), start/end, device fingerprint, IP, geo, IP type
  - `behavioral_events` — keystroke dwell/flight, backspace count, paste flag, nav path, cursor metrics, call-active flag
  - `ussd_events` — menu selection + timestamp, path sequence, retry count, timeout count
  - `telco_state` *(simulated)* — msisdn, IMEI, sim-device pairing, last_sim_swap_at, cell region, otp_request_count
  - `transactions` — amount, beneficiary, beneficiary_novelty flag, timestamp
  - `decisions` — risk score, verdict (ALLOW/CHALLENGE/BLOCK), triggered rules, feature contributions, explanation text, latency_ms
  - `audit_log` — hash-chained: `hash(row_data + prev_hash)`
  - `correlation_edges` — device/IP ↔ account links for the identity graph
  - `sensor_alerts` — Suricata/Zeek alert ingestion
- Alembic migrations so the schema is versioned, not hand-made

### Why first
The synthetic data generator (Div 3) writes into this schema. The feature engineering layer (Div 4) reads from it. Get it wrong here and you rebuild twice.

### Demo moment
`docker compose up` → whole platform live. Shown once at the start, briefly.

---

## DIVISION 2 — The Bank + USSD Gateway
**The target system. You cannot detect attacks against nothing.**

### 2A. The web/mobile bank
- React: login (PIN entry), dashboard, send-money form, transaction history
- Full behavioral telemetry capture wired in from day one:
  - `onKeyDown`/`onKeyUp` → dwell + flight timing per key pair
  - `onPaste` → paste flag
  - backspace counter
  - `mousemove`/`touchmove` sampling → movement smoothness metric
  - screen navigation sequence logger
  - device fingerprint (user-agent, screen res, timezone, language — nothing invasive)
  - "call active" flag (simulated toggle in demo; in production would come from mobile SDK/telephony state)
- Every event streams to `POST /ingest/behavior` in real time, not on submit

### 2B. The USSD gateway — how it actually works

This is worth understanding properly because it's a real differentiator and most teams will fake it badly.

**How real USSD banking works:**
1. Customer dials `*737#` on any phone, including a ₦5,000 feature phone
2. The telco (MTN/Airtel/Glo) routes it to an aggregator
3. The aggregator sends an HTTP POST to the bank's USSD endpoint containing: `sessionId`, `phoneNumber` (MSISDN), `serviceCode`, and `text` — where `text` is the **accumulated string of everything the user has pressed so far**, e.g. `"1*2*5000"`
4. The bank replies with a plain-text string starting with either:
   - `CON ` — continue, show this menu, wait for more input
   - `END ` — terminate the session, show this final message
5. Session dies after ~180 seconds of inactivity

**What we build:** a FastAPI endpoint that speaks *exactly this protocol* — same request shape, same `CON`/`END` response contract. This is the key point for judges: **our USSD backend is protocol-accurate. Plug a real aggregator in front of it and it works unchanged.** We're not simulating USSD, we're implementing the real interface and simulating only the telco in front of it.

**The simulator front-end:** a React component styled as a feature phone (Nokia-style keypad, small monochrome screen) that POSTs to that same endpoint. On stage it *looks* like someone using a basic phone; underneath it's hitting the identical production-shaped endpoint.

**Optional free upgrade:** Africa's Talking offers a free USSD sandbox simulator. If we point it at our endpoint via a free ngrok tunnel, we can demo through a *third-party telco sandbox* rather than our own UI — that's a strong "this is real" credential. Build our own simulator first as the reliable path; treat the sandbox as a bonus, never a live dependency on stage.

**What we capture per USSD session:** timestamp of every menu step (gives us hesitation/pace without keystrokes), path sequence, retry count, timeout count, session duration — plus the simulated telco fields (IMEI, SIM-swap flag, cell region) which is where USSD users get their *real* protection, since the handset gives us nothing.

### Demo moment
Judge sees a normal web transfer, then the same bank accessed from a feature phone — and both are being scored, by different signal sets.

---

## DIVISION 3 — Synthetic Data Engine
**The foundation of every number we will show. This gets serious effort, not a lazy `random.random()`.**

### What we build
**A persona-driven generator, not a random-noise generator.** This is the single biggest quality differentiator in the whole project, because everything downstream inherits its realism.

- **~50–100 user personas**, each with a stable behavioural fingerprint:
  - typing speed distribution (mean + variance — some people are consistent, some erratic)
  - habitual transaction hours (a market trader transacts at 6am; a salaried worker at 8pm)
  - typical amount range and how tight that range is
  - device history (1 device? 3? a shared family phone?)
  - channel preference (web-only, USSD-only, both)
  - navigation habits
- **Normal sessions:** thousands, sampled from those personas with realistic within-person variance. Critically, includes **legitimate anomalies** — the honest customer paying an unusually large hospital bill, the person who just bought a new phone, the family sharing one handset. *These are our false-positive test cases and they must exist in the data.* This is how we prove we respect the brief's "blocking a genuine transfer is not harmless" constraint.
- **Attacker sessions**, one archetype per attack (matching the simulator in Div 7):
  - credential stuffing (pasted creds, machine-fast, no browsing)
  - OTP replay / session reuse
  - SIM-swap takeover (correct PIN + correct OTP, new IMEI, recent swap flag — the scenario that beats every behaviour-only system)
  - social-engineering / coached victim (real user's own device and typing rhythm, but abnormal hesitation, call-active, new beneficiary, unusual amount)
  - slow-drift fraud (patient, under-threshold, escalating over days)
  - impossible travel / mid-session device swap
- **Class imbalance kept realistic** — fraud is rare. We do NOT generate 50/50 data. We generate something like 98/2 and then handle imbalance properly in training, because that's the actual problem the brief describes.
- **`DATA_GENERATION.md`** — a written methodology document: every distribution, every assumption, every parameter, and why. The brief says *"say clearly how you generated it."* This document is a graded deliverable, not an afterthought.

### Demo moment
A slide/screen showing the persona system and the distribution charts — "here's our data, here's exactly how it was made, nothing is hand-picked."

---

## DIVISION 4 — Detection Core
**The brain. First point where the platform actually decides something.**

### What we build
**4A. Feature engineering service** — turns raw events into the scored feature vector: all behavioural signals, plus derived compound features (amount-vs-personal-baseline ratio, time-vs-personal-pattern deviation, beneficiary novelty, dormancy, impossible-travel velocity, USSD pace deviation).

**4B. Redis velocity layer** — rolling counters: login attempts/min, transfers/hour, OTP requests/window, per-device account touches. Sub-millisecond reads. **This is what makes "<1 second" architecturally true rather than a claim.** We will measure and display actual decision latency in the UI — a live `47ms` readout on screen is worth more than any sentence about speed.

**4C. Model training pipeline** (`/ml`)
- **Isolation Forest** — unsupervised baseline, learns "normal" without labeled fraud. Directly answers *"real fraud examples are rare and arrive late."*
- **XGBoost** — supervised, trained on the labeled synthetic set, with class-imbalance handling (scale_pos_weight / stratified splits).
- **Ensemble scoring** → risk score 0–100.
- Reproducible training script + versioned model artifacts. **Model versioning shown in the UI** ("scored by aegis-xgb-v3") — small detail, very "real platform."

**4D. Threshold policy engine**
- ALLOW / **CHALLENGE** / BLOCK, with the CHALLENGE tier as the direct answer to the false-positive harm constraint.
- **Threshold tuning study**: sweep thresholds across the dataset, produce ROC/PR curves, and pick the operating point deliberately — then *show that curve to the judges*. "We chose this threshold, here's the tradeoff we accepted, here's what it costs us in false positives." Almost no student team does this.

**4E. Rules fallback engine** — velocity caps and amount limits that auto-engage if the ML service is unreachable. Health-check driven, with a visible banner in the UI when degraded.

### Demo moment
Live score appearing on a transaction with a real latency number, and the "kill the ML service → fallback engages, system keeps protecting" toggle.

---

## DIVISION 5 — Hard Controls (the part ML cannot do)
**This division exists because a fraudster with the correct PIN and correct OTP passes every behavioural check. This is where we stop them anyway.**

### 5A. Token Integrity Service
JWT with unique `jti`, tracked in Redis, burned on use. Replay = instant deterministic BLOCK. Not a probability — a refusal.

### 5B. SIM-Swap / OTP Defense Module
Runs as a **hard-rule layer alongside** the ML score, never inside it:
1. **SIM-swap check** — recent swap on this MSISDN → automatic CHALLENGE/BLOCK regardless of behavioural score
2. **Device-SIM pairing, with context** — new IMEI *alone* = weak/ignored (families share phones, people upgrade). New IMEI **+ recent SIM swap** = strong. New IMEI **+ first-time SIM on account** = strong. This is precisely how we honour *"families share phones and people change SIMs — neither is fraud"* while still catching swap-based takeover.
3. **OTP request-rate anomaly** — repeated OTP requests in a short window, tracked independently of any transaction.
4. **Out-of-band fallback** — when the swap flag is live, we do **not** send another OTP to that number (the attacker holds the SIM). We escalate to a secondary channel / manual hold. This single design decision demonstrates understanding of *why* SMS-OTP breaks in a swap scenario.
5. **Call-state + OTP interlock** — if the coaching signals fire (call active, abnormal hesitation, re-reading pattern) *while* an OTP is being entered, risk is elevated **even though the OTP is technically valid**. Nothing gets waved through just because the code matched. This is the module that makes the platform check the human, not the secret.

### 5C. Identity Correlation Engine
Graph of session ↔ device ↔ IP ↔ account. One account seeing a new device = ignored. One device touching five accounts in an hour = fraud-ring alert, independent of any single session's score. Built with NetworkX + SQL — cheap, and visually spectacular on the dashboard (Div 9).

### Demo moment
The strongest single moment in the whole demo: *"PIN correct. OTP correct. Every behavioural check passed. And we blocked it anyway — here's why."*

---

## DIVISION 6 — AI Explainability & Analyst Intelligence
**The innovation layer. Judges respond to AI, but only when it does a job — so every use below replaces real manual work.**

### 6A. SHAP → structured reason codes
SHAP values per decision, converted into ranked, weighted reason codes. This is the deterministic, auditable base layer — the AI sits *on top* of it, never replaces it. (Important framing: the explanation is always grounded in actual model math, so we never risk an LLM inventing a reason. Judges with ML background will specifically test for this.)

### 6B. LLM-generated dual-audience explanations
One decision, two automatically-generated explanations from the same SHAP reason codes:
- **Customer version** — plain, non-technical, non-accusatory, the sentence the brief asks for: *"We paused this transfer because it was going to a new account, for more than you usually send, from a phone we haven't seen before."*
- **Analyst version** — technical, with feature weights, triggered rules, and correlation context.

The brief asks for *"a plain sentence... of the kind a bank could give a customer."* Generating both audiences from one grounded source, live, is a clean, defensible AI application.

### 6C. AI Analyst Copilot (the showcase feature)
A natural-language query box on the investigation console:
- *"Why was session 4471 blocked?"*
- *"Show me everything this device touched today"*
- *"Summarise this incident for a report"*
- *"What would have happened if the threshold were 70 instead of 60?"*

The LLM is given the retrieved session data, SHAP output, correlation edges, and sensor alerts as context, and answers **only** from those. This is genuinely how modern SOC copilots work, and it turns a static dashboard into something that feels like a product.

### 6D. AI-drafted incident report
One click on a blocked session → auto-generated incident summary: what happened, which signals fired, what the correlation graph shows, recommended analyst action. Exportable. This is the "we automated the analyst's paperwork" beat.

### 6E. AI-assisted persona realism (used during Div 3)
LLM used to help design varied, plausible behavioural personas rather than us hand-writing 50 by hand. Mentioned honestly as a build-time tool, not a runtime claim.

**Free LLM options:** Groq free tier (very fast, good for live demo), Google Gemini free tier, or Ollama running a small local model (fully offline — and *offline is a genuine advantage on unreliable venue wifi*). Build against a thin abstraction so we can swap providers if one rate-limits us on demo day. **Have Ollama as the offline fallback — never let the demo depend on venue internet.**

### Demo moment
Ask the copilot a question live, on stage, about the attack that just got blocked. That's the moment the room goes quiet.

---

## DIVISION 7 — Attack Simulator
**Proves the numbers. Without this we have claims, not evidence.**

### What we build
Scripts that run real sessions against our own bank — six attack archetypes matching Div 3:
1. Credential stuffing
2. OTP replay
3. SIM-swap takeover
4. Social-engineering / coached victim
5. Slow-drift under-threshold fraud
6. Impossible travel / mid-session device swap

Each fires from a button on the dashboard. Each produces a **different detection signature and a different explanation** — which is the point: it proves the system reasons about attacks rather than pattern-matching one shape.

**Plus: a "normal traffic" generator** running continuously in the background during the demo, so the dashboard shows a realistic stream of legitimate activity that stays green — proving we're not flagging everything.

**Scope note:** this is entirely self-contained — our scripts against our own sandboxed fake bank. No offensive tooling, nothing pointed at anything we don't own. That line stays firm; it's also what keeps organisers comfortable.

### Demo moment
The attack panel. Judge picks which attack to launch — that interactivity is memorable.

---

## DIVISION 8 — Security Ops Backend (the "high-tech company" layer)
**This is the division that makes the platform feel like infrastructure rather than a school project.**

### 8A. Edge/gateway hardening
Nginx reverse proxy, TLS, rate limiting, basic WAF rules. Obvious scripted floods die at the door before touching the <1s decision path.

### 8B. Honeytokens
CSS-hidden form fields no human ever fills. Bots auto-fill them. Near-zero false positive → hard risk override. Cheap, real, elegant.

### 8C. Network sensors (Suricata / Zeek)
Run against our own simulated traffic. Burst patterns and anomalies become **an additional feature feeding the risk score** — defense in depth wired into the loop, not decoration sitting beside it.

### 8D. SIEM correlation (Wazuh or ELK — both free)
All logs into one timeline: app auth events, behavioural ingest, Suricata alerts, decision log. The demo value: show the *same attack* corroborated by three independent sensors on one screen.

### 8E. Hash-chained tamper-evident audit log
Each decision row hashed with the previous row's hash. Plus a **"Verify Chain"** button in the UI that walks the chain live and returns green. Then — for the demo — deliberately tamper with a row in the database and hit verify again to show it go red. *That is a spectacular five-second demo beat and it's trivially cheap to build.*

### 8F. OWASP ZAP self-scan
One baseline scan of our own app, kept as a report artifact. "We hardened our own attack surface before asking you to trust our detection layer."

### 8G. Live metrics service
Real-time catch rate, false-positive rate, precision/recall, decision latency (p50/p95), all computed from actual runs — never hardcoded. Powers the honesty dashboard in Div 9.

### Demo moment
Chain verification going red on tampered data, and the three-sensor SIEM correlation view.

---

## DIVISION 9 — Frontend, Investigation Console & Demo Assembly
**What the judges actually experience. Built last, because it needs everything else to exist — but designed early.**

### 9A. Design direction
Dark, dense, operational — the aesthetic of a real SOC, not a consumer fintech app. Restrained palette (deep slate base, single cool accent, semantic red/amber/green reserved *only* for verdicts so risk states read instantly). Monospace for data/IDs, clean sans for prose. High information density. Serious tools look serious.

### 9B. Screens
1. **Live Operations Dashboard** — streaming transaction feed via WebSocket, each row scoring in real time with visible latency; risk gauge; channel split (web vs USSD)
2. **Attack Control Panel** — six labelled attack triggers, plus the network-outage and tamper toggles
3. **Investigation Console** *(the flagship screen)* — click any blocked session, get a full forensic view:
   - full timeline of every raw signal in that session
   - SHAP contribution waterfall
   - telco state panel (IMEI, SIM-swap flag, cell region)
   - which hard rules fired vs which ML contributed
   - the identity correlation graph, live
   - linked Suricata alerts
   - both AI explanations (customer + analyst)
   - the AI copilot query box
   - "Verify audit chain" button
4. **Honesty Metrics Dashboard** — catch rate AND false-positive rate side by side, ROC/PR curves, threshold-tradeoff explorer, and an explicit **"What We Get Wrong"** panel naming our weakest attack type with real measured numbers
5. **USSD Simulator** — feature-phone UI, side-by-side with the live scoring so judges see USSD users being protected in parallel
6. **SIEM/Correlation View** — the three-sensor unified timeline

### 9C. Animation & motion (free, all of it)
Framer Motion throughout. Purposeful, never decorative:
- transactions sliding into the live feed as they arrive
- risk gauge animating up as a score climbs
- **the row turning red on BLOCK, with the explanation expanding beneath it** — the signature visual moment
- correlation graph nodes physically drawing connections as the ring is discovered (D3/force-directed)
- SHAP waterfall bars animating in sequence
- degraded-mode banner sliding down when ML is killed
- audit chain links flipping green one by one during verification, then one snapping red on tampered data

Motion should always be *communicating state*, never ornament. That restraint is itself a design signal to judges.

### 9D. Demo assembly & rehearsal
Final run-of-show:
1. One command brings the platform up
2. Normal traffic flows, dashboard green, USSD session running alongside
3. Credential stuffing → red, explained, sub-second latency shown
4. SIM-swap takeover → **the headline moment**: correct PIN, correct OTP, blocked anyway
5. Coached-victim attack → the socially-engineered case behavioural-only systems miss
6. Investigation Console deep dive → SHAP, telco state, correlation graph
7. AI copilot answers a live question about the incident
8. Kill the ML service → fallback engages, still protecting
9. Slow-drift attack → catches the patient under-threshold criminal
10. Audit chain verify → green; tamper; verify → red
11. Honesty dashboard → both numbers, plus what we get wrong and why
12. Close on USSD protection + the "our USSD endpoint is protocol-accurate" point

**Rehearse end-to-end, repeatedly, on the actual demo machine, with venue wifi assumed broken.** Everything must run locally. Non-negotiable.

---

# APPENDIX A — Full Stack (all free / free-tier)

| Layer | Tool | Cost |
|---|---|---|
| Backend | FastAPI, Uvicorn | Free (OSS) |
| Database | PostgreSQL | Free (OSS, local) |
| Cache/velocity | Redis | Free (OSS, local) |
| ML | scikit-learn, XGBoost, SHAP, pandas, NumPy | Free (OSS) |
| Graph | NetworkX | Free (OSS) |
| Frontend | React, Vite, TailwindCSS | Free (OSS) |
| Animation | Framer Motion | Free (OSS) |
| Charts | Recharts / D3 | Free (OSS) |
| Network sensors | Suricata, Zeek | Free (OSS) |
| SIEM | Wazuh or ELK (Basic) | Free |
| Packet artifacts | Wireshark | Free (OSS) |
| Self-pentest | OWASP ZAP | Free (OSS) |
| Dashboards | Grafana OSS | Free |
| Orchestration | Docker Compose | Free |
| LLM | Groq free tier / Gemini free tier / **Ollama (local, offline)** | Free |
| USSD sandbox *(optional)* | Africa's Talking sandbox + ngrok free | Free |

---

# APPENDIX B — Requirement → Division Traceability

| Brief requirement | Division(s) |
|---|---|
| Decision under 1 second | 4B (Redis), 8A (edge), 9B (visible latency) |
| USSD / feature-phone users | 2B, 3, 5B (telco signals), 9B |
| Fraud rare, arrives late | 3 (realistic imbalance), 4C (Isolation Forest) |
| False positives cause real harm | 3 (legitimate anomalies in data), 4D (CHALLENGE tier), 8B (honeytokens), 9B (honest FP reporting) |
| Shared phones / SIM swaps ≠ fraud | 5B (contextual pairing logic), 5C (correlation) |
| OTP phished / bought / read aloud | 5A, 5B (full module incl. call-state interlock) |
| Synthetic dataset, documented | 3 + `DATA_GENERATION.md` |
| Model scores live | 4C, 4D |
| Show catch rate AND false-positive rate | 8G, 9B (honesty dashboard) |
| Plain sentence per decision | 6A, 6B |
| Sensible, different USSD answer | 2B, 5B |

---

# APPENDIX C — What Makes This Win

Ranked by how much each one separates us from the field:

1. **The SIM-swap block** — correct PIN, correct OTP, blocked anyway. Nobody else will build a specific answer to the scenario the brief's own opening paragraph describes.
2. **Protocol-accurate USSD** — not a fake menu; the real `CON`/`END` interface contract, with protection sourced from the telco layer where it actually lives.
3. **The coached-victim attack** — recognising that a huge share of Nigerian fraud is a real user on their own device being talked through it. Behavioural-only systems are blind to this.
4. **The honesty dashboard** — showing what we get wrong, with real measured numbers.
5. **The AI copilot on the investigation console** — makes it feel like a product, not a project.
6. **The audit chain going red on tamper** — five seconds, unforgettable.
7. **Threshold tradeoff study** — demonstrable rigor almost no student team brings.
8. **Everything runs locally, offline, in one command** — nothing breaks on venue wifi.

---

*Next step on request: judge-facing pitch and presentation structure, built directly off Appendix B and C.*
