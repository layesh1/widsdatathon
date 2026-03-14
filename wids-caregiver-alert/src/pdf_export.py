"""
pdf_export.py — Generates a downloadable PDF evacuation plan.

Requires: reportlab
    pip install reportlab
"""

from __future__ import annotations

import io
from datetime import datetime

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor, white
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors as rl_colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ── Default checklist used when caller doesn't supply one ─────────────────────
DEFAULT_CHECKLIST = [
    "Government-issued ID for all household members",
    "Prescription medications (minimum 7-day supply)",
    "Medical equipment & chargers (CPAP, oxygen, hearing aids)",
    "Insurance documents & important financial records",
    "Cash and debit/credit cards",
    "Phone charger and portable power bank",
    "Water — at least 1 gallon per person per day (3-day supply)",
    "Non-perishable food for 3 days",
    "Change of clothes and sturdy shoes",
    "Blankets or sleeping bags",
    "Pet carriers, pet food, vaccination records",
    "First-aid kit and hand sanitizer",
    "Flashlight and extra batteries",
    "Copies of your evacuation plan and shelter locations",
    "N95 masks (wildfire smoke protection)",
    "Car keys, gas tank filled (fill NOW if order is imminent)",
    "List of emergency contacts (written, not just in your phone)",
    "Children's items: formula, diapers, comfort items",
    "Download offline maps before you leave",
]


# ── Mobility-specific checklist additions ─────────────────────────────────────

_MOBILITY_EXTRA: dict[str, list[str]] = {
    "mobile_adult": [],
    "elderly": [
        "Complete medications list with dosages and prescriber contacts",
        "Medical alert bracelet or necklace",
        "Hearing aid batteries (extra pack)",
        "Walker, cane, or mobility aid",
        "Extra glasses or contact lenses + solution",
    ],
    "disabled": [
        "Wheelchair battery backup (fully charged)",
        "All medical devices and power adapters",
        "Transfer equipment (transfer board, gait belt, Hoyer sling)",
        "10-day supply of critical medications",
        "Copies of care instructions for responders",
    ],
    "no_vehicle": [
        "Transit agency emergency transportation number (call 211 for your county)",
        "Pre-register for accessible evacuation transport with county emergency services",
        "Written walk route to the nearest pickup/staging point",
        "Neighbor or mutual aid contact who can provide a ride",
    ],
    "medical_equipment": [
        "Nebulizer and extra medication canisters",
        "Backup oxygen supply (portable tank if applicable)",
        "CPAP machine with full battery backup",
        "Medication refrigeration plan (cooler + ice packs for insulin, biologics, etc.)",
        "14-day supply of all critical medications",
        "Generator or power-bank rated for medical device wattage",
    ],
    "caregiver": [
        "Care recipient's complete medication list",
        "Care recipient's mobility equipment (wheelchair, walker, lift sling)",
        "Care recipient's government-issued ID and insurance cards",
        "Contact information for care recipient's primary physician and specialists",
        "Signed medical release / care authorization document",
        "List of care recipient's dietary restrictions and allergies",
    ],
}

# Spanish translations for mobility extras
_MOBILITY_EXTRA_ES: dict[str, list[str]] = {
    "mobile_adult": [],
    "elderly": [
        "Lista completa de medicamentos con dosis y contactos del médico",
        "Brazalete o collar de alerta médica",
        "Pilas extra para el audífono",
        "Andador, bastón o ayuda para la movilidad",
        "Lentes o lentes de contacto adicionales + solución",
    ],
    "disabled": [
        "Batería de reserva para silla de ruedas (completamente cargada)",
        "Todos los dispositivos médicos y adaptadores de corriente",
        "Equipo de transferencia (tabla de transferencia, cinturón de marcha, cabestrillo Hoyer)",
        "Suministro de medicamentos críticos para 10 días",
        "Copias de instrucciones de cuidado para socorristas",
    ],
    "no_vehicle": [
        "Número de transporte de emergencia de la agencia de tránsito (llame al 211 para su condado)",
        "Regístrese previamente para transporte de evacuación accesible con servicios de emergencia del condado",
        "Ruta escrita a pie al punto de recogida más cercano",
        "Contacto de vecino o ayuda mutua que pueda dar un aventón",
    ],
    "medical_equipment": [
        "Nebulizador y cartuchos de medicamento extra",
        "Suministro de oxígeno de respaldo (tanque portátil si aplica)",
        "Máquina CPAP con batería de respaldo completa",
        "Plan de refrigeración de medicamentos (hielera + bolsas de hielo para insulina, biológicos, etc.)",
        "Suministro de 14 días de todos los medicamentos críticos",
        "Generador o banco de energía con potencia suficiente para el dispositivo médico",
    ],
    "caregiver": [
        "Lista completa de medicamentos del receptor de cuidados",
        "Equipo de movilidad del receptor de cuidados (silla de ruedas, andador, cabestrillo de elevación)",
        "Identificación oficial y tarjetas de seguro del receptor de cuidados",
        "Información de contacto del médico de cabecera y especialistas del receptor de cuidados",
        "Documento de autorización médica / de cuidado firmado",
        "Lista de restricciones dietéticas y alergias del receptor de cuidados",
    ],
}


