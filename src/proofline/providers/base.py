from collections.abc import Sequence
from typing import Protocol

from proofline.contracts import FinancialClaim


class ProviderUnavailable(RuntimeError):
    """Raised when an optional hosted extraction provider is not configured."""


class ClaimExtractionProvider(Protocol):
    async def extract_claims(self, page_text: Sequence[str]) -> tuple[FinancialClaim, ...]: ...
