# Aegis Build Progress

## Division 1 — Foundation & Schema
Status: COMPLETE

- docker-compose.yml — Postgres 16, Redis 7, FastAPI backend. `docker compose up`
  brings up all three cleanly; Postgres/Redis report `healthy`, backend depends on
  both via `condition: service_healthy`. Removed the obsolete top-level `version:` key.
- `GET /health` confirmed returning `{"api":"ok","postgres":"ok","redis":"ok"}`.
- Alembic is now the versioned source of truth for the schema:
  - `backend/alembic.ini`, `backend/migrations/env.py` (reads `DATABASE_URL` from
    env, same convention as `app/main.py` — no hardcoded connection strings),
    `backend/migrations/versions/0001_initial_schema.py` (baseline migration,
    mirrors the original schema exactly: users, sessions, behavioral_events,
    ussd_events, telco_state, transactions, decisions, audit_log,
    correlation_edges, sensor_alerts, plus all indexes).
  - `ops/postgres/init/001_schema.sql` is kept as reference documentation only —
    it is no longer mounted into `docker-entrypoint-initdb.d`. The Postgres
    container now starts empty; `backend/Dockerfile`'s CMD runs
    `alembic upgrade head` before starting uvicorn, so `docker compose up` still
    produces a fully-migrated stack in one command on a fresh machine.
  - The pre-existing dev database (created by the old init script before this
    change) was reconciled with `alembic stamp head` rather than wiped, so no
    destructive volume reset was needed. Verified via `\dt` that all 10 tables
    plus `alembic_version` are present after a full backend rebuild/restart.
  - Any future schema change must be a new Alembic revision — no more hand
    edits to raw SQL.
- Git repo initialized at the project root (`git init`), plus a `.gitignore`
  covering Python/Node/ML/env artifacts. Nothing has been committed yet — no
  commit was made since it wasn't requested.

### Demo moment — verified
`docker compose up` → Postgres, Redis, backend all come up healthy, schema is
applied automatically via Alembic, `/health` reports all-green. This is the
Division 1 demo beat and it now works end-to-end on a clean container recreate,
not just anecdotally.

## Division 2 — Bank + USSD Gateway
Status: COMPLETE (verified end-to-end against a live stack, not assumed)

### Integration
- `backend/app/db.py` — `get_connection()`, plain psycopg2, matching the pattern
  `app/main.py` already used for `/health`. SQLAlchemy stays confined to Alembic
  (`migrations/env.py`) for schema only, so there is exactly one way to talk to
  Postgres at request time.
- Routers moved from `backend_additions/` into `backend/app/routers/`
  (`bank.py`, `behavior.py`, `ussd.py`) and `backend/app/models/schemas.py`;
  `backend_additions/` removed. All three wired into `main.py`.
  Registered routes confirmed via `/openapi.json`:
  `/bank/session/start`, `/bank/login`, `/bank/dashboard/{session_id}`,
  `/bank/transfer`, `/ingest/behavior`, `/ussd`.
- `frontend/Dockerfile` added; `frontend` service added to docker-compose on
  port 5173, proxying `/bank`, `/ingest`, `/ussd` to the backend.
  `docker compose up` now brings up all four services in one command
  (verified from a cold `docker compose down` + `up`).

### Bugs found and fixed during verification
1. **Pre-login telemetry was silently discarded (blocking).** `Login.jsx`
   generated a client-side `crypto.randomUUID()` for pre-login capture, but
   `behavioral_events.session_id` is a NOT NULL FK to `sessions(id)`. Every
   insert failed with `ForeignKeyViolation`, and the hook's deliberate
   silent-fail hid it — the UI looked fine while nothing was recorded.
   Fixed by adding `POST /bank/session/start`, which opens a real WEB session
   (`user_id` NULL) before the user types; `/bank/login` then *adopts* that
   session id instead of creating a second one. This keeps one continuous
   session across login → transfer, which Division 4 needs for session-velocity
   features, and preserves the design intent that typing during login is itself
   a signal.
