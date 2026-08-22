from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = "1.0.0"
METRIC_REGISTRY_VERSION = "1.0.0"
POLICY_VERSION = "1.0.0"

Identifier = Annotated[
    str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Classification(StrEnum):
    SUPPORTED = "supported"
    UNCERTAIN = "uncertain"
    CONTRADICTED = "contradicted"


class ExceptionalState(StrEnum):
    MISSING_INPUT = "missing_input"
    INCOMPARABLE = "incomparable"
    ZERO_OR_NEGATIVE_DENOMINATOR = "zero_or_negative_denominator"
    UNRESOLVED_SIGN = "unresolved_sign"
    INVALID_PLAN = "invalid_plan"
    NUMERIC_RANGE = "numeric_range"


class MetricId(StrEnum):
    REVENUE_GROWTH_YOY = "revenue_growth_yoy"
    OPERATING_MARGIN = "operating_margin"
    CURRENT_RATIO = "current_ratio"
    FCF_MARGIN = "fcf_margin"


class Period(FrozenModel):
    start: date | None = None
    end: date
    duration_weeks: int | None = Field(default=None, ge=1, le=54)

    @model_validator(mode="after")
    def ordered_dates(self) -> Period:
        if self.start is not None and self.start > self.end:
            raise ValueError("period start must be on or before end")
        return self


class PdfSourceRef(FrozenModel):
    kind: Literal["pdf"] = "pdf"
    document_id: Identifier
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=2_000)


class SpreadsheetSourceRef(FrozenModel):
    kind: Literal["spreadsheet"] = "spreadsheet"
    document_id: Identifier
    sheet: str = Field(min_length=1, max_length=128)
    cell: str = Field(pattern=r"^[A-Z]{1,3}[1-9][0-9]*(?::[A-Z]{1,3}[1-9][0-9]*)?$")
    display_value: str = Field(min_length=1, max_length=256)


SourceRef = Annotated[PdfSourceRef | SpreadsheetSourceRef, Field(discriminator="kind")]


class DocumentVersion(FrozenModel):
    id: Identifier
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    issuer: str = Field(min_length=1, max_length=256)
    source_url: str
    retrieved_at: datetime
    reporting_basis: str = Field(min_length=1, max_length=256)
    version_label: str = Field(min_length=1, max_length=128)


class SourceSpan(FrozenModel):
    id: Identifier
    document_version_id: Identifier
    source: SourceRef


class FactObservation(FrozenModel):
    id: Identifier
    source_span_id: Identifier
    concept: str = Field(min_length=1, max_length=128)
    numeric_value: Decimal
    display_value: str = Field(min_length=1, max_length=256)
    unit: str = Field(min_length=1, max_length=64)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    period: Period
    entity_scope: str = Field(min_length=1, max_length=256)
    restated: bool | None
    sign_convention: (
        Literal["positive", "cash_outflow_positive", "cash_outflow_negative"] | None
    ) = None
    fixture_status: Literal["official", "derived"]


class FinancialClaim(FrozenModel):
    id: Identifier
    text: str = Field(min_length=1, max_length=4_000)
    entity: str | None = Field(default=None, max_length=256)
    metric_id: MetricId
    period: Period
    asserted_value: Decimal | None = None
    asserted_direction: Literal["up", "down", "flat"] | None = None
    unit: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    source_span_id: Identifier
    extraction_warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def has_assertion(self) -> FinancialClaim:
        if self.asserted_value is None and self.asserted_direction is None:
            raise ValueError("a claim requires asserted_value or asserted_direction")
        return self


class CalculationInput(FrozenModel):
    role: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    observation_id: Identifier


class MetricCalculationPlan(FrozenModel):
    """A data-only dispatch plan; expressions and executable code are not accepted."""

    metric_id: MetricId
    inputs: tuple[CalculationInput, ...] = Field(min_length=1, max_length=8)


class AnalysisItem(FrozenModel):
    claim_id: Identifier
    calculation_plan: MetricCalculationPlan


