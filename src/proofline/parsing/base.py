from collections.abc import Sequence
from typing import Protocol

from proofline.contracts import FactObservation, SourceSpan


class DocumentAdapter(Protocol):
    """Narrow, page-aware contract implemented by future native PDF adapters."""

    def extract_spans(self, content: bytes) -> Sequence[SourceSpan]: ...


class WorkbookAdapter(Protocol):
    """Narrow contract for allowlisted workbook layouts; not a universal parser."""

    def extract_observations(self, content: bytes) -> Sequence[FactObservation]: ...
