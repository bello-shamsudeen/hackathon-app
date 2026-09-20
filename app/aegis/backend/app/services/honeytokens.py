"""
Division 8B - Honeytokens.
A form field real humans never see or fill (CSS-hidden, no tabindex).
Scripted/bot submissions that auto-fill every field often fill it anyway.
Any submission with this field non-empty is a near-zero-false-positive bot
signal - cheap, real, and worth an immediate hard override.
"""

HONEYTOKEN_FIELD_NAME = "confirm_email_address"  # deliberately looks like a real field name


def check_honeytoken(form_data: dict) -> dict:
    value = form_data.get(HONEYTOKEN_FIELD_NAME, "")
    if value:
        return {"triggered": True, "field": HONEYTOKEN_FIELD_NAME,
                "message": "an automated form-filling pattern was detected"}
    return {"triggered": False}
