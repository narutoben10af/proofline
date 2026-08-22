from proofline.contracts import FinancialClaim
from proofline.providers.contracts import (
    AssistantRequest,
    AssistantResult,
    ClaimExtractionRequest,
    ClaimExtractionResult,
    EvidenceCitation,
    ProviderConnectionTest,
    ProviderError,
    ProviderState,
    ProviderStatus,
)


class DeterministicFixtureProvider:
    """Test/demo provider that only returns injected, source-linked fixture outputs."""

    def __init__(
        self, answers: dict[str, str] | None = None, claims: tuple[FinancialClaim, ...] = ()
    ) -> None:
        self._answers = {key.casefold().strip(): value for key, value in (answers or {}).items()}
        self._claims = claims

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            state="fixture",
            provider="deterministic_fixture",
            model="fixture-v1",
            live_transport_enabled=False,
            disclosure=(
                "Deterministic fixture only; no network request or model inference occurred."
            ),
        )

    async def test_connection(self) -> ProviderConnectionTest:
        return ProviderConnectionTest(
            reachable=False,
            state="error",
            disclosure="Fixture provider has no external connection to test.",
        )

    async def assist(self, request: AssistantRequest) -> AssistantResult:
        answer = self._answers.get(request.prompt.casefold().strip())
        disclosure = "Deterministic fixture only; no network request or model inference occurred."
        if answer is None:
            return AssistantResult(
                state=ProviderState.ERROR,
                error=ProviderError(
                    code="unsupported_prompt",
                    message="This deterministic fixture does not support that prompt.",
                    retryable=False,
                ),
                provider="deterministic_fixture",
                model="fixture-v1",
                disclosure=disclosure,
            )
        evidence = request.evidence[0]
        return AssistantResult(
            state=ProviderState.FALLBACK,
            content=answer,
            citations=(
                EvidenceCitation(
                    evidence_id=evidence.evidence_id,
                    source_span_id=evidence.source_span_id,
                    label=evidence.evidence_id,
                ),
            ),
            provider="deterministic_fixture",
            model="fixture-v1",
            disclosure=disclosure,
        )

    async def extract_claims(self, request: ClaimExtractionRequest) -> ClaimExtractionResult:
        span_ids = {page.source_span_id for page in request.pages}
        claims = tuple(claim for claim in self._claims if claim.source_span_id in span_ids)
        citations = tuple(
            EvidenceCitation(
                evidence_id=claim.source_span_id,
                source_span_id=claim.source_span_id,
                label=claim.source_span_id,
            )
            for claim in claims
        )
        return ClaimExtractionResult(
            state=ProviderState.FALLBACK,
            claims=claims,
            citations=citations,
            provider="deterministic_fixture",
            model="fixture-v1",
            disclosure=(
                "Deterministic fixture only; no network request or model inference occurred."
            ),
        )
