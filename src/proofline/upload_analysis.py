from __future__ import annotations

import hashlib
from datetime import datetime

from proofline.annual_report_mapping import AnnualReportMapper, AnnualReportMappingError
from proofline.contracts import (
    AnalysisItem,
    AnalysisRequest,
    AnalysisResponse,
    DocumentVersion,
)
from proofline.normalization import NormalizationResult, normalize_financial_workbook
from proofline.parsing.base import OcrAdapter
from proofline.parsing.ocr import OcrExtractionError
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
    ocr: OcrAdapter | None = None,
    pdf_document_id: str | None = None,
    workbook_document_id: str | None = None,
    pdf_display_name: str | None = None,
    workbook_display_name: str | None = None,
    pdf_extraction_warnings: tuple[str, ...] = (),
) -> AnalysisResponse:
    """Build an AnalysisResponse solely from one uploaded PDF/XLSX pair.

    The PDF side selects a bounded set of relevant annual-report pages and corroborates generic
    metric claims against normalized workbook facts. The workbook remains the authoritative
    arithmetic source and fails closed on unsupported or ambiguous structures.
    """

    pdf_document_id = pdf_document_id or f"{session_id}:report"
    workbook_document_id = workbook_document_id or f"{session_id}:workbook"
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
    mapper = AnnualReportMapper()
    try:
        mapping = mapper.map(
            pdf_content,
            pdf_document_id,
            normalized,
            inherited_warnings=pdf_extraction_warnings,
        )
    except AnnualReportMappingError as native_mapping_error:
        try:
            pages = NativePdfAdapter(ocr=ocr).extract_pages(pdf_content, pdf_document_id)
        except OcrExtractionError as error:
            raise UploadAnalysisError("OCR_FAILED", str(error)) from error
        except PdfExtractionError:
            raise UploadAnalysisError(
                "PDF_MAPPING_REQUIRED", str(native_mapping_error)
            ) from native_mapping_error
        usable_pages = [page for page in pages if page.span is not None]
        if not usable_pages:
            if any(
                warning.code == "ocr_not_configured"
                for page in pages
                for warning in page.warnings
            ):
                raise UploadAnalysisError(
                    "OCR_UNAVAILABLE",
                    "The PDF contains scanned or text-sparse pages and no verified OCR runtime "
                    "is available in this deployment.",
                ) from native_mapping_error
            raise UploadAnalysisError(
                "PDF_MAPPING_REQUIRED", str(native_mapping_error)
            ) from native_mapping_error
        if any(
            warning.code == "ocr_low_confidence"
            for page in usable_pages
            for warning in page.warnings
        ):
            raise UploadAnalysisError(
                "OCR_LOW_CONFIDENCE",
                "OCR text was below the configured confidence threshold and cannot be used as "
                "financial evidence.",
            ) from native_mapping_error
        if ocr is None:
            raise UploadAnalysisError(
                "PDF_MAPPING_REQUIRED", str(native_mapping_error)
            ) from native_mapping_error
        try:
            mapping = mapper.map_extracted_pages(
                usable_pages,
                pdf_document_id,
                normalized,
                inherited_warnings=pdf_extraction_warnings,
            )
        except AnnualReportMappingError as error:
            raise UploadAnalysisError("PDF_MAPPING_REQUIRED", str(error)) from error

    workbook_span_ids = {
        span_id for fact in normalized.facts for span_id in fact.provenance_span_ids
    }
    workbook_spans = tuple(cell.span for cell in cells if cell.span.id in workbook_span_ids)
    pdf_spans = tuple(page.span for page in mapping.pages if page.span is not None)
    source_spans = tuple({span.id: span for span in (*pdf_spans, *workbook_spans)}.values())
    documents = (
        _document(
            pdf_document_id,
            pdf_file_id,
            pdf_content,
            normalized.issuer,
            normalized.entity_scope,
            retrieved_at,
            normalized,
            pdf_display_name,
        ),
        _document(
            workbook_document_id,
            workbook_file_id,
            workbook_content,
            normalized.issuer,
            normalized.entity_scope,
            retrieved_at,
            normalized,
            workbook_display_name,
        ),
    )
    plans = {item.plan.metric_id: item.plan for item in normalized.metric_inputs}
    items = tuple(
        AnalysisItem(claim_id=claim.id, calculation_plan=plans[claim.metric_id])
        for claim in mapping.claims
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
        claims=mapping.claims,
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
    display_name: str | None = None,
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
        version_label=display_name or f"FY{latest_year}",
    )
