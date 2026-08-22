from __future__ import annotations

import hashlib
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from proofline.contracts import (
    AnalysisItem,
    AnalysisRequest,
    AnalysisResponse,
    DocumentVersion,
    FinancialClaim,
    MetricId,
)
from proofline.normalization import NormalizationResult, normalize_financial_workbook
from proofline.parsing.models import ExtractedPage
from proofline.parsing.pdf import NativePdfAdapter, PdfExtractionError
from proofline.parsing.workbook import StructuralXlsxAdapter, WorkbookExtractionError
from proofline.service import analyze


class UploadAnalysisError(ValueError):
    """A safe, user-actionable failure while mapping uploaded evidence."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_REVIEW_CODES = frozenset(
    {
        "document_mismatch",
        "issuer_missing",
        "issuer_ambiguous",
        "entity_scope_missing",
        "entity_scope_ambiguous",
        "currency_missing",
        "currency_ambiguous",
        "currency_invalid",
        "scale_missing",
        "scale_ambiguous",
        "scale_invalid",
        "restatement_missing",
        "restatement_ambiguous",
        "restatement_invalid",
        "fact_ambiguous",
        "no_financial_facts",
    }
)


def analyze_uploaded_evidence(
    *,
    pdf_content: bytes,
    workbook_content: bytes,
    session_id: str,
    pdf_file_id: str,
    workbook_file_id: str,
    retrieved_at: datetime,
) -> AnalysisResponse:
    """Build an AnalysisResponse solely from one uploaded PDF/XLSX pair.

    The PDF side intentionally accepts only explicit, short claim sentences. It is a reviewed
    deterministic boundary, not a general narrative extractor. The workbook side is mapped by the
    generic normalizer and fails closed on unsupported or ambiguous structures.
    """

    pdf_document_id = f"{session_id}:report"
    workbook_document_id = f"{session_id}:workbook"
    try:
        pages = NativePdfAdapter().extract_pages(pdf_content, pdf_document_id)
    except PdfExtractionError as error:
        raise UploadAnalysisError("PDF_MAPPING_REQUIRED", str(error)) from error
    if not pages or any(page.span is None for page in pages):
        raise UploadAnalysisError(
            "PDF_MAPPING_REQUIRED",
            "Every PDF page must contain enough native text for reviewed claim mapping; "
            "OCR or a human mapping is required.",
        )
    try:
        cells = StructuralXlsxAdapter().extract_cells(workbook_content, workbook_document_id)
    except WorkbookExtractionError as error:
        raise UploadAnalysisError("WORKBOOK_MAPPING_REQUIRED", str(error)) from error
    if any(cell.data_type == "formula" or cell.warnings for cell in cells):
        raise UploadAnalysisError(
            "WORKBOOK_MAPPING_REQUIRED",
            "Formula cells and workbook extraction warnings require reviewed mapping before "
            "arithmetic.",
        )

    normalized = normalize_financial_workbook(cells, workbook_document_id)
    _raise_for_normalization_warnings(normalized)
    if not normalized.facts or not normalized.metric_inputs:
        raise UploadAnalysisError(
            "WORKBOOK_MAPPING_REQUIRED",
            "The workbook did not produce a complete, unambiguous Tier-0 metric plan.",
        )
    claims = _claims_from_pdf(pages, normalized)
    if not claims:
        raise UploadAnalysisError(
            "PDF_MAPPING_REQUIRED",
            "The PDF contains no supported explicit metric claim sentence for the normalized "
            "workbook.",
        )

    source_spans = tuple(
        [page.span for page in pages if page.span is not None] + [cell.span for cell in cells]
    )
    documents = (
        _document(
            pdf_document_id,
            pdf_file_id,
            pdf_content,
            normalized.issuer,
            normalized.entity_scope,
            retrieved_at,
            normalized,
        ),
        _document(
            workbook_document_id,
            workbook_file_id,
            workbook_content,
            normalized.issuer,
            normalized.entity_scope,
            retrieved_at,
            normalized,
        ),
    )
    plans = {item.plan.metric_id: item.plan for item in normalized.metric_inputs}
    items = tuple(
        AnalysisItem(claim_id=claim.id, calculation_plan=plans[claim.metric_id])
        for claim in claims
        if claim.metric_id in plans
    )
    if not items:
        raise UploadAnalysisError(
            "PDF_MAPPING_REQUIRED",
            "Supported PDF claims did not match an available normalized metric plan.",
        )
    request = AnalysisRequest(
        documents=documents,
        source_spans=source_spans,
        claims=claims,
        observations=tuple(fact.observation for fact in normalized.facts),
        items=items,
    )
    try:
        return analyze(request)
    except ValueError as error:
        raise UploadAnalysisError("ANALYSIS_MAPPING_REQUIRED", str(error)) from error


def _raise_for_normalization_warnings(result: NormalizationResult) -> None:
    review = [warning for warning in result.warnings if warning.code in _REVIEW_CODES]
    if review:
        codes = ", ".join(sorted({warning.code for warning in review}))
        raise UploadAnalysisError(
            "WORKBOOK_MAPPING_REQUIRED",
            f"Workbook normalization requires reviewed mapping ({codes}).",
        )


def _document(
    document_id: str,
    file_id: str,
    content: bytes,
    issuer: str | None,
    entity_scope: str | None,
    retrieved_at: datetime,
    result: NormalizationResult,
) -> DocumentVersion:
    if not issuer or not entity_scope:
        raise UploadAnalysisError("WORKBOOK_MAPPING_REQUIRED", "Issuer metadata is required.")
    periods = [fact.observation.period.end for fact in result.facts]
    latest_year = max(periods).year if periods else retrieved_at.year
    return DocumentVersion(
        id=document_id,
        sha256=hashlib.sha256(content).hexdigest(),
        issuer=issuer,
        source_url=f"urn:proofline:session:{file_id}",
        retrieved_at=retrieved_at,
        reporting_basis=entity_scope,
        version_label=f"FY{latest_year}",
    )


_CLAIM_PATTERNS: tuple[tuple[MetricId, re.Pattern[str], Decimal], ...] = (
    (
        MetricId.REVENUE_GROWTH_YOY,
        re.compile(
            r"\brevenue\s+(?:grew|growth(?:\s+yoy)?\s+(?:was|of))\s+"
            r"(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*%"
            r"(?:\s+(?:in|for)\s+(?P<year>20\d{2}))?",
            re.IGNORECASE,
        ),
        Decimal("0.01"),
    ),
    (
        MetricId.OPERATING_MARGIN,
        re.compile(
            r"\boperating\s+margin\s+(?:was|of)\s+"
            r"(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*%"
            r"(?:\s+(?:in|for)\s+(?P<year>20\d{2}))?",
            re.IGNORECASE,
        ),
        Decimal("0.01"),
    ),
    (
        MetricId.CURRENT_RATIO,
        re.compile(
            r"\bcurrent\s+ratio\s+(?:was|of)\s+"
            r"(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))"
            r"(?:\s+(?:in|for)\s+(?P<year>20\d{2}))?",
            re.IGNORECASE,
        ),
        Decimal("1"),
    ),
    (
        MetricId.FCF_MARGIN,
        re.compile(
            r"\b(?:project[- ]defined\s+)?(?:free[- ]cash[- ]flow|fcf)\s+margin\s+"
            r"(?:was|of)\s+(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*%"
            r"(?:\s+(?:in|for)\s+(?P<year>20\d{2}))?",
            re.IGNORECASE,
        ),
        Decimal("0.01"),
    ),
)


def _claims_from_pdf(
    pages: tuple[ExtractedPage, ...] | list[ExtractedPage], result: NormalizationResult
) -> tuple[FinancialClaim, ...]:
    plans = {item.plan.metric_id: item for item in result.metric_inputs}
    claims: list[FinancialClaim] = []
    seen: set[MetricId] = set()
    declared_issuer = _declared_issuer(pages)
    if declared_issuer is not None and _label(declared_issuer) != _label(result.issuer or ""):
        raise UploadAnalysisError(
            "PDF_MAPPING_REQUIRED",
            "The PDF issuer does not match the workbook issuer metadata.",
        )
    for page in pages:
        if page.span is None:
            continue
        quote = page.span.source.quote
        for metric_id, pattern, factor in _CLAIM_PATTERNS:
            match = pattern.search(quote)
            if match is None:
                continue
            if metric_id in seen:
                raise UploadAnalysisError(
                    "PDF_MAPPING_REQUIRED",
                    f"The PDF contains duplicate {metric_id.value} claim candidates.",
                )
            plan = plans.get(metric_id)
            if plan is None:
                raise UploadAnalysisError(
                    "PDF_MAPPING_REQUIRED",
                    f"The PDF includes {metric_id.value}, but the workbook has no compatible plan.",
                )
            year = match.group("year")
            if year and int(year) != plan.period.end.year:
                raise UploadAnalysisError(
                    "PDF_MAPPING_REQUIRED",
                    f"The PDF claim period does not match the normalized {metric_id.value} period.",
                )
            try:
                value = Decimal(match.group("value")) * factor
            except (InvalidOperation, TypeError) as error:
                raise UploadAnalysisError(
                    "PDF_MAPPING_REQUIRED", "A PDF claim value is not a finite decimal."
                ) from error
            if not value.is_finite():
                raise UploadAnalysisError(
                    "PDF_MAPPING_REQUIRED", "A PDF claim value is not a finite decimal."
                )
            claims.append(
                FinancialClaim(
                    id=f"claim:{page.span.document_version_id}:{metric_id.value}",
                    text=match.group(0),
                    entity=result.entity_scope,
                    metric_id=metric_id,
                    period=plan.period,
                    asserted_value=value,
                    unit="ratio" if metric_id == MetricId.CURRENT_RATIO else "ratio",
                    currency=result.currency,
                    source_span_id=page.span.id,
                )
            )
            seen.add(metric_id)
    return tuple(claims)


def _declared_issuer(pages: tuple[ExtractedPage, ...] | list[ExtractedPage]) -> str | None:
    for page in pages:
        if page.span is None:
            continue
        match = re.search(
            r"\bissuer\s*:\s*(.+?)(?=\brevenue\s+(?:grew|growth)\b|"
            r"\boperating\s+margin\b|\bcurrent\s+ratio\b|"
            r"\b(?:project[- ]defined\s+)?(?:free[- ]cash[- ]flow|fcf)\s+margin\b|$)",
            page.span.source.quote,
            re.IGNORECASE,
        )
        if match is not None:
            return match.group(1).strip()
    return None


def _label(value: str) -> str:
    return " ".join(value.casefold().split())
