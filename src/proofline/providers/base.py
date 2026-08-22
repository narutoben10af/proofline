from typing import Protocol

from proofline.providers.contracts import (
    AssistantRequest,
    AssistantResult,
    ClaimExtractionRequest,
    ClaimExtractionResult,
    ProviderConnectionTest,
    ProviderStatus,
)


class ProviderUnavailable(RuntimeError):
    """Raised when an optional hosted extraction provider is not configured."""


class AnalysisProvider(Protocol):
    def status(self) -> ProviderStatus: ...

    async def test_connection(self) -> ProviderConnectionTest: ...

    async def assist(self, request: AssistantRequest) -> AssistantResult: ...

    async def extract_claims(self, request: ClaimExtractionRequest) -> ClaimExtractionResult: ...


ClaimExtractionProvider = AnalysisProvider
