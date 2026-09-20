"""
Division 3 — persona definitions.
This is the single biggest quality lever in the whole dataset. Random noise
produces a model that's learned nothing real; personas with internally
consistent, stable behavioural fingerprints produce a model that's learned
something resembling actual human variation.

Each persona is a template. generate_dataset.py samples many synthetic USERS
from these templates, giving each user their own small random jitter around
the persona's baseline — so two users of the same persona aren't identical,
but users of DIFFERENT personas are meaningfully distinguishable.
"""
import random

PERSONAS = [
    {
        "tag": "market_trader",
        "typing_speed_mean": 3.2, "typing_speed_std": 0.6,   # chars/sec, slower/erratic
        "typical_hours": (5, 9),                              # early morning transactor
        "amount_mean": 8000, "amount_std": 4000,
        "channel_pref": "USSD",
        "device_count": 1,
        "screens_typically_visited": 4,                        # out of 6 max
    },
    {
        "tag": "salaried_worker",
        "typing_speed_mean": 4.5, "typing_speed_std": 0.5,
        "typical_hours": (19, 22),
        "amount_mean": 15000, "amount_std": 6000,
        "channel_pref": "WEB",
        "device_count": 1,
        "screens_typically_visited": 6,
    },
    {
        "tag": "student",
        "typing_speed_mean": 5.5, "typing_speed_std": 0.8,     # fast, comfortable with tech
        "typical_hours": (12, 23),
        "amount_mean": 4000, "amount_std": 2500,
        "channel_pref": "WEB",
        "device_count": 2,                                     # phone + occasional laptop
        "screens_typically_visited": 5,
    },
    {
        "tag": "small_business_owner",
        "typing_speed_mean": 4.0, "typing_speed_std": 0.4,
        "typical_hours": (8, 18),
        "amount_mean": 35000, "amount_std": 20000,              # larger, more variable amounts
        "channel_pref": "BOTH",
        "device_count": 1,
        "screens_typically_visited": 6,
    },
    {
        "tag": "elderly_low_tech",
        "typing_speed_mean": 2.0, "typing_speed_std": 0.7,     # slow, hesitant
        "typical_hours": (9, 15),
        "amount_mean": 12000, "amount_std": 5000,
        "channel_pref": "USSD",
        "device_count": 1,
        "screens_typically_visited": 3,                         # tends to skip/miss steps genuinely
    },
    {
        "tag": "family_shared_phone",
        "typing_speed_mean": 3.8, "typing_speed_std": 1.2,     # HIGH variance — multiple real users
        "typical_hours": (7, 21),
        "amount_mean": 10000, "amount_std": 7000,
        "channel_pref": "USSD",
        "device_count": 3,                                      # deliberately multiple devices — NOT fraud
        "screens_typically_visited": 4,
    },
]


def sample_user_from_persona(persona: dict) -> dict:
    """One synthetic user's fixed baseline, jittered from their persona template."""
    return {
        "persona_tag": persona["tag"],
        "typing_speed_baseline": max(0.5, random.gauss(persona["typing_speed_mean"], persona["typing_speed_std"] * 0.3)),
        "typing_speed_std": persona["typing_speed_std"],
        "typical_hour_start": persona["typical_hours"][0],
        "typical_hour_end": persona["typical_hours"][1],
        "amount_baseline": max(500, random.gauss(persona["amount_mean"], persona["amount_std"] * 0.3)),
        "amount_std": persona["amount_std"],
        "channel_pref": persona["channel_pref"],
        "device_count": persona["device_count"],
        "screens_typically_visited": persona["screens_typically_visited"],
    }
