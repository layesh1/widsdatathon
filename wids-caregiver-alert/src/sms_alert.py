"""
sms_alert.py
Twilio SMS integration for WiDS Wildfire Caregiver Alert System.

Reads credentials from Streamlit secrets:
    [twilio]
    sid   = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    token = "your_auth_token"
    from  = "+15005550006"

If secrets are absent or Twilio is unavailable, all functions degrade gracefully
to a no-op (logged to stderr only) so the dashboard never crashes.
"""

from __future__ import annotations
import logging
from typing import Optional

log = logging.getLogger(__name__)

_TWILIO_AVAILABLE: Optional[bool] = None
_CLIENT = None


def _get_client():
    """Lazy-init Twilio client from Streamlit secrets."""
    global _TWILIO_AVAILABLE, _CLIENT
    if _TWILIO_AVAILABLE is not None:
        return _CLIENT

    try:
        import streamlit as st
        from twilio.rest import Client  # type: ignore

        sid   = st.secrets.get("twilio", {}).get("sid") or st.secrets.get("TWILIO_SID")
        token = st.secrets.get("twilio", {}).get("token") or st.secrets.get("TWILIO_TOKEN")
        from_ = st.secrets.get("twilio", {}).get("from") or st.secrets.get("TWILIO_FROM")

        if sid and token and from_:
            _CLIENT = Client(sid, token)
            _CLIENT._from = from_
            _TWILIO_AVAILABLE = True
        else:
            _TWILIO_AVAILABLE = False
    except Exception as exc:
        log.debug("Twilio not available: %s", exc)
        _TWILIO_AVAILABLE = False

    return _CLIENT


def is_sms_available() -> bool:
    """Return True if Twilio credentials are configured and Twilio package is installed."""
    return bool(_get_client())


def send_sms_alert(phone: str, message: str) -> bool:
    """
    Send an SMS alert via Twilio.

    Parameters
    ----------
    phone   : E.164 format phone number, e.g. '+15556667777'
    message : Text body (max 1,600 chars; longer messages will be truncated)

    Returns
    -------
    True on success, False on any failure (including credentials absent).
    """
    client = _get_client()
    if client is None:
        log.debug("SMS not sent (Twilio unavailable): %s", phone)
        return False

    # Normalize phone number
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if not digits:
        log.warning("SMS skipped — invalid phone: %r", phone)
        return False
    if not digits.startswith("+"):
        digits = "+1" + digits  # Default to US country code

    try:
        msg = client.messages.create(
            body=message[:1_600],
            from_=client._from,
            to=digits,
        )
        log.info("SMS sent to %s — SID: %s", phone, msg.sid)
        return True
    except Exception as exc:
        log.warning("SMS failed to %s: %s", phone, exc)
        return False


def send_evacuation_alert(
    phone: str,
    resident_name: str,
    county: str,
    shelter_name: str = "",
    lang: str = "en",
) -> bool:
    """
    Convenience wrapper: send a templated evacuation alert SMS.

    Parameters
    ----------
    phone         : Recipient phone (E.164 or 10-digit US)
    resident_name : Name of the person needing evacuation
    county        : County name
    shelter_name  : Optional shelter name to include
    lang          : 'en' (English) or 'es' (Spanish)

    Returns
    -------
    True on success, False otherwise.
    """
    if lang == "es":
        shelter_line = f"Refugio sugerido: {shelter_name}. " if shelter_name else ""
        message = (
            f"ALERTA DE EVACUACION — {county}: Se ha emitido una orden de evacuación. "
            f"{resident_name} necesita asistencia inmediata. "
            f"{shelter_line}"
            "Llame al 9-1-1 si necesita transporte de emergencia."
        )
    else:
        shelter_line = f"Suggested shelter: {shelter_name}. " if shelter_name else ""
        message = (
            f"EVACUATION ALERT — {county}: An evacuation order has been issued. "
            f"{resident_name} needs immediate assistance. "
            f"{shelter_line}"
            "Call 9-1-1 if emergency transportation is needed."
        )

    return send_sms_alert(phone, message)
