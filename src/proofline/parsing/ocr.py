from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Iterable
from itertools import islice

from proofline.contracts import PdfSourceRef, SourceSpan
from proofline.parsing.models import ExtractedPage, ExtractionMethod, ExtractionWarning

OcrLine = tuple[str, float]
MAX_OCR_LINES = 500


class OcrExtractionError(ValueError):
    pass


class PaddleOcrCompatibleAdapter:
    """Adapter for an injected PaddleOCR-like callable; Paddle is not bundled."""

    def __init__(
        self, engine: Callable[[bytes], Iterable[OcrLine]], threshold: float = 0.7
    ) -> None:
        self._engine = engine
        self._threshold = threshold

    def extract_page(self, image: bytes, document_id: str, page: int) -> ExtractedPage:
        raw_lines = tuple(islice(self._engine(image), MAX_OCR_LINES + 1))
        if len(raw_lines) > MAX_OCR_LINES:
            raise OcrExtractionError("OCR output exceeds the line limit")
        lines = tuple((text.strip(), float(score)) for text, score in raw_lines if text.strip())
        if any(not math.isfinite(score) or not 0 <= score <= 1 for _, score in lines):
            raise OcrExtractionError("OCR output contains an invalid confidence score")
        if not lines:
            return ExtractedPage(
                span=None,
                page=page,
                method=ExtractionMethod.OCR,
                confidence=0,
                warnings=(
                    ExtractionWarning(
                        code="ocr_low_confidence", message="OCR returned no usable text."
                    ),
                ),
            )
        text = " ".join(text for text, _ in lines)[:2_000]
        confidence = sum(score for _, score in lines) / len(lines)
        warnings = ()
        if confidence < self._threshold:
            warnings = (
                ExtractionWarning(
                    code="ocr_low_confidence",
                    message="OCR text is below the configured confidence threshold.",
                ),
            )
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        span = SourceSpan(
            id=f"span:{document_id}:pdf:{page}:ocr:{digest}",
            document_version_id=document_id,
            source=PdfSourceRef(document_id=document_id, page=page, quote=text),
        )
        return ExtractedPage(
            span=span,
            page=page,
            method=ExtractionMethod.OCR,
            confidence=confidence,
            warnings=warnings,
        )
