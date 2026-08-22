from collections.abc import Sequence

from proofline.contracts import FinancialClaim
from proofline.providers.base import ProviderUnavailable


class GemmaProvider:
    """Narrow server-side boundary for future schema-constrained Gemma extraction.

    This first backend PR deliberately does not send source material over the network.
    Tests and deterministic analysis require no API key. A later adapter can implement
    this interface with timeout, retry, quota, and response-schema enforcement.
    """

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float, max_retries: int):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def extract_claims(self, page_text: Sequence[str]) -> tuple[FinancialClaim, ...]:
        del page_text
        if not self.configured:
            raise ProviderUnavailable("Gemma extraction is not configured; set GEMINI_API_KEY.")
        raise ProviderUnavailable(
            "Live Gemma transport is intentionally outside the first contract-focused backend PR."
        )
