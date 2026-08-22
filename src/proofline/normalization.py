from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import Field

from proofline.contracts import (
    CalculationInput,
    FactObservation,
    FrozenModel,
    MetricCalculationPlan,
    MetricId,
    Period,
)
from proofline.parsing.models import ExtractedCell

Confidence = Annotated[Decimal, Field(ge=0, le=1, max_digits=3, decimal_places=2)]


class NormalizationWarning(FrozenModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    message: str = Field(min_length=1, max_length=500)
    source_span_ids: tuple[str, ...] = ()


class NormalizedFact(FrozenModel):
    observation: FactObservation
    provenance_span_ids: tuple[str, ...] = Field(min_length=3)
    confidence: Confidence
    warnings: tuple[NormalizationWarning, ...] = ()


class Tier0MetricInputs(FrozenModel):
    id: str
    period: Period
    plan: MetricCalculationPlan
    input_fact_ids: tuple[str, ...]
    confidence: Confidence
    warnings: tuple[NormalizationWarning, ...] = ()


class NormalizationResult(FrozenModel):
    document_id: str
    issuer: str | None = None
    entity_scope: str | None = None
    currency: str | None = None
    source_scale: str | None = None
    facts: tuple[NormalizedFact, ...] = ()
    metric_inputs: tuple[Tier0MetricInputs, ...] = ()
    warnings: tuple[NormalizationWarning, ...] = ()


_CONCEPT_ALIASES = {
    "revenue": {"revenue", "net sales", "sales revenue", "turnover"},
    "operating_profit": {"operating profit", "operating income"},
    "current_assets": {"current assets", "total current assets"},
    "current_liabilities": {"current liabilities", "total current liabilities"},
    "operating_cash_flow": {
        "net cash from operating activities",
        "net cash provided by operating activities",
        "operating cash flow",
    },
    "capex": {
        "capital expenditure",
        "capital expenditures",
        "purchase of property plant and equipment",
        "purchases of property plant and equipment",
    },
}
_ALIAS_TO_CONCEPT = {
    alias: concept for concept, aliases in _CONCEPT_ALIASES.items() for alias in aliases
}
_INSTANT_CONCEPTS = {"current_assets", "current_liabilities"}
_METADATA_KEYS = {
    "issuer": {"issuer", "company", "reporting entity"},
    "entity_scope": {"entity scope", "scope"},
    "currency": {"currency", "reporting currency"},
    "scale": {"unit", "units", "scale", "amounts in"},
    "restatement": {"restatement basis", "restatement status"},
}
_SCALE_FACTORS = {
    "base units": Decimal(1),
    "units": Decimal(1),
    "ones": Decimal(1),
    "thousand": Decimal(1_000),
    "thousands": Decimal(1_000),
    "million": Decimal(1_000_000),
    "millions": Decimal(1_000_000),
    "billion": Decimal(1_000_000_000),
    "billions": Decimal(1_000_000_000),
}
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


class _Cell(FrozenModel):
    extracted: ExtractedCell
    sheet: str
    row: int
    column: int
    text: str


class _Metadata(FrozenModel):
    value: str
    span_ids: tuple[str, ...]


class _PeriodHeader(FrozenModel):
    end: date
    confidence: Confidence
    warning: NormalizationWarning | None = None


class _Candidate(FrozenModel):
    concept: str
    value: Decimal
    display_value: str
    period: Period
    concept_cell: _Cell
    period_cell: _Cell
    value_cell: _Cell
    confidence: Confidence
    warnings: tuple[NormalizationWarning, ...] = ()


def normalize_financial_workbook(
    cells: tuple[ExtractedCell, ...] | list[ExtractedCell], document_id: str
) -> NormalizationResult:
    """Convert extracted XLSX cells into conservative, calculation-ready financial facts.

    The resolver accepts row-oriented and transposed statement matrices. It requires explicit,
    unambiguous issuer, entity scope, ISO currency, source scale, and restatement metadata. Missing
    or conflicting metadata yields no facts; duplicate concept/period values are omitted.
    """

    indexed = tuple(_index_cell(cell) for cell in cells)
    warnings: list[NormalizationWarning] = []
    if not indexed:
        return NormalizationResult(
            document_id=document_id,
            warnings=(_warning("no_cells", "The workbook contained no extracted cells."),),
        )
    if any(cell.extracted.span.document_version_id != document_id for cell in indexed):
        return NormalizationResult(
            document_id=document_id,
            warnings=(
                _warning(
                    "document_mismatch",
                    "At least one extracted cell belongs to a different document version.",
                ),
            ),
        )

    metadata: dict[str, _Metadata] = {}
    for field, aliases in _METADATA_KEYS.items():
        resolved, issue = _resolve_metadata(indexed, aliases, field)
        if issue is not None:
            warnings.append(issue)
        elif resolved is not None:
            metadata[field] = resolved

    issuer = metadata.get("issuer")
    scope = metadata.get("entity_scope")
    currency_metadata = metadata.get("currency")
    scale_metadata = metadata.get("scale")
    restatement_metadata = metadata.get("restatement")
    currency = _parse_currency(currency_metadata.value) if currency_metadata else None
    scale = _parse_scale(scale_metadata.value) if scale_metadata else None
    restated = _parse_restatement(restatement_metadata.value) if restatement_metadata else None

    for field, value in (
        ("issuer", issuer),
        ("entity_scope", scope),
        ("currency", currency_metadata),
        ("scale", scale_metadata),
        ("restatement", restatement_metadata),
    ):
        if value is None and not any(item.code.startswith(f"{field}_") for item in warnings):
            warnings.append(_warning(f"{field}_missing", f"Explicit {field} metadata is required."))
    if currency_metadata and currency is None:
        warnings.append(
            _warning(
                "currency_invalid",
                "Reporting currency must be an explicit three-letter ISO code.",
                currency_metadata.span_ids,
            )
        )
    if scale_metadata and scale is None:
        warnings.append(
            _warning(
                "scale_invalid",
                "Source scale must be one of base units, thousands, millions, or billions.",
                scale_metadata.span_ids,
            )
        )
    if restatement_metadata and restated is None:
        warnings.append(
            _warning(
                "restatement_invalid",
                "Restatement basis must explicitly state restated or not restated.",
                restatement_metadata.span_ids,
            )
        )

    fatal_codes = {
        "issuer_missing",
        "issuer_ambiguous",
        "entity_scope_missing",
        "entity_scope_ambiguous",
        "currency_missing",
        "currency_ambiguous",
        "currency_invalid",
        "scale_missing",
        "scale_ambiguous",
        "scale_invalid",
        "restatement_missing",
        "restatement_ambiguous",
        "restatement_invalid",
    }
    if any(warning.code in fatal_codes for warning in warnings):
        return NormalizationResult(
            document_id=document_id,
            issuer=issuer.value if issuer else None,
            entity_scope=scope.value if scope else None,
            currency=currency,
            source_scale=scale_metadata.value if scale_metadata else None,
            warnings=tuple(warnings),
        )

    assert issuer and scope and currency and scale and restated is not None
    candidates = _find_candidates(indexed)
    metadata_span_ids = _unique(span_id for item in metadata.values() for span_id in item.span_ids)
    facts: list[NormalizedFact] = []
    grouped: dict[tuple[str, Period], list[_Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[(candidate.concept, candidate.period)].append(candidate)
    for (concept, period), matches in sorted(
        grouped.items(), key=lambda item: (item[0][1].end, item[0][0])
    ):
        unique_values = {(item.value, item.value_cell.extracted.span.id) for item in matches}
        if len(unique_values) != 1:
            warnings.append(
                _warning(
                    "fact_ambiguous",
                    f"Multiple cells could supply {concept} for {period.end.isoformat()}; omitted.",
                    _unique(item.value_cell.extracted.span.id for item in matches),
                )
            )
            continue
        candidate = matches[0]
        normalized_value = candidate.value * scale
        sign_convention = "positive"
        if concept == "capex":
            normalized_value = normalized_value.copy_abs()
            sign_convention = "cash_outflow_positive"
        observation_id = _fact_id(
            document_id, concept, period, candidate.value_cell.extracted.span.id
        )
        fact_warnings = candidate.warnings
        provenance = _unique(
            (
                candidate.value_cell.extracted.span.id,
                candidate.concept_cell.extracted.span.id,
                candidate.period_cell.extracted.span.id,
                *metadata_span_ids,
            )
        )
        facts.append(
            NormalizedFact(
                observation=FactObservation(
                    id=observation_id,
                    source_span_id=candidate.value_cell.extracted.span.id,
                    concept=concept,
                    numeric_value=normalized_value,
                    display_value=candidate.display_value,
                    unit=f"{currency} base units",
                    currency=currency,
                    period=period,
                    entity_scope=scope.value,
                    restated=restated,
                    sign_convention=sign_convention,
                    fixture_status="derived",
                ),
                provenance_span_ids=provenance,
                confidence=candidate.confidence,
                warnings=fact_warnings,
            )
        )
    if not facts:
        warnings.append(
            _warning(
                "no_financial_facts",
                "No unambiguous supported concept/period/value intersections were found.",
            )
        )
    metric_inputs, metric_warnings = _build_metric_inputs(facts)
    warnings.extend(metric_warnings)
    return NormalizationResult(
        document_id=document_id,
        issuer=issuer.value,
        entity_scope=scope.value,
        currency=currency,
        source_scale=scale_metadata.value,
        facts=tuple(facts),
        metric_inputs=metric_inputs,
        warnings=tuple(warnings),
    )


def _index_cell(cell: ExtractedCell) -> _Cell:
    source = cell.span.source
    if source.kind != "spreadsheet":
        raise ValueError("workbook normalization accepts spreadsheet source spans only")
    match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]*)", source.cell)
    if match is None:
        raise ValueError("range source spans cannot be normalized as individual cells")
    column = 0
    for character in match.group(1):
        column = column * 26 + ord(character) - 64
    return _Cell(
        extracted=cell,
        sheet=source.sheet,
        row=int(match.group(2)),
        column=column,
        text=source.display_value.strip(),
    )


def _resolve_metadata(
    cells: tuple[_Cell, ...], aliases: set[str], field: str
) -> tuple[_Metadata | None, NormalizationWarning | None]:
    grid = {(cell.sheet, cell.row, cell.column): cell for cell in cells}
    found: list[_Metadata] = []
    for cell in cells:
        normalized = _normalize_label(cell.text)
        inline = next(
            (
                cell.text.split(":", 1)[1].strip()
                for alias in aliases
                if normalized.startswith(f"{alias} ") and ":" in cell.text
            ),
            None,
        )
        if inline:
            found.append(_Metadata(value=inline, span_ids=(cell.extracted.span.id,)))
            continue
        if normalized not in aliases:
            continue
        value_cell = grid.get((cell.sheet, cell.row, cell.column + 1)) or grid.get(
            (cell.sheet, cell.row + 1, cell.column)
        )
        if value_cell is not None:
            found.append(
                _Metadata(
                    value=value_cell.text,
                    span_ids=(cell.extracted.span.id, value_cell.extracted.span.id),
                )
            )
    distinct = {_normalize_label(item.value): item for item in found if item.value.strip()}
    if not distinct:
        return None, None
    if len(distinct) > 1:
        return None, _warning(
            f"{field}_ambiguous",
            f"Conflicting explicit {field} metadata was found.",
            _unique(span_id for item in found for span_id in item.span_ids),
        )
    return next(iter(distinct.values())), None


def _find_candidates(cells: tuple[_Cell, ...]) -> tuple[_Candidate, ...]:
    by_sheet_row: dict[tuple[str, int], list[_Cell]] = defaultdict(list)
    by_sheet_column: dict[tuple[str, int], list[_Cell]] = defaultdict(list)
    for cell in cells:
        by_sheet_row[(cell.sheet, cell.row)].append(cell)
        by_sheet_column[(cell.sheet, cell.column)].append(cell)
    output: dict[tuple[str, str, date], _Candidate] = {}
    for value_cell in cells:
        value = _parse_number(value_cell.text)
        if value is None:
            continue
        row_cells = by_sheet_row[(value_cell.sheet, value_cell.row)]
        column_cells = by_sheet_column[(value_cell.sheet, value_cell.column)]
        orientations = (
            (
                _nearest_concept(row_cells, value_cell, axis="column"),
                _nearest_period(column_cells, value_cell, axis="row"),
            ),
            (
                _nearest_concept(column_cells, value_cell, axis="row"),
                _nearest_period(row_cells, value_cell, axis="column"),
            ),
        )
        for concept_match, period_match in orientations:
            if concept_match is None or period_match is None:
                continue
            concept_cell, concept = concept_match
            period_cell, header = period_match
            period = _period_for_concept(header.end, concept)
            candidate_warnings = (header.warning,) if header.warning else ()
            confidence = min(
                Decimal(str(value_cell.extracted.confidence)), header.confidence
            ).quantize(Decimal("0.01"))
            candidate = _Candidate(
                concept=concept,
                value=value,
                display_value=value_cell.text,
                period=period,
                concept_cell=concept_cell,
                period_cell=period_cell,
                value_cell=value_cell,
                confidence=confidence,
                warnings=candidate_warnings,
            )
            output[(value_cell.extracted.span.id, concept, period.end)] = candidate
    return tuple(output.values())


def _nearest_concept(
    cells: list[_Cell], value_cell: _Cell, *, axis: str
) -> tuple[_Cell, str] | None:
    candidates = []
    for cell in cells:
        concept = _ALIAS_TO_CONCEPT.get(_normalize_label(cell.text))
        if concept:
            distance = abs(getattr(cell, axis) - getattr(value_cell, axis))
            candidates.append((distance, cell, concept))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    _, cell, concept = candidates[0]
    return cell, concept


def _nearest_period(
    cells: list[_Cell], value_cell: _Cell, *, axis: str
) -> tuple[_Cell, _PeriodHeader] | None:
    candidates = []
    for cell in cells:
        header = _parse_period_header(cell.text)
        if header:
            distance = abs(getattr(cell, axis) - getattr(value_cell, axis))
            candidates.append((distance, cell, header))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    _, cell, header = candidates[0]
    return cell, header


def _parse_period_header(value: str) -> _PeriodHeader | None:
    normalized = _normalize_label(value)
    iso = re.search(r"\b(20[0-9]{2})-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])\b", value)
    if iso:
        try:
            return _PeriodHeader(
                end=date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))),
                confidence=Decimal("1.00"),
            )
        except ValueError:
            return None
    long_date = re.search(
        r"\b([0-2]?[0-9]|3[01])\s+(" + "|".join(_MONTHS) + r")\s+(20[0-9]{2})\b",
        normalized,
    )
    if long_date:
        try:
            return _PeriodHeader(
                end=date(
                    int(long_date.group(3)),
                    _MONTHS[long_date.group(2)],
                    int(long_date.group(1)),
                ),
                confidence=Decimal("1.00"),
            )
        except ValueError:
            return None
    year = re.fullmatch(r"(?:calendar year\s+|year\s+)?(20[0-9]{2})", normalized)
    if year:
        end = date(int(year.group(1)), 12, 31)
        warning = _warning(
            "calendar_period_inferred",
            f"Calendar-year boundaries were inferred from the header {value!r}.",
        )
        return _PeriodHeader(end=end, confidence=Decimal("0.90"), warning=warning)
    return None


def _period_for_concept(end: date, concept: str) -> Period:
    if concept in _INSTANT_CONCEPTS:
        return Period(end=end)
    try:
        start = end.replace(year=end.year - 1) + timedelta(days=1)
    except ValueError:
        start = end.replace(year=end.year - 1, day=28) + timedelta(days=1)
    days = (end - start).days + 1
    return Period(start=start, end=end, duration_weeks=round(days / 7))


def _build_metric_inputs(
    facts: list[NormalizedFact],
) -> tuple[tuple[Tier0MetricInputs, ...], tuple[NormalizationWarning, ...]]:
    by_concept: dict[str, list[NormalizedFact]] = defaultdict(list)
    for fact in facts:
        by_concept[fact.observation.concept].append(fact)
    output: list[Tier0MetricInputs] = []
    warnings: list[NormalizationWarning] = []

    revenue = sorted(by_concept["revenue"], key=lambda item: item.observation.period.end)
    if len(revenue) >= 2:
        selected = (revenue[-1], revenue[-2])
        if _annual_periods_are_adjacent(
            selected[0].observation.period, selected[1].observation.period
        ):
            output.append(
                _metric_input(
                    MetricId.REVENUE_GROWTH_YOY,
                    selected[0].observation.period,
                    ("revenue_current", "revenue_prior"),
                    selected,
                )
            )
        else:
            warnings.append(
                _warning(
                    "metric_inputs_incomparable",
                    "The latest two revenue periods are not adjacent comparable annual periods.",
                    tuple(fact.observation.source_span_id for fact in selected),
                )
            )

    definitions = (
        (
            MetricId.OPERATING_MARGIN,
            ("operating_profit", "revenue"),
            ("operating_profit", "revenue"),
        ),
        (
            MetricId.CURRENT_RATIO,
            ("current_assets", "current_liabilities"),
            ("current_assets", "current_liabilities"),
        ),
        (
            MetricId.FCF_MARGIN,
            ("operating_cash_flow", "capex", "revenue"),
            ("operating_cash_flow", "capex", "revenue"),
        ),
    )
    for metric_id, concepts, roles in definitions:
        common_periods = None
        lookup: dict[str, dict[Period, NormalizedFact]] = {}
        for concept in concepts:
            concept_lookup = {item.observation.period: item for item in by_concept[concept]}
            lookup[concept] = concept_lookup
            periods = set(concept_lookup)
            common_periods = periods if common_periods is None else common_periods & periods
        if common_periods:
            period = max(common_periods, key=lambda item: item.end)
            selected = tuple(lookup[concept][period] for concept in concepts)
            output.append(_metric_input(metric_id, period, roles, selected))
        else:
            warnings.append(
                _warning(
                    "metric_inputs_incomplete",
                    f"No common unambiguous period supplies every input for {metric_id.value}.",
                )
            )
    return tuple(output), tuple(warnings)


