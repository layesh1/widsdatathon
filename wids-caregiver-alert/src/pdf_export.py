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
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.units import inch
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


def generate_evacuation_plan(
    county: str,
    risk_level: str,
    household: dict,
    checklist_items: list[str] | None = None,
) -> io.BytesIO | None:
    """
    Generates a PDF evacuation plan.
    Returns a BytesIO buffer ready for st.download_button, or None if
    reportlab is not installed.
    """
    if not REPORTLAB_AVAILABLE:
        return None

    if checklist_items is None:
        checklist_items = DEFAULT_CHECKLIST

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

    story = []

    # ── Title ─────────────────────────────────────────────────────────────────
    story.append(Paragraph("🔥 WILDFIRE EVACUATION PLAN", title_style))
    ts = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    story.append(Paragraph(f"Generated for: {county}  |  {ts}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#dddddd"), spaceAfter=14))

    # ── Risk level ────────────────────────────────────────────────────────────
    story.append(Paragraph(f"YOUR RISK LEVEL: {risk_level.upper()}", risk_style))

    # ── Household profile ─────────────────────────────────────────────────────
    story.append(Paragraph("HOUSEHOLD PROFILE", h2_style))
    for key, val in household.items():
        story.append(Paragraph(f"• {key}: {val}", body_style))
    story.append(Spacer(1, 10))

    # ── Checklist ─────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#eeeeee"), spaceAfter=6))
    story.append(Paragraph("EVACUATION CHECKLIST", h2_style))
    for item in checklist_items:
        story.append(Paragraph(f"☐  {item}", body_style))
    story.append(Spacer(1, 10))

    # ── Emergency contacts ────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#eeeeee"), spaceAfter=6))
    story.append(Paragraph("EMERGENCY RESOURCES", h2_style))
    contacts = [
        "Emergency: 911",
        "FEMA Disaster Assistance: 1-800-621-3362",
        "American Red Cross: 1-800-733-2767",
        "Local evacuation info: Dial 211",
        "Road conditions: Call 511",
        "Poison Control: 1-800-222-1222",
        "Crisis & Suicide Lifeline: 988",
    ]
    for c in contacts:
        story.append(Paragraph(f"• {c}", body_style))

    # ── Important notes ───────────────────────────────────────────────────────
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#eeeeee"), spaceAfter=6))
    story.append(Paragraph("IMPORTANT NOTES", h2_style))
    notes = [
        "Leave EARLY — do not wait for a mandatory order if you feel at risk.",
        "Share this plan with all household members and a trusted contact.",
        "Keep your car pointed toward your evacuation route.",
        "If you have mobility limitations, register with your county emergency management office NOW.",
        "Follow official orders only — do not return until the all-clear is given.",
    ]
    for n in notes:
        story.append(Paragraph(f"• {n}", body_style))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "Generated by the Wildfire Caregiver Alert System  ·  49ers Intelligence Lab  ·  WiDS Datathon 2025  "
        "|  For informational purposes only. Always follow official emergency management guidance.",
        footer_style,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer
