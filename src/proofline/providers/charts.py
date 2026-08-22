from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from proofline.contracts import FactObservation, MetricResult, Period
from proofline.providers.contracts import (
    ChartPoint,
    ChartProposal,
    ChartRequest,
    ChartSeries,
    ChartSpec,
    EvidenceCitation,
)


@dataclass(frozen=True)
class _ResolvedPoint:
    id: str
    period: Period
    value: Decimal
    entity_scope: str
    unit: str
    currency: str | None
    source_span_ids: tuple[str, ...]


def resolve_chart_proposal(proposal: ChartProposal, request: ChartRequest) -> ChartSpec:
    observations = {item.id: item for item in request.observations}
    metrics = {item.id: item for item in request.metric_results}
    resolved_series: list[ChartSeries] = []
    all_points: list[_ResolvedPoint] = []
    citation_pairs: set[tuple[str, str]] = set()

    for proposed_series in proposal.series:
        if proposed_series.observation_ids:
            points = [
                _observation_point(_require(observations, item))
                for item in proposed_series.observation_ids
            ]
        else:
            points = [
                _metric_point(_require(metrics, item), observations)
                for item in proposed_series.metric_result_ids
            ]
        expected_sources = {source for point in points for source in point.source_span_ids}
        if set(proposed_series.source_span_ids) != expected_sources:
            raise ValueError("chart source IDs do not match deterministic evidence")
        if len({point.period.end for point in points}) != len(points):
            raise ValueError("a chart series cannot contain duplicate periods")
        _require_compatible(points)
        points.sort(key=lambda point: point.period.end)
        first = points[0]
        resolved_series.append(
            ChartSeries(
                label=proposed_series.label,
                entity_scope=first.entity_scope,
                unit=first.unit,
                currency=first.currency,
                points=tuple(
                    ChartPoint(
                        id=point.id,
                        period_start=point.period.start,
                        period_end=point.period.end,
                        value=point.value,
                        source_span_ids=point.source_span_ids,
                    )
                    for point in points
                ),
            )
        )
        all_points.extend(points)
        citation_pairs.update(
            (point.id, source_span_id)
            for point in points
            for source_span_id in point.source_span_ids
        )

    _require_compatible(all_points)
    expected_start = _earliest_start(all_points)
    expected_end = max(point.period.end for point in all_points)
    if proposal.period_start != expected_start or proposal.period_end != expected_end:
        raise ValueError("chart period range does not match deterministic evidence")

    return ChartSpec(
        chart_type=proposal.chart_type,
        title=proposal.title,
        description=proposal.description,
        period_start=expected_start,
        period_end=expected_end,
        series=tuple(resolved_series),
        citations=tuple(
            EvidenceCitation(
                evidence_id=evidence_id,
                source_span_id=source_span_id,
                label=evidence_id,
            )
            for evidence_id, source_span_id in sorted(citation_pairs)
        ),
    )


def _require(mapping: dict[str, object], identifier: str):
    try:
        return mapping[identifier]
    except KeyError as error:
        raise ValueError(f"unknown chart evidence ID: {identifier}") from error


def _observation_point(observation: FactObservation) -> _ResolvedPoint:
    return _ResolvedPoint(
        id=observation.id,
        period=observation.period,
        value=observation.numeric_value,
        entity_scope=observation.entity_scope,
        unit=observation.unit,
        currency=observation.currency,
        source_span_ids=(observation.source_span_id,),
    )


def _metric_point(metric: MetricResult, observations: dict[str, FactObservation]) -> _ResolvedPoint:
    if metric.result is None or metric.exceptional_state is not None:
        raise ValueError("chart metrics require a deterministic numeric result")
    inputs = [_require(observations, item) for item in metric.input_observation_ids]
    _require_compatible(inputs)
    latest = max(inputs, key=lambda item: item.period.end)
    return _ResolvedPoint(
        id=metric.id,
        period=latest.period,
        value=metric.result,
        entity_scope=latest.entity_scope,
        unit="ratio",
        currency=None,
        source_span_ids=tuple(sorted({item.source_span_id for item in inputs})),
    )


def _require_compatible(points) -> None:
    if not points:
        raise ValueError("a chart requires evidence points")
    for attribute, label in (
        ("entity_scope", "issuer scope"),
        ("unit", "unit"),
        ("currency", "currency"),
    ):
        if len({getattr(point, attribute) for point in points}) != 1:
            raise ValueError(f"chart evidence has mixed {label}")
    durations = {point.period.duration_weeks for point in points}
    if len(durations) != 1:
        raise ValueError("chart evidence has mixed period bases")


def _earliest_start(points: list[_ResolvedPoint]) -> date | None:
    starts = [point.period.start for point in points]
    if any(value is None for value in starts):
        return None
    return min(value for value in starts if value is not None)
