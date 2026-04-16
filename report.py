import logging
import os
from datetime import datetime, timedelta

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak

from config import LOGO_PATH

logger = logging.getLogger(__name__)

LBL_GREEN = colors.Color(0, 0.5, 0, 1)
LIGHT_GREEN = colors.Color(0.94, 0.98, 0.94)
DARK_GREEN = colors.Color(0, 0.38, 0, 1)

COLUMN_LABELS = {
    'batter_name': 'Player',
    'playId': 'Video',
    'launch_speed': 'Exit Velo',
    'launch_angle': 'Launch Angle',
    'events': 'Result',
}

EVENT_LABELS = {
    'home_run': 'Home Run',
    'field_out': 'Field Out',
    'single': 'Single',
    'double': 'Double',
    'triple': 'Triple',
    'sacrifice_fly': 'Sac Fly',
    'sac_fly_double_play': 'Sac Fly DP',
    'field_error': 'Field Error',
}

COL_WIDTHS = [2.0*inch, 0.55*inch, 0.95*inch, 1.1*inch, 1.1*inch]


def create_definitions_page():
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Definitions", ParagraphStyle(
            name='DefinitionsTitle', parent=styles['Title'],
            textColor=LBL_GREEN, fontSize=18, alignment=1, spaceAfter=12,
        )),
        Spacer(1, 0.2 * inch),
    ]
    definition_style = ParagraphStyle(
        name='Definition', parent=styles['Normal'], fontSize=10, spaceAfter=10,
    )
    definitions = [
        ("Action Item", "Per Keenan's Statcast query, a non-client batted ball to LF/RF that is not a home run and >= 365 ft, or to CF and >= 380 ft."),
        ("Front Row Joe", "For clients only. A home run to LF/RF <= 350 ft, or to CF <= 380 ft."),
    ]
    for term, definition in definitions:
        elements.append(Paragraph(f"<b>{term}:</b> {definition}", definition_style))
    elements.append(PageBreak())
    return elements


def create_styled_table(df: pd.DataFrame, title: str):
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(title, ParagraphStyle(
            name='SectionTitle', parent=styles['Title'],
            textColor=LBL_GREEN, fontSize=15, alignment=1, spaceAfter=8,
        )),
    ]

    if df.empty:
        elements.append(Paragraph("No results.", ParagraphStyle(
            name='Empty', parent=styles['Normal'],
            fontSize=9, textColor=colors.gray, alignment=1, spaceAfter=20,
        )))
        elements.append(Spacer(1, 0.25 * inch))
        return elements

    df = df.drop(columns=['batter'], errors='ignore').copy()
    df['playId'] = df['playId'].apply(
        lambda x: f'<link href="https://baseballsavant.mlb.com/sporty-videos?playId={x}">Link</link>'
    )
    df['events'] = df['events'].map(EVENT_LABELS).fillna(df['events'])
    df[['launch_speed', 'launch_angle']] = df[['launch_speed', 'launch_angle']].round(1)
    df.columns = [COLUMN_LABELS.get(c, c) for c in df.columns]

    header_style = ParagraphStyle(name='Header', parent=styles['Normal'],
                                  fontSize=9, textColor=colors.white, fontName='Helvetica-Bold')
    cell_style = ParagraphStyle(name='Cell', parent=styles['Normal'], fontSize=8.5)

    header = [Paragraph(col, header_style) for col in df.columns]
    rows = [
        [Paragraph(str(cell), cell_style) if isinstance(cell, str) else cell for cell in row]
        for row in df.values.tolist()
    ]
    data = [header] + rows

    t = Table(data, colWidths=COL_WIDTHS, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), LBL_GREEN),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8.5),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GREEN]),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, DARK_GREEN),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.Color(0.85, 0.85, 0.85)),
        ('BOX', (0, 0), (-1, -1), 1, LBL_GREEN),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.4 * inch))
    return elements


def create_daily_report(action_items: pd.DataFrame, frjs: pd.DataFrame, client_hrs: pd.DataFrame, output_filename: str):
    doc = SimpleDocTemplate(
        output_filename, pagesize=letter,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
    )
    styles = getSampleStyleSheet()
    elements = []

    if os.path.exists(LOGO_PATH):
        elements.append(Image(LOGO_PATH, width=1.1*inch, height=1.1*inch))
        elements.append(Spacer(1, 0.15*inch))
    else:
        logger.warning(f"Logo not found at {LOGO_PATH}, skipping")

    elements.append(Paragraph("Daily Longball Labs Report", ParagraphStyle(
        name='ReportTitle', parent=styles['Title'],
        textColor=LBL_GREEN, fontSize=22, alignment=1, spaceAfter=4,
    )))
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%B %-d, %Y")
    elements.append(Paragraph(yesterday, ParagraphStyle(
        name='DateRange', parent=styles['Normal'],
        alignment=1, fontSize=10, textColor=colors.darkgray, spaceAfter=20,
    )))

    elements.extend(create_definitions_page())
    elements.extend(create_styled_table(action_items, "Action Items"))
    elements.extend(create_styled_table(frjs, "Front Row Joes"))
    elements.extend(create_styled_table(client_hrs, "Client Home Runs"))
    doc.build(elements)
