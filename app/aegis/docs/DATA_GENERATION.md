# Aegis — Synthetic Data Generation Methodology

This document exists because the hackathon brief explicitly requires it:
*"A synthetic dataset of user sessions and transactions, including normal
users and attackers. Say clearly how you generated it."* This is graded, not
a footnote — treat this file as part of the deliverable, not internal notes.

## Why synthetic, and why we say so

We do not use real customer data — none exists for us to use, and using real
banking behaviour would be both impossible and inappropriate for a hackathon
demo. Every number in this dataset is generated. We state this plainly rather
than implying otherwise.

## The persona system (`data/personas.py`)

Rather than generating pure random noise, we define 6 named personas, each
with a stable behavioural fingerprint: typing speed mean/variance, typical
active hours, typical transaction amount mean/variance, channel preference
(WEB/USSD/BOTH), device count, and typical navigation depth. See the file for
exact parameters.

**Why personas instead of uniform randomness:** a model trained on pure noise
learns nothing generalizable. A model trained on internally-consistent
personas learns to recognize *deviation from an individual's own baseline* —
which is exactly what the hackathon brief asks the system to do ("what time
this customer normally sends money... almost none of this is used").

Each of the 80 synthetic users is sampled from one of the 6 persona templates
with individual random jitter, so users sharing a persona aren't identical,
but users of different personas are meaningfully distinguishable.

One persona (`family_shared_phone`) is deliberately given a high device count
and high typing-speed variance — this exists specifically to test that our
system does NOT penalize shared-phone usage on its own, per the brief's
explicit warning: *"Families share phones and people change SIMs. Neither is
fraud."*

## Normal sessions

Each synthetic user generates 25 App-channel and 25 USSD-channel "normal"
sessions, each session's raw values drawn from a Gaussian centered on that
user's own persona baseline (not the population average) — reflecting that
a fast typist has a fast typist's version of "normal," not the same normal
as a slow typist.

## Legitimate anomalies (our false-positive test set)

6% of each user's own sessions are deliberately generated as **genuine
customers doing something unusual but honest** — a hospital-bill-sized
transfer, typing rhythm thrown off by a new device, a rushed transfer that
skips screens. These are labeled `0` (not fraud) despite looking statistically
unusual. Without sessions like these, we cannot honestly test or report a
false-positive rate — a model tested only on "obviously normal" vs "obviously
attacker" sessions has never been challenged on the case the brief cares about
most: *"Blocking a genuine transfer is not harmless."*

## Attacker sessions

Attacker sessions are generated per named archetype so the model learns
distinct signatures rather than one generic "fraud blob":

| Archetype | Behavioural signature |
|---|---|
| Credential stuffing | Very fast fill, pasted credentials, minimal navigation |
| OTP replay | Near-normal typing, but abnormally few screens/retries |
| SIM-swap takeover | Behaviourally near-normal on this model — caught by the SEPARATE SIM-swap/OTP hard-control module (Division 5), not this classifier. Included here so the dataset honestly reflects that this attack type is a known weak spot for a behaviour-only model. |
| Coached victim | Real device, but abnormally SLOW and hesitant — the opposite signature from a bot |
| Slow-drift | Amounts kept deliberately just under the typical threshold |
| Impossible travel | Behaviourally near-normal here — geographic/velocity signal lives outside these 4 features, in Division 4's fuller feature set |

**Honesty note:** two archetypes (SIM-swap takeover, impossible travel) are
intentionally NOT strongly separable by these 4 basic features alone. This is
correct and disclosed, not a bug — those attacks are caught by other layers of
the system (the SIM-swap/OTP hard-control module, geo-velocity checks in the
fuller Division 4 pipeline), and the demo's "here's what we get wrong and why"
panel should name this explicitly rather than hide it.

## Deviation feature formulas — canonical, not duplicated

The exact formulas converting raw session values into the 4+4 model features
are defined ONCE, in `data/generate_dataset.py`, and are copy-identical to the
formulas used at live inference time in the frontend/backend (originally
specified in the frontend build brief). This is deliberate: using the same
formula in two places by coincidence is how train/serve mismatches happen
silently. Here, there is only one canonical definition.

```
App channel:
  typing_speed_deviation   = (chars_per_sec - 4.0) / 1.0
  pasted_char_ratio        = 0.9 if pasted else 0.05
  screen_sequence_anomaly  = (6 - screens_visited) / 6
  amount_deviation         = (amount - 15000) / (15000 * 2.06)

USSD channel:
  time_of_day_deviation    = abs(hour - 14) / 12
  session_retry_deviation  = retries / 2.0
  sim_swap_risk            = {OVER_30: 0.0, 15_30: 0.2, 5_14: 0.6, 0_4: 0.95}
  amount_deviation         = (amount - 4000) / (4000 * 0.98)
```

## Class balance

Target positive rates (~4.8% app, ~5.1% USSD) were chosen to match the fixed
contract already agreed with the model-training brief, and reflect the
hackathon brief's own framing: *"real fraud examples are rare... heavily
outnumbered by normal transactions."*

The class split is built by a fixed count of attacker sessions layered on top
of the 2,000 normal sessions per channel (80 users x 25):

| Channel | Normal rows | Attacker rows | Total | Achieved positive rate | Target |
|---|---|---|---|---|---|
| App  | 2,000 | 101 | 2,101 | **4.81%** | ~4.8% |
| USSD | 2,000 | 107 | 2,107 | **5.08%** | ~5.1% |

Generation is deterministic (`random.seed(42)` / `np.random.seed(42)`), so these
are the exact rates every run produces, not a sample that drifts. They are also
printed at generation time and recorded in `data/generation_summary.json`; that
file is the machine-readable source of truth if the two ever disagree.

## Two outputs, one generation pass

This generator produces:
1. **`data/app_channel_data.csv`** and **`data/ussd_channel_data.csv`** — flat
   files with exactly the 4 deviation features + label, for the Model Agent's
   RandomForest training.
2. **Rich rows directly in Postgres** (`users`, `telco_state`) — for Aegis's
   own fuller Division 4 detection core, which uses a richer feature set
   beyond just these 4 (per-key dwell/flight timing, mouse movement, call
   state, etc. — see `docs/Aegis_Build_Plan.md` Division 4).

Both outputs come from the same underlying random draws per synthetic user,
so the two efforts are testing consistent, not contradictory, ground truth.
