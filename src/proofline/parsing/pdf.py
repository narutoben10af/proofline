from __future__ import annotations

import hashlib

import fitz

from proofline.contracts import PdfSourceRef, SourceSpan
from proofline.parsing.base import OcrAdapter
from proofline.parsing.models import ExtractedPage, ExtractionMethod, ExtractionWarning

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PAGES = 250
MAX_PAGE_TEXT = 2_000
MIN_NATIVE_CHARACTERS = 20
MAX_OCR_PIXELS = 20_000_000
OCR_SCALE = 2


class PdfExtractionError(ValueError):
    pass


class NativePdfAdapter:
    def __init__(self, ocr: OcrAdapter | None = None) -> None:
        self._ocr = ocr

    def extract_pages(self, content: bytes, document_id: str) -> tuple[ExtractedPage, ...]:
        if not content.startswith(b"%PDF-"):
            raise PdfExtractionError("content is not a PDF")
        if len(content) > MAX_PDF_BYTES:
            raise PdfExtractionError("PDF exceeds the extraction size limit")
        try:
            document = fitz.open(stream=content, filetype="pdf")
        except Exception as error:
            raise PdfExtractionError("PDF could not be opened") from error
        try:
            if document.needs_pass:
                raise PdfExtractionError("encrypted PDFs are not supported")
            if document.page_count > MAX_PAGES:
                raise PdfExtractionError("PDF exceeds the page limit")
            return tuple(
                self._extract_page(document, index, content, document_id)
                for index in range(document.page_count)
            )
        finally:
            document.close()

    def _extract_page(
        self, document: fitz.Document, index: int, content: bytes, document_id: str
    ) -> ExtractedPage:
        page_number = index + 1
        text = " ".join(document[index].get_text("text").split())
        if len(text) >= MIN_NATIVE_CHARACTERS:
            quote = text[:MAX_PAGE_TEXT]
            span = SourceSpan(
                id=_span_id(document_id, page_number, quote, "native"),
                document_version_id=document_id,
                source=PdfSourceRef(document_id=document_id, page=page_number, quote=quote),
            )
            confidence = min(1.0, 0.8 + len(text) / 1_000)
            return ExtractedPage(
                span=span,
                page=page_number,
                method=ExtractionMethod.NATIVE_PDF,
                confidence=confidence,
            )

        warning = ExtractionWarning(
            code="native_text_missing" if not text else "native_text_sparse",
            message="Native PDF text was absent or too sparse for reliable extraction.",
        )
        if self._ocr is None:
            return ExtractedPage(
                span=None,
                page=page_number,
                method=ExtractionMethod.NATIVE_PDF,
                confidence=0,
                warnings=(
                    warning,
                    ExtractionWarning(
                        code="ocr_not_configured",
                        message="OCR fallback is optional and is not configured.",
                    ),
                ),
            )
        page = document[index]
        raster_width = int(page.rect.width * OCR_SCALE)
        raster_height = int(page.rect.height * OCR_SCALE)
        if raster_width * raster_height > MAX_OCR_PIXELS:
            raise PdfExtractionError("PDF page exceeds the OCR raster limit")
        pixmap = page.get_pixmap(matrix=fitz.Matrix(OCR_SCALE, OCR_SCALE), alpha=False)
        ocr_page = self._ocr.extract_page(pixmap.tobytes("png"), document_id, page_number)
        return ocr_page.model_copy(update={"warnings": (warning, *ocr_page.warnings)})


def _span_id(document_id: str, page: int, text: str, method: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"span:{document_id}:pdf:{page}:{method}:{digest}"