def get_mobility_checklist(mobility_type: str) -> list[str]:
    """
    Return a full evacuation checklist tailored to the given mobility type.

    Parameters
    ----------
    mobility_type : one of "mobile_adult", "elderly", "disabled", "no_vehicle",
                    "medical_equipment", "caregiver"

    Returns
    -------
    List of checklist item strings (DEFAULT_CHECKLIST + mobility-specific extras).
    """
    extras = _MOBILITY_EXTRA.get(mobility_type, [])
    return list(DEFAULT_CHECKLIST) + extras


# ── Section heading translations ──────────────────────────────────────────────

_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "title":         "WILDFIRE EVACUATION PLAN",
        "generated_for": "Generated for",
        "risk_level":    "YOUR RISK LEVEL",
        "household":     "HOUSEHOLD PROFILE",
        "destination":   "EVACUATION DESTINATION",
        "route":         "PRIMARY EVACUATION ROUTE",
        "travel_time":   "ESTIMATED TRAVEL TIME",
        "fire_dept":     "LOCAL FIRE DEPARTMENT",
        "checklist":     "EVACUATION CHECKLIST",
        "contacts":      "PERSONAL EMERGENCY CONTACTS",
        "resources":     "EMERGENCY RESOURCES",
        "mobility":      "MOBILITY-SPECIFIC INSTRUCTIONS",
        "notes":         "IMPORTANT NOTES",
        "footer":        (
            "Generated by the Wildfire Caregiver Alert System  ·  49ers Intelligence Lab  "
            "·  WiDS Datathon 2025  |  For informational purposes only. "
            "Always follow official emergency management guidance."
        ),
    },
    "es": {
        "title":         "PLAN DE EVACUACION POR INCENDIO FORESTAL",
        "generated_for": "Generado para",
        "risk_level":    "SU NIVEL DE RIESGO",
        "household":     "PERFIL DEL HOGAR",
        "destination":   "DESTINO DE EVACUACION",
        "route":         "RUTA PRINCIPAL DE EVACUACION",
        "travel_time":   "TIEMPO DE VIAJE ESTIMADO",
        "fire_dept":     "DEPARTAMENTO DE BOMBEROS LOCAL",
        "checklist":     "LISTA DE EVACUACION",
        "contacts":      "CONTACTOS PERSONALES DE EMERGENCIA",
        "resources":     "RECURSOS DE EMERGENCIA",
        "mobility":      "INSTRUCCIONES SEGUN MOVILIDAD",
        "notes":         "NOTAS IMPORTANTES",
        "footer":        (
            "Generado por el Sistema de Alerta de Cuidadores de Incendios Forestales  ·  "
            "49ers Intelligence Lab  ·  WiDS Datathon 2025  |  Solo para fines informativos. "
            "Siga siempre las instrucciones oficiales de gestión de emergencias."
        ),
    },
}

_NOTES: dict[str, list[str]] = {
    "en": [
        "Leave EARLY — do not wait for a mandatory order if you feel at risk.",
        "Share this plan with all household members and a trusted contact.",
        "Keep your car pointed toward your evacuation route.",
        "If you have mobility limitations, register with your county emergency management office NOW.",
        "Follow official orders only — do not return until the all-clear is given.",
    ],
    "es": [
        "Salga TEMPRANO — no espere una orden obligatoria si siente que está en riesgo.",
        "Comparta este plan con todos los miembros del hogar y un contacto de confianza.",
        "Mantenga su auto orientado hacia su ruta de evacuación.",
        "Si tiene limitaciones de movilidad, regístrese ahora con la oficina de manejo de emergencias de su condado.",
        "Siga solo las órdenes oficiales — no regrese hasta recibir la señal de que es seguro.",
    ],
}

