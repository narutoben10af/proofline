from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from proofline.contracts import FinancialClaim, FrozenModel, Identifier


class ProviderState(StrEnum):
    NOT_CONFIGURED = "not_configured"
    LOADING = "loading"
    COMPLETED = "completed"
    OFFLINE = "offline"
    ERROR = "error"
    FALLBACK = "fallback"


class ProviderError(FrozenModel):
    code: Literal["not_configured", "offline", "provider_error", "unsupported_prompt"]
    message: str = Field(min_length=1, max_length=240)
    retryable: bool


class EvidenceCitation(FrozenModel):
    evidence_id: Identifier
    source_span_id: Identifier
    label: str = Field(min_length=1, max_length=160)


class EvidenceExcerpt(FrozenModel):
    evidence_id: Identifier
    source_span_id: Identifier
    text: str = Field(min_length=1, max_length=4_000)


class AssistantRequest(FrozenModel):
    prompt: str = Field(min_length=1, max_length=2_000)
    evidence: tuple[EvidenceExcerpt, ...] = Field(min_length=1, max_length=12)
    provider_sent: Literal[True]

    @model_validator(mode="after")
    def unique_spans(self) -> "AssistantRequest":
        evidence_ids = [item.evidence_id for item in self.evidence]
        span_ids = [item.source_span_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)) or len(span_ids) != len(set(span_ids)):
            raise ValueError("evidence IDs and source span IDs must be unique")
        if sum(len(item.text) for item in self.evidence) > 16_000:
            raise ValueError("combined assistant evidence exceeds 16000 characters")
        return self


class AssistantResult(FrozenModel):
    state: ProviderState
    content: str | None = Field(default=None, max_length=4_000)
    citations: tuple[EvidenceCitation, ...] = Field(default=(), max_length=12)
    error: ProviderError | None = None
    provider: str
    model: str
    disclosure: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def state_is_consistent(self) -> "AssistantResult":
        answered = self.state in {ProviderState.COMPLETED, ProviderState.FALLBACK}
        if answered and (not self.content or not self.citations):
            raise ValueError("answers require content and at least one citation")
        if not answered and (self.content is not None or self.citations):
            raise ValueError("non-answer states cannot contain content or citations")
        if (self.state == ProviderState.ERROR) != (self.error is not None):
            raise ValueError("only error state may contain an error")
        return self


class SourcePage(FrozenModel):
    page: int = Field(ge=1, le=500)
    source_span_id: Identifier
    text: str = Field(min_length=1, max_length=8_000)


class ClaimExtractionRequest(FrozenModel):
    pages: tuple[SourcePage, ...] = Field(min_length=1, max_length=8)
    provider_sent: Literal[True]

    @model_validator(mode="after")
    def bounded_unique_pages(self) -> "ClaimExtractionRequest":
        pages = [page.page for page in self.pages]
        spans = [page.source_span_id for page in self.pages]
        if len(pages) != len(set(pages)) or len(spans) != len(set(spans)):
            raise ValueError("pages and source_span_ids must be unique")
        if sum(len(page.text) for page in self.pages) > 32_000:
            raise ValueError("combined source text exceeds 32000 characters")
        return self


class ClaimExtractionResult(FrozenModel):
    state: ProviderState
    claims: tuple[FinancialClaim, ...] = Field(default=(), max_length=24)
    citations: tuple[EvidenceCitation, ...] = Field(default=(), max_length=24)
    error: ProviderError | None = None
    provider: str
    model: str
    disclosure: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def provenance_is_complete(self) -> "ClaimExtractionResult":
        if self.state not in {ProviderState.COMPLETED, ProviderState.FALLBACK}:
            if self.claims or self.citations:
                raise ValueError("non-answer states cannot contain claims or citations")
        cited = {citation.source_span_id for citation in self.citations}
        if any(claim.source_span_id not in cited for claim in self.claims):
            raise ValueError("every extracted claim requires a source-span citation")
        if (self.state == ProviderState.ERROR) != (self.error is not None):
            raise ValueError("only error state may contain an error")
        return self


class ProviderStatus(FrozenModel):
    state: Literal["not_configured", "ready", "fixture"]
    provider: str
    model: str
    live_transport_enabled: bool
    document_content_sent: Literal[False] = False
    disclosure: str


class ProviderConnectionTest(FrozenModel):
    reachable: bool
    state: Literal["not_configured", "ready", "offline", "error"]
    disclosure: str
