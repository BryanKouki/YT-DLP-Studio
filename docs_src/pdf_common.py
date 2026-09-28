"""Estilos e funções auxiliares compartilhadas pelos dois manuais em PDF."""
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem,
    HRFlowable, Image, PageBreak, KeepTogether, NextPageTemplate,
)

RED = colors.HexColor("#E62117")
DARK = colors.HexColor("#1E2024")
GRAY = colors.HexColor("#555555")
LIGHTBG = colors.HexColor("#F2F2F2")
CODEBG = colors.HexColor("#1E2024")
CODEFG = colors.HexColor("#F5F5F5")

_base = getSampleStyleSheet()

STYLES = {
    "cover_title": ParagraphStyle(
        "cover_title", parent=_base["Title"], fontSize=28, leading=32,
        textColor=DARK, alignment=TA_CENTER, spaceAfter=6,
    ),
    "cover_subtitle": ParagraphStyle(
        "cover_subtitle", parent=_base["Normal"], fontSize=14, leading=18,
        textColor=RED, alignment=TA_CENTER, spaceAfter=4, fontName="Helvetica-Bold",
    ),
    "cover_meta": ParagraphStyle(
        "cover_meta", parent=_base["Normal"], fontSize=10, leading=14,
        textColor=GRAY, alignment=TA_CENTER,
    ),
    "h1": ParagraphStyle(
        "h1", parent=_base["Heading1"], fontSize=18, leading=22, spaceBefore=18,
        spaceAfter=8, textColor=DARK, borderPadding=0,
    ),
    "h2": ParagraphStyle(
        "h2", parent=_base["Heading2"], fontSize=13.5, leading=17, spaceBefore=14,
        spaceAfter=6, textColor=RED,
    ),
    "h3": ParagraphStyle(
        "h3", parent=_base["Heading3"], fontSize=11.5, leading=15, spaceBefore=10,
        spaceAfter=4, textColor=DARK, fontName="Helvetica-Bold",
    ),
    "body": ParagraphStyle(
        "body", parent=_base["Normal"], fontSize=10, leading=15, spaceAfter=8,
        textColor=colors.HexColor("#222222"), alignment=TA_LEFT,
    ),
    "bullet": ParagraphStyle(
        "bullet", parent=_base["Normal"], fontSize=10, leading=14.5, spaceAfter=3,
        textColor=colors.HexColor("#222222"),
    ),
    "code": ParagraphStyle(
        "code", parent=_base["Code"], fontSize=8.3, leading=11.5, fontName="Courier",
        textColor=CODEFG, backColor=CODEBG, borderPadding=(8, 10, 8, 10),
        spaceAfter=10, spaceBefore=2,
    ),
    "caption": ParagraphStyle(
        "caption", parent=_base["Normal"], fontSize=8.5, leading=11,
        textColor=GRAY, alignment=TA_LEFT, spaceBefore=2, spaceAfter=10,
    ),
    "toc": ParagraphStyle(
        "toc", parent=_base["Normal"], fontSize=10.5, leading=20,
        textColor=DARK,
    ),
    "footer": ParagraphStyle(
        "footer", parent=_base["Normal"], fontSize=8, textColor=GRAY, alignment=TA_CENTER,
    ),
}


def h1(text):
    return Paragraph(text, STYLES["h1"])


def h2(text):
    return Paragraph(text, STYLES["h2"])


def h3(text):
    return Paragraph(text, STYLES["h3"])


def body(text):
    return Paragraph(text, STYLES["body"])


def caption(text):
    return Paragraph(text, STYLES["caption"])


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(it, STYLES["bullet"]), spaceAfter=3) for it in items],
        bulletType="bullet", start="•", leftIndent=14, bulletFontSize=9,
    )


def numbered(items):
    return ListFlowable(
        [ListItem(Paragraph(it, STYLES["bullet"]), spaceAfter=3) for it in items],
        bulletType="1", leftIndent=16, bulletFontSize=9.5,
    )


def code(text):
    escaped = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    escaped = escaped.replace("\n", "<br/>").replace(" ", "&nbsp;")
    return Paragraph(escaped, STYLES["code"])


def hr():
    return HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#DDDDDD"),
                       spaceBefore=6, spaceAfter=12)


def sp(height=6):
    return Spacer(1, height)


def simple_table(rows, col_widths=None, header=True):
    cell_style = ParagraphStyle(
        "table_cell", parent=_base["Normal"], fontSize=9, leading=12.5,
        textColor=colors.HexColor("#222222"),
    )
    header_style = ParagraphStyle(
        "table_header", parent=cell_style, textColor=colors.white, fontName="Helvetica-Bold",
    )
    wrapped_rows = []
    for r_idx, row in enumerate(rows):
        is_header = header and r_idx == 0
        style = header_style if is_header else cell_style
        wrapped_rows.append([
            cell if not isinstance(cell, str) else Paragraph(cell, style)
            for cell in row
        ])
    t = Table(wrapped_rows, colWidths=col_widths, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ]
    t.setStyle(TableStyle(style))
    return t


def page_decoration(canvas, doc, title):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#DDDDDD"))
    canvas.setLineWidth(0.6)
    canvas.line(2 * cm, 27.7 * cm, A4[0] - 2 * cm, 27.7 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(2 * cm, 27.9 * cm, title)
    canvas.drawRightString(A4[0] - 2 * cm, 1.3 * cm, f"Página {doc.page}")
    canvas.drawString(2 * cm, 1.3 * cm, "YT-DLP Studio")
    canvas.restoreState()
