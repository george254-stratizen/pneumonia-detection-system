"""
report.py

Builds a one-result PDF report (patient, AI output, images, clinician diagnosis).
"""

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modules.analysis import ROOT
from modules.patients import age_text

DISCLAIMER = ("This report was produced with AI decision support. ")


def _img(path, caption, styles, width=5.3 * cm):
    full = ROOT / path if path else None
    if not full or not full.exists():
        return Paragraph(f"{caption}<br/>(image not available)", styles["Small"])
    im = Image(str(full))
    ratio = im.imageHeight / im.imageWidth
    im.drawWidth, im.drawHeight = width, width * ratio
    return [im, Paragraph(caption, styles["Small"])]


def build_pdf(detail: dict, generated_by: str) -> bytes:
    base = getSampleStyleSheet()
    styles = {
        "Title": ParagraphStyle("T", parent=base["Title"], fontSize=18, spaceAfter=4),
        "H": ParagraphStyle("H", parent=base["Heading3"], spaceBefore=10, spaceAfter=4),
        "Body": base["BodyText"],
        "Small": ParagraphStyle("S", parent=base["BodyText"], fontSize=8, alignment=1),
        "Disc": ParagraphStyle("D", parent=base["BodyText"], fontSize=8, textColor=colors.grey),
    }
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title=f"X-ray report {detail['patient_number']}")
    d = detail
    now = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    story = [
        Paragraph("Chest X-ray Analysis Report", styles["Title"]),
        Paragraph(f"Generated {now} (EAT) by {generated_by}", styles["Disc"]),
        Paragraph("Patient", styles["H"]),
    ]

    def table(rows):
        t = Table(rows, colWidths=[4.2 * cm, 12.8 * cm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    story.append(table([
        ["Patient number", d["patient_number"]],
        ["Name", f"{d['first_name']} {d['last_name']}"],
        ["Age / Gender", f"{age_text(d['date_of_birth'])} / {d['gender']}"],
        ["X-ray file", f"{d['file_name']} (uploaded {d['upload_date']})"],
    ]))

    story.append(Paragraph("AI result", styles["H"]))
    story.append(table([
        ["Prediction", f"{d['prediction']}  ({d['confidence']:.1%} confidence)"],
        ["Probability of pneumonia", f"{d['probability']:.1%}"],
        ["Model", f"{d['model_name']} v{d['model_version']}, {d['technique']} preprocessing"],
        ["Analysed", d["date"]],
    ]))
    if d["confidence"] < 0.70:
        story.append(Paragraph("<b>Low confidence result. Review carefully.</b>", styles["Body"]))

    cells = [_img(d["file_path"], "Original", styles),
             _img(d["processed_image_path"], "After CLAHE", styles),
             _img(d["heatmap_path"], "Grad-CAM", styles)]
    story += [Spacer(1, 8), Table([cells], colWidths=[5.7 * cm] * 3)]
    story.append(Paragraph("The heatmap shows where the model looked; it is not a confirmed "
                           "lesion location.", styles["Disc"]))

    story.append(Paragraph("Clinician diagnosis", styles["H"]))
    if d["final_diagnosis"]:
        verdict = "Agrees with AI" if d["agreed"] else "Differs from AI"
        story.append(table([
            ["Final diagnosis", f"{d['final_diagnosis']}  ({verdict})"],
            ["Recorded by", f"{d['diagnosed_by']} on {d['diagnosis_date']}"],
            ["Notes", d["diagnosis_notes"] or "-"],
        ]))
    else:
        story.append(Paragraph("Not yet recorded by a clinician.", styles["Body"]))

    story += [Spacer(1, 14), Paragraph(DISCLAIMER, styles["Disc"])]
    doc.build(story)
    return buf.getvalue()