class AnalysisRequest(FrozenModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    documents: tuple[DocumentVersion, ...] = Field(min_length=1, max_length=20)
    source_spans: tuple[SourceSpan, ...] = Field(min_length=1, max_length=1_000)
    claims: tuple[FinancialClaim, ...] = Field(min_length=1, max_length=100)
    observations: tuple[FactObservation, ...] = Field(min_length=1, max_length=500)
    items: tuple[AnalysisItem, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def ids_are_unique(self) -> AnalysisRequest:
        for label, values in (
            ("document", (document.id for document in self.documents)),
            ("source span", (span.id for span in self.source_spans)),
            ("claim", (claim.id for claim in self.claims)),
            ("observation", (observation.id for observation in self.observations)),
        ):
            identifiers = tuple(values)
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"duplicate {label} IDs are not allowed")
        return self

    @model_validator(mode="after")
    def references_are_resolvable(self) -> AnalysisRequest:
        document_ids = {document.id for document in self.documents}
        spans = {span.id: span for span in self.source_spans}
        claim_ids = {claim.id for claim in self.claims}
        for span in self.source_spans:
            if span.document_version_id not in document_ids:
                raise ValueError(f"unknown document_version_id: {span.document_version_id}")
            if span.source.document_id != span.document_version_id:
                raise ValueError(f"source document_id differs for span: {span.id}")
        for observation in self.observations:
            if observation.source_span_id not in spans:
                raise ValueError(
                    f"unknown observation source_span_id: {observation.source_span_id}"
                )
        for claim in self.claims:
            if claim.source_span_id not in spans:
                raise ValueError(f"unknown claim source_span_id: {claim.source_span_id}")
        for item in self.items:
            if item.claim_id not in claim_ids:
                raise ValueError(f"unknown claim_id: {item.claim_id}")
        return self


class MetricResult(FrozenModel):
    id: Identifier
    metric_id: MetricId
    registry_version: Literal["1.0.0"] = METRIC_REGISTRY_VERSION
    formula_id: str
    input_observation_ids: tuple[Identifier, ...]
    result: Decimal | None = None
    exceptional_state: ExceptionalState | None = None
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def exactly_one_outcome(self) -> MetricResult:
        if (self.result is None) == (self.exceptional_state is None):
            raise ValueError("metric result requires exactly one of result or exceptional_state")
        return self


class Finding(FrozenModel):
    id: Identifier
    claim_id: Identifier
    metric_result_id: Identifier
    policy_version: Literal["1.0.0"] = POLICY_VERSION
    classification: Classification
    rationale: str
    tolerance: Decimal | None = None
    evidence_source_span_ids: tuple[Identifier, ...]
    warnings: tuple[str, ...] = ()
    suggested_investigation: str | None = None


class AnalysisResponse(FrozenModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    metric_registry_version: Literal["1.0.0"] = METRIC_REGISTRY_VERSION
    policy_version: Literal["1.0.0"] = POLICY_VERSION
    output_status: Literal["calculated"] = "calculated"
    cached_output: Literal[False] = False
    fallback_disclosure: str | None = None
    documents: tuple[DocumentVersion, ...]
    source_spans: tuple[SourceSpan, ...]
    claims: tuple[FinancialClaim, ...]
    observations: tuple[FactObservation, ...]
    metric_results: tuple[MetricResult, ...]
    findings: tuple[Finding, ...]


class EvidenceChainSnapshot(FrozenModel):
    """Portable, versioned representation of the immutable evidence lineage."""

    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    documents: tuple[DocumentVersion, ...]
    source_spans: tuple[SourceSpan, ...]
    observations: tuple[FactObservation, ...]
    metric_results: tuple[MetricResult, ...]
    findings: tuple[Finding, ...]


class HealthResponse(FrozenModel):
    status: Literal["ok"] = "ok"
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    metric_registry_version: Literal["1.0.0"] = METRIC_REGISTRY_VERSION
    model_provider: str
    model_configured: bool


class FixtureInput(FrozenModel):
    kind: Literal["fixture"] = "fixture"
    fixture_id: Literal["apple-fy2025", "pcg-fy2025"]
    public_data_confirmed: Literal[True]


class UploadInput(FrozenModel):
    kind: Literal["upload"] = "upload"
    pdf_filename: str = Field(min_length=5, max_length=255, pattern=r"(?i)^.+\.pdf$")
    workbook_filename: str = Field(
        min_length=6, max_length=255, pattern=r"(?i)^.+\.(xlsx|csv|json)$"
    )
    public_data_confirmed: Literal[True]


SessionInput = Annotated[FixtureInput | UploadInput, Field(discriminator="kind")]


class CreateSessionRequest(FrozenModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    input: SessionInput


class ProcessingError(FrozenModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    stage: Literal["intake", "pdf", "workbook", "model", "analysis"]
    message: str = Field(min_length=1, max_length=500)
    retryable: bool


class SessionStatus(FrozenModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    session_id: Identifier
    state: Literal["accepted", "processing", "completed", "failed"]
    input: SessionInput
    cached_output_status: Literal["not_checked", "available", "in_use", "unavailable"]
    fallback_disclosure: str | None = None
    errors: tuple[ProcessingError, ...] = ()


class DeletionReceipt(FrozenModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    session_id: Identifier
    deleted_at: datetime
    deleted: Literal[True] = True
    scope: tuple[Literal["in_memory_session_metadata"], ...] = ("in_memory_session_metadata",)
    disclosure: str


class EconomicContextPoint(FrozenModel):
    id: Identifier
    indicator: str = Field(min_length=1, max_length=128)
    geography: str = Field(min_length=1, max_length=128)
    period: Period
    value: Decimal
    unit: str = Field(min_length=1, max_length=64)
    source_url: str
    source_date: date
    causation_caveat: Literal["Context only; no causal relationship is asserted."] = (
        "Context only; no causal relationship is asserted."
    )


class ClassificationCounts(FrozenModel):
    supported: int = Field(ge=0)
    uncertain: int = Field(ge=0)
    contradicted: int = Field(ge=0)


class AnalysisHistorySummary(FrozenModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    analysis_id: Identifier
    session_id: Identifier
    created_at: datetime
    classification_counts: ClassificationCounts
    cached_output: bool
    session_local_only: Literal[True] = True


class ReportSnapshot(FrozenModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    snapshot_id: Identifier
    analysis_id: Identifier
    title: str = Field(min_length=1, max_length=256)
    reviewed_at: datetime
    review_status: Literal["reviewed"] = "reviewed"
    classification_counts: ClassificationCounts
    finding_ids: tuple[Identifier, ...] = Field(max_length=100)
    evidence_chain_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    economic_context_point_ids: tuple[Identifier, ...] = Field(max_length=100)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=50)
    includes_forecast: Literal[False] = False


class ExtensionContracts(FrozenModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    economic_context_points: tuple[EconomicContextPoint, ...]
    analysis_history: tuple[AnalysisHistorySummary, ...]
    report_snapshots: tuple[ReportSnapshot, ...]
