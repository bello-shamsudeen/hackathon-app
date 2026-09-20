# Project: AEGIS
Behavioural account-takeover detection platform — ICSC Hackathon, Track A1
(Financial Services & Digital Payments — "Spotting Account Takeover From Behaviour")

## Before doing anything
Read these two files in full before writing or changing any code:
1. `/docs/Aegis_Full_Blueprint.md` — the WHAT and WHY: every feature, and the exact
   line in the hackathon brief it answers. Do not remove or contradict anything here
   without flagging it to the user first.
2. `/docs/Aegis_Build_Plan.md` — the WHAT WE BUILD, IN WHAT ORDER: nine divisions,
   dependency-ordered, each ending in a named demo moment. Appendix A lists the full
   free/free-tier tech stack — do not introduce paid dependencies. Appendix B maps
   every hackathon requirement to the division that answers it. Appendix C ranks
   what actually differentiates this build — keep these features intact.

## Current status
- Division 1 (Foundation & Schema) is scaffolded: docker-compose.yml, Postgres
  schema (ops/postgres/init/001_schema.sql), FastAPI skeleton (backend/app/main.py).
- Check `/docs/progress.md` for the current division and what's done vs pending.

## Hard rules for this project
- Nothing gets built that has no demo moment. If you're about to add something
  decorative, stop and check the Build Plan first.
- All synthetic data. Never attempt to source or fabricate real user data.
- 100% free/free-tier tooling only (see Build Plan Appendix A).
- The SIM-swap/OTP hard-control logic (Division 5) must never treat a raw device
  or SIM change as fraud on its own — only device/SIM change IN COMBINATION with
  a recent swap or first-time pairing. This is a named brief requirement; do not
  simplify it away.
- The USSD backend (Division 2B) must implement the real USSD protocol contract
  (sessionId, phoneNumber, accumulated text, CON/END responses) — not a fake menu.
- AI explanations (Division 6) must always be generated FROM grounded SHAP output,
  never as a free-standing LLM guess.

## Model usage guidance (for cost-conscious builds)
- Opus-tier reasoning: synthetic data design (Div 3), ML/threshold tuning (Div 4),
  SIM-swap/OTP hard-control logic (Div 5), correlation-graph logic (Div 5C/8).
- Standard-tier: CRUD, protocol implementation, config, integration glue,
  frontend components, attack scripts.
- Reserve extra reasoning effort for anything in Appendix C of the Build Plan.

## Working style
State which division you're working on before making changes. After finishing a
division's scope, update `/docs/progress.md` with what was completed and what
demo moment it produces, so the next session (which starts with no memory of this
one) can pick up correctly.
