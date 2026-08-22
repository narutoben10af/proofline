from __future__ import annotations

import hashlib
import html
import io
import re
import unicodedata

from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

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


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(html.escape(_core_text(value), quote=False), style)


def _decimal_display(value) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _section(title: str, styles: dict[str, ParagraphStyle]) -> list:
    return [Spacer(1, 4 * mm), _paragraph(title, styles["Section"]), Spacer(1, 1.5 * mm)]


def _evidence_table(rows: list[list[object]], widths: tuple, styles) -> Table:
    rendered = [
        [
            _paragraph(cell, styles["TableHeader"] if index == 0 else styles["TableCell"])
            for cell in row
        ]
        for index, row in enumerate(rows)
    ]
    table = Table(rendered, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _trend_chart(bundle: ReportRenderBundle, styles: dict[str, ParagraphStyle]) -> list:
    trend = bundle.trend
    if trend is None:
        return []
    labels = [str(point.period.end.year) for point in trend.points]
    values = [float(point.value) for point in trend.points]
    drawing = Drawing(168 * mm, 58 * mm)
    chart = HorizontalLineChart()
    chart.x = 14 * mm
    chart.y = 12 * mm
    chart.height = 38 * mm
    chart.width = 142 * mm
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.lines[0].strokeColor = colors.HexColor("#137A72")
    chart.lines[0].strokeWidth = 2
    chart.lines[0].symbol = None
    drawing.add(chart)
    drawing.add(
        String(
            84 * mm,
            2 * mm,
            _core_text(f"{trend.indicator} ({trend.unit})"),
            textAnchor="middle",
            fontName="Helvetica",
            fontSize=8,
            fillColor=colors.HexColor("#334155"),
        )
    )
    rows = [["Period", "Value", "Basis"]]
    rows.extend(
        [
            str(point.period.end.year),
            _decimal_display(point.value),
            _core_text(point.reporting_basis),
        ]
        for point in trend.points
    )
    table = Table(rows, colWidths=(24 * mm, 32 * mm, 104 * mm), repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [drawing, Spacer(1, 2 * mm), table]


def _page_frame(pdf: canvas.Canvas, document: SimpleDocTemplate) -> None:
    pdf.saveState()
    pdf.setTitle(_core_text(document.title))
    pdf.setAuthor("Proofline")
    pdf.setSubject("Reviewed prototype financial evidence report")
    pdf.setCreator("Proofline deterministic ReportLab renderer")
    pdf.setFont("Helvetica", 7)
    pdf.setFillColor(colors.HexColor("#64748B"))
    pdf.drawString(18 * mm, 10 * mm, "Proofline - prototype output - human review required")
    pdf.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {document.page}")
    pdf.restoreState()


def render_pdf(bundle: ReportRenderBundle) -> bytes:
    """Render only the supplied immutable bundle; this function performs no I/O or calculation."""

    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#0F172A"),
            alignment=TA_LEFT,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            "Banner",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#7C2D12"),
            backColor=colors.HexColor("#FFEDD5"),
            borderPadding=7,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#0F172A"),
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            "BodySmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#334155"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            "TableHeader",
            parent=styles["BodySmall"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            "TableCell",
            parent=styles["BodySmall"],
            fontSize=7.5,
            leading=9.5,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            "Hero",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#134E4A"),
            backColor=colors.HexColor("#CCFBF1"),
            borderPadding=8,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            "CenterSmall",
            parent=styles["BodySmall"],
            alignment=TA_CENTER,
        )
    )

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title=_core_text(bundle.snapshot.title),
        author="Proofline",
        subject="Reviewed prototype financial evidence report",
        pageCompression=1,
    )
    story: list = []
    story.append(_paragraph("PROTOTYPE - HUMAN REVIEW REQUIRED", styles["Banner"]))
    banner = CACHED_BANNER if bundle.source_mode == SourceMode.VERIFIED_CACHED else LIVE_BANNER
    story.append(_paragraph(banner, styles["Banner"]))
    story.append(_paragraph(bundle.source_disclosure, styles["BodySmall"]))
    story.append(_paragraph(bundle.snapshot.title, styles["ReportTitle"]))
    story.append(
        _paragraph(
            f"Company: {bundle.company} | Reporting period end: "
            f"{bundle.report_profile.reporting_period.end.isoformat()} | Reviewer state: "
            f"{bundle.report_profile.reviewer_state.upper()} | Snapshot "
            f"{bundle.snapshot.snapshot_id}",
            styles["BodySmall"],
        )
    )

    findings = {finding.id: finding for finding in bundle.analysis.findings}
    claims = {claim.id: claim for claim in bundle.analysis.claims}
    results = {result.id: result for result in bundle.analysis.metric_results}
    observations = {item.id: item for item in bundle.analysis.observations}
    ordered_findings = [findings[item] for item in bundle.snapshot.finding_ids]
    counts = bundle.snapshot.classification_counts

    story.extend(_section("1. Executive summary", styles))
    story.append(
        _paragraph(
            f"Reviewed findings: {len(ordered_findings)}. Supported: {counts.supported}; "
            f"uncertain: {counts.uncertain}; contradicted: {counts.contradicted}. This report "
            "summarizes reviewed evidence and does not provide an investment recommendation.",
            styles["BodySmall"],
        )
    )
    hero = ordered_findings[0]
    hero_claim = claims[hero.claim_id]
    story.append(
        _paragraph(
            f"Hero finding - {hero.classification.value.upper()}: "
            f"{report_claim_text(hero_claim)} Review rationale: "
            f"{report_finding_rationale(hero_claim, results[hero.metric_result_id])}",
            styles["Hero"],
        )
    )

    primary = [observations[item] for item in bundle.report_profile.primary_observation_ids]
    story.extend(_section("2. Four primary financial metrics", styles))
    story.append(
        _evidence_table(
            [["Metric", "Value", "Unit", "Period", "Evidence"]]
            + [
                [
                    primary_metric_label(item.concept),
                    item.display_value,
                    item.unit,
                    item.period.end.isoformat(),
                    item.source_span_id,
                ]
                for item in primary
            ],
            (35 * mm, 24 * mm, 34 * mm, 30 * mm, 37 * mm),
            styles,
        )
    )

    story.extend(_section("3. Secondary ratios", styles))
    ratio_rows: list[list[object]] = [["Ratio", "Result", "Status", "Input evidence"]]
    for result_id in bundle.report_profile.secondary_metric_result_ids:
        result = results[result_id]
        outcome = (
            _decimal_display(result.result)
            if result.result is not None
            else f"Not calculated: {result.exceptional_state.value}"
        )
        ratio_rows.append(
            [
                secondary_metric_label(result.metric_id),
                outcome,
                "calculated" if result.result is not None else "exception",
                ", ".join(result.input_observation_ids),
            ]
        )
    story.append(_evidence_table(ratio_rows, (43 * mm, 28 * mm, 28 * mm, 61 * mm), styles))

    if bundle.trend is not None:
        story.append(
            KeepTogether(
                _section("4. Historical trend and value table", styles)
                + _trend_chart(bundle, styles)
            )
        )

    story.extend(_section("5. Exceptions and review risks", styles))
    exception_results = [item for item in results.values() if item.exceptional_state is not None]
    review_risks = [
        item
        for item in ordered_findings
        if item.classification.value in {"uncertain", "contradicted"}
    ]
    story.append(
        _paragraph(
            f"Exceptional metric outcomes: {len(exception_results)}. Findings requiring review: "
            f"{len(review_risks)}. These are evidence-review flags, not predictions or advice.",
            styles["BodySmall"],
        )
    )
    for finding in review_risks:
        story.append(
            _paragraph(
                f"{finding.classification.value.upper()}: "
                f"{report_claim_text(claims[finding.claim_id])}",
                styles["BodySmall"],
            )
        )

    story.extend(_section("6. Narrative-versus-numbers findings", styles))
    for index, finding in enumerate(ordered_findings, start=1):
        claim = claims[finding.claim_id]
        result = results[finding.metric_result_id]
        outcome = (
            _decimal_display(result.result)
            if result.result is not None
            else f"Exceptional state: {result.exceptional_state.value}"
        )
        warning_count = len(result.warnings + finding.warnings)
        warning = (
            f" Review warning count: {warning_count}; see evidence export." if warning_count else ""
        )
        story.append(
            KeepTogether(
                [
                    _paragraph(
                        f"{index}. {finding.classification.value.upper()} - "
                        f"{report_claim_text(claim)}",
                        styles["BodySmall"],
                    ),
                    _paragraph(
                        f"Result: {outcome}. {report_finding_rationale(claim, result)}{warning}",
                        styles["BodySmall"],
                    ),
                ]
            )
        )

    story.extend(_section("7. Economic context - no causation", styles))
    story.append(_paragraph(NO_CAUSATION, styles["Hero"]))
    default_points = [point for point in bundle.economic_context if point.default_visible]
    additional_points = [point for point in bundle.economic_context if not point.default_visible]
    if not bundle.economic_context:
        story.append(
            _paragraph(
                "No reviewed economic context was supplied in the immutable report bundle.",
                styles["BodySmall"],
            )
        )
    for point in default_points:
        story.append(
            _paragraph(
                f"{point.indicator} ({point.geography}, {point.period.end.isoformat()}): "
                f"{point.display_value} {point.unit}. {point.relevance} Comparability: "
                f"{point.comparability_warning} Source: {point.official_source_url} "
                f"(published {point.published_on.isoformat()}, retrieved "
                f"{point.retrieved_on.isoformat()}).",
                styles["BodySmall"],
            )
        )
    if additional_points:
        story.append(
            _paragraph(
                f"Additional context disclosed ({len(additional_points)} point(s)); kept outside "
                "the compact default Company Lens.",
                styles["BodySmall"],
            )
        )
        for point in additional_points:
            story.append(
                _paragraph(
                    f"Additional - {point.indicator}: {point.display_value} {point.unit}. "
                    f"{point.comparability_warning} Source: {point.official_source_url}.",
                    styles["BodySmall"],
                )
            )

    story.extend(_section("8. Evidence and provenance appendix", styles))
    for document in bundle.analysis.documents:
        story.append(
            _paragraph(
                f"Document {document.id}: {document.issuer}; {document.version_label}; "
                f"SHA-256 {document.sha256}; retrieved {document.retrieved_at.isoformat()}; "
                f"source {document.source_url}.",
                styles["BodySmall"],
            )
        )
        story.append(Spacer(1, 1 * mm))
    for span in bundle.analysis.source_spans:
        if span.source.kind == "pdf":
            detail = f"page {span.source.page}; quote: {span.source.quote}"
        else:
            detail = (
                f"sheet {span.source.sheet}; cell {span.source.cell}; "
                f"display value {span.source.display_value}"
            )
        story.append(
            _paragraph(
                f"Evidence {span.id} -> {span.document_version_id}: {detail}",
                styles["BodySmall"],
            )
        )
        story.append(Spacer(1, 1 * mm))

    story.extend(_section("9. Methodology and limitations", styles))
    story.append(
        _paragraph(
            "This report renders a reviewed, immutable input bundle. It does not fetch source "
            "data, recalculate metrics, update economic observations, or create forecasts. The "
            "forecast section is omitted; no validated forecast method, inputs, history, and "
            "uncertainty model are present in this contract.",
            styles["BodySmall"],
        )
    )
    for limitation in bundle.snapshot.limitations:
        story.append(_paragraph(f"- {limitation}", styles["BodySmall"]))

    story.extend(_section("10. Data handling and export disclosure", styles))
    story.append(_paragraph(bundle.data_handling_disclosure, styles["BodySmall"]))

    doc.build(
        story,
        onFirstPage=_page_frame,
        onLaterPages=_page_frame,
        canvasmaker=_DeterministicCanvas,
    )
    return buffer.getvalue()


def render_evidence_json(bundle: ReportRenderBundle) -> bytes:
    """Reviewed JSON export fallback using the same immutable, canonical bundle."""

    return canonical_json_bytes(bundle) + b"\n"


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def attachment_filename(bundle: ReportRenderBundle, suffix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", bundle.company_id.lower()).strip("-") or "company"
    snapshot = re.sub(r"[^A-Za-z0-9._-]+", "-", bundle.snapshot.snapshot_id).strip("-")
    return f"proofline-{slug}-{snapshot}.{suffix}"
