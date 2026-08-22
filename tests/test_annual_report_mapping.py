from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import fitz
import pytest
from openpyxl import Workbook

from proofline.annual_report_mapping import AnnualReportMapper, AnnualReportMappingError
from proofline.classification import classify
from proofline.contracts import PdfSourceRef, SourceSpan
from proofline.metrics import calculate_metric
from proofline.normalization import NormalizationResult, normalize_financial_workbook
from proofline.parsing.models import ExtractedPage, ExtractionMethod, ExtractionWarning
from proofline.parsing.workbook import StructuralXlsxAdapter

PDF_DOCUMENT_ID = "annual-report"
WORKBOOK_DOCUMENT_ID = "evidence-workbook"


def _normalized() -> NormalizationResult:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Consolidated statement"
    for row in (
        ("Issuer", "Alpine Robotics SE"),
        ("Entity scope", "Alpine Robotics SE consolidated"),
        ("Currency", "EUR"),
        ("Units", "millions"),
        ("Restatement basis", "not restated"),
        ("Line item", 2025, 2026),
        ("Revenue", 1_000, 1_200),
        ("Operating profit", 150, 240),
        ("Total current assets", 400, 500),
        ("Total current liabilities", 200, 250),
        ("Net cash from operating activities", 260, 320),
        ("Capital expenditures", "(80)", "(100)"),
    ):
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    cells = StructuralXlsxAdapter().extract_cells(output.getvalue(), WORKBOOK_DOCUMENT_ID)
    result = normalize_financial_workbook(cells, WORKBOOK_DOCUMENT_ID)
    assert result.facts and result.metric_inputs
    return result


def _page(
    page: int,
    text: str,
    *,
    confidence: float = 1.0,
    method: ExtractionMethod = ExtractionMethod.NATIVE_PDF,
    warnings: tuple[ExtractionWarning, ...] = (),
) -> ExtractedPage:
    return ExtractedPage(
        span=SourceSpan(
            id=f"input-span-{page}",
            document_version_id=PDF_DOCUMENT_ID,
            source=PdfSourceRef(
                document_id=PDF_DOCUMENT_ID,
                page=page,
                quote=text,
            ),
        ),
        page=page,
        method=method,
        confidence=confidence,
        warnings=warnings,
    )


def _identity(text: str) -> str:
    return "Alpine Robotics SE consolidated financial statements. Amounts in EUR millions. " + text


def _revenue_only(result: NormalizationResult) -> NormalizationResult:
    plan = next(
        item for item in result.metric_inputs if item.plan.metric_id == "revenue_growth_yoy"
    )
    fact_ids = set(plan.input_fact_ids)
    return result.model_copy(
        update={
            "facts": tuple(fact for fact in result.facts if fact.observation.id in fact_ids),
            "metric_inputs": (plan,),
        }
    )


def test_wrong_issuer_fails_closed() -> None:
    pages = (
        _page(
            1,
            "Other Industries PLC consolidated financial statements. "
            "Amounts in EUR millions. Revenue grew 20% for 2026.",
        ),
    )

    with pytest.raises(AnnualReportMappingError, match="issuer does not match"):
        AnnualReportMapper().map_extracted_pages(
            pages, PDF_DOCUMENT_ID, _revenue_only(_normalized())
        )


def test_conflicting_explicit_issuer_identity_fails_closed() -> None:
    pages = (
        _page(
            1,
            _identity("Issuer: Other Industries PLC. Revenue grew 20% for 2026."),
        ),
    )

    with pytest.raises(AnnualReportMappingError, match="issuer identity is ambiguous"):
        AnnualReportMapper().map_extracted_pages(
            pages, PDF_DOCUMENT_ID, _revenue_only(_normalized())
        )


def test_wrong_currency_fails_closed() -> None:
    pages = (
        _page(
            1,
            "Alpine Robotics SE consolidated financial statements. "
            "Amounts in USD millions. Revenue grew 20% for 2026.",
        ),
    )

    with pytest.raises(AnnualReportMappingError, match="currency does not match"):
        AnnualReportMapper().map_extracted_pages(
            pages, PDF_DOCUMENT_ID, _revenue_only(_normalized())
        )


