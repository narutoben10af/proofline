from __future__ import annotations

import hashlib
import html
import io
import re
import unicodedata
from decimal import Decimal

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from proofline.contracts import Classification, MetricId
from proofline.report_contracts import (
    CACHED_BANNER,
    LIVE_BANNER,
    NO_CAUSATION,
    ReportRenderBundle,
    SourceMode,
    canonical_json_bytes,
    primary_metric_label,
    report_claim_text,
    report_finding_rationale,
    secondary_metric_label,
)

PAPER = colors.HexColor("#F7F4EE")
SURFACE = colors.HexColor("#FFFDF8")
WASH = colors.HexColor("#EFEAE1")
INK = colors.HexColor("#191815")
MUTED = colors.HexColor("#625F58")
RULE = colors.HexColor("#D8D2C8")
RED = colors.HexColor("#B52D24")
RED_WASH = colors.HexColor("#F6E2DE")
GREEN = colors.HexColor("#2F704C")
GREEN_WASH = colors.HexColor("#E3EEE6")
AMBER = colors.HexColor("#815000")
AMBER_WASH = colors.HexColor("#F4EAD4")

_CORE_REPLACEMENTS = {
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
}
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class _DeterministicCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs) -> None:
        kwargs["invariant"] = 1
        kwargs["pageCompression"] = 1
        super().__init__(*args, **kwargs)


def _core_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    output: list[str] = []
    for character in text:
        replacement = _CORE_REPLACEMENTS.get(character, character)
        try:
            replacement.encode("cp1252")
            output.append(replacement)
        except UnicodeEncodeError:
            output.append(f"[U+{ord(character):04X}]")
    return "".join(output)


def _safe(value: object) -> str:
    return html.escape(_core_text(value), quote=False)


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_safe(value), style)


def _rich(value: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_core_text(value), style)


def _decimal_display(value: Decimal) -> str:
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _percent_display(value: Decimal) -> str:
    return f"{_decimal_display(value * 100)}%"


def _human_date(value) -> str:
    return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"


def _classification_colors(classification: Classification):
    return {
        Classification.SUPPORTED: (GREEN, GREEN_WASH),
        Classification.UNCERTAIN: (AMBER, AMBER_WASH),
        Classification.CONTRADICTED: (RED, RED_WASH),
    }[classification]


def _styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    definitions = (
        ("Brand", "Times-Bold", 22, 24, INK, TA_LEFT),
        ("Deck", "Helvetica-Bold", 7.5, 10, MUTED, TA_LEFT),
        ("ReportTitle", "Times-Roman", 28, 31, INK, TA_LEFT),
        ("Subtitle", "Helvetica", 10, 14, MUTED, TA_LEFT),
        ("Eyebrow", "Helvetica-Bold", 7.2, 9, RED, TA_LEFT),
        ("Section", "Times-Roman", 21, 24, INK, TA_LEFT),
        ("Subsection", "Times-Roman", 14, 17, INK, TA_LEFT),
        ("Body", "Helvetica", 8.5, 12.2, INK, TA_LEFT),
        ("BodySmall", "Helvetica", 7.6, 10.6, MUTED, TA_LEFT),
        ("BoxLabel", "Helvetica-Bold", 7, 9, INK, TA_LEFT),
        ("CardLabel", "Helvetica-Bold", 6.6, 8, MUTED, TA_LEFT),
        ("CardMeta", "Helvetica", 6.8, 8.7, MUTED, TA_LEFT),
        ("EvidenceMeta", "Courier", 6.1, 8, MUTED, TA_LEFT),
        ("MetricNumber", "Times-Bold", 19, 23, INK, TA_LEFT),
        ("StatusNumber", "Times-Bold", 18, 21, INK, TA_LEFT),
        ("RatioName", "Helvetica", 9, 12, INK, TA_LEFT),
        ("RatioValue", "Times-Bold", 16, 19, INK, TA_RIGHT),
        ("TableHeader", "Helvetica-Bold", 6.8, 8.5, SURFACE, TA_LEFT),
        ("TableCell", "Helvetica", 6.9, 9.2, INK, TA_LEFT),
        ("BulletMark", "Times-Bold", 14, 13, RED, TA_LEFT),
        ("FindingNumber", "Times-Bold", 18, 21, INK, TA_LEFT),
        ("FindingTitle", "Times-Bold", 12.5, 15, INK, TA_LEFT),
    )
    for name, font, size, leading, color, alignment in definitions:
        styles.add(
            ParagraphStyle(
                name,
                parent=styles["Normal"],
                fontName=font,
                fontSize=size,
                leading=leading,
                textColor=color,
                alignment=alignment,
                spaceAfter=3,
            )
        )
    return styles


