from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from proofline.contracts import (
    METRIC_REGISTRY_VERSION,
    POLICY_VERSION,
    SCHEMA_VERSION,
    AnalysisResponse,
    Classification,
    FrozenModel,
    Identifier,
    Period,
    ReportSnapshot,
)

NO_CAUSATION = "Context only; no causal relationship is asserted."
DATA_HANDLING_DISCLOSURE = (
    "Deletion applies only to application-managed session storage. It does not provide "
    "secure erasure, delete data held by providers, or remove PDF or JSON exports already "
    "downloaded by users."
)
LIVE_SOURCE_DISCLOSURE = (
    "Rendered from the supplied calculated analysis; no data was fetched or recalculated "
    "during PDF rendering."
)
CACHED_BANNER = "VERIFIED CACHED ANALYSIS - review the cache disclosure below."
LIVE_BANNER = "CALCULATED ANALYSIS - rendered from the supplied immutable bundle."

_OFFICIAL_HOSTS = {
    "apple.com",
    "bea.gov",
    "bls.gov",
    "bnm.gov.my",
    "dosm.gov.my",
    "eia.gov",
    "federalreserve.gov",
    "financialmarkets.bnm.gov.my",
    "fred.stlouisfed.org",
    "petronas.com",
}
_CAUSAL_LANGUAGE = re.compile(r"\b(driven by|resulted in|explains?)\b", re.IGNORECASE)


class SourceMode(StrEnum):
    CALCULATED_LIVE = "calculated_live"
    VERIFIED_CACHED = "verified_cached"