_RESOURCES: dict[str, list[str]] = {
    "en": [
        "Emergency: 911",
        "FEMA Disaster Assistance: 1-800-621-3362",
        "American Red Cross: 1-800-733-2767",
        "Local evacuation info: Dial 211",
        "Road conditions: Call 511",
        "Poison Control: 1-800-222-1222",
        "Crisis & Suicide Lifeline: 988",
    ],
    "es": [
        "Emergencias: 911",
        "Asistencia por desastre FEMA: 1-800-621-3362",
        "Cruz Roja Americana: 1-800-733-2767",
        "Información de evacuación local: Marque 211",
        "Condiciones de carretera: Llame al 511",
        "Control de Intoxicaciones: 1-800-222-1222",
        "Línea de Crisis y Suicidio: 988",
    ],
}

_MOBILITY_NOTES: dict[str, dict[str, str]] = {
    "en": {
        "mobile_adult":      "",
        "elderly":           "Contact your county emergency management office to enroll in the special-needs registry for priority evacuation assistance.",
        "disabled":          "Pre-register for paratransit/accessible evacuation transport at least 72 hours before a predicted event. Keep your county emergency management number on hand.",
        "no_vehicle":        "Pre-register for accessible evacuation transport at {county} emergency services. Know your nearest pickup staging area and have a backup walking route.",
        "medical_equipment": "Notify your utility provider of medical baseline status so power is restored to your address first. Carry a letter from your physician describing critical equipment needs.",
        "caregiver":         "Inform your care recipient's physician and home health agency of your evacuation plan. Ensure respite care or backup caregiver knows the plan too.",
    },
    "es": {
        "mobile_adult":      "",
        "elderly":           "Comuníquese con la oficina de manejo de emergencias de su condado para inscribirse en el registro de necesidades especiales y recibir asistencia de evacuación prioritaria.",
        "disabled":          "Regístrese previamente para transporte de evacuación accesible/paratránsito al menos 72 horas antes de un evento previsto. Tenga a mano el número de emergencias de su condado.",
        "no_vehicle":        "Regístrese previamente para transporte de evacuación accesible en los servicios de emergencia de {county}. Conozca el área de recogida más cercana y tenga una ruta de caminata de respaldo.",
        "medical_equipment": "Notifique a su proveedor de servicios públicos sobre su condición médica especial para que la energía se restablezca primero en su dirección. Lleve una carta de su médico que describa sus necesidades críticas de equipo.",
        "caregiver":         "Informe al médico del receptor de cuidados y a la agencia de salud en el hogar sobre su plan de evacuación. Asegúrese de que el cuidador de respaldo también conozca el plan.",
    },
}


def generate_evacuation_plan(
    county: str,
    risk_level: str,
    household: dict,
    checklist_items: list[str] | None = None,
    shelter_name: str = "",
    shelter_address: str = "",
    evacuation_route: str = "",
    fire_dept_phone: str = "911",
    estimated_evac_time: str = "",
    emergency_contacts: list[dict] | None = None,
    mobility_type: str = "mobile_adult",
    lang: str = "en",
) -> io.BytesIO | None:
    """
    Generates a PDF evacuation plan.

    Parameters
    ----------
    county              : County name shown in the header
    risk_level          : "LOW", "MEDIUM", "HIGH", or "CRITICAL"
    household           : Dict of profile fields, e.g. {"Name": "Jane", "Members": 2}
    checklist_items     : Override the default checklist; None → use get_mobility_checklist()
    shelter_name        : Designated evacuation shelter name
    shelter_address     : Physical address of the shelter
    evacuation_route    : Written description of the primary route (e.g. "Take Hwy 1 North...")
    fire_dept_phone     : Local fire department / non-emergency number
    estimated_evac_time : Human-readable travel estimate (e.g. "45 minutes")
    emergency_contacts  : List of dicts with keys "name" and "phone"
    mobility_type       : One of the keys in _MOBILITY_EXTRA
    lang                : "en" or "es"

    Returns
    -------
    BytesIO buffer ready for st.download_button, or None if reportlab is not installed.
    """
    if not REPORTLAB_AVAILABLE:
        return None

    lbl = _LABELS.get(lang, _LABELS["en"])

    if checklist_items is None:
        checklist_items = get_mobility_checklist(mobility_type)

    if emergency_contacts is None:
        emergency_contacts = []

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
    )

    styles = getSampleStyleSheet()

    def _style(name, **kwargs) -> ParagraphStyle:
        return ParagraphStyle(name, parent=styles["Normal"], **kwargs)

    title_style = _style(
        "WiDSTitle",
        fontSize=22,
        fontName="Helvetica-Bold",
        textColor=HexColor("#CC0000"),
        spaceAfter=4,
    )
    subtitle_style = _style(
        "WiDSSub",
        fontSize=10,
        textColor=HexColor("#666666"),
        spaceAfter=18,
    )
    risk_colors = {
        "LOW":      "#2d7d33",
        "MEDIUM":   "#a07000",
        "HIGH":     "#CC0000",
        "CRITICAL": "#6b0000",
    }
    risk_color = risk_colors.get(risk_level.upper(), "#555555")
    risk_style = _style(
        "WiDSRisk",
        fontSize=16,
        fontName="Helvetica-Bold",
        textColor=HexColor(risk_color),
        spaceAfter=18,
    )
    h2_style = _style(
        "WiDSH2",
        fontSize=13,
        fontName="Helvetica-Bold",
        textColor=HexColor("#222222"),
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = _style(
        "WiDSBody",
        fontSize=10,
        leading=15,
        spaceAfter=3,
    )
    footer_style = _style(
        "WiDSFooter",
        fontSize=8,
        textColor=HexColor("#999999"),
        spaceBefore=20,
    )
    highlight_style = _style(
        "WiDSHighlight",
        fontSize=10,
        leading=15,
        spaceAfter=3,
        textColor=HexColor("#003366"),
    )

    story = []

    # ── Title ─────────────────────────────────────────────────────────────────
    story.append(Paragraph(lbl["title"], title_style))
    ts = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    story.append(Paragraph(f"{lbl['generated_for']}: {county}  |  {ts}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#dddddd"), spaceAfter=14))

    # ── Risk level ────────────────────────────────────────────────────────────
    story.append(Paragraph(f"{lbl['risk_level']}: {risk_level.upper()}", risk_style))

    # ── Household profile ─────────────────────────────────────────────────────
    story.append(Paragraph(lbl["household"], h2_style))
    for key, val in household.items():
        story.append(Paragraph(f"• {key}: {val}", body_style))
    story.append(Spacer(1, 10))

    # ── Evacuation destination ────────────────────────────────────────────────
    if shelter_name or shelter_address or evacuation_route or estimated_evac_time or fire_dept_phone != "911":
        story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#eeeeee"), spaceAfter=6))
        story.append(Paragraph(lbl["destination"], h2_style))

        if shelter_name:
            story.append(Paragraph(f"• {shelter_name}", highlight_style))
        if shelter_address:
            story.append(Paragraph(f"  {shelter_address}", body_style))

        if evacuation_route:
            story.append(Spacer(1, 6))
            story.append(Paragraph(lbl["route"], h2_style))
            story.append(Paragraph(evacuation_route, body_style))

        if estimated_evac_time:
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"{lbl['travel_time']}: {estimated_evac_time}", body_style))

        if fire_dept_phone:
            story.append(Paragraph(f"{lbl['fire_dept']}: {fire_dept_phone}", body_style))

        story.append(Spacer(1, 10))

    # ── Checklist ─────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#eeeeee"), spaceAfter=6))
    story.append(Paragraph(lbl["checklist"], h2_style))
    for item in checklist_items:
        story.append(Paragraph(f"&#9744;  {item}", body_style))
    story.append(Spacer(1, 10))

    # ── Personal emergency contacts ───────────────────────────────────────────
    if emergency_contacts:
        story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#eeeeee"), spaceAfter=6))
        story.append(Paragraph(lbl["contacts"], h2_style))
        for contact in emergency_contacts:
            name = contact.get("name", "")
            phone = contact.get("phone", "")
            if name or phone:
                story.append(Paragraph(f"• {name}: {phone}", body_style))
        story.append(Spacer(1, 10))

    # ── Emergency resources ────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#eeeeee"), spaceAfter=6))
    story.append(Paragraph(lbl["resources"], h2_style))
    resource_list = _RESOURCES.get(lang, _RESOURCES["en"])
    for c in resource_list:
        story.append(Paragraph(f"• {c}", body_style))

    # ── Mobility-specific instructions ────────────────────────────────────────
    mobility_notes_map = _MOBILITY_NOTES.get(lang, _MOBILITY_NOTES["en"])
    mobility_note = mobility_notes_map.get(mobility_type, "")
    if mobility_note:
        story.append(Spacer(1, 14))
        story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#eeeeee"), spaceAfter=6))
        story.append(Paragraph(lbl["mobility"], h2_style))
        story.append(Paragraph(f"• {mobility_note.replace('{county}', county)}", body_style))

        # Also list the mobility-specific checklist extras as reminders
        extras_map = _MOBILITY_EXTRA_ES if lang == "es" else _MOBILITY_EXTRA
        extras = extras_map.get(mobility_type, [])
        for extra in extras:
            story.append(Paragraph(f"• {extra}", body_style))
        story.append(Spacer(1, 6))

    # ── Important notes ───────────────────────────────────────────────────────
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#eeeeee"), spaceAfter=6))
    story.append(Paragraph(lbl["notes"], h2_style))
    notes_list = _NOTES.get(lang, _NOTES["en"])
    for n in notes_list:
        story.append(Paragraph(f"• {n}", body_style))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(Paragraph(lbl["footer"], footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ── Wallet card ───────────────────────────────────────────────────────────────

_WALLET_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "header":    "WILDFIRE EMERGENCY CARD",
        "name":      "Name",
        "county":    "County",
        "shelter":   "Shelter",
        "route":     "Route",
        "fire_dept": "Fire Dept",
        "evac_time": "Est. Evac Time",
        "footer":    "Print and keep in your wallet. Call 911 in an emergency.",
    },
    "es": {
        "header":    "TARJETA DE EMERGENCIA POR INCENDIO",
        "name":      "Nombre",
        "county":    "Condado",
        "shelter":   "Refugio",
        "route":     "Ruta",
        "fire_dept": "Bomberos",
        "evac_time": "Tiempo estimado",
        "footer":    "Imprima y guarde en su billetera. Llame al 911 en caso de emergencia.",
    },
}


def generate_wallet_card(
    name: str,
    county: str,
    shelter_name: str,
    shelter_address: str,
    route_summary: str,
    fire_dept_phone: str,
    evac_time: str,
    lang: str = "en",
) -> io.BytesIO | None:
    """
    Generate a compact half-page (5.5" x 8.5") wallet card with key evacuation info.

    Parameters
    ----------
    name            : Resident's name
    county          : County name
    shelter_name    : Destination shelter
    shelter_address : Shelter street address
    route_summary   : One-line route description (e.g. "Hwy 101 N to Fairgrounds")
    fire_dept_phone : Local fire dept / emergency number
    evac_time       : Human-readable estimated travel time (e.g. "30 min")
    lang            : "en" or "es"

    Returns
    -------
    BytesIO buffer (half-letter PDF) ready for st.download_button, or None if
    reportlab is not installed.
    """
    if not REPORTLAB_AVAILABLE:
        return None

    lbl = _WALLET_LABELS.get(lang, _WALLET_LABELS["en"])

    # Half-letter page: 5.5" wide x 8.5" tall
    HALF_LETTER = (5.5 * inch, 8.5 * inch)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=HALF_LETTER,
        topMargin=0,
        bottomMargin=0.4 * inch,
        leftMargin=0.4 * inch,
        rightMargin=0.4 * inch,
    )

    styles = getSampleStyleSheet()

    def _style(name, **kwargs) -> ParagraphStyle:
        return ParagraphStyle(name, parent=styles["Normal"], **kwargs)

    card_header_style = _style(
        "CardHeader",
        fontSize=16,
        fontName="Helvetica-Bold",
        textColor=HexColor("#FFFFFF"),
        alignment=1,  # center
        spaceBefore=10,
        spaceAfter=10,
    )
    card_label_style = _style(
        "CardLabel",
        fontSize=9,
        fontName="Helvetica-Bold",
        textColor=HexColor("#555555"),
        spaceAfter=1,
    )
    card_value_style = _style(
        "CardValue",
        fontSize=11,
        fontName="Helvetica",
        textColor=HexColor("#111111"),
        spaceAfter=8,
        leading=14,
    )
    card_footer_style = _style(
        "CardFooter",
        fontSize=8,
        textColor=HexColor("#888888"),
        alignment=1,
        spaceBefore=16,
    )
    ts = datetime.now().strftime("%m/%d/%Y")

    story = []

    # ── Red header bar (simulate with a single-cell table) ────────────────────
    header_table = Table(
        [[Paragraph(lbl["header"], card_header_style)]],
        colWidths=[4.7 * inch],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#CC0000")),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 14))

    # ── Key fields ────────────────────────────────────────────────────────────
    def _field(label: str, value: str) -> None:
        if value:
            story.append(Paragraph(label.upper(), card_label_style))
            story.append(Paragraph(value, card_value_style))

    _field(lbl["name"],      name or "—")
    _field(lbl["county"],    county or "—")
    _field(lbl["shelter"],   f"{shelter_name}  {shelter_address}".strip() if shelter_name else "—")
    _field(lbl["route"],     route_summary or "—")
    _field(lbl["fire_dept"], fire_dept_phone or "911")
    _field(lbl["evac_time"], evac_time or "—")

    # ── Divider + footer ──────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#cccccc"), spaceAfter=6))
    story.append(Paragraph(f"{lbl['footer']}  |  {ts}", card_footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer
