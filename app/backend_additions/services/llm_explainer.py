"""
Division 6B — LLM-generated dual-audience explanations.

CRITICAL DESIGN RULE: the LLM is given the SHAP reason codes from
explainability.py as context and is ONLY allowed to rewrite them into plain
language for two audiences (customer, analyst). It must never be asked to
invent its own reasons from scratch — this is what keeps the explanation
grounded and defensible if a judge probes it.

PROVIDER CHAIN (free-tier first, always with a deterministic fallback):
  1. Groq (fast, free tier) — tried first, best for a live demo
  2. Google Gemini (free tier) — tried if Groq fails/unavailable
  3. Ollama (local, fully offline) — tried if both cloud options fail;
     THIS IS THE ONE TO ACTUALLY SET UP AND TEST BEFORE DEMO DAY, since
     venue wifi is never something to depend on
  4. Deterministic template fallback — if ALL of the above fail, we still
     produce a correct plain-English sentence using the same
     REASON_TEMPLATES dict from decision_engine.py. This is the guarantee
     that the hackathon's graded "plain sentence" requirement NEVER breaks,
     even if every LLM option is unavailable on demo day.

Set provider API keys via environment variables (see .env.example):
  GROQ_API_KEY, GEMINI_API_KEY. Ollama needs no key, just a local install.
"""
import os
import requests

REASON_TEMPLATES = {
    "typing_speed_deviation": "you typed at an unusual speed for you",
    "pasted_char_ratio": "your details were pasted rather than typed",
    "screen_sequence_anomaly": "you skipped steps you normally go through",
    "amount_deviation": "this amount is unusual for you",
    "time_of_day_deviation": "this was sent at an unusual time for you",
    "session_retry_deviation": "there were more retries than usual",
    "sim_swap_risk": "your SIM was recently changed",
}

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def _build_prompt(reason_codes: list, tier: str, audience: str) -> str:
    codes_text = "; ".join(
        f"{rc['feature']} (value={rc['value']}, contribution={rc['shap_contribution']})"
        for rc in reason_codes
    )
    if audience == "customer":
        return (
            f"A fraud detection system flagged a bank transaction with tier '{tier}'. "
            f"The ONLY grounded reasons, from real model attribution, are: {codes_text}. "
            f"Write ONE short, plain, non-technical, non-accusatory sentence a bank could "
            f"say to a customer explaining why their transaction was paused. Do not invent "
            f"any reason not listed above. Do not use technical feature names."
        )
    else:
        return (
            f"A fraud detection system flagged a transaction with tier '{tier}'. "
            f"Grounded SHAP attributions: {codes_text}. Write a short technical explanation "
            f"for a fraud analyst, naming the actual feature names and their contribution "
            f"direction and magnitude. Do not invent anything beyond the data given."
        )


def _try_groq(prompt: str) -> str | None:
    if not GROQ_API_KEY:
        return None
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
            },
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _try_gemini(prompt: str) -> str | None:
    if not GEMINI_API_KEY:
        return None
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None


def _try_ollama(prompt: str) -> str | None:
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=8,
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()
    except Exception:
        return None


def _deterministic_fallback(reason_codes: list, tier: str) -> str:
    """This NEVER fails and NEVER depends on network access — the true guarantee."""
    if tier == "low" or not reason_codes:
        return "This transaction looks consistent with your normal activity."
    top_two = reason_codes[:2]
    reason_a = REASON_TEMPLATES.get(top_two[0]["feature"], "unusual activity was detected")
    if len(top_two) > 1:
        reason_b = REASON_TEMPLATES.get(top_two[1]["feature"], "additional unusual activity was detected")
        return f"This transaction was flagged because {reason_a}, and {reason_b}."
    return f"This transaction was flagged because {reason_a}."


def generate_explanation(reason_codes: list, tier: str, audience: str = "customer") -> dict:
    """
    Tries each provider in order, returns the first success. ALWAYS returns
    a usable sentence — never raises, never leaves the caller with nothing.
    """
    prompt = _build_prompt(reason_codes, tier, audience)

    for provider_name, provider_fn in [("groq", _try_groq), ("gemini", _try_gemini), ("ollama", _try_ollama)]:
        result = provider_fn(prompt)
        if result:
            return {"text": result, "source": provider_name}

    return {"text": _deterministic_fallback(reason_codes, tier), "source": "deterministic_fallback"}