def _require_official_https(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not any(
        host == allowed or host.endswith(f".{allowed}") for allowed in _OFFICIAL_HOSTS
    ):
        raise ValueError("official source URL must use HTTPS on an approved official domain")
    return value


def _reject_causal_language(value: str, field: str) -> None:
    if _CAUSAL_LANGUAGE.search(value):
        raise ValueError(f"{field} contains prohibited causal language")


class ResolvedEconomicContextPoint(FrozenModel):
    id: Identifier
    company: str = Field(min_length=1, max_length=256)
    indicator: str = Field(min_length=1, max_length=128)
    geography: str = Field(min_length=1, max_length=128)
    period: Period
    value: Decimal
    display_value: str = Field(min_length=1, max_length=64)
    unit: str = Field(min_length=1, max_length=64)
    official_source_url: str
    published_on: date
    retrieved_on: date
    relevance: str = Field(min_length=1, max_length=1_000)
    comparability_warning: str = Field(min_length=1, max_length=1_000)
    caveat: Literal["Context only; no causal relationship is asserted."] = NO_CAUSATION
    default_visible: bool = True

    @model_validator(mode="after")
    def validate_source_and_language(self) -> ResolvedEconomicContextPoint:
        _require_official_https(self.official_source_url)
        if not self.value.is_finite() or abs(self.value) > Decimal("1e12"):
            raise ValueError("economic context value must be finite and bounded")
        if self.published_on > self.retrieved_on:
            raise ValueError("publication date cannot be after retrieval date")
        _reject_causal_language(self.relevance, "relevance")
        _reject_causal_language(self.comparability_warning, "comparability warning")
        return self


class FinancialTrendPoint(FrozenModel):
    period: Period
    value: Decimal
    reporting_basis: str = Field(min_length=1, max_length=256)
    evidence_source_span_id: Identifier | None = None
    official_source_url: str | None = None
    historical: Literal[True] = True

    @model_validator(mode="after")
    def validate_value_and_source(self) -> FinancialTrendPoint:
        if not self.value.is_finite() or abs(self.value) > Decimal("1e100"):
            raise ValueError("trend value must be finite and bounded")
        if self.official_source_url is not None:
            _require_official_https(self.official_source_url)
        return self


class FinancialTrendSeries(FrozenModel):
    id: Identifier
    company: str = Field(min_length=1, max_length=256)
    indicator: str = Field(min_length=1, max_length=128)
    unit: str = Field(min_length=1, max_length=64)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    points: tuple[FinancialTrendPoint, ...] = Field(min_length=3, max_length=20)
    includes_forecast: Literal[False] = False

    @model_validator(mode="after")
    def comparable_historical_points(self) -> FinancialTrendSeries:
        periods = tuple(point.period.end for point in self.points)
        if periods != tuple(sorted(periods)) or len(set(periods)) != len(periods):
            raise ValueError("trend periods must be unique and chronological")
        bases = {point.reporting_basis for point in self.points}
        if len(bases) != 1:
            raise ValueError("trend points must use one reporting basis")
        durations = {point.period.duration_weeks for point in self.points}
        if len(durations) != 1:
            raise ValueError("trend points must use comparable period durations")
        return self


class CompanyLens(FrozenModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    company_id: Identifier
    company: str
    reviewed_period: str
    trend: FinancialTrendSeries
    economic_context: tuple[ResolvedEconomicContextPoint, ...] = Field(min_length=1, max_length=4)
    additional_context: tuple[ResolvedEconomicContextPoint, ...] = Field(default=(), max_length=4)
    context_caveat: Literal["Context only; no causal relationship is asserted."] = NO_CAUSATION

    @model_validator(mode="after")
    def compact_and_consistent(self) -> CompanyLens:
        if len(self.economic_context) > 4:
            raise ValueError("Company Lens shows no more than four context points by default")
        all_points = self.economic_context + self.additional_context
        if any(point.company != self.company for point in all_points):
            raise ValueError("Company Lens context must match the company")
        if self.trend.company != self.company:
            raise ValueError("Company Lens trend must match the company")
        return self


class ReportRenderBundle(FrozenModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    policy_version: Literal["1.0.0"] = POLICY_VERSION
    metric_registry_version: Literal["1.0.0"] = METRIC_REGISTRY_VERSION
    company_id: Identifier
    company: str = Field(min_length=1, max_length=256)
    analysis: AnalysisResponse
    snapshot: ReportSnapshot
    trend: FinancialTrendSeries | None = None
    economic_context: tuple[ResolvedEconomicContextPoint, ...] = Field(min_length=1, max_length=8)
    source_mode: SourceMode
    source_disclosure: str = Field(min_length=1, max_length=1_000)
    data_handling_disclosure: Literal[
        "Deletion applies only to application-managed session storage. It does not provide "
        "secure erasure, delete data held by providers, or remove PDF or JSON exports already "
        "downloaded by users."
    ] = DATA_HANDLING_DISCLOSURE
    includes_forecast: Literal[False] = False

    @model_validator(mode="after")
    def validate_report_boundary(self) -> ReportRenderBundle:
        if (
            self.analysis.schema_version != self.schema_version
            or self.analysis.policy_version != self.policy_version
            or self.analysis.metric_registry_version != self.metric_registry_version
            or self.snapshot.schema_version != self.schema_version
        ):
            raise ValueError("bundle, analysis, snapshot, policy, and registry versions must match")
        if self.source_mode == SourceMode.CALCULATED_LIVE:
            if self.source_disclosure != LIVE_SOURCE_DISCLOSURE:
                raise ValueError("calculated_live requires the fixed live disclosure")
        elif not self.source_disclosure.strip():
            raise ValueError("verified_cached requires a cache disclosure")

        groups = (
            ("document", tuple(item.id for item in self.analysis.documents)),
            ("source span", tuple(item.id for item in self.analysis.source_spans)),
            ("claim", tuple(item.id for item in self.analysis.claims)),
            ("observation", tuple(item.id for item in self.analysis.observations)),
            ("metric result", tuple(item.id for item in self.analysis.metric_results)),
            ("finding", tuple(item.id for item in self.analysis.findings)),
            ("context", tuple(item.id for item in self.economic_context)),
        )
        for label, identifiers in groups:
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"duplicate {label} IDs are not allowed")

        documents = {item.id for item in self.analysis.documents}
        spans = {item.id: item for item in self.analysis.source_spans}
        claims = {item.id: item for item in self.analysis.claims}
        observations = {item.id: item for item in self.analysis.observations}
        results = {item.id: item for item in self.analysis.metric_results}
        findings = {item.id: item for item in self.analysis.findings}
        for span in spans.values():
            if span.document_version_id not in documents:
                raise ValueError(f"unknown document_version_id: {span.document_version_id}")
            if span.source.document_id != span.document_version_id:
                raise ValueError(f"source document_id differs for span: {span.id}")
        for observation in observations.values():
            if observation.source_span_id not in spans:
                raise ValueError(
                    f"unknown observation source_span_id: {observation.source_span_id}"
                )
        for claim in claims.values():
            if claim.source_span_id not in spans:
                raise ValueError(f"unknown claim source_span_id: {claim.source_span_id}")
        for result in results.values():
            unknown = set(result.input_observation_ids) - observations.keys()
            if unknown:
                raise ValueError(f"unknown metric input observation IDs: {sorted(unknown)}")
        for finding in findings.values():
            if finding.claim_id not in claims:
                raise ValueError(f"unknown finding claim_id: {finding.claim_id}")
            if finding.metric_result_id not in results:
                raise ValueError(f"unknown finding metric_result_id: {finding.metric_result_id}")
            unknown = set(finding.evidence_source_span_ids) - spans.keys()
            if unknown:
                raise ValueError(f"unknown finding evidence span IDs: {sorted(unknown)}")
            _reject_causal_language(finding.rationale, "finding rationale")
            if finding.suggested_investigation is not None:
                _reject_causal_language(
                    finding.suggested_investigation,
                    "finding suggested investigation",
                )

        ordered_finding_ids = self.snapshot.finding_ids
        if not ordered_finding_ids:
            raise ValueError("report requires at least one reviewed finding")
        if len(ordered_finding_ids) != len(set(ordered_finding_ids)):
            raise ValueError("snapshot finding IDs must be unique")
        if set(ordered_finding_ids) != findings.keys():
            raise ValueError("snapshot finding IDs must exactly match analysis findings")
        actual_counts = {
            classification: sum(
                finding.classification == classification for finding in findings.values()
            )
            for classification in Classification
        }
        if (
            self.snapshot.classification_counts.supported != actual_counts[Classification.SUPPORTED]
            or self.snapshot.classification_counts.uncertain
            != actual_counts[Classification.UNCERTAIN]
            or self.snapshot.classification_counts.contradicted
            != actual_counts[Classification.CONTRADICTED]
        ):
            raise ValueError("snapshot classification counts do not match analysis findings")

        context_ids = tuple(point.id for point in self.economic_context)
        if len(self.snapshot.economic_context_point_ids) != len(
            set(self.snapshot.economic_context_point_ids)
        ):
            raise ValueError("snapshot economic context IDs must be unique")
        if set(self.snapshot.economic_context_point_ids) != set(context_ids):
            raise ValueError("snapshot context IDs must exactly match resolved context")
        if any(point.company != self.company for point in self.economic_context):
            raise ValueError("economic context must match bundle company")
        if sum(point.default_visible for point in self.economic_context) > 4:
            raise ValueError("no more than four context points may be visible by default")

        if self.snapshot.evidence_chain_sha256 != canonical_sha256(self.analysis):
            raise ValueError("snapshot evidence hash does not match the full analysis response")
        if (
            self.snapshot.reviewed_at.tzinfo is None
            or self.snapshot.reviewed_at.utcoffset() is None
        ):
            raise ValueError("snapshot review timestamp must be timezone-aware")
        if self.trend is not None:
            if self.trend.company != self.company:
                raise ValueError("trend must match bundle company")
            for point in self.trend.points:
                if point.evidence_source_span_id is None:
                    raise ValueError("report trend points require evidence source span IDs")
                if point.evidence_source_span_id not in spans:
                    raise ValueError(
                        f"unknown trend evidence span ID: {point.evidence_source_span_id}"
                    )
                if point.period.end > self.snapshot.reviewed_at.date():
                    raise ValueError("trend cannot include a period after the review date")
        for value in (self.snapshot.title, *self.snapshot.limitations):
            _reject_causal_language(value, "report-generated text")
        return self


def _decimal_string(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("non-finite Decimal cannot be canonicalized")
    if value == 0:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _timestamp_string(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("canonical timestamps must be timezone-aware")
    utc = value.astimezone(UTC)
    rendered = utc.strftime("%Y-%m-%dT%H:%M:%S")
    if utc.microsecond:
        rendered += f".{utc.microsecond:06d}".rstrip("0")
    return f"{rendered}Z"


def canonical_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return canonical_value(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {str(key): canonical_value(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple | list):
        return [canonical_value(item) for item in value]
    if isinstance(value, Decimal):
        return _decimal_string(value)
    if isinstance(value, datetime):
        return _timestamp_string(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite float cannot be canonicalized")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        canonical_value(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
