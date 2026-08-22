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


class MetricId(StrEnum):
    REVENUE_GROWTH_YOY = "revenue_growth_yoy"
    OPERATING_MARGIN = "operating_margin"
    CURRENT_RATIO = "current_ratio"
    FCF_MARGIN = "fcf_margin"


class Period(FrozenModel):
    start: date | None = None
    end: date
    duration_weeks: int | None = Field(default=None, ge=1, le=54)


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
    claims: tuple[FinancialClaim, ...] = Field(min_length=1, max_length=100)
    observations: tuple[FactObservation, ...] = Field(min_length=1, max_length=500)
    items: tuple[AnalysisItem, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def ids_are_unique(self) -> AnalysisRequest:
        for label, values in (
            ("claim", (claim.id for claim in self.claims)),
            ("observation", (observation.id for observation in self.observations)),
        ):
            identifiers = tuple(values)
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"duplicate {label} IDs are not allowed")
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
