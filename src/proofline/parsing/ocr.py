from __future__ import annotations

import hashlib
import math
import os
import subprocess
from collections.abc import Callable, Iterable
from itertools import islice
from pathlib import Path

from proofline.contracts import PdfSourceRef, SourceSpan
from proofline.parsing.models import ExtractedPage, ExtractionMethod, ExtractionWarning

OcrLine = tuple[str, float]
MAX_OCR_LINES = 500


class OcrExtractionError(ValueError):
    pass


class TesseractOcrEngine:
    """Bounded adapter for an explicitly configured local Tesseract executable."""

    def __init__(self, command: Path, timeout_seconds: float = 20.0) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds

    def __call__(self, image: bytes) -> Iterable[OcrLine]:
        try:
            result = subprocess.run(  # noqa: S603
                [str(self.command), "stdin", "stdout", "--psm", "6", "tsv"],
                input=image,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OcrExtractionError("configured OCR runtime is unavailable") from error
        if result.returncode != 0 or len(result.stdout) > 2 * 1024 * 1024:
            raise OcrExtractionError("configured OCR runtime failed safely")
        lines: list[OcrLine] = []
        for raw_line in result.stdout.decode("utf-8", errors="replace").splitlines()[1:]:
            columns = raw_line.split("\t", 11)
            if len(columns) != 12 or not columns[11].strip():
                continue
            try:
                confidence = float(columns[10]) / 100
            except ValueError:
                continue
            if confidence >= 0:
                lines.append((columns[11], confidence))
        return lines


def configured_ocr_adapter(
    command: Path | None,
    *,
    timeout_seconds: float = 20.0,
    threshold: float = 0.7,
) -> PaddleOcrCompatibleAdapter | None:
    """Activate OCR only when an explicit absolute executable is genuinely available."""

    if command is None or not command.is_absolute():
        return None
    resolved = command.resolve()
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        return None
    return PaddleOcrCompatibleAdapter(
        TesseractOcrEngine(resolved, timeout_seconds=timeout_seconds), threshold=threshold
    )


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
