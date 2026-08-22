from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from proofline.classification import classify
from proofline.contracts import (
    METRIC_REGISTRY_VERSION,
    POLICY_VERSION,
    SCHEMA_VERSION,
    AnalysisResponse,
    Classification,
    FinancialClaim,
    FrozenModel,
    Identifier,
    MetricId,
    MetricResult,
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
VERIFIED_CACHED_SOURCE_DISCLOSURE = (
    "Verified cached fixture reviewed on 2026-08-22; no source refresh occurred."
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
_REGISTERED_COMPANIES = {
    "apple-fy2025": "Apple Inc.",
    "example-group-fy2025": "Example Group",
    "pcg-fy2025": "PETRONAS Chemicals Group Berhad",
}
_ALLOWED_LIMITATIONS = frozenset({"Prototype output requires human review."})
_ALLOWED_DOCUMENT_VERSION_LABELS = frozenset({"FY2023", "FY2024", "FY2025"})
_ALLOWED_TREND_VOCABULARY = frozenset(
    {
        ("Apple Inc.", "Total net sales", "USD millions", "Apple consolidated annual net sales"),
        ("Example Group", "Revenue", "USD millions", "Consolidated annual revenue"),
        (
            "PETRONAS Chemicals Group Berhad",
            "Revenue",
            "RM millions",
            "PCG consolidated annual revenue",
        ),
    }
)


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


def _require_company_id_matches_name(company_id: str, company: str) -> None:
    registered_company = _REGISTERED_COMPANIES.get(company_id)
    if registered_company is None:
        raise ValueError("company_id is not in the reviewed company registry")
    if registered_company.casefold() != company.casefold():
        raise ValueError("company_id does not match the registered company")


def report_claim_text(claim: FinancialClaim) -> str:
    if claim.asserted_value is not None:
        if claim.metric_id == MetricId.REVENUE_GROWTH_YOY:
            return f"Revenue grew {_decimal_string(claim.asserted_value * 100)}%."
        if claim.metric_id == MetricId.OPERATING_MARGIN:
            return f"Operating margin was {_decimal_string(claim.asserted_value * 100)}%."
        if claim.metric_id == MetricId.CURRENT_RATIO:
            return f"Current ratio was {format(claim.asserted_value, 'f')}."
        if claim.metric_id == MetricId.FCF_MARGIN:
            return f"Project-defined FCF margin was {_decimal_string(claim.asserted_value * 100)}%."
    if claim.metric_id == MetricId.REVENUE_GROWTH_YOY and claim.asserted_direction is not None:
        direction = {
            "up": "increased",
            "down": "decreased",
            "flat": "was unchanged",
        }[claim.asserted_direction]
        return f"Revenue {direction}."
    raise ValueError("claim is not representable by the fixed report vocabulary")


def report_finding_rationale(claim: FinancialClaim, result: MetricResult) -> str:
    if result.exceptional_state is not None:
        return f"A deterministic comparison was not possible: {result.exceptional_state.value}."
    if claim.asserted_value is not None and result.result is not None:
        difference = abs(claim.asserted_value - result.result)
        return (
            f"Claimed {_decimal_string(claim.asserted_value)} and calculated "
            f"{_decimal_string(result.result)} differ by {_decimal_string(difference)}."
        )
    return "The typed evidence did not meet the fixed requirements for a decisive comparison."


def _context_narrative(record: Any) -> tuple[str, ...]:
    return (
        record["company"] if isinstance(record, dict) else record.company,
        record["indicator"] if isinstance(record, dict) else record.indicator,
        record["geography"] if isinstance(record, dict) else record.geography,
        record["display_value"] if isinstance(record, dict) else record.display_value,
        record["unit"] if isinstance(record, dict) else record.unit,
        record["relevance"] if isinstance(record, dict) else record.relevance,
        record["comparability_warning"]
        if isinstance(record, dict)
        else record.comparability_warning,
    )


@lru_cache(maxsize=1)
def _approved_context_narratives() -> dict[str, tuple[str, ...]]:
    path = files("proofline").joinpath("fixtures/economic_context_fy2025.json")
    fixture = json.loads(path.read_text(encoding="utf-8"))
    approved = {
        record["id"]: _context_narrative(record)
        for company in fixture["companies"].values()
        for record in company["context"]
    }
    approved["context-us-gdp"] = (
        "Example Group",
        "U.S. real GDP annual growth",
        "United States",
        "2.1%",
        "percent year over year",
        "Broad activity context for the reviewed period.",
        "National output does not match the reporting entity or fiscal period.",
    )
    return approved


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
        approved = _approved_context_narratives().get(self.id)
        if approved is None or _context_narrative(self) != approved:
            raise ValueError("context narrative is not in the reviewed context registry")
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
        vocabulary = (self.company, self.indicator, self.unit, next(iter(bases)))
        if vocabulary not in _ALLOWED_TREND_VOCABULARY:
            raise ValueError("trend labels are not in the reviewed trend vocabulary")
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
        _require_company_id_matches_name(self.company_id, self.company)
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
        elif self.source_disclosure != VERIFIED_CACHED_SOURCE_DISCLOSURE:
            raise ValueError("verified_cached requires the fixed cache disclosure")
        _require_company_id_matches_name(self.company_id, self.company)

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
        issuers = {item.issuer.casefold() for item in self.analysis.documents}
        if not issuers:
            raise ValueError("report requires at least one issuer-bearing document")
        if len(issuers) != 1:
            raise ValueError("report documents must use one issuer")
        if next(iter(issuers)) != self.company.casefold():
            raise ValueError("report document issuer must match bundle company")
        for document in self.analysis.documents:
            if document.version_label not in _ALLOWED_DOCUMENT_VERSION_LABELS:
                raise ValueError("document version label is not in the reviewed vocabulary")
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
            if claim.entity is not None and claim.entity.casefold() != self.company.casefold():
                raise ValueError("claim entity must match bundle company")
            if claim.text != report_claim_text(claim):
                raise ValueError("claim text does not match the fixed metric vocabulary")
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
            input_observations = tuple(
                observations[observation_id]
                for observation_id in results[finding.metric_result_id].input_observation_ids
            )
            expected_finding = classify(
                finding.id,
                claims[finding.claim_id],
                results[finding.metric_result_id],
                input_observations,
                finding.evidence_source_span_ids,
            )
            if finding != expected_finding:
                raise ValueError("finding does not match deterministic classification output")

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

        analysis_sha256 = canonical_sha256(self.analysis)
        if self.snapshot.evidence_chain_sha256 != analysis_sha256:
            raise ValueError("snapshot evidence hash does not match the full analysis response")
        if self.snapshot.analysis_id != f"sha256:{analysis_sha256}":
            raise ValueError("snapshot analysis_id must identify the canonical analysis hash")
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
        if self.snapshot.title != f"{self.company} reviewed evidence report":
            raise ValueError("snapshot title must use the fixed company-bound report title")
        if any(value not in _ALLOWED_LIMITATIONS for value in self.snapshot.limitations):
            raise ValueError("snapshot limitation is not in the reviewed report vocabulary")
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
        if any(not isinstance(key, str) for key in value):
            raise TypeError("canonical mappings require string keys")
        return {key: canonical_value(value[key]) for key in sorted(value)}
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
        if value == 0:
            return 0.0
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