def _annual_periods_are_adjacent(current: Period, prior: Period) -> bool:
    if current.start is None or prior.start is None:
        return False
    if current.duration_weeks != prior.duration_weeks:
        return False
    gap_days = (current.start - prior.end).days
    return current.end > prior.end and 1 <= gap_days <= 7


def _metric_input(
    metric_id: MetricId,
    period: Period,
    roles: tuple[str, ...],
    facts: tuple[NormalizedFact, ...],
) -> Tier0MetricInputs:
    return Tier0MetricInputs(
        id=f"metric-inputs:{metric_id.value}:{period.end.isoformat()}",
        period=period,
        plan=MetricCalculationPlan(
            metric_id=metric_id,
            inputs=tuple(
                CalculationInput(role=role, observation_id=fact.observation.id)
                for role, fact in zip(roles, facts, strict=True)
            ),
        ),
        input_fact_ids=tuple(fact.observation.id for fact in facts),
        confidence=min(fact.confidence for fact in facts),
        warnings=tuple(warning for fact in facts for warning in fact.warnings),
    )


def _parse_currency(value: str) -> str | None:
    matches = re.findall(r"\b[A-Z]{3}\b", value.upper())
    return matches[0] if len(set(matches)) == 1 else None


def _parse_scale(value: str) -> Decimal | None:
    normalized = _normalize_label(value)
    matches = [factor for label, factor in _SCALE_FACTORS.items() if label == normalized]
    return matches[0] if len(set(matches)) == 1 else None


def _parse_restatement(value: str) -> bool | None:
    normalized = _normalize_label(value)
    if normalized in {"not restated", "unrestated", "original"}:
        return False
    if normalized in {"restated", "as restated"}:
        return True
    return None


def _parse_number(value: str) -> Decimal | None:
    text = unicodedata.normalize("NFKC", value).strip()
    if not text or "%" in text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = text.replace(",", "").replace(" ", "")
    text = re.sub(r"^[€£$¥]", "", text)
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)", text):
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return -number if negative else number


def _normalize_label(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def _fact_id(document_id: str, concept: str, period: Period, span_id: str) -> str:
    payload = f"{document_id}\0{concept}\0{period.end.isoformat()}\0{span_id}"
    digest = hashlib.sha256(payload.encode()).hexdigest()[:20]
    return f"fact:{digest}"


def _warning(
    code: str, message: str, span_ids: tuple[str, ...] | list[str] = ()
) -> NormalizationWarning:
    return NormalizationWarning(code=code, message=message, source_span_ids=tuple(span_ids))


def _unique(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