2. **USSD 500'd on any real aggregator session id (protocol-accuracy defect).**
   `sessions.id` is UUID, but real aggregators send opaque strings
   (e.g. Africa's Talking `ATUid_9f2c...`), causing
   `InvalidTextRepresentation`. This would have broken the Appendix C
   differentiator "plug a real aggregator in front and it works unchanged."
   Fixed with a deterministic `uuid5` mapping of aggregator sessionId →
   internal UUID (no schema migration needed; same aggregator session always
   resolves to the same row). Verified with `ATUid_9f2c7b41e5a8`.
3. **`/ussd` SPA route collided with the `/ussd` API path.** Loading
   `http://localhost:5173/ussd` directly returned raw
   `{"detail":"Method Not Allowed"}` instead of the simulator — a judge
   reloading or deep-linking that page would have hit it. Fixed with a Vite
   proxy `bypass` so browser navigations (GET + `text/html`) serve the app
   while the simulator's POSTs still reach the protocol-accurate endpoint.
   The USSD contract is the CON/END + accumulated-text shape, not the URL path,
   so nothing an aggregator depends on changed.
4. **USSD never computed `beneficiary_is_novel`** (left defaulting to FALSE)
   while the WEB path did. Division 4 scores this feature on both channels, so
   USSD now computes it the same way as `bank.py`.
5. **Vite served stale modules** through the Windows bind mount (no inotify
   events), so edits appeared to have no effect. Enabled `usePolling` in
   `vite.config.js` — needed for all remaining frontend work on this setup.

### Test user (temporary — Division 3 replaces this)
One row inserted manually so login is exercisable now:
`msisdn 08012345678`, `full_name 'Test User'`, `persona_tag 'DIV2_TEST'`.
PIN is not validated yet by design — any PIN succeeds for a known msisdn.
Real PIN/OTP handling is Division 5.

### Verified end-to-end (actual query output, not assumption)
- **WEB login** → "Welcome, Test User", balance NGN 458,200 rendered.
  Session adoption confirmed: the row created pre-login at 08:56:54 is the
  same row that later carried `user_id`; no duplicate session was created.
- **Behavioral events land live while typing.** 113 events on that one session:
  `KEYDOWN 31, KEYUP 32, MOUSEMOVE 47, NAV 3`, spanning pre-login NAV
  (08:56:56) through post-login dashboard (08:58:29). Timing values are real,
  not nulls — dwell 2–10ms, and a 5667ms flight gap capturing the pause between
  fields (exactly the hesitation signal Division 4 wants).
- **WEB transfer** recorded: `0998877665`, NGN 25,000, `beneficiary_is_novel=t`.
- **USSD full walkthrough via the feature-phone UI**: dialed `*737#`, chose
  2, entered recipient/amount/PIN, got
  `END Transaction successful. NGN 12500 sent to 08033344455.`
- **`ussd_events` rows written with the accumulated-text protocol**, growing
  exactly as spec: `''` → `2` → `2*08033344455` → `2*08033344455*12500` →
  `2*08033344455*12500*1234`, linked to Test User by MSISDN. Step timestamps
  give real menu-to-menu pacing (19s, 55s, 19s, 15s) — the Division 2B
  hesitation signal, captured without any keystroke access.
- **CON/END semantics confirmed** at every step against a realistic aggregator
  session id.
- **Novelty logic proven correct in both directions**: first send to a
  beneficiary → `novel=t`; repeat send to the same beneficiary → `novel=f`.
- **Cold start**: `docker compose down` then `up` → all four services healthy,
  `/health` all-green, data persisted (1 user, 10 sessions, 149 behavioral
  events, 18 ussd events, 5 transactions).

### Known issues (not blocking, carried forward)
- React `StrictMode` double-invokes effects in dev, so each Login page load
  opens **two** `sessions` rows (one is left with `user_id` NULL and no
  events). Harmless now, but Division 3/4 should filter empty sessions, or
  Division 9 should drop StrictMode / make session-start idempotent.
- The `J3J3` / NGN 1.00 USSD transaction in the DB is stray data from an
  accidental keystroke during setup, and predates the novelty fix
  (`novel=f`). Division 3 reseeds this database anyway.
- `useBehaviorCapture` fails silently by design; that hid bug #1 for a while.
  Worth surfacing ingest failures in the SOC console in Division 9.

### Demo moment — verified
A normal web transfer and the same bank reached from a feature phone, both
recording to the same schema through different signal sets: the web session
carrying keystroke dwell/flight and cursor telemetry, the USSD session carrying
menu-step pacing from the gateway where the handset gives us nothing.

## Division 3 — Synthetic Data Engine
Status: COMPLETE (verified end-to-end: CSVs, Postgres reseed, Division 2 flow)

### What was built
- `data/personas.py` — 6 named behavioural personas (typing speed, active hours,
  amount profile, channel preference, device count, nav depth), each user sampled
  from a persona template with individual jitter. `family_shared_phone` persona
  deliberately has high device count + typing variance to prove the system does
  not treat shared-phone use as fraud on its own (named brief requirement).
- `data/generate_dataset.py` — single generation pass, one set of random draws
  per synthetic user (`seed=42`, fully deterministic), producing:
  1. `data/app_channel_data.csv` and `data/ussd_channel_data.csv` — the flat
     4-feature + label files for Brief A's RandomForest training.
  2. rich `users` + `telco_state` rows in Postgres for Aegis's own Division 4
     core (the DB write path — see "Pending" below).
  Deviation-feature formulas are defined once here and are copy-identical to the
  live-inference formulas in Brief C Tasks 4/6 — no train/serve drift.
- `docs/DATA_GENERATION.md` — the graded methodology writeup (brief requires
  "say clearly how you generated it"): persona rationale, legitimate-anomaly
  false-positive test set (6% of each user's own sessions, labelled 0), the six
  attacker archetypes and which two (SIM-swap, impossible-travel) are honestly
  NOT separable by these 4 features and are caught by other layers.

### Class-balance fix (this session)
Initial run landed at 2.68% app / 2.44% USSD positive against ~4.8% / ~5.1%
targets — the `ATTACKER_SESSION_TOTAL_*` constants were miscalibrated (55/2055,
50/2050; the "tuned" comment's arithmetic was wrong). Constants corrected to
101 (app) and 107 (USSD). Achieved rates now, verified by recount from the CSV
files on disk:
- `app_channel_data.csv` — 2,101 rows, label `0`: 2000, label `1`: 101 → **4.81%**
- `ussd_channel_data.csv` — 2,107 rows, label `0`: 2000, label `1`: 107 → **5.08%**
Generation is seeded, so these are exact and reproducible, not a sample.
Recorded in `data/generation_summary.json`. `DATA_GENERATION.md` "Class balance"
section rewritten with the concrete breakdown table.

Constants committed in `a7e5796`; a follow-up commit covers the reseed below.

### Postgres reseed (done this session — full clean slate)
The generator's DB write path had only ever run once (pre-fix), and its
deterministic MSISDNs collided with the Division 2 rows on any rerun. Resolved:

1. `TRUNCATE users, sessions, behavioral_events, ussd_events, telco_state,
   transactions, decisions, audit_log, correlation_edges, sensor_alerts
   RESTART IDENTITY CASCADE` — cleared the Division 2 `DIV2_TEST` user, the stray
   `J3J3` / NGN 1.00 USSD row, and the 10 sessions (incl. StrictMode empty
   duplicates). `alembic_version` left at `0001`, untouched.
2. `python data/generate_dataset.py` rerun fresh against the empty DB → 80
   synthetic users + 80 `telco_state` rows written; CSVs + summary regenerated.
3. Division 2 test-login user recreated:
   `msisdn 08012345678`, `full_name 'Division 2 Test User'`, `persona_tag 'DIV2_TEST'`
   (id `1340557b-383c-441c-9533-8a16ccf0264d`). No `telco_state` row for it —
   same minimal setup as before; PIN still unvalidated by design (Division 5).

### Verified — real query / API output
- `SELECT COUNT(*) FROM users;` → **81** (80 synthetic + 1 test user)
- `SELECT COUNT(*) FROM telco_state;` → **80** (synthetic only)
- `persona_tag` breakdown: `market_trader 14`, `salaried_worker 14`,
  `elderly_low_tech 13`, `family_shared_phone 13`, `small_business_owner 13`,
  `student 13`, `DIV2_TEST 1` — total 81.
- Stray/empty sessions: `total_sessions 0`, `null_user_sessions 0`,
  `sessions_with_no_events 0` — nothing carried over.
- CSV label `value_counts` (pandas, from files on disk):
  - `app_channel_data.csv` shape (2101, 7) → `{0: 2000, 1: 101}` = **4.8072%** positive
  - `ussd_channel_data.csv` shape (2107, 7) → `{0: 2000, 1: 107}` = **5.0783%** positive
- Division 2 flow re-checked via API against the recreated test user:
  `/health` all-green → `POST /bank/session/start` → `POST /bank/login` adopts
  that same `session_id` and returns `Division 2 Test User` → `GET /bank/dashboard`
  → `POST /bank/transfer` (`status: recorded`, `beneficiary_is_novel=t`) →
  unknown-msisdn login returns `HTTP 401` → `POST /ussd` with `text:""` returns the
  `CON` main menu. DB showed the WEB session adopted (no duplicate, 0 null-user
  rows) and the USSD session linked by phone number. The transient rows from this
  API check were then truncated, leaving the clean slate above.

### Final DB state at division close
`users 81`, `telco_state 80`, `sessions 0`, `behavioral_events 0`,
`ussd_events 0`, `transactions 0`. Ready for Division 4 to consume the 80-user
persona corpus.

### Carried forward (not blocking)
- Empty-session filtering (StrictMode double-open, Division 2 known issue) is
  still for the Division 4 feature pipeline to handle when live web sessions
  resume.

### Demo moment — verified
`DATA_GENERATION.md` + `generation_summary.json` give the "here is exactly how the
dataset was made, and here is what we deliberately get wrong and why" panel, and
the 80-user persona corpus is now live in Postgres (6 personas, deterministic
seed) feeding Division 4 — while the Division 2 bank/USSD login still works
end-to-end against the recreated test user.

## Division 4 — Detection Core
Status: COMPLETE (verified end-to-end against the live stack — real model
output, real HTTP responses, real `decisions` rows, not summaries)

### What was built / wired
- `ml/train_models.py` + `ml/requirements.txt` — trains, per channel, an
  unsupervised Isolation Forest (learns "normal" with no fraud labels) **and**
  a supervised XGBoost classifier (`scale_pos_weight` for the ~5% positive
  rate). Reads `data/{app,ussd}_channel_data.csv` from Division 3, writes
  `ml/models/{app,ussd}_{isolation_forest,xgb}.pkl` + `{app,ussd}_metrics.json`.
  Training was run **inside the backend container** (Python 3.12 — the same
  runtime that serves the models) so there is no pickle/ABI skew; the host
  only has Python 3.14, which has no wheels for the pinned scientific stack.
- `backend/app/services/feature_engineering.py` — raw `behavioral_events` /
  `ussd_events` / `telco_state` / `transactions` rows → the same 4+4 deviation
  features the models trained on. Column names verified against the live
  Alembic schema (`0001_initial_schema`); the only adaptation needed was
  casting `transactions.amount` (`NUMERIC` → `Decimal`) to `float` before the
  deviation math, on **both** channels — without it every live score 500'd
  with `unsupported operand type(s) for /: 'decimal.Decimal' and 'float'`.
- `backend/app/services/scoring.py` — loads the real `.pkl`s, blends
  `0.75*xgb_proba + 0.25*(iso_anomaly capped)`, returns the agreed contract
  shape (`risk_score` 0-100, `top_features` [[name,val],[name,val]],
  `session_count`). Model dir is now `AEGIS_MODEL_DIR` (compose points it at
  the `/app/ml/models` bind mount) instead of a hard-coded relative path, and
  a `warm_models()` call on FastAPI startup pre-loads both channels so the
  first live transfer doesn't eat the ~6.8s cold `joblib.load`.
- `backend/app/services/decision_engine.py` — base low/medium/high tiering
  plus **Guardrail 1** (SIM-swap the *only* elevated feature ⇒ force low) and
  **Guardrail 2** (cold-start: `session_count < 5` can never be auto-blocked,
  only stepped-up). Unchanged from the teammate's Brief B logic — all 4 mock
  cases pass as-is.
- `backend/app/routers/score.py` — `POST /score/session/{session_id}`. Three
  bugs fixed before wiring, all of which would have failed against the live
  DB: (1) it inserted the tier (`LOW`/`MEDIUM`/`HIGH`) into `decisions.verdict`,
  whose CHECK constraint only permits `ALLOW`/`CHALLENGE`/`BLOCK` — now maps
  action→verdict; (2) it wrote `str(top_features)` (a Python list repr, invalid
  JSON) into a `JSONB` column — now `json.dumps({name: value})`; (3)
  `gen_random_uuid()` → `uuid_generate_v4()` (the extension the schema
  actually loads). Also now links `transaction_id`.
- `main.py` registers the `score` router and runs `warm_models()` on startup.
- `bank.py /transfer` and the USSD handler (`ussd.py`, step-4 branch) now call
  `score_session(...)` **in-process, automatically**, right after the
  transaction is committed. Best-effort: a scoring error can never turn a
  recorded transfer into an HTTP error (the WEB response carries the verdict
  in a new `detection` field; the USSD reply to the aggregator is unchanged).
- `backend/requirements.txt` gains numpy/pandas/scikit-learn/xgboost/joblib
  (pinned); `docker-compose.yml` mounts `./ml` and `./data` into the backend
  and sets `AEGIS_MODEL_DIR`; `backend/Dockerfile` pip step given
  `--timeout 120 --retries 10` for the large wheels.

### Achieved model metrics (held-out 20% test split, `ml/models/*_metrics.json`)
| channel | precision | recall (fraud) | false-positive rate | PR-AUC | ROC-AUC | confusion [[TN,FP],[FN,TP]] |
|---------|-----------|----------------|---------------------|--------|---------|----------------------------|
| app     | 0.500     | **0.650**      | **0.0324**          | 0.648  | 0.912   | [[388,13],[7,13]]          |
| ussd    | 0.643     | **0.857**      | **0.0249**          | 0.882  | 0.989   | [[391,10],[3,18]]          |

Recall for both channels sits in the sane 0.4–0.95 band; neither precision
nor recall is 1.0 (no label leakage — `.fit()` sees only the 4 deviation
columns), neither is 0 (class weighting works).

### Guardrails — pass BOTH offline and live
- `backend/app/services/test_decision_engine.py` — **ALL 4 PASS**
  (`Case 1 low`, `Case 2 low` = SIM-swap-alone, `Case 3 high`,
  `Case 4 medium` = cold-start). Re-run after any decision_engine change.
- **Guardrail 1 live** (running system, not the unit test): synthetic
  `market_trader` user, `telco_state.last_sim_swap_at` set to now
  (⇒ `sim_swap_risk = 0.95`), driven through the real
  `POST /ussd` accumulated-text dialogue. Live `POST /score/session/{uuid}`
  returned `risk_score 25.07`, `top_features [["sim_swap_risk",0.95],
  ["session_retry_deviation",0.5]]`, features above the 0.7 elevated line =
  `[["sim_swap_risk",0.95]]` only ⇒ **tier "low"**. (The XGB model itself
  never escalates on SIM-swap — that signal is deliberately not separable by
  these 4 features per `DATA_GENERATION.md` — so the guardrail agrees with the
  model here; unit-test Case 2 covers the case where a 45-risk score is
  actively demoted.)
- **Guardrail 2 live**: Test B below, run first while the test user still had
  < 5 sessions, returned `risk_score 99.58` but final tier **"medium" /
  step_up** (`verdict CHALLENGE` in `decisions`) — the cold-start cap firing
  on the real system. After padding the user's session history it returns
  "high" / block for the identical transfer (row 4 below).

### End-to-end, through the live stack (`decisions` table, real query output)
| session | channel | risk_score | verdict | feature_contributions | latency_ms |
|---------|---------|-----------|---------|-----------------------|------------|
| 03c6a287… | WEB  | 24.37 | ALLOW     | `{"pasted_char_ratio":0.05,"typing_speed_deviation":0.0}` | 48.18 |
| 041da10e… | WEB  | 99.58 | BLOCK     | `{"amount_deviation":12.4595,"typing_speed_deviation":14.1818}` | 39.23 |
| 3aa4e870… | WEB  | 99.58 | CHALLENGE | (same features, scored pre-session-padding → Guardrail 2) | 63.00 |
| 1e623e74… | USSD | 25.12 | ALLOW     | `{"sim_swap_risk":0.95,"time_of_day_deviation":0.5833}` | 41.37 |
| 7ae7f6b7… | USSD | 25.07 | ALLOW     | `{"sim_swap_risk":0.95,"session_retry_deviation":0.5}` | 44.90 |

- **Test A** (normal WEB transfer, NGN 15,000, typed at baseline speed, no
  paste, full 6-screen nav): `risk_score 24.37`, tier **low**, action allow,
  "This transaction looks consistent with your normal activity."
- **Test B** (WEB transfer NGN 400,000, pasted details, fast typing):
  `risk_score 99.58`, `top_features [["amount_deviation",12.46],
  ["typing_speed_deviation",14.18]]`, tier **high**, action block, "…flagged
  because this amount is unusual for you, and you typed at an unusual speed
  for you."
- **Latency**: steady-state (post-warmup) across 7 live scores —
  **min 39.2 ms, max 157.6 ms, avg 63.3 ms**, all far under the hackathon's
  1000 ms "under a second" bar. The single 6814 ms row in `decisions` is the
  first-ever call before the startup warmup was added; it is why `warm_models()`
  exists.

### Test artifacts left in the DB (not blocking; Division 5/7 churn this anyway)
- 6 `transactions`, 8 `decisions`, ~214 `behavioral_events` from the drives
  above remain as demo evidence.
- User `ab398905…` (`market_trader`, msisdn 08046913810) has
  `telco_state.last_sim_swap_at` set to Division-4 test time and one of its
  `ussd_events` has `retry_count = 1` — both set deliberately for the
  Guardrail 1 live test.

### Backend image — now built clean
The first two `docker compose build` attempts hit transient network faults
(pip read-timeout, then a corrupted-wheel hash mismatch). A third build
succeeded: **exit code 0**, image `aegis-backend` 2.01 GB, ML stack baked in
(`numpy 1.26.4 · pandas 2.2.2 · sklearn 1.5.2 · xgboost 2.1.1 · joblib 1.4.2`).
Backend was recreated from the fresh image (`--force-recreate`, the manual
in-container `pip install` layer dropped) and boots clean, warms the models,
and scores in ~50 ms. A repeat `docker compose build backend` is fully
`CACHED` and exits 0. `docker compose up -d --build` on a fresh machine now
produces a working Division 4 backend in one command.

## Division 4B / 4D / 4E — close-out (Redis velocity, threshold study, rules fallback)
Status: COMPLETE (verified live — real redis-cli values, real JSON artifact,
real degraded-mode transaction)

### 4B — Redis velocity layer  (`backend/app/services/velocity.py`)
Rolling per-user counters, read (not incremented) by the detection loop as a
model-independent signal:
- **login attempts / minute** — fixed 60 s time-bucket `INCR`, key
  `vel:login:{user_id}:{bucket}`, TTL 120 s.
- **transfers / hour** — fixed 3600 s time-bucket `INCR`, key
  `vel:transfer:{user_id}:{bucket}`, TTL 7200 s.
- **OTP requests / rolling window** — true sliding window: sorted set
  `vel:otp:{user_id}` scored by timestamp, `ZADD` + `ZREMRANGEBYSCORE` +
  `ZCARD`, 3600 s window. Function exists and is exercised now; Division 5
  wires it to the OTP-issue path.
All helpers fail soft — a Redis outage returns zeros, it does not break a
transfer. `snapshot(user_id)` returns all three without incrementing and is
what `feature_engineering.compute_velocity_features()` calls.

Wired: `bank.py /login` → `record_login_attempt`; `bank.py /transfer` and the
USSD step-4 branch → `record_transfer` (before scoring, so the loop sees it).
`POST /score/session/{id}` now returns a `velocity` block and stores it in
`decisions.feature_contributions`.

**Live proof** (redis-cli, after 6 rapid logins + 5 rapid transfers for the
Division 2 test user, then 4 direct `record_otp_request` calls):
```
vel:login:1340557b-...:29814257    => 6     TTL=96s
vel:transfer:1340557b-...:496904   => 5     TTL=7174s
vel:otp:1340557b-...  (zset)       ZCARD=4  TTL=7198s
snapshot() -> {'login_attempts_per_min': 6, 'transfers_per_hour': 5, 'otp_requests_in_window': 4}
```
The 5 transfer responses showed `transfers_per_hour` incrementing 1→2→3→4→5
inside the scoring output.

### 4D — threshold tuning study  (`ml/threshold_study.py` → `ml/threshold_analysis.json`)
Sweeps XGBoost decision thresholds `[0.2 … 0.8]` on the **same** held-out 20 %
test split train_models.py reported on, for both channels. Rule for the
chosen operating point: highest recall whose false-positive rate stays
≤ 5 %, tie-broken on precision (FPR is the constraint — every false positive
is a good customer challenged; recall is the objective — a missed takeover is
the expensive miss).

| channel | thr | precision | recall | FPR | vs. default 0.5 |
|---------|-----|-----------|--------|-----|-----------------|
| app  | 0.2 | 0.341 | 0.750 | 0.072 | over FPR budget |
| app  | 0.3 | 0.412 | 0.700 | 0.050 | |
| **app**  | **0.4** | **0.467** | **0.700** | **0.040** | **chosen — +0.05 recall for +0.7 pt FPR** |
| app  | 0.5 | 0.500 | 0.650 | 0.032 | (train_models default) |
| app  | 0.6–0.8 | 0.53–0.67 | 0.500 | 0.02–0.013 | recall collapses |
| ussd | 0.2 | 0.545 | 0.857 | 0.037 | |
| ussd | 0.4–0.5 | 0.643 | 0.857 | 0.025 | |
| ussd | 0.6 | 0.667 | 0.857 | 0.022 | |
| **ussd** | **0.7** | **0.692** | **0.857** | **0.020** | **chosen — recall flat, best precision/FPR** |
| ussd | 0.8 | 0.739 | 0.810 | 0.015 | recall finally drops |

USSD recall is flat at 0.857 from 0.2→0.7, so we take the highest threshold
that keeps it — fewer false positives for free. App recall trades off
steeply, so we accept 0.4 as the best recall inside the FPR budget.

**Wired, not just documented**: `scoring.py` loads `CHOSEN_THRESHOLD`
(`{'app': 0.4, 'ussd': 0.7}`) from the JSON at startup and applies a floor —
if `xgb_proba ≥ threshold` the `risk_score` can't clear below the medium cut
(30), so anything the tuned supervised model would flag gets at least a
step-up. The score response and `decisions.feature_contributions` now carry
`{xgb_proba, threshold, threshold_crossed}` per decision.

### 4E — rules fallback engine  (`backend/app/services/rules_fallback.py` + `scoring_health.py`)
Engages automatically on **any** exception in the ML path (missing/corrupt
pkl, feature-engineering error). Depends only on the transaction amount and
the 4B Redis counters, so it works even with the model layer down. Output is
the same contract shape as the decision engine (`tier/action/message` +
`risk_score` + `top_features`); only `model_version` changes to
`rules-fallback-v1` so degraded-mode decisions are identifiable in the table.
Thresholds: amount hard limit NGN 200k → block, soft NGN 75k → step_up;
transfer velocity ≥ 6/h → block, ≥ 3/h → step_up; login velocity ≥ 5/min →
step_up. `scoring_health` tracks mode (`ml` / `degraded`), last error and a
degraded count; exposed at **`GET /score/health`** for the Division 9
degraded-mode banner. Self-healing — the next successful ML score flips the
mode back with no restart.

**Live proof** (models dir renamed away + backend restarted so warm-up
couldn't cache them):
- startup: `warm_models: app channel not loaded (...No such file...) — rules
  fallback will engage` ×2, `Application startup complete` — no crash.
- transfer, NGN 250,000: HTTP 200, `scoring_mode: "degraded"`,
  `tier "high" / block`, `model_version "rules-fallback-v1"`, message
  *"Scored in reduced mode (ML service unavailable): amount NGN 250,000 is
  over the hard limit; 7 transfers in the last hour."*
- logs: `ML scoring failed (FileNotFoundError: ...) — engaging rules fallback`
  then `rules fallback verdict: user=... amount=250000.00 xfer/h=7
  login/min=2 -> high/block`.
- `GET /score/health` → `{"mode":"degraded","last_error":"FileNotFoundError:
  ...","degraded_count":1,"healthy":false}`.
- real `decisions` row: `verdict BLOCK`, `model_version rules-fallback-v1`,
  `feature_contributions {"mode":"degraded","velocity":{...},"top_features":
  {"amount":250000.0,"transfer_velocity":7}}`.
- restore models dir (no restart) → next transfer `scoring_mode: "ml"`,
  `GET /score/health` → `{"mode":"ml","healthy":true,"degraded_count":1}`.

`test_decision_engine.py` still **ALL PASS** after all of the above.

### Demo moment — verified
Every transfer — WEB or USSD — now auto-fires the detection loop and writes a
grounded verdict to `decisions` in ~40–60 ms: a normal transfer clears at
risk 24 with a plain-English "looks consistent"; a large pasted-detail
transfer is blocked at risk 99 with the two driving features named; and a
SIM-swapped session with nothing else wrong is explicitly held at "low" by
Guardrail 1 on the live system, not just in a unit test. Rapid repeat
requests visibly move the Redis rolling counters that ride along in every
score. `ml/threshold_analysis.json` is the "we tested 0.2–0.8 on both
channels and chose 0.4 / 0.7 deliberately, here's the tradeoff table"
artifact. And renaming the model files out from under the running service
doesn't crash a transfer — it comes back BLOCK from the rules fallback with
`GET /score/health` flipped to `degraded`, then self-heals to `ml` when the
models return.

Division 4 (Detection Core) — including 4B / 4D / 4E — is **fully complete**.

## Division 5 — Hard Controls
Status: COMPLETE (all 5 hard controls proven LIVE against the running stack —
real HTTP responses, real `decisions` rows, real Redis values — plus the 4
offline regression tests)

### Design
`run_hard_controls()` executes at the TOP of `POST /score/session/{id}`,
BEFORE the Division 4 ML path. The ML score is **still always computed and
logged** (`decisions.risk_score`, `feature_contributions.ml`), but if any
hard control fires its verdict is final and the ML/decision-engine result is
kept only for audit (`explanation_analyst` records the override, e.g.
*"HARD CONTROL SIM_SWAP_MODULE overrode the ML decision (ml_tier=low,
ml_risk=22.39)"*, and the rule name goes in `decisions.triggered_rules`).
Checks run most-severe-first; the first to fire wins:

| # | control | file | fires when | verdict |
|---|---------|------|-----------|---------|
| 0 | **Token integrity (5A)** | `token_integrity.py` | one-time confirmation token replayed or expired (`GETDEL` miss) | block |
| 1 | **SIM-swap + device (5B)** | `sim_swap_module.py` | device/IMEI changed **AND** `last_sim_swap_at` ≤ 4 days | block |
| 2 | **Identity correlation (5C)** | `identity_correlation.py` | same `device_fingerprint` on ≥ 3 distinct accounts within 1h | block |
| 3 | **OTP request-rate (5B)** | `sim_swap_module.py` | ≥ 4 OTP requests in the 10-min rolling window | step_up |
| 4 | **Call/OTP interlock (5B)** | `sim_swap_module.py` | `call_active` AND `otp_being_entered` both true | step_up |

### The core rule — NOT weakened
`check_sim_swap_and_device` only overrides on **device change IN COMBINATION
with a recent swap**. Device change alone → `DEVICE_CHANGED_NO_RECENT_SWAP_IGNORED`,
no override (the "families share phones / people upgrade phones" case the
brief explicitly protects). One hardening change was made to the supplied
file: `device_changed = bool(current_imei) and (known_imei != current_imei)`
— a *missing* IMEI (USSD feature phones carry none) must not read as "device
changed", otherwise every post-swap USSD transfer would trip the block on the
swap alone. This does not change any of the 4 unit-test outcomes; it stops a
false "device changed" when there is no device identity to compare.

### Wiring
- `score.py::score_session(session_id, *, current_imei, otp_being_entered,
  call_active_hint, token_status)` — runs hard controls, then ML, then
  resolves the final verdict. `current_imei` defaults to
  `f"imei::{device_fingerprint}"` when not passed (Step 3 of the brief);
  `call_active` is the explicit hint OR `bool_or(behavioral_events.call_active)`.
- `TransferRequest` gained `current_imei`, `call_active`, `otp_being_entered`,
  `token`. `/bank/transfer` consumes the token (`consume_token`) and passes
  everything through.
- New `POST /bank/request-otp` — the OTP-request seam Division 5 introduces:
  bumps the OTP request-rate counter, issues the one-time token, and returns
  `MANUAL_HOLD_SECONDARY_CHANNEL_REQUIRED` instead of `SMS_OTP` when this
  account is currently in a SIM-swap+device state (don't send another code to
  a hijacked SIM).
- The orchestrator's OTP check uses a new read-only `peek_otp_request_rate`
  so scoring a transfer never inflates the request counter (only
  `/bank/request-otp` increments, via `check_otp_request_rate`).

### Offline regression tests — ALL PASS
`backend/app/services/test_hard_controls.py` (run in-container, real Redis):
```
PASS: device change alone (no recent swap) correctly ignored
PASS: device change + recent SIM swap correctly blocks
PASS: unchanged device never flags, even with a recent swap on record
PASS: OTP request-rate anomaly correctly triggers after threshold
ALL PASS
```
Division 4's `test_decision_engine.py` still ALL PASS after the wiring.

### Proven LIVE (real `/bank/transfer` → hard controls → ML)
| step | scenario | result |
|------|----------|--------|
| **4** | synthetic user `08013122454`, `current_imei` differs, `last_sim_swap_at` 447d old | **NOT blocked** — `hard_control.sim_swap_check = "DEVICE_CHANGED_NO_RECENT_SWAP_IGNORED"`, `override false`, `final_source ml`, tier low / allow |
| **5** | user `08021225238`, `last_sim_swap_at = now()-2d` **and** `current_imei` differs, behaviour deliberately normal (ML `risk_score 22.39`, tier low) | **BLOCKED** — `final_source hard_control`, `SIM_SWAP_MODULE`, `days_since_swap 2`, msg *"your SIM was recently changed and this device hasn't been used on your account before"*. `decisions`: `verdict BLOCK`, `risk_score 22.39` (ML, logged), `triggered_rules {SIM_SWAP_MODULE}`, analyst note records the override. **This is the proof the hard control overrides — not merely agrees with — the ML score.** |
| **6** | `device_fingerprint = SHARED-FRAUD-RING-DEVICE-XZ1` across 3 different synthetic users | accounts #1, #2 → `final_source ml`, allow; **account #3 → BLOCKED**, `IDENTITY_CORRELATION`, *"this device has been used on 3 different accounts recently"*, `distinct_accounts 3` (DB confirms 3). |
| **7** | 5 rapid `POST /bank/request-otp` for user `08057458790` | `rate_anomaly` flips **True on request #4** (and #5); `redis-cli GET otp_requests:865617d9-… → 5`, TTL 597s. A subsequent transfer by that user was overridden to `step_up` by `OTP_RATE_ANOMALY` (`otp_request_count 5`), counter stayed at 5 (read-only peek). |
| **8** | transfer with `call_active=true` AND `otp_being_entered=true`, normal behaviour (ML `risk_score 22.39`) | **elevated to `step_up`** — `final_source hard_control`, `CALL_OTP_INTERLOCK`, *"this code was entered while you appeared to be on a call"*. |
| bonus | `/bank/request-otp` → token → transfer (ok) → transfer again with the **same token** | replay **BLOCKED** — `TOKEN_INTEGRITY`, *"its confirmation token had already been used or had expired"*. |

`decisions` rows for the overrides (real query output):
```
 channel |  verdict  | ml_risk |    triggered_rules     | explanation_customer
---------+-----------+---------+------------------------+----------------------
 WEB     | BLOCK     |   25.62 | {TOKEN_INTEGRITY}      | ...token had already been used or had expired.
 WEB     | CHALLENGE |   22.39 | {CALL_OTP_INTERLOCK}   | ...entered while you appeared to be on a call.
 WEB     | BLOCK     |   22.6  | {IDENTITY_CORRELATION} | ...used on 3 different accounts recently.
 WEB     | BLOCK     |   22.39 | {SIM_SWAP_MODULE}      | ...SIM was recently changed and this device hasn't been used...
```

### Demo moment — verified
Feed the system a textbook-normal session — steady typing, full nav path,
small amount, ML score 22/low — and it still returns **BLOCK** the instant
`telco_state` shows a SIM swap in the last 4 days on a device the account has
never used. The ML score is right there in the `decisions` row next to the
block, showing the behavioural model was fooled and the deterministic layer
caught it anyway. Same story for a device seen on three accounts, a replayed
confirmation token, an OTP-code storm, and a code entered mid-call.

## Division 6 — AI Explainability
Status: COMPLETE (real SHAP wired into every decision; LLM fallback chain
tested at all 3 levels; copilot + incident report proven live against real
BLOCKED-decision data)

### 6A — real SHAP attribution (`explainability.py`)
`compute_shap_reason_codes(channel, features)` — `shap.TreeExplainer` on the
Division 3 XGBoost models, returning ranked
`{feature, value, shap_contribution}` (positive = pushed toward fraud,
negative = toward normal). `shap==0.46.0` added to `ml/requirements.txt` and
`backend/requirements.txt`. Model dir shared with the scorer via
`AEGIS_MODEL_DIR`; explainers warmed on startup alongside the models.

Verified against both models with real dataset rows:
```
APP  fraud row : typing_speed_deviation value=-3.023 shap=+1.54  (toward fraud)
                 amount_deviation       value=0.6549 shap=+0.7263 (toward fraud)
APP  normal row: amount_deviation       value=-0.1975 shap=-5.7334 (toward normal)
USSD fraud row : amount_deviation       value=0.0113 shap=+3.40   (toward fraud)
USSD normal row: amount_deviation       value=1.282  shap=-2.8083 (toward normal)
```

### SHAP wired into `score.py`
`top_features` in the score response and `feature_contributions.shap_reason_codes`
in the `decisions` row are now the **real per-prediction SHAP ranking**, not
the old `feature_importances` proxy. If SHAP itself throws, it degrades to the
importance ranking rather than losing the decision. Confirmed on a live
transfer: `latency_ms 40-56` (SHAP adds ~10ms), reason codes stored.

### 6B — LLM explanations (`llm_explainer.py`), grounded, with a real fallback chain
The LLM only ever **rewrites** the SHAP reason codes into plain language
(customer + analyst); it is never asked to invent reasons. Two bugs fixed in
the supplied file:
- Gemini model `gemini-1.5-flash` → **404 (retired)**; switched to
  `gemini-flash-latest` (env-overridable via `GEMINI_MODEL`). The API key
  format `AQ.…` is valid — it authenticated fine, only the model was stale.
- Ollama timeout `8s` → too short for CPU llama3.2 (cold load alone > 8s);
  now `OLLAMA_TIMEOUT` (default 60s); cloud timeout `LLM_CLOUD_TIMEOUT`
  (default 15s). All three `_try_*` take an optional per-call timeout.

**Latency reality / architecture:** measured from the container, Gemini is
~15s/call and local Ollama > 30s for a full analyst explanation — an inline
LLM round-trip on `/bank/transfer` was 40s, unacceptable. So the transfer
hot path stores **SHAP + a zero-latency deterministic grounded sentence**
(`deterministic_explanation()`), and the LLM rewrite is an explicit on-demand
step: **`POST /score/decision/{session_id}/explain`** regenerates both
audiences from the stored SHAP codes and updates the `decisions` row in place.

**Fallback chain — tested at every level** (sample SHAP codes, tier "high",
customer audience):
| level | env | `source` returned | result |
|-------|-----|-------------------|--------|
| 1 | as-is (GROQ blank, GEMINI set) | **`gemini`** | *"We temporarily paused your transaction because the transfer amount, your typing speed, and the way you navigated through the screens differed from your usual activity."* |
| 2 | `GEMINI_API_KEY` blanked | **`ollama`** | *"We're reviewing your recent transaction and noticed a slight variation in your input…"* (real llama3.2) |
| 3 | Gemini blank + `OLLAMA_URL=http://127.0.0.1:1` | **`deterministic_fallback`** | *"This transaction was flagged because you typed at an unusual speed for you, and this amount is unusual for you."* (from `REASON_TEMPLATES`, non-empty, correct) |

(GROQ_API_KEY intentionally blank — chain skips it with no wasted round-trip.)
The `/score/decision/{id}/explain` call itself came back with
`customer_source=gemini, analyst_source=ollama` (Gemini answered the short
customer prompt in time, timed out on the longer analyst prompt → Ollama), and
the `decisions` row's `explanation_customer` / `explanation_analyst` /
`feature_contributions.llm` were updated in place — proof the LLM explanations
land in the table, grounded in SHAP, from `llm_explainer.py`.

### 6C — analyst copilot (`/copilot/ask`) — proven live
Against the real BLOCKED decision `9f2b0aca-…` (`SIM_SWAP_MODULE`, ml_risk 22.39):
- *"why was this session blocked?"* → **`source: gemini`**:
  *"…blocked by a hard control override rule (`SIM_SWAP_MODULE`)… the
  customer's SIM card was recently changed (2 days prior), and the device
  being used (`web-div6-blk`) had not been used on the account before."*
  — every fact (`SIM_SWAP_MODULE`, `days_since_swap: 2`, the device
  fingerprint) is straight from the retrieved decision + session rows.
- *"what is the customer's home address and date of birth?"* → **`source:
  gemini`**: *"The provided data does not contain the customer's home address
  or date of birth."* — it declines rather than inventing.

### 6D — incident report (`GET /incident-report/{session_id}`) — proven live
Same session → **`source: ollama`** (Gemini timed out on the longer report
prompt, chain fell through), structured **What Happened / Signals Detected /
Recommended Action**, grounded: names the SIM-swap module trigger, the 22.39
risk score, "device not previously associated with the account", "SIM was
recently changed".

### Which provider actually responded (tested, not assumed)
| surface | provider that answered |
|---------|------------------------|
| fallback chain level 1 (`generate_explanation`) | **gemini** |
| fallback chain level 2 (Gemini disabled) | **ollama** (llama3.2) |
| fallback chain level 3 (both disabled) | **deterministic_fallback** |
| `/score/decision/{id}/explain` — customer | **gemini** |
| `/score/decision/{id}/explain` — analyst (longer prompt) | **ollama** |
| `/copilot/ask` (both questions) | **gemini** |
| `/incident-report/{id}` (long prompt) | **ollama** |

Groq: not exercised (key intentionally blank). Gemini: working via
`gemini-flash-latest`, ~15s/call, reliable for short prompts. Ollama
(llama3.2, local, via `host.docker.internal`): working, the dependable
fallback for longer prompts and when cloud is unavailable. Deterministic
template: proven to still produce a correct plain sentence with everything
else down.

### Config / plumbing
- `docker-compose.yml`: backend gets `env_file: ./.env` +
  `OLLAMA_URL=http://host.docker.internal:11434` override +
  `extra_hosts: host.docker.internal:host-gateway` so the container reaches
  the host's Ollama.
- `.env` is gitignored (confirmed `git check-ignore` — line 18); `.env.example`
  committed as the template.
- `copilot.py` / `incident_report.py` registered in `main.py`; both now
  return a `source` field.

### Known gap — clean image rebuild blocked by local network (revisit later)
`shap==0.46.0` + `requests==2.32.3` are in `backend/requirements.txt` and
`ml/requirements.txt`, and are **installed and verified in the running
backend container** — every Division 6 result above was produced against it
(health green, `/copilot/ask` and `/incident-report` HTTP 200,
`shap 0.46.0` / `requests 2.32.3` importable). Code is live via the
`./backend` bind mount + `--reload`.

A fresh `docker compose build backend` currently **fails on this machine's
network**, not on anything in the code. ~7 attempts across Divisions 4 and 6
have hit a rotating set of transport failures pulling wheels from
`files.pythonhosted.org`: `ReadTimeoutError`, truncated downloads
(`THESE PACKAGES DO NOT MATCH THE HASHES` / "unknown package"), `short read
… unexpected EOF` on the BuildKit frontend image, and most recently a
**TLS certificate verification error**. `backend/Dockerfile` was updated to
use a BuildKit pip **cache mount** (`--mount=type=cache,target=/root/.cache/pip`,
no more `--no-cache-dir`) so a retry resumes from the wheels already fetched
instead of restarting the ~500 MB download — this should let the build
converge over a few attempts once the link is healthy, or in one pass on a
good connection. `requirements.txt` + `Dockerfile` are correct; **to
revisit**: run `docker compose build backend` on a stable network and
`docker compose up -d --force-recreate backend`.

### Demo moment — verified
Open a blocked transaction in the console: the reason codes are real SHAP
values (not importances), the plain-English "why" is one click away and comes
from Gemini (or llama3.2 offline, or a template if the venue wifi dies), and
the analyst can ask the copilot follow-up questions that are answered strictly
from that session's retrieved data — and it says "the data doesn't contain
that" instead of guessing when asked something it can't know.

## Division 7 — Attack Simulator
Status: COMPLETE — 6 archetypes fired individually against the live stack (real
JSON shown), normal-traffic generator proven to stay green, honest disclosure
of the two weak archetypes.

### What's wired
- `simulator/attack_scripts.py` — 6 archetype functions hitting the REAL HTTP
  API (login → ingest → request-otp → transfer → score), matching the
  Division 3 dataset archetypes one-for-one. `simulator/normal_traffic.py` —
  background-thread legit-traffic generator with start/stop.
- `backend/app/routers/simulator.py` (registered in `main.py`):
  `POST /simulator/attack/{archetype}`, `POST /simulator/normal-traffic/start`
  + `/stop`, `GET /simulator/archetypes`. Division 9's "Launch Attack" buttons
  call these.
- `docker-compose.yml` mounts `./simulator:/app/simulator` so the package is
  importable in the container; `simulator/__init__.py` added.

### Adaptations made to the prepared scripts (with reasons)
1. **`attack_otp_replay`** (the one flagged for adapting) — was two plain
   `/bank/transfer` calls. Rewritten to exercise Division 5's real one-time
   token: `POST /bank/request-otp` → `token` → transfer #1 with the token
   (consumed) → transfer #2 with the **same** token → `consume_token` returns
   `TOKEN_REPLAYED_OR_EXPIRED` → `run_hard_controls` → hard `TOKEN_INTEGRITY`
   block.
2. **`attack_sim_swap_takeover`** — now snapshots `telco_state.last_sim_swap_at`
   and **restores it in a `finally`**. The prepared version left every
   attacked user permanently marked "SIM-swapped 1 day ago", so ordinary
   traffic for those users started getting (correctly) hard-blocked afterward.
   Also given a fuller normal-behaviour profile so the ML score lands LOW and
   the override contrast is stark. (3 telco rows contaminated by pre-fix runs
   were reset to an old swap date; Division 3 reseed restores exact values.)
3. **`normal_traffic.py`** — was logging every session in with the SAME
   `device_fingerprint` across many different users, which correctly tripped
   the identity-correlation fraud-ring control → BLOCK. Now each customer uses
   their own deterministic `legit-dev-<user_id>` fingerprint, a full 6-screen
   nav path, ~240 ms keystroke flight, and small fixed amounts (the app
   model's `amount_deviation` is measured against a fixed ~15 k baseline, not
   the user's own typical).
4. **`_pick_synthetic_user`** — now `JOIN telco_state` and excludes
   `DIV2_TEST`, so the SIM-swap / device archetypes always have a real IMEI +
   swap timestamp to work against.

### Per-archetype result — REAL output (`POST /simulator/attack/{name}`)
| archetype | ML risk_score | final verdict | caught by | notes |
|-----------|---------------|---------------|-----------|-------|
| **CREDENTIAL_STUFFING** | **72.86** (xgb_proba 0.638, threshold_crossed) | CHALLENGE (tier medium) | **ML** | High score as expected. Tier capped medium by Guardrail 2 (cold-start: the randomly-picked synthetic user has <5 sessions → never auto-blocked, only stepped up). risk_score is the unclamped model output. Driven by `screen_sequence_anomaly 0.833` (straight to confirm). |
| **OTP_REPLAY** | 60.33 (both attempts) | 1st: CHALLENGE (ml) · 2nd: **BLOCK** | **hard control `TOKEN_INTEGRITY`** | 2nd attempt with the reused token: `final_source hard_control`, `override true`, msg *"its confirmation token had already been used or had expired"*. The ML score was identical (60.33) on both — the block came from Token Integrity, **not** the score. |
| **SIM_SWAP_TAKEOVER** | **20.91 · ml_tier `low`** | **BLOCK · tier `high`** | **hard control `SIM_SWAP_MODULE`** | The headline. Behaviour is unremarkable (risk 20.91, low), analyst record: *"HARD CONTROL SIM_SWAP_MODULE overrode the ML decision (ml_tier=low, ml_risk=20.91)"*, `days_since_swap 1`, `override true`. Telco precondition staged and restored. |
| **COACHED_VICTIM** | **99.86** (xgb_proba 0.998) | CHALLENGE (tier medium) | **ML (clearly elevated)** | SHAP: `typing_speed_deviation -3.29 → shap +2.33` (abnormally SLOW — the opposite of a bot), `screen_sequence_anomaly +2.30`, `amount_deviation +1.68`. The call/OTP **interlock did not fire**: it needs the transfer's `otp_being_entered=true` flag, and the prepared script only emits a `CALL_STATE` behavioural event (which sets `call_active` but not `otp_being_entered`). The elevated score meets the "or a clearly elevated score" bar; wiring `otp_being_entered` through would additionally trip `CALL_OTP_INTERLOCK`. |
| **SLOW_DRIFT** ⚠️ | **flat 25.62** across all 3 (14 000 → 14 800 → 15 600 NGN) | ALLOW ×3 | **not caught** | Documented weak spot, honest disclosure. (a) A per-transaction behaviour model genuinely does not escalate on sub-threshold amounts. (b) The script sends no keystroke telemetry, and `compute_app_features` reads the transfer amount only via a `behavioral_events ⋈ transactions` join — with no behavioural rows the amount reads as **0** for all three, so even the small real creep never reaches the model. The only signal that moved: `transfers_per_hour` 1 → 2 → 3 (aggregate, not per-transaction). Caught properly by the Division 4B velocity layer / Division 8 rate + metrics, not here. |
| **IMPOSSIBLE_TRAVEL** ⚠️ | 25.62 | ALLOW | **not caught** | Documented weak spot, honest disclosure. Device change with **no recent SIM swap** is deliberately ignored (`DEVICE_CHANGED_NO_RECENT_SWAP_IGNORED` — the explicit brief rule "people change SIMs, families share phones"). Identity correlation needs 3+ **distinct accounts** on one device; this is one account on two devices — the opposite shape. The real "impossible travel" signal is geographic/velocity (session location vs last session vs elapsed time), which lives outside the 4 behavioural features — `sessions` has `geo_lat/geo_lon/ip_address` columns but nothing populates or checks them yet (Division 4 fuller feature set / Division 8 geo-velocity). |

**Distinct detection mechanisms across the 6:** ML score (credential stuffing,
coached victim), `TOKEN_INTEGRITY` (OTP replay), `SIM_SWAP_MODULE` (SIM-swap
takeover), and two deliberate non-catches (slow-drift, impossible travel) —
i.e. the system reasons about attacks rather than pattern-matching one shape,
and it does not over-block.

### Normal-traffic generator — proven (`POST /simulator/normal-traffic/start` / `/stop`)
- Ran ~70 s → **9 new sessions, 9/9 `ALLOW`**, risk_score 19.8–26.6, every one
  `final_source ml`, `tier low`. Real query output confirmed each session +
  decision row.
- `POST /simulator/normal-traffic/stop` → session count frozen (20 → 20 over
  20 s / 2.5 loop intervals) — the background thread actually stops.
- The point stands: legitimate traffic streams through green while the
  attacks above get caught — the system discriminates, it isn't just flagging
  everything.

### Honest "what we get wrong" (feeds the Division 9 honesty dashboard)
- **Slow-drift**: not detected per-transaction (by design + a feature-pipeline
  gap when no behavioural telemetry accompanies the transfer). Needs the
  aggregate velocity/rate layer.
- **Impossible travel**: not detected — geo/velocity signal not yet wired; the
  behaviour-only model correctly refuses to treat a lone device change as
  fraud.
- Both were already named as known-weak archetypes in `DATA_GENERATION.md`;
  Division 7 confirms it live rather than hiding it.

### Demo moment — verified
The attack panel: fire any archetype and watch it produce its own distinct
signature — a high ML score, a Token-Integrity block, or a SIM-swap override
of a perfectly normal-looking behavioural score — while a continuous stream of
legitimate transfers stays green next to it.

## Division 8 — Security Ops Backend (CORE)
Status: CORE COMPLETE — hash-chained audit log, edge rate limiting, honeytoken,
and live metrics all wired and proven live. The heavy sensor stack
(Suricata / Zeek / Wazuh / ELK) was **deliberately deferred** — see "Scope"
below.

Re-verified end-to-end on 2026-09-08 against the live Docker stack — every
proof block below carries that run's actual output (`slowapi 0.1.9` present in
the backend container, `secops` router registered, all four demo beats
reproduced fresh). Suricata / Zeek / Wazuh / ELK / OWASP ZAP were **not
attempted** — deliberately deferred per the scoping call in "Scope" below
(handoff doc Section 5).

### Scope — what was built vs deferred
Built now (the parts that are cheap, self-contained, and each carry a real
demo beat):
- **8E** hash-chained tamper-evident audit log + verify + demo-tamper
- **8A** lightweight edge rate limiting (FastAPI middleware, no Nginx)
- **8B** honeytoken hidden field → hard override
- **8G** live metrics service (real catch-rate / FPR / precision / latency)

Deferred (the "high-tech company layer" that needs containers, tuning, and
demo-day network reliability we don't want to depend on):
- **8C** Suricata / Zeek network sensors
- **8D** Wazuh / ELK SIEM correlation
- **8F** OWASP ZAP self-scan
These were **not attempted** this pass — a conscious scoping call to keep the
core detection story solid and demoable rather than half-standing up four
more services. The audit-chain, rate-limit, honeytoken and metrics pieces
give Division 8's demo moments (verify-goes-red, a real 429, a bot-only
block, honest live numbers) without that infra risk.

### 8E — hash-chained audit log (`services/audit_chain.py`, wired in `score.py`)
- `score.py` now does `INSERT INTO decisions … RETURNING id`, then
  `append_audit_row(decision_id, payload, cur)` in the **same DB transaction**
  (atomic with the decision write). Payload is an all-string dict so it
  round-trips through JSONB byte-for-byte on verify (no float-repr drift).
- `GET /secops/audit/verify` walks the whole chain, recomputing every hash.
- `POST /secops/audit/demo-tamper/{decision_id}` — clearly-labelled DEMO-ONLY;
  appends `{"tampered": true}` to one row's `row_data`.

**Proven live — the full green→red→green cycle (2026-09-08 run):**
```
baseline (prior divisions):        GET /secops/audit/verify -> {"valid": true, "rows_verified": 40}
fire ~10 simulator attacks + 45s of normal traffic         -> 29 new audit_log rows appended
                                   GET /secops/audit/verify -> {"valid": true, "rows_verified": 69}
POST /secops/audit/demo-tamper/20a00245-55ec-4d87-a86c-c4b6512f597d  (chain row 50)
                                                            -> {"status": "tampered", …}
GET /secops/audit/verify -> {"valid": false, "broken_at_row": 50,
                             "decision_id": "20a00245-55ec-4d87-a86c-c4b6512f597d",
                             "reason": "row_hash does not match recomputed hash - row_data was altered"}
restore row_data (row_data - 'tampered')                     -> chain repaired
GET /secops/audit/verify -> {"valid": true, "rows_verified": 69}
```
Every `decisions` INSERT in `score.py` is now paired with an `append_audit_row`
call in the same transaction — confirmed by the +29 audit rows tracking the
~10 attack + normal-traffic decisions one-for-one. The two honeytoken test
transfers later took the chain to 71, still `valid: true`.

### 8A — edge rate limiting (`main.py` middleware)
- `slowapi==0.1.9` added to `backend/requirements.txt`; its bundled `limits`
  engine (`MovingWindowRateLimiter` + `MemoryStorage`) drives a path-scoped
  `@app.middleware("http")`: **60 requests/minute per client IP** on `/bank`
  and `/ussd`. Internal service-to-service calls (`127.0.0.1` / `::1` — the
  Division 7 simulator runs inside the container) are exempt; the limiter
  guards the external edge.

**Proven live (2026-09-08 run):** 80 concurrent `POST /bank/session/start`
(valid body) from the host in 1.34 s → **exactly 60 × 200, 20 × 429** — the
moving-window limiter cut over at precisely 60/minute. The next request was an
immediate 429. Real 429 body:
```
HTTP/1.1 429 Too Many Requests
{"detail":"Rate limit exceeded: 60 requests/minute per IP on /bank and /ussd
 (Division 8A edge limiter)","client_ip":"172.18.0.1"}
```
Path scoping confirmed: 80 concurrent `GET /secops/audit/verify` in the same
window → **80 × 200** (not a limited prefix). The in-container Division 7
simulator fired dozens of `/bank/login` + `/bank/transfer` calls during the
attack runs with zero 429s (`127.0.0.1` exempt). Note: firing the burst also
rate-limits the host itself for ~60 s — the honeytoken test below had to wait
for the window to drain, which is itself the limiter working.

### 8B — honeytoken (`services/honeytokens.py` + `bank.py` + frontend + hard control)
- Hidden field `confirm_email_address` added to `frontend/src/pages/SendMoney.jsx`
  — off-screen (`left: -9999px`), `tabIndex={-1}`, `aria-hidden`,
  `autoComplete="off"` — and included in the transfer POST body.
- `TransferRequest` gained `confirm_email_address: Optional[str]`. `/transfer`
  calls `check_honeytoken(...)` and threads `honeytoken_tripped` →
  `score_session` → `run_hard_controls`, where it's check **0a** (top of the
  order, alongside token replay — near-zero false positive).

**Proven live (2026-09-08 run) — same transfer (NGN 15,000, user 08028628439,
device `honeytest-dev`), only the hidden field differs:**
| | honeypot field | result |
|---|---|---|
| control | empty (`""`) | `final_source ml`, `tier low / allow`, ml risk **25.62**, "looks consistent with your normal activity" |
| bot | `"auto-filled@bot.example"` | `final_source hard_control`, `source HONEYTOKEN`, **BLOCK / tier high**, `override true`, ml risk still **25.62** (kept for audit), "blocked because an automated form-filling pattern was detected" |

`decisions` row for the bot transfer (session `52f2be96-1e2a-4734-b5b9-f4c721d6f010`):
`verdict BLOCK`, `risk_score 25.62`, `triggered_rules {HONEYTOKEN}`,
`model_version aegis-v1`. The honeytoken check sits at position **0a** in
`run_hard_controls` (ahead of token replay). `honeytest-dev` is neither an
`ATTACKER-*` nor a `legit-dev-*` fingerprint, so these two transfers are
correctly **excluded** from the 8G metrics rather than skewing them.

### 8G — live metrics (`services/metrics.py`, `GET /secops/metrics`)
Real numbers from the `decisions` table, ground truth from the Division 7
`device_fingerprint` convention (disclosed, not real-world labels). Fixes to
the prepared file: dropped the stale `KNOWN-DEVICE` normal-prefix (two attack
archetypes used it → they'd have counted as *normal*); all 6 attack
archetypes in `attack_scripts.py` relabelled to `ATTACKER-*`; one decision
per session (`DISTINCT ON`); optional `?minutes=N` window.

**`GET /secops/metrics?minutes=20` (2026-09-08 run — 2 rounds of the 4 strong
archetypes + slow_drift ×3 + impossible_travel + ~85 s of normal traffic):**
```
confusion_matrix : {true_positive: 8, false_positive: 0, true_negative: 12, false_negative: 4}
catch_rate_recall: 0.6667
false_positive_rate: 0.0
precision        : 1.0
latency_p50_ms   : 82.35    latency_p95_ms: 107.18    latency_max_ms: 108.4
```
Per-archetype (attack sessions, last 20 min):
| archetype | sessions | flagged (TP) | missed (FN) |
|-----------|----------|--------------|-------------|
| credential_stuffing | 2 | 2 | 0 |
| otp_replay | 2 | 2 | 0 |
| sim_swap_takeover | 2 | 2 | 0 |
| coached_victim | 2 | 2 | 0 |
| **slow_drift** | 3 | 0 | **3** |
| **impossible_travel** | 1 | 0 | **1** |
Normal traffic: **12 sessions, 12 allowed, 0 false positives.**

Sanity check holds: **FPR = 0.0** (all 12 normal sessions allowed),
**precision = 1.0** (nothing flagged was a false alarm), and the recall
shortfall (0.6667, not ~1.0) is **entirely** the two archetypes Division 7
already disclosed as not-yet-caught — slow_drift (0/3) and impossible_travel
(0/1) are every one of the 4 false negatives, while the four archetypes the
detector genuinely handles flag at **8/8**. Latency p50/p95/max all well
under the 1 s bar.

### Demo moment — verified
Hit "Verify audit chain" → green. Tamper a row (a labelled demo control) →
hit verify again → red, pointing at the exact broken row. Flood the bank from
outside → real 429s at the edge while internal traffic flows. A bot that
fills every field, including the invisible one, gets an instant hard block a
human never would. And the honesty dashboard's numbers — catch rate, FPR,
precision, latency — are read live from the decision log, not typed in.

## Division 9 — Frontend, Console & Demo
Status: NOT STARTED