def _section(title: str, kicker: str, styles) -> list:
    return [
        KeepTogether(
            [
                _paragraph(kicker.upper(), styles["Eyebrow"]),
                Spacer(1, 1.5 * mm),
                _paragraph(title, styles["Section"]),
                Spacer(1, 1.5 * mm),
                HRFlowable(width="100%", thickness=0.6, color=RULE, spaceAfter=4 * mm),
            ]
        )
    ]


def _note_box(title: str, body: str, styles, *, tone: str = "neutral") -> Table:
    accent, background = {
        "neutral": (INK, WASH),
        "green": (GREEN, GREEN_WASH),
        "amber": (AMBER, AMBER_WASH),
        "red": (RED, RED_WASH),
    }[tone]
    content = [_paragraph(title.upper(), styles["BoxLabel"]), _paragraph(body, styles["Body"])]
    table = Table([[content]], colWidths=(170 * mm,), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _summary_bullets(items: list[tuple[str, str]], styles) -> Table:
    rows = [
        [
            _paragraph("+", styles["BulletMark"]),
            _rich(f"<b>{_safe(label)}</b> {_safe(body)}", styles["Body"]),
        ]
        for label, body in items
    ]
    table = Table(rows, colWidths=(8 * mm, 162 * mm), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _status_strip(bundle: ReportRenderBundle, styles) -> Table:
    counts = bundle.snapshot.classification_counts
    items = (
        ("Supported", counts.supported, GREEN, GREEN_WASH),
        ("Uncertain", counts.uncertain, AMBER, AMBER_WASH),
        ("Contradicted", counts.contradicted, RED, RED_WASH),
    )
    cells = [
        [
            _paragraph(label.upper(), styles["CardLabel"]),
            _paragraph(value, styles["StatusNumber"]),
            _paragraph(
                "reviewed finding" if value == 1 else "reviewed findings", styles["CardMeta"]
            ),
        ]
        for label, value, _accent, _background in items
    ]
    table = Table([cells], colWidths=(56.67 * mm,) * 3, hAlign="LEFT")
    commands = [
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]
    for index, (_label, _value, accent, background) in enumerate(items):
        commands.extend(
            [
                ("BACKGROUND", (index, 0), (index, 0), background),
                ("LINEBELOW", (index, 0), (index, 0), 2.2, accent),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def _metric_cards(primary, styles) -> Table:
    cells = [
        [
            _paragraph(primary_metric_label(item.concept).upper(), styles["CardLabel"]),
            _paragraph(item.display_value, styles["MetricNumber"]),
            _paragraph(item.unit, styles["CardMeta"]),
            _paragraph(f"Period end {_human_date(item.period.end)}", styles["CardMeta"]),
            _paragraph(f"Evidence {item.source_span_id}", styles["EvidenceMeta"]),
        ]
        for item in primary
    ]
    table = Table([cells], colWidths=(42.5 * mm,) * 4, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.6, RULE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


_INTERPRETATIONS = {
    MetricId.REVENUE_GROWTH_YOY: (
        "Growth",
        "Compares revenue with the prior comparable period. A positive result means reported "
        "revenue was higher; it does not establish why it changed or whether it will persist.",
    ),
    MetricId.OPERATING_MARGIN: (
        "Profitability",
        "Shows operating profit earned for each unit of revenue. It helps assess operating "
        "efficiency, but issuer definitions and one-off items can affect comparability.",
    ),
    MetricId.CURRENT_RATIO: (
        "Liquidity",
        "Shows current assets available per unit of current liabilities at the reporting date. "
        "It is a point-in-time coverage indicator, not a direct measure of cash or solvency.",
    ),
    MetricId.FCF_MARGIN: (
        "Cash flow",
        "Shows project-defined free cash flow after capital expenditure as a share of revenue. "
        "This is a non-GAAP view and depends on the stated capital-expenditure sign convention.",
    ),
}


def _ratio_rows(bundle, results, findings_by_result, styles) -> Table:
    rows = []
    for result_id in bundle.report_profile.secondary_metric_result_ids:
        result = results[result_id]
        label, interpretation = _INTERPRETATIONS[result.metric_id]
        if result.result is None:
            value = "Not calculated"
            note = f"Exceptional state: {result.exceptional_state.value}."
        elif result.metric_id == MetricId.CURRENT_RATIO:
            value, note = f"{_decimal_display(result.result)}x", "Calculated from cited inputs."
        else:
            value, note = _percent_display(result.result), "Calculated from cited inputs."
        finding = findings_by_result.get(result_id)
        status = finding.classification.value.upper() if finding else "CALCULATED"
        accent = _classification_colors(finding.classification)[0] if finding else INK
        rows.append(
            [
                _rich(
                    f"<b>{_safe(label)}</b><br/><font size='8'>"
                    f"{_safe(secondary_metric_label(result.metric_id))}</font>",
                    styles["RatioName"],
                ),
                _paragraph(value, styles["RatioValue"]),
                _rich(
                    f"<font color='{accent.hexval()}'><b>{_safe(status)}</b></font>"
                    f"<br/>{_safe(note)}",
                    styles["TableCell"],
                ),
                _paragraph(interpretation, styles["TableCell"]),
            ]
        )
    table = Table(rows, colWidths=(34 * mm, 25 * mm, 39 * mm, 72 * mm), hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]
    for row in range(len(rows)):
        if row % 2:
            commands.append(("BACKGROUND", (0, row), (-1, row), PAPER))
    table.setStyle(TableStyle(commands))
    return table


def _evidence_table(rows, widths, styles, *, compact: bool = False) -> Table:
    rendered = [
        [
            _paragraph(cell, styles["TableHeader"] if row_index == 0 else styles["TableCell"])
            for cell in row
        ]
        for row_index, row in enumerate(rows)
    ]
    table = Table(rendered, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("BOX", (0, 0), (-1, -1), 0.55, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4 if compact else 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 if compact else 6),
    ]
    for row in range(1, len(rows)):
        commands.append(("BACKGROUND", (0, row), (-1, row), SURFACE if row % 2 else PAPER))
    table.setStyle(TableStyle(commands))
    return table


def _trend_chart(bundle: ReportRenderBundle, styles) -> list:
    trend = bundle.trend
    if trend is None:
        return []
    values = [float(point.value) for point in trend.points]
    labels = [str(point.period.end.year) for point in trend.points]
    width, height = 170 * mm, 73 * mm
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=SURFACE, strokeColor=RULE, strokeWidth=0.6))
    left, bottom, chart_width, chart_height = 18 * mm, 15 * mm, 140 * mm, 44 * mm
    maximum, minimum = max(values), min(0.0, min(values))
    span = maximum - minimum or 1.0
    baseline = bottom + (0 - minimum) / span * chart_height
    for step in range(5):
        y = bottom + chart_height * step / 4
        drawing.add(Line(left, y, left + chart_width, y, strokeColor=RULE, strokeWidth=0.35))
        tick = minimum + span * step / 4
        drawing.add(
            String(
                left - 3 * mm,
                y - 1.5 * mm,
                f"{tick:g}",
                textAnchor="end",
                fontName="Helvetica",
                fontSize=6.5,
                fillColor=MUTED,
            )
        )
    drawing.add(
        Line(left, baseline, left + chart_width, baseline, strokeColor=INK, strokeWidth=0.8)
    )
    slot = chart_width / len(values)
    bar_width = min(22 * mm, slot * 0.48)
    for index, (label, value) in enumerate(zip(labels, values, strict=True)):
        x = left + slot * index + (slot - bar_width) / 2
        value_y = bottom + (value - minimum) / span * chart_height
        bar_bottom = min(baseline, value_y)
        drawing.add(
            Rect(
                x,
                bar_bottom,
                bar_width,
                max(0.8, abs(value_y - baseline)),
                fillColor=RED if value < 0 else GREEN,
                strokeColor=INK,
                strokeWidth=0.45,
            )
        )
        drawing.add(
            String(
                x + bar_width / 2,
                max(value_y, baseline) + 2.2 * mm,
                f"{value:g}",
                textAnchor="middle",
                fontName="Helvetica-Bold",
                fontSize=8,
                fillColor=INK,
            )
        )
        drawing.add(
            String(
                x + bar_width / 2,
                7 * mm,
                label,
                textAnchor="middle",
                fontName="Helvetica",
                fontSize=8,
                fillColor=MUTED,
            )
        )
    drawing.add(
        String(
            width - 8 * mm,
            height - 8 * mm,
            _core_text(trend.unit),
            textAnchor="end",
            fontName="Helvetica",
            fontSize=7,
            fillColor=MUTED,
        )
    )
    rows = [["Period", "Exact value", "Reporting basis", "Evidence"]]
    rows.extend(
        [
            _human_date(point.period.end),
            _decimal_display(point.value),
            point.reporting_basis,
            point.evidence_source_span_id,
        ]
        for point in trend.points
    )
    return [
        drawing,
        Spacer(1, 2.5 * mm),
        _evidence_table(rows, (30 * mm, 28 * mm, 72 * mm, 40 * mm), styles, compact=True),
    ]


def _finding_block(index, finding, claim, result, styles) -> Table:
    accent, background = _classification_colors(finding.classification)
    outcome = (
        _decimal_display(result.result)
        if result.result is not None
        else f"Exceptional state: {result.exceptional_state.value}"
    )
    warning_count = len(result.warnings + finding.warnings)
    warning = f" {warning_count} warning(s) remain in the evidence export." if warning_count else ""
    left = [
        _paragraph(f"{index:02d}", styles["FindingNumber"]),
        _paragraph(finding.classification.value.upper(), styles["CardLabel"]),
    ]
    right = [
        _paragraph(report_claim_text(claim), styles["FindingTitle"]),
        _paragraph(
            f"Calculated result: {outcome}. {report_finding_rationale(claim, result)}{warning}",
            styles["Body"],
        ),
        _paragraph(
            f"Evidence trail: claim {claim.source_span_id}; "
            f"inputs {', '.join(result.input_observation_ids)}.",
            styles["EvidenceMeta"],
        ),
    ]
    table = Table([[left, right]], colWidths=(28 * mm, 142 * mm), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), background),
                ("BACKGROUND", (1, 0), (1, 0), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.55, RULE),
                ("LINEBEFORE", (0, 0), (0, 0), 3, accent),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _page_frame(pdf: canvas.Canvas, document: SimpleDocTemplate) -> None:
    pdf.saveState()
    page_number = pdf.getPageNumber()
    pdf.setTitle(_core_text(document.title))
    pdf.setAuthor("MagicFin / Proofline")
    pdf.setSubject("Reviewed executive financial evidence report")
    pdf.setCreator("MagicFin deterministic ReportLab renderer")
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
    if page_number > 1:
        pdf.setStrokeColor(RULE)
        pdf.setLineWidth(0.5)
        pdf.line(18 * mm, A4[1] - 12.5 * mm, A4[0] - 18 * mm, A4[1] - 12.5 * mm)
        pdf.setFont("Times-Bold", 8)
        pdf.setFillColor(INK)
        pdf.drawString(18 * mm, A4[1] - 9.5 * mm, "MagicFin")
        pdf.setFont("Helvetica", 6.5)
        pdf.setFillColor(MUTED)
        pdf.drawRightString(A4[0] - 18 * mm, A4[1] - 9.5 * mm, _core_text(document.title))
    pdf.setStrokeColor(RULE)
    pdf.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
    pdf.setFont("Helvetica", 6.4)
    pdf.setFillColor(MUTED)
    pdf.drawString(18 * mm, 8.8 * mm, "EDITORIAL LEDGER - PROTOTYPE - HUMAN REVIEW REQUIRED")
    pdf.drawCentredString(A4[0] / 2, 8.8 * mm, _core_text(document._magicfin_snapshot))
    pdf.drawRightString(A4[0] - 18 * mm, 8.8 * mm, f"PAGE {page_number:02d}")
    pdf.restoreState()


def render_pdf(bundle: ReportRenderBundle) -> bytes:
    """Render only the supplied immutable bundle; this function performs no I/O or calculation."""

    buffer = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=_core_text(bundle.snapshot.title),
        author="MagicFin / Proofline",
        subject="Reviewed executive financial evidence report",
        pageCompression=1,
    )
    doc._magicfin_snapshot = bundle.snapshot.snapshot_id
    findings = {finding.id: finding for finding in bundle.analysis.findings}
    claims = {claim.id: claim for claim in bundle.analysis.claims}
    results = {result.id: result for result in bundle.analysis.metric_results}
    observations = {item.id: item for item in bundle.analysis.observations}
    ordered = [findings[item] for item in bundle.snapshot.finding_ids]
    findings_by_result = {finding.metric_result_id: finding for finding in ordered}
    primary = [observations[item] for item in bundle.report_profile.primary_observation_ids]
    counts = bundle.snapshot.classification_counts
    hero = ordered[0]
    hero_claim, hero_result = claims[hero.claim_id], results[hero.metric_result_id]
    hero_outcome = (
        _decimal_display(hero_result.result)
        if hero_result.result is not None
        else hero_result.exceptional_state.value
    )
    banner = CACHED_BANNER if bundle.source_mode == SourceMode.VERIFIED_CACHED else LIVE_BANNER
    story: list = []

    story.extend(
        [
            _paragraph("MagicFin", styles["Brand"]),
            _paragraph("EDITORIAL LEDGER  /  REVIEWED FINANCIAL EVIDENCE", styles["Deck"]),
            Spacer(1, 13 * mm),
            _paragraph(bundle.company, styles["Eyebrow"]),
            _paragraph("Reviewed financial evidence report", styles["ReportTitle"]),
            _paragraph(
                "Reporting period ended "
                f"{_human_date(bundle.report_profile.reporting_period.end)}. A deterministic "
                "comparison of selected narrative claims with cited financial evidence.",
                styles["Subtitle"],
            ),
            Spacer(1, 7 * mm),
        ]
    )
    meta = Table(
        [
            ["REVIEW STATE", "REVIEWED ON", "SOURCE MODE", "SNAPSHOT"],
            [
                bundle.report_profile.reviewer_state.upper(),
                _human_date(bundle.snapshot.reviewed_at.date()),
                bundle.source_mode.value.replace("_", " ").upper(),
                bundle.snapshot.snapshot_id,
            ],
        ],
        colWidths=(34 * mm, 38 * mm, 43 * mm, 55 * mm),
        hAlign="LEFT",
    )
    meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.6, RULE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, RULE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 6.3),
                ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, 1), 7.3),
                ("TEXTCOLOR", (0, 1), (-1, 1), INK),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([meta, Spacer(1, 8 * mm)])
    story.extend(_section("1. Executive summary", "Bottom line", styles))
    story.append(
        _summary_bullets(
            [
                (
                    "The evidence set is mostly aligned.",
                    f"Of {len(ordered)} reviewed findings, {counts.supported} are supported, "
                    f"{counts.uncertain} are uncertain, and {counts.contradicted} are "
                    "contradicted.",
                ),
                (
                    "The lead item needs a clear reviewer disposition.",
                    f"{report_claim_text(hero_claim)} The deterministic result is {hero_outcome}.",
                ),
                (
                    "Read the ratios as indicators, not conclusions.",
                    "Profitability, liquidity, cash-flow and growth measures describe different "
                    "parts of the financial picture; each is translated in plain English on the "
                    "next page.",
                ),
                (
                    "Scope is deliberately bounded.",
                    "This report verifies supplied evidence. It makes no investment "
                    "recommendation, "
                    "forecast, causation claim or unsupported corporate assertion.",
                ),
            ],
            styles,
        )
    )
    story.extend([Spacer(1, 3 * mm), _status_strip(bundle, styles), Spacer(1, 4 * mm)])
    story.append(
        _note_box(
            f"Lead finding - {hero.classification.value}",
            f"{report_claim_text(hero_claim)} {report_finding_rationale(hero_claim, hero_result)}",
            styles,
            tone={
                Classification.SUPPORTED: "green",
                Classification.UNCERTAIN: "amber",
                Classification.CONTRADICTED: "red",
            }[hero.classification],
        )
    )
    story.extend(
        [
            Spacer(1, 2 * mm),
            _paragraph(banner, styles["BodySmall"]),
            _paragraph(bundle.source_disclosure, styles["BodySmall"]),
        ]
    )

    story.append(PageBreak())
    story.extend(
        _section("2. Four primary financial metrics", "Financial position at a glance", styles)
    )
    story.append(
        _paragraph(
            "These four cited observations are the report's headline amounts. They are displayed "
            "exactly as supplied in the immutable bundle; the renderer does not recalculate them.",
            styles["Body"],
        )
    )
    story.extend([Spacer(1, 3 * mm), _metric_cards(primary, styles), Spacer(1, 9 * mm)])
    story.extend(_section("3. Secondary ratios", "What the numbers mean", styles))
    story.append(
        _paragraph(
            "The ratios below answer different questions. The status refers to the related "
            "narrative-versus-numbers review, while the explanation describes how to interpret "
            "the metric.",
            styles["Body"],
        )
    )
    story.extend(
        [
            Spacer(1, 3 * mm),
            _ratio_rows(bundle, results, findings_by_result, styles),
            Spacer(1, 5 * mm),
        ]
    )
    story.append(
        _note_box(
            "Reader guidance",
            "No single ratio determines financial quality. Read profitability with revenue and "
            "operating profit, liquidity with the balance-sheet date, and cash-flow measures with "
            "their non-GAAP definition and sign convention.",
            styles,
        )
    )

    story.append(PageBreak())
    story.extend(_section("4. Historical trend and value table", "Performance evidence", styles))
    if bundle.trend is not None:
        story.append(
            _paragraph(
                f"{bundle.trend.indicator} across the reviewed historical periods",
                styles["Subsection"],
            )
        )
        story.append(
            _paragraph(
                "The columns show direction and relative magnitude across the available annual "
                "anchor periods. With only a small number of observations, this is a discrete "
                "period comparison rather than a detailed time-series pattern. Exact values "
                "follow.",
                styles["Body"],
            )
        )
        story.extend([Spacer(1, 2 * mm), *_trend_chart(bundle, styles)])
    else:
        story.append(
            _note_box(
                "Trend unavailable",
                "No validated historical trend was supplied in the immutable report bundle.",
                styles,
                tone="amber",
            )
        )
    story.append(Spacer(1, 8 * mm))
    story.extend(_section("5. Exceptions and review risks", "Review queue", styles))
    exception_results = [item for item in results.values() if item.exceptional_state is not None]
    review_risks = [
        item
        for item in ordered
        if item.classification in {Classification.UNCERTAIN, Classification.CONTRADICTED}
    ]
    story.append(
        _paragraph(
            f"{len(exception_results)} metric calculation(s) ended in an exceptional state and "
            f"{len(review_risks)} finding(s) require reviewer attention. These are evidence-review "
            "flags, not predictions or advice.",
            styles["Body"],
        )
    )
    if review_risks:
        risk_rows = [["Priority", "State", "Narrative claim", "Reviewer action"]]
        for index, finding in enumerate(review_risks, start=1):
            risk_rows.append(
                [
                    f"R{index}",
                    finding.classification.value.upper(),
                    report_claim_text(claims[finding.claim_id]),
                    finding.suggested_investigation or "Verify the cited source evidence.",
                ]
            )
        story.extend(
            [
                Spacer(1, 2 * mm),
                _evidence_table(risk_rows, (15 * mm, 26 * mm, 52 * mm, 77 * mm), styles),
            ]
        )
    else:
        story.append(
            _note_box(
                "No open review flags",
                "All supplied findings are supported under the fixed policy and tolerance rules.",
                styles,
                tone="green",
            )
        )

    story.append(PageBreak())
    story.extend(_section("6. Narrative-versus-numbers findings", "Evidence review", styles))
    story.append(
        _paragraph(
            "Each item compares a reviewed narrative claim with a deterministic metric result. "
            "Classification reflects the fixed policy and cited inputs; it is not an accounting "
            "opinion.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 3 * mm))
    for index, finding in enumerate(ordered, start=1):
        story.append(
            KeepTogether(
                _finding_block(
                    index,
                    finding,
                    claims[finding.claim_id],
                    results[finding.metric_result_id],
                    styles,
                )
            )
        )
        story.append(Spacer(1, 3 * mm))
    story.append(
        _note_box(
            "Recommended next step",
            "Resolve contradicted and uncertain items against the cited source pages and cells, "
            "record the reviewer disposition, and regenerate the immutable bundle only if reviewed "
            "evidence changes.",
            styles,
        )
    )

    story.append(PageBreak())
    story.extend(_section("7. Economic context - no causation", "Context, not explanation", styles))
    story.extend(
        [
            _note_box("Interpretation boundary", NO_CAUSATION, styles, tone="amber"),
            Spacer(1, 4 * mm),
        ]
    )
    default_points = [point for point in bundle.economic_context if point.default_visible]
    additional_points = [point for point in bundle.economic_context if not point.default_visible]
    if not bundle.economic_context:
        story.append(
            _paragraph(
                "No reviewed economic context was supplied in the immutable report bundle.",
                styles["Body"],
            )
        )
    for point in default_points:
        story.append(_paragraph(f"{point.indicator} - {point.geography}", styles["Subsection"]))
        story.append(
            _rich(
                f"<b>{_safe(point.display_value)} {_safe(point.unit)}</b> for the period ended "
                f"{_safe(_human_date(point.period.end))}. {_safe(point.relevance)} "
                f"<b>Comparability:</b> {_safe(point.comparability_warning)}",
                styles["Body"],
            )
        )
        story.append(
            _paragraph(
                f"Official source: {point.official_source_url} | "
                f"Published {_human_date(point.published_on)} | "
                f"Retrieved {_human_date(point.retrieved_on)}",
                styles["EvidenceMeta"],
            )
        )
        story.append(Spacer(1, 4 * mm))
    for point in additional_points:
        story.append(
            _paragraph(
                f"Additional context - {point.indicator}: {point.display_value} {point.unit}. "
                f"{point.comparability_warning} Source: {point.official_source_url}.",
                styles["BodySmall"],
            )
        )
    story.extend([Spacer(1, 5 * mm), _paragraph("Further questions", styles["Subsection"])])
    story.append(
        _summary_bullets(
            [
                (
                    "Comparability",
                    "Do all source periods use the same scope, duration, currency and "
                    "restatement basis?",
                ),
                (
                    "Reviewer disposition",
                    "What evidence resolves each contradicted or uncertain item?",
                ),
                (
                    "Context",
                    "Would issuer-specific operating data add context without implying causation?",
                ),
            ],
            styles,
        )
    )
    story.extend(_section("8. Evidence and provenance appendix", "Audit trail", styles))
    story.append(
        _paragraph(
            "Document hashes, source locations and evidence identifiers below bind the report to "
            "the reviewed analysis. Long source quotations are preserved safely and may wrap "
            "across rows.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 2 * mm))
    document_rows = [["Document", "Issuer / version", "Retrieved", "SHA-256 / source"]]
    for document in bundle.analysis.documents:
        document_rows.append(
            [
                document.id,
                f"{document.issuer} | {document.version_label} | {document.reporting_basis}",
                document.retrieved_at.isoformat(),
                f"{document.sha256}\n{document.source_url}",
            ]
        )
    story.extend(
        [
            _evidence_table(
                document_rows, (25 * mm, 49 * mm, 31 * mm, 65 * mm), styles, compact=True
            ),
            Spacer(1, 5 * mm),
        ]
    )
    span_rows = [["Evidence ID", "Document", "Locator", "Reviewed content"]]
    for span in bundle.analysis.source_spans:
        if span.source.kind == "pdf":
            locator, detail = f"PDF page {span.source.page}", span.source.quote
        else:
            locator, detail = (
                f"{span.source.sheet}!{span.source.cell}",
                f"Displayed value: {span.source.display_value}",
            )
        span_rows.append([span.id, span.document_version_id, locator, detail])
    story.append(
        _evidence_table(span_rows, (33 * mm, 29 * mm, 32 * mm, 76 * mm), styles, compact=True)
    )
    story.append(Spacer(1, 6 * mm))
    story.extend(_section("9. Methodology and limitations", "How to use this report", styles))
    story.append(
        _paragraph(
            "This report renders a reviewed, immutable input bundle. It does not fetch source "
            "data, recalculate metrics, update economic observations, or create forecasts. It "
            "uses selected observations and metric results already validated by the typed v1 "
            "contracts.",
            styles["Body"],
        )
    )
    method_rows = [["Metric", "Formula ID", "Input evidence", "Rendered outcome"]]
    for result_id in bundle.report_profile.secondary_metric_result_ids:
        result = results[result_id]
        if result.result is None:
            outcome = f"Exception: {result.exceptional_state.value}"
        elif result.metric_id == MetricId.CURRENT_RATIO:
            outcome = f"{_decimal_display(result.result)}x"
        else:
            outcome = _percent_display(result.result)
        method_rows.append(
            [
                secondary_metric_label(result.metric_id),
                result.formula_id,
                ", ".join(result.input_observation_ids),
                outcome,
            ]
        )
    story.extend(
        [
            Spacer(1, 2 * mm),
            _evidence_table(
                method_rows,
                (37 * mm, 47 * mm, 62 * mm, 24 * mm),
                styles,
                compact=True,
            ),
            Spacer(1, 4 * mm),
            _note_box(
                "Reviewer and version control",
                f"State: {bundle.report_profile.reviewer_state.upper()}. "
                f"Schema {bundle.schema_version}; policy {bundle.policy_version}; metric registry "
                f"{bundle.metric_registry_version}. Reissue only from a newly reviewed immutable "
                "bundle when evidence changes.",
                styles,
            ),
            Spacer(1, 3 * mm),
        ]
    )
    for limitation in bundle.snapshot.limitations:
        story.append(_rich(f"<b>Limitation:</b> {_safe(limitation)}", styles["Body"]))
    story.append(
        _paragraph(
            "Forecasts are omitted: no validated forecast method, inputs, history and uncertainty "
            "model are present in this contract.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.extend(_section("10. Data handling and export disclosure", "Portable output", styles))
    story.extend(
        [
            _note_box("Export boundary", bundle.data_handling_disclosure, styles, tone="red"),
            Spacer(1, 3 * mm),
        ]
    )
    story.append(
        _paragraph(
            f"Evidence-chain SHA-256: {bundle.snapshot.evidence_chain_sha256}",
            styles["EvidenceMeta"],
        )
    )
    story.append(
        _paragraph(
            f"Analysis ID: {bundle.snapshot.analysis_id} | Schema {bundle.schema_version} | "
            f"Policy {bundle.policy_version} | Metric registry {bundle.metric_registry_version}",
            styles["EvidenceMeta"],
        )
    )

    doc.build(
        story, onFirstPage=_page_frame, onLaterPages=_page_frame, canvasmaker=_DeterministicCanvas
    )
    return buffer.getvalue()


def render_evidence_json(bundle: ReportRenderBundle) -> bytes:
    return canonical_json_bytes(bundle) + b"\n"


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def attachment_filename(bundle: ReportRenderBundle, suffix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", bundle.company_id.lower()).strip("-") or "company"
    snapshot = re.sub(r"[^A-Za-z0-9._-]+", "-", bundle.snapshot.snapshot_id).strip("-")
    return f"proofline-{slug}-{snapshot}.{suffix}"
