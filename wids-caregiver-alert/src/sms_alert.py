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
import re
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


# ── Pre-order early warning SMS ───────────────────────────────────────────────

def send_preorder_alert(
    phone: str,
    resident_name: str,
    address: str,
    estimated_hours: float,
    wind_mph: float,
    wind_dir: str,
    mobility_type: str = "mobile_adult",
    lang: str = "en",
) -> bool:
    """
    Send a pre-order early warning SMS when a fire is detected nearby but no
    official evacuation order has yet been issued.

    Parameters
    ----------
    phone           : Recipient phone (E.164 or 10-digit US)
    resident_name   : Resident's first name (used in personalization)
    address         : Resident's street address / neighborhood
    estimated_hours : Estimated hours until the fire front reaches the area
    wind_mph        : Current wind speed in mph
    wind_dir        : Wind direction string (e.g. "NE", "Southwest")
    mobility_type   : Used to adjust urgency language (e.g. "no_vehicle", "disabled")
    lang            : "en" or "es"

    Returns
    -------
    True on success, False otherwise.
    """
    # Format estimated time as "Xh Ym"
    total_min = int(round(estimated_hours * 60))
    hrs = total_min // 60
    mins = total_min % 60
    if hrs > 0 and mins > 0:
        time_str = f"{hrs}h {mins}m"
    elif hrs > 0:
        time_str = f"{hrs}h"
    else:
        time_str = f"{mins}m"

    # Mobility-specific action line
    _action_en = {
        "mobile_adult":      "Begin evacuating NOW.",
        "elderly":           "Begin evacuating NOW. Call your county special-needs hotline for priority assistance.",
        "disabled":          "Begin evacuating NOW. Contact paratransit or call 211 for accessible transport.",
        "no_vehicle":        "Begin evacuating NOW. Call 211 or 911 for emergency transport — do NOT wait.",
        "medical_equipment": "Begin evacuating NOW. Secure all medical equipment first. Call 911 if transport help is needed.",
        "caregiver":         "Begin evacuating NOW with your care recipient. Call 911 if transport assistance is needed.",
    }
    _action_es = {
        "mobile_adult":      "Comience a evacuar AHORA.",
        "elderly":           "Comience a evacuar AHORA. Llame a la línea especial de su condado para asistencia prioritaria.",
        "disabled":          "Comience a evacuar AHORA. Contacte paratransporte o llame al 211 para transporte accesible.",
        "no_vehicle":        "Comience a evacuar AHORA. Llame al 211 o al 911 para transporte de emergencia — NO espere.",
        "medical_equipment": "Comience a evacuar AHORA. Asegure primero todo el equipo médico. Llame al 911 si necesita ayuda.",
        "caregiver":         "Comience a evacuar AHORA con su receptor de cuidados. Llame al 911 si necesita asistencia.",
    }

    if lang == "es":
        action = _action_es.get(mobility_type, _action_es["mobile_adult"])
        prefix = "URGENTE — " if estimated_hours < 1 else ""
        message = (
            f"{prefix}ALERTA PREVIA DE INCENDIO FORESTAL: Se detectó un incendio cerca de {address}. "
            f"Frente de fuego estimado: {time_str}. "
            f"Viento {wind_mph:.0f} mph {wind_dir}. "
            f"Orden oficial aún no emitida (promedio histórico de retraso: 1.1h). "
            f"Con su nivel de movilidad, {action} "
            "Llame al 911 si necesita transporte."
        )
    else:
        action = _action_en.get(mobility_type, _action_en["mobile_adult"])
        prefix = "URGENT — " if estimated_hours < 1 else ""
        message = (
            f"{prefix}WILDFIRE PRE-ORDER ALERT: A fire was detected near {address}. "
            f"Estimated fire front: {time_str}. "
            f"Wind {wind_mph:.0f} mph {wind_dir}. "
            f"Official order not yet issued (historical avg: 1.1h delay). "
            f"With your mobility level, {action} "
            "Call 911 if you need transport."
        )

    return send_sms_alert(phone, message)


# ── Check-in request SMS ──────────────────────────────────────────────────────

def send_checkin_request(
    phone: str,
    resident_name: str,
    shelter_name: str = "",
    estimated_travel_min: int = 60,
    lang: str = "en",
) -> bool:
    """
    Send a check-in request SMS after the estimated travel time has elapsed,
    asking the resident to confirm safe arrival.

    Parameters
    ----------
    phone                : Recipient phone (E.164 or 10-digit US)
    resident_name        : Resident's first name
    shelter_name         : Destination shelter (shown as context if provided)
    estimated_travel_min : Minutes estimated for travel (included in message for context)
    lang                 : "en" or "es"

    Returns
    -------
    True on success, False otherwise.
    """
    first_name = resident_name.split()[0] if resident_name else "there"

    if lang == "es":
        shelter_line = f"Refugio: {shelter_name}. " if shelter_name else ""
        message = (
            f"Hola {first_name}, este es su recordatorio de registro por incendio forestal. "
            f"¿Llegó a un lugar seguro? "
            f"{shelter_line}"
            "Responda SI para confirmar. "
            "Responda AYUDA si necesita asistencia."
        )
    else:
        shelter_line = f"Shelter: {shelter_name}. " if shelter_name else ""
        message = (
            f"Hi {first_name}, this is your wildfire check-in. "
            f"Did you arrive safely? "
            f"{shelter_line}"
            "Reply YES to confirm. "
            "Reply HELP if you need assistance."
        )

    return send_sms_alert(phone, message)


# ── Check-in response handler ─────────────────────────────────────────────────

# Patterns are matched case-insensitively against the full trimmed message body.
_CONFIRMED_PATTERN = re.compile(
    r"\b(yes|si|sí|safe|llegue|llegué|ok|okay|bien|aqui|aquí|here|arrived)\b",
    re.IGNORECASE,
)
_NEEDS_HELP_PATTERN = re.compile(
    r"\b(help|ayuda|no|stuck|atrapado|atrapada|trapped|need help|necesito ayuda|emergency|emergencia)\b",
    re.IGNORECASE,
)


def parse_checkin_reply(message_body: str) -> str:
    """
    Parse a resident's reply to a check-in SMS and return a status string.

    Parameters
    ----------
    message_body : Raw text body of the incoming SMS reply

    Returns
    -------
    "confirmed"  — resident confirmed safe arrival
                   (matches: YES, SI, SAFE, LLEGUE, OK, AQUI, ARRIVED, etc.)
    "needs_help" — resident needs assistance
                   (matches: HELP, AYUDA, NO, STUCK, ATRAPADO, TRAPPED, etc.)
    "unknown"    — message could not be classified
    """
    text = (message_body or "").strip()

    # Check for help signals first (higher priority if both appear)
    if _NEEDS_HELP_PATTERN.search(text):
        return "needs_help"
    if _CONFIRMED_PATTERN.search(text):
        return "confirmed"
    return "unknown"
