from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from proofline.contracts import FrozenModel, SourceSpan


class ExtractionMethod(StrEnum):
    NATIVE_PDF = "native_pdf"
    SPREADSHEET = "spreadsheet"
    OCR = "ocr"


class ExtractionWarning(FrozenModel):
    code: Literal[
        "native_text_missing",
        "native_text_sparse",
        "ocr_not_configured",
        "ocr_low_confidence",
        "formula_without_cached_value",
        "formula_cached_value_unverified",
        "cell_limit_reached",
    ]
    message: str = Field(min_length=1, max_length=500)


class ExtractedPage(FrozenModel):
    span: SourceSpan | None
    page: int = Field(ge=1)
    method: Literal[ExtractionMethod.NATIVE_PDF, ExtractionMethod.OCR]
    confidence: float = Field(ge=0, le=1)
    warnings: tuple[ExtractionWarning, ...] = ()


class ExtractedCell(FrozenModel):
    span: SourceSpan
    method: Literal[ExtractionMethod.SPREADSHEET] = ExtractionMethod.SPREADSHEET
    confidence: Literal[1.0] = 1.0
    data_type: Literal["number", "text", "boolean", "date", "formula", "error"]
    warnings: tuple[ExtractionWarning, ...] = ()
