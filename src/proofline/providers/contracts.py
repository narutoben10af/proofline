from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from proofline.contracts import (
    FactObservation,
    FinancialClaim,
    FrozenModel,
    Identifier,
    MetricResult,
)

SafeChartText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=500, pattern=r"^[^<>{}]*$"),
]


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


class ChartType(StrEnum):
    LINE = "line"
    BAR = "bar"
    COMPARISON = "comparison"


class ChartSeriesProposal(FrozenModel):
    label: SafeChartText
    observation_ids: tuple[Identifier, ...] = Field(default=(), max_length=12)
    metric_result_ids: tuple[Identifier, ...] = Field(default=(), max_length=12)
    source_span_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def one_reference_kind(self) -> "ChartSeriesProposal":
        if bool(self.observation_ids) == bool(self.metric_result_ids):
            raise ValueError("a chart series must reference observations or metric results")
        identifiers = self.observation_ids or self.metric_result_ids
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("chart point IDs must be unique within a series")
        if len(self.source_span_ids) != len(set(self.source_span_ids)):
            raise ValueError("chart source span IDs must be unique within a series")
        return self


class ChartProposal(FrozenModel):
    chart_type: ChartType
    title: SafeChartText
    description: SafeChartText
    period_start: date | None = None
    period_end: date
    series: tuple[ChartSeriesProposal, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def valid_range_and_size(self) -> "ChartProposal":
        if self.period_start is not None and self.period_start > self.period_end:
            raise ValueError("chart period start must not follow period end")
        total = sum(len(item.observation_ids or item.metric_result_ids) for item in self.series)
        if total > 24:
            raise ValueError("chart proposal exceeds 24 total points")
        return self


class ChartRequest(FrozenModel):
    prompt: str = Field(min_length=1, max_length=2_000)
    observations: tuple[FactObservation, ...] = Field(min_length=1, max_length=24)
    metric_results: tuple[MetricResult, ...] = Field(default=(), max_length=12)
    provider_sent: Literal[True]

    @model_validator(mode="after")
    def unique_backend_ids(self) -> "ChartRequest":
        for label, identifiers in (
            ("observation", [item.id for item in self.observations]),
            ("metric result", [item.id for item in self.metric_results]),
        ):
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"duplicate {label} IDs are not allowed")
        observation_ids = {item.id for item in self.observations}
        if any(
            input_id not in observation_ids
            for result in self.metric_results
            for input_id in result.input_observation_ids
        ):
            raise ValueError("metric result inputs must resolve to supplied observations")
        return self


class ChartPoint(FrozenModel):
    id: Identifier
    period_start: date | None = None
    period_end: date
    value: Decimal
    source_span_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=8)


class ChartSeries(FrozenModel):
    label: SafeChartText
    entity_scope: str = Field(min_length=1, max_length=256)
    unit: str = Field(min_length=1, max_length=64)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    points: tuple[ChartPoint, ...] = Field(min_length=1, max_length=12)


class ChartSpec(FrozenModel):
    chart_type: ChartType
    title: SafeChartText
    description: SafeChartText
    period_start: date | None = None
    period_end: date
    series: tuple[ChartSeries, ...] = Field(min_length=1, max_length=4)
    citations: tuple[EvidenceCitation, ...] = Field(min_length=1, max_length=48)
    authoritative_values: Literal["deterministic_backend"] = "deterministic_backend"


class ChartResult(FrozenModel):
    state: ProviderState
    chart: ChartSpec | None = None
    error: ProviderError | None = None
    provider: str
    model: str
    disclosure: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def state_is_consistent(self) -> "ChartResult":
        completed = self.state in {ProviderState.COMPLETED, ProviderState.FALLBACK}
        if completed != (self.chart is not None):
            raise ValueError("only completed or fallback chart states may contain a chart")
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