def test_wrong_explicit_period_does_not_become_a_claim() -> None:
    pages = (_page(1, _identity("Revenue grew 20% for 2024.")),)

    with pytest.raises(AnnualReportMappingError, match="period does not match"):
        AnnualReportMapper().map_extracted_pages(
            pages, PDF_DOCUMENT_ID, _revenue_only(_normalized())
        )


def test_page_provenance_must_match_mapped_document() -> None:
    page = _page(1, _identity("Revenue grew 20% for 2026."))

    with pytest.raises(AnnualReportMappingError, match="provenance does not match"):
        AnnualReportMapper().map_extracted_pages(
            (page,), "different-document", _revenue_only(_normalized())
        )


def test_conflicting_currency_declarations_fail_closed() -> None:
    pages = (
        _page(1, _identity("Revenue grew 20% for 2026.")),
        _page(
            2,
            "Alpine Robotics SE consolidated statement of income. "
            "Amounts in USD millions. Revenue 2026 1200 2025 1000.",
        ),
    )

    with pytest.raises(AnnualReportMappingError, match="currency declarations are ambiguous"):
        AnnualReportMapper().map_extracted_pages(
            pages, PDF_DOCUMENT_ID, _revenue_only(_normalized())
        )


def test_discovery_time_limit_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), _identity("Revenue grew 20% for 2026."))
    content = document.tobytes()
    document.close()
    readings = iter((0.0, 0.0, 11.0))
    monkeypatch.setattr("proofline.annual_report_mapping.time.monotonic", lambda: next(readings))

    with pytest.raises(AnnualReportMappingError, match="processing time limit"):
        AnnualReportMapper().map(content, PDF_DOCUMENT_ID, _revenue_only(_normalized()))


def test_native_page_extraction_error_is_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenPage:
        def get_text(self, _kind: str) -> str:
            raise RuntimeError("parser detail must not escape")

    class BrokenDocument:
        needs_pass = False
        page_count = 1

        def __getitem__(self, _index: int) -> BrokenPage:
            return BrokenPage()

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        "proofline.annual_report_mapping.fitz.open", lambda **_kwargs: BrokenDocument()
    )

    with pytest.raises(AnnualReportMappingError, match="page text extraction failed") as error:
        AnnualReportMapper().map(b"%PDF-safe-placeholder", PDF_DOCUMENT_ID, _normalized())

    assert "parser detail" not in str(error.value)


def test_sparse_irrelevant_pages_are_ignored() -> None:
    sparse = ExtractedPage(
        span=None,
        page=1,
        method=ExtractionMethod.NATIVE_PDF,
        confidence=0,
        warnings=(
            ExtractionWarning(
                code="native_text_sparse",
                message="Native text was too sparse for reliable extraction.",
            ),
        ),
    )
    relevant = _page(27, _identity("Revenue grew 20% for 2026."))

    mapping = AnnualReportMapper().map_extracted_pages(
        (sparse, relevant), PDF_DOCUMENT_ID, _revenue_only(_normalized())
    )

    assert len(mapping.claims) == 1
    assert [page.page for page in mapping.pages] == [27]
    assert mapping.claims[0].source_span_id == mapping.pages[0].span.id


def test_repeated_identical_narrative_boilerplate_is_deduplicated() -> None:
    repeated = _identity("Revenue grew 20% for 2026.")

    mapping = AnnualReportMapper().map_extracted_pages(
        (_page(4, repeated), _page(18, repeated)),
        PDF_DOCUMENT_ID,
        _revenue_only(_normalized()),
    )

    assert len(mapping.claims) == 1
    assert len(mapping.pages) == 1
    assert mapping.pages[0].page == 4


def test_conflicting_narrative_claims_fail_closed() -> None:
    pages = (
        _page(4, _identity("Revenue grew 20% for 2026.")),
        _page(18, _identity("Revenue grew 25% for 2026.")),
    )

    with pytest.raises(AnnualReportMappingError, match="conflicting revenue_growth_yoy"):
        AnnualReportMapper().map_extracted_pages(
            pages, PDF_DOCUMENT_ID, _revenue_only(_normalized())
        )


