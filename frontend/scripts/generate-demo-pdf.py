#!/usr/bin/env python3
"""Generate the deterministic MagicFin static-demo report from its checked-in snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "src" / "demo-report-snapshot.json"
OUTPUT_PATH = ROOT / "public" / "magicfin-demo-reviewed-report.pdf"

INK = colors.HexColor("#191815")
MUTED = colors.HexColor("#68645C")
PAPER = colors.HexColor("#F7F4EE")
SURFACE = colors.HexColor("#FFFDF8")
RULE = colors.HexColor("#D9D2C7")
GREEN = colors.HexColor("#2F704C")
MAGIC = colors.HexColor("#5E4B8B")
RED = colors.HexColor("#9F3B32")


def build_pdf(snapshot: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=24,
        leading=27,
        textColor=INK,
        spaceAfter=5,
    )
    eyebrow = ParagraphStyle(
        "Eyebrow",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        tracking=1.1,
        textColor=MAGIC,
        uppercase=True,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.4,
        leading=12.2,
        textColor=MUTED,
    )
    small = ParagraphStyle("Small", parent=body, fontSize=7, leading=9.4)
    metric_label = ParagraphStyle(
        "MetricLabel", parent=small, fontName="Helvetica-Bold", textColor=MUTED
    )
    metric_value = ParagraphStyle(
        "MetricValue",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=20,
        leading=22,
        textColor=INK,
    )
    right_small = ParagraphStyle("RightSmall", parent=small, alignment=TA_RIGHT)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"MagicFin - {snapshot['company']} {snapshot['period']} reviewed report",
        author="MagicFin",
    )

    story = []
    header = Table(
        [
            [
                Paragraph("MAGICFIN / REVIEWED DEMO REPORT", eyebrow),
                Paragraph(snapshot["data_state"], right_small),
            ],
            [
                Paragraph(snapshot["company"], title),
                Paragraph(
                    snapshot["period"],
                    ParagraphStyle(
                        "Period", parent=title, alignment=TA_RIGHT, fontSize=15, textColor=MAGIC
                    ),
                ),
            ],
        ],
        colWidths=[125 * mm, 38 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, -1), (-1, -1), 1.2, INK),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
            ]
        )
    )
    story.extend(
        [
            header,
            Spacer(1, 7 * mm),
            Paragraph("EXECUTIVE PERFORMANCE BRIEF", eyebrow),
            Spacer(1, 2 * mm),
            Paragraph(
                snapshot["executive_brief"],
                ParagraphStyle(
                    "Brief",
                    parent=body,
                    fontName="Times-Roman",
                    fontSize=12,
                    leading=17,
                    textColor=INK,
                ),
            ),
            Spacer(1, 6 * mm),
        ]
    )

    metric_cells = []
    for item in snapshot["headline_metrics"]:
        metric_cells.append(
            [
                Paragraph(item["label"], metric_label),
                Paragraph(item["value"], metric_value),
                Paragraph(item["change"], small),
                Paragraph(item["source"], small),
            ]
        )
    metrics = Table(
        [metric_cells[:2], metric_cells[2:]],
        colWidths=[81.5 * mm, 81.5 * mm],
        rowHeights=[35 * mm, 35 * mm],
    )
    metrics.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.7, RULE),
                ("INNERGRID", (0, 0), (-1, -1), 0.7, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([metrics, Spacer(1, 7 * mm)])

    trend_rows = [
        [
            Paragraph("Period", metric_label),
            Paragraph("Revenue (USD millions)", metric_label),
            Paragraph("Type", metric_label),
            Paragraph("Source", metric_label),
        ]
    ]
    for point in snapshot["trend"]:
        trend_rows.append(
            [
                point["period"],
                f"${point['revenue_usd_m']:,.1f}m",
                "Reported history",
                "Financials fixture",
            ]
        )
    trend = Table(trend_rows, colWidths=[28 * mm, 46 * mm, 43 * mm, 46 * mm], repeatRows=1)
    trend.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PAPER),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("TEXTCOLOR", (0, 1), (-1, -1), MUTED),
                ("GRID", (0, 0), (-1, -1), 0.5, RULE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend(
        [Paragraph("REPORTED TRAJECTORY", eyebrow), Spacer(1, 2 * mm), trend, Spacer(1, 7 * mm)]
    )

    findings = [
        Paragraph(f"<b>{index}.</b> {finding}", body)
        for index, finding in enumerate(snapshot["material_findings"], 1)
    ]
    finding_box = Table(
        [[Paragraph("MATERIAL FINDINGS", eyebrow)], *[[item] for item in findings]],
        colWidths=[163 * mm],
    )
    finding_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.7, RULE),
                ("LINEABOVE", (0, 0), (-1, 0), 2, RED),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([KeepTogether(finding_box), Spacer(1, 6 * mm)])

    limitation_text = "<br/>".join(f"- {item}" for item in snapshot["limitations"])
    footer_box = Table(
        [
            [Paragraph("BOUNDARIES", eyebrow), Paragraph(snapshot["review_status"], right_small)],
            [
                Paragraph(limitation_text, small),
                Paragraph(
                    f"Snapshot: {snapshot['snapshot_id']}<br/>Reviewed: {snapshot['reviewed_at']}",
                    right_small,
                ),
            ],
        ],
        colWidths=[112 * mm, 51 * mm],
    )
    footer_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PAPER),
                ("BOX", (0, 0), (-1, -1), 0.7, RULE),
                ("LINEABOVE", (0, 0), (-1, 0), 2, GREEN),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(footer_box)

    def on_page(canvas, document):
        canvas.saveState()
        canvas.setFillColor(PAPER)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(
            16 * mm,
            7 * mm,
            "MagicFin verified synthetic fixture - evidence support, not financial advice",
        )
        canvas.drawRightString(A4[0] - 16 * mm, 7 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


if __name__ == "__main__":
    build_pdf(json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8")), OUTPUT_PATH)
    print(OUTPUT_PATH)
