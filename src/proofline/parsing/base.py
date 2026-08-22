from collections.abc import Sequence
from typing import Protocol

from proofline.parsing.models import ExtractedCell, ExtractedPage


class DocumentAdapter(Protocol):
    """Page-aware deterministic document extraction contract."""

    def extract_pages(self, content: bytes, document_id: str) -> Sequence[ExtractedPage]: ...


class WorkbookAdapter(Protocol):
    """Structural workbook extraction contract; semantic mapping remains separate."""

    def extract_cells(self, content: bytes, document_id: str) -> Sequence[ExtractedCell]: ...


class OcrAdapter(Protocol):
    """Optional page-image OCR boundary; implementations never perform analysis."""

    def extract_page(self, image: bytes, document_id: str, page: int) -> ExtractedPage: ...