def test_low_ocr_confidence_is_propagated_and_forces_uncertain_classification() -> None:
    normalized = _revenue_only(_normalized())
    low_confidence = ExtractionWarning(
        code="ocr_low_confidence",
        message="OCR text is below the configured confidence threshold.",
    )
    mapping = AnnualReportMapper().map_extracted_pages(
        (
            _page(
                9,
                _identity("Revenue grew 20% for 2026."),
                confidence=0.72,
                method=ExtractionMethod.OCR,
                warnings=(low_confidence,),
            ),
        ),
        PDF_DOCUMENT_ID,
        normalized,
    )
    claim = mapping.claims[0]
    plan = normalized.metric_inputs[0].plan
    observations = {fact.observation.id: fact.observation for fact in normalized.facts}
    result = calculate_metric("mapped-result", plan, observations)
    inputs = tuple(observations[item.observation_id] for item in plan.inputs)

    finding = classify(
        "mapped-finding",
        claim,
        result,
        inputs,
        tuple(observation.source_span_id for observation in inputs),
    )

    assert claim.extraction_warnings == (low_confidence.message,)
    assert mapping.pages[0].warnings == (low_confidence,)
    assert finding.classification == "uncertain"
    assert "Extraction warnings" in finding.rationale


def test_table_backed_claims_are_dynamic_and_citation_resolving() -> None:
    normalized = _normalized()
    statement = _identity(
        """
        Consolidated statement of profit or loss for 2026 and 2025
        Revenue 2026 1,200 2025 1,000
        Operating profit 2026 240 2025 150
        Consolidated statement of financial position at 31 December 2026
        Total current assets 2026 500 2025 400
        Total current liabilities 2026 250 2025 200
        Consolidated statement of cash flows for 2026 and 2025
        Net cash from operating activities 2026 320 2025 260
        Capital expenditures 2026 (100) 2025 (80)
        """
    )

    mapping = AnnualReportMapper().map_extracted_pages(
        (_page(31, statement),), PDF_DOCUMENT_ID, normalized
    )

    spans = {page.span.id: page.span for page in mapping.pages if page.span is not None}
    claims = {claim.metric_id: claim for claim in mapping.claims}
    assert set(claims) == {
        "revenue_growth_yoy",
        "operating_margin",
        "current_ratio",
        "fcf_margin",
    }
    assert claims["revenue_growth_yoy"].asserted_value == Decimal("0.2")
    assert claims["operating_margin"].asserted_value == Decimal("0.2")
    assert claims["current_ratio"].asserted_value == Decimal("2")
    assert claims["fcf_margin"].asserted_value == Decimal("0.1833333333333333333333333333")
    assert all(
        claim.text.startswith("Financial statement tables imply") for claim in claims.values()
    )
    assert all(claim.source_span_id in spans for claim in claims.values())
    assert all(spans[claim.source_span_id].source.page == 31 for claim in claims.values())
    assert all(spans[claim.source_span_id].source.quote for claim in claims.values())


def test_table_values_must_be_locally_associated_with_their_concept() -> None:
    normalized = _revenue_only(_normalized())
    shifted = _identity(
        """
        Consolidated statement of profit or loss for 2026 and 2025
        Revenue 2026 999 2025 998
        Other income 2026 1,200 2025 1,000
        """
    )

    with pytest.raises(AnnualReportMappingError, match="no unambiguous report page"):
        AnnualReportMapper().map_extracted_pages((_page(31, shifted),), PDF_DOCUMENT_ID, normalized)


def test_table_current_and_prior_values_cannot_be_swapped() -> None:
    normalized = _revenue_only(_normalized())
    swapped = _identity(
        """
        Consolidated statement of profit or loss for 2026 and 2025
        Revenue 2026 1,000 2025 1,200
        """
    )

    with pytest.raises(AnnualReportMappingError, match="no unambiguous report page"):
        AnnualReportMapper().map_extracted_pages((_page(31, swapped),), PDF_DOCUMENT_ID, normalized)
