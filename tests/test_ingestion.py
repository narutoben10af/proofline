from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import fitz
import pytest
from openpyxl import Workbook

from proofline.parsing import NativePdfAdapter, PaddleOcrCompatibleAdapter, StructuralXlsxAdapter
from proofline.parsing.ocr import OcrExtractionError
from proofline.parsing.pdf import PdfExtractionError
from proofline.parsing.workbook import WorkbookExtractionError


def _pdf(text: str | None) -> bytes:
    document = fitz.open()
    page = document.new_page()
    if text is not None:
        page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    return content


def _xlsx() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Financial Statements"
    sheet["A1"] = "Revenue"
    sheet["B1"] = 100
    sheet["C1"] = "=B1*2"
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def _xlsx_with_cached_formula() -> bytes:
    source = BytesIO(_xlsx())
    output = BytesIO()
    with ZipFile(source) as archive, ZipFile(output, "w", compression=ZIP_DEFLATED) as rewritten:
        for member in archive.infolist():
            content = archive.read(member)
            if member.filename == "xl/worksheets/sheet1.xml":
                content = content.replace(b"<f>B1*2</f><v />", b"<f>B1*2</f><v>200</v>")
            rewritten.writestr(member, content)
    return output.getvalue()


def test_native_pdf_text_preserves_page_provenance() -> None:
    result = NativePdfAdapter().extract_pages(
        _pdf("Revenue increased to 100 million for the reviewed financial year."), "annual-report"
    )
    page = result[0]
    assert page.method == "native_pdf"
    assert page.confidence >= 0.8
    assert page.warnings == ()
    assert page.span is not None
    assert page.span.source.page == 1
    assert page.span.source.document_id == "annual-report"
    assert "Revenue increased" in page.span.source.quote


def test_scanned_page_exposes_truthful_unconfigured_ocr_boundary() -> None:
    page = NativePdfAdapter().extract_pages(_pdf(None), "scan")[0]
    assert page.span is None
    assert page.confidence == 0
    assert [warning.code for warning in page.warnings] == [
        "native_text_missing",
        "ocr_not_configured",
    ]


def test_paddle_compatible_fallback_is_injected_and_typed() -> None:
    seen: list[bytes] = []

    def engine(image: bytes):
        seen.append(image)
        return (("Audited revenue was 100 million.", 0.94),)

    page = NativePdfAdapter(PaddleOcrCompatibleAdapter(engine)).extract_pages(_pdf(None), "scan")[0]
    assert seen[0].startswith(b"\x89PNG")
    assert page.method == "ocr"
    assert page.confidence == pytest.approx(0.94)
    assert page.span is not None
    assert page.span.source.quote == "Audited revenue was 100 million."
    assert [warning.code for warning in page.warnings] == ["native_text_missing"]


def test_low_confidence_ocr_never_becomes_silent_evidence() -> None:
    ocr = PaddleOcrCompatibleAdapter(lambda _: (("unclear value", 0.42),))
    page = NativePdfAdapter(ocr).extract_pages(_pdf(None), "scan")[0]
    assert page.confidence == pytest.approx(0.42)
    assert [warning.code for warning in page.warnings] == [
        "native_text_missing",
        "ocr_low_confidence",
    ]


def test_invalid_or_unbounded_ocr_output_fails_closed() -> None:
    invalid = PaddleOcrCompatibleAdapter(lambda _: (("value", float("nan")),))
    with pytest.raises(OcrExtractionError, match="invalid confidence"):
        NativePdfAdapter(invalid).extract_pages(_pdf(None), "scan")

    unbounded = PaddleOcrCompatibleAdapter(lambda _: (("value", 0.9) for _ in range(501)))
    with pytest.raises(OcrExtractionError, match="line limit"):
        NativePdfAdapter(unbounded).extract_pages(_pdf(None), "scan")


def test_structural_xlsx_reader_preserves_sheet_cells_and_does_not_run_formulas() -> None:
    cells = StructuralXlsxAdapter().extract_cells(_xlsx(), "workbook")
    by_cell = {cell.span.source.cell: cell for cell in cells}
    assert by_cell["A1"].span.source.sheet == "Financial Statements"
    assert by_cell["A1"].span.source.display_value == "Revenue"
    assert by_cell["A1"].data_type == "text"
    assert by_cell["B1"].span.source.display_value == "100"
    assert by_cell["B1"].data_type == "number"
    assert by_cell["C1"].span.source.display_value == "=B1*2"
    assert by_cell["C1"].data_type == "formula"
    assert [warning.code for warning in by_cell["C1"].warnings] == ["formula_without_cached_value"]


def test_cached_formula_is_retained_only_with_unverified_warning() -> None:
    cells = StructuralXlsxAdapter().extract_cells(_xlsx_with_cached_formula(), "workbook")
    formula_cell = next(cell for cell in cells if cell.span.source.cell == "C1")
    assert formula_cell.span.source.display_value == "200"
    assert formula_cell.data_type == "formula"
    assert [warning.code for warning in formula_cell.warnings] == [
        "formula_cached_value_unverified"
    ]


def test_invalid_inputs_fail_closed() -> None:
    with pytest.raises(PdfExtractionError, match="not a PDF"):
        NativePdfAdapter().extract_pages(b"not a pdf", "document")
    with pytest.raises(WorkbookExtractionError, match="not an XLSX"):
        StructuralXlsxAdapter().extract_cells(b"not a workbook", "workbook")


def test_encrypted_pdf_and_macro_package_are_rejected() -> None:
    document = fitz.open()
    document.new_page()
    encrypted = document.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="user-secret",
    )
    document.close()
    with pytest.raises(PdfExtractionError, match="encrypted PDFs"):
        NativePdfAdapter().extract_pages(encrypted, "encrypted")

    stream = BytesIO(_xlsx())
    with ZipFile(stream, "a") as archive:
        archive.writestr("xl/vbaProject.bin", b"synthetic macro marker")
    with pytest.raises(WorkbookExtractionError, match="macro-enabled"):
        StructuralXlsxAdapter().extract_cells(stream.getvalue(), "macro-workbook")


def test_xlsx_expansion_and_declared_dimension_limits_fail_closed() -> None:
    oversized_archive = BytesIO(_xlsx())
    with ZipFile(oversized_archive, "a", compression=ZIP_DEFLATED) as archive:
        archive.writestr("xl/media/padding.bin", b"0" * (101 * 1024 * 1024))
    with pytest.raises(WorkbookExtractionError, match="uncompressed size limit"):
        StructuralXlsxAdapter().extract_cells(oversized_archive.getvalue(), "zip-bomb")

    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "Revenue"
    sheet["XFD1048576"] = "declared edge"
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    with pytest.raises(WorkbookExtractionError, match="cell limit"):
        StructuralXlsxAdapter().extract_cells(stream.getvalue(), "oversized-grid")


def test_oversized_pdf_page_is_not_rasterized_for_ocr() -> None:
    document = fitz.open()
    document.new_page(width=10_000, height=10_000)
    content = document.tobytes()
    document.close()
    ocr = PaddleOcrCompatibleAdapter(lambda _: (("should not run", 1.0),))
    with pytest.raises(PdfExtractionError, match="OCR raster limit"):
        NativePdfAdapter(ocr).extract_pages(content, "oversized-page")
