from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from proofline.contracts import (
    ExceptionalState,
    FactObservation,
    MetricCalculationPlan,
    MetricId,
    MetricResult,
)


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: MetricId
    formula_id: str
    display_name: str
    required_roles: tuple[str, ...]
    role_concepts: Mapping[str, str]
    tolerance: Decimal
    applicability: str
    calculate: Callable[[Mapping[str, Decimal]], Decimal]


def _revenue_growth(values: Mapping[str, Decimal]) -> Decimal:
    return values["revenue_current"] / values["revenue_prior"] - Decimal(1)


def _operating_margin(values: Mapping[str, Decimal]) -> Decimal:
    return values["operating_profit"] / values["revenue"]


def _current_ratio(values: Mapping[str, Decimal]) -> Decimal:
    return values["current_assets"] / values["current_liabilities"]


def _fcf_margin(values: Mapping[str, Decimal]) -> Decimal:
    return (values["operating_cash_flow"] - values["capex"]) / values["revenue"]


REGISTRY: dict[MetricId, MetricDefinition] = {
    MetricId.REVENUE_GROWTH_YOY: MetricDefinition(
        MetricId.REVENUE_GROWTH_YOY,
        "revenue_current_div_revenue_prior_minus_one",
        "Revenue growth YoY",
        ("revenue_current", "revenue_prior"),
        {"revenue_current": "revenue", "revenue_prior": "revenue"},
        Decimal("0.005"),
        "non-bank operating companies with comparable periods",
        _revenue_growth,
    ),
    MetricId.OPERATING_MARGIN: MetricDefinition(
        MetricId.OPERATING_MARGIN,
        "operating_profit_div_revenue",
        "Operating margin",
        ("operating_profit", "revenue"),
        {"operating_profit": "operating_profit", "revenue": "revenue"},
        Decimal("0.005"),
        "non-bank operating companies; issuer definitions may differ",
        _operating_margin,
    ),
    MetricId.CURRENT_RATIO: MetricDefinition(
        MetricId.CURRENT_RATIO,
        "current_assets_div_current_liabilities",
        "Current ratio",
        ("current_assets", "current_liabilities"),
        {"current_assets": "current_assets", "current_liabilities": "current_liabilities"},
        Decimal("0.01"),
        "non-bank operating companies",
        _current_ratio,
    ),
    MetricId.FCF_MARGIN: MetricDefinition(
        MetricId.FCF_MARGIN,
        "operating_cash_flow_minus_capex_div_revenue",
        "Free-cash-flow margin (project-defined non-GAAP)",
        ("operating_cash_flow", "capex", "revenue"),
        {"operating_cash_flow": "operating_cash_flow", "capex": "capex", "revenue": "revenue"},
        Decimal("0.005"),
        "non-bank operating companies; project-defined non-GAAP measure",
        _fcf_margin,
    ),
}


def calculate_metric(
    result_id: str,
    plan: MetricCalculationPlan,
    observations: Mapping[str, FactObservation],
) -> MetricResult:
    definition = REGISTRY[plan.metric_id]
    role_map = {item.role: item.observation_id for item in plan.inputs}
    if len(role_map) != len(plan.inputs) or set(role_map) != set(definition.required_roles):
        return _exception(result_id, plan, definition, ExceptionalState.INVALID_PLAN)
    if any(observation_id not in observations for observation_id in role_map.values()):
        return _exception(result_id, plan, definition, ExceptionalState.MISSING_INPUT)

    facts = [observations[role_map[role]] for role in definition.required_roles]
    if any(
        observations[role_map[role]].concept != definition.role_concepts[role]
        for role in definition.required_roles
    ):
        return _exception(
            result_id,
            plan,
            definition,
            ExceptionalState.INVALID_PLAN,
            "An observation concept does not match its calculation role.",
        )
    warning = _comparability_warning(plan.metric_id, facts)
    if warning:
        return _exception(result_id, plan, definition, ExceptionalState.INCOMPARABLE, warning)

    denominator_role = {
        MetricId.REVENUE_GROWTH_YOY: "revenue_prior",
        MetricId.OPERATING_MARGIN: "revenue",
        MetricId.CURRENT_RATIO: "current_liabilities",
        MetricId.FCF_MARGIN: "revenue",
    }[plan.metric_id]
    values = {
        role: observations[observation_id].numeric_value
        for role, observation_id in role_map.items()
    }
    if values[denominator_role] <= 0:
        return _exception(
            result_id, plan, definition, ExceptionalState.ZERO_OR_NEGATIVE_DENOMINATOR
        )
    if plan.metric_id == MetricId.FCF_MARGIN:
        capex = observations[role_map["capex"]]
        if capex.sign_convention != "cash_outflow_positive" or capex.numeric_value < 0:
            return _exception(result_id, plan, definition, ExceptionalState.UNRESOLVED_SIGN)
    try:
        value = definition.calculate(values)
    except (InvalidOperation, ZeroDivisionError):
        return _exception(result_id, plan, definition, ExceptionalState.INCOMPARABLE)
    if not value.is_finite():
        return _exception(result_id, plan, definition, ExceptionalState.INCOMPARABLE)
    return MetricResult(
        id=result_id,
        metric_id=plan.metric_id,
        formula_id=definition.formula_id,
        input_observation_ids=tuple(role_map[role] for role in definition.required_roles),
        result=value,
    )


def _comparability_warning(metric_id: MetricId, facts: list[FactObservation]) -> str | None:
    if len({fact.entity_scope for fact in facts}) != 1:
        return "Input entity scopes differ."
    if len({fact.currency for fact in facts}) != 1:
        return "Input currencies differ."
    if len({fact.unit for fact in facts}) != 1:
        return "Input units differ."
    restated = {fact.restated for fact in facts}
    if None in restated or len(restated) != 1:
        return "Restatement basis is unresolved or inconsistent."
    if metric_id == MetricId.REVENUE_GROWTH_YOY:
        if any(fact.period.duration_weeks is None for fact in facts):
            return "Period duration is required for year-over-year comparison."
        if len({fact.period.duration_weeks for fact in facts}) != 1:
            return "Period durations differ."
        if len({fact.period.end for fact in facts}) != 2:
            return "Current and prior revenue periods must differ."
    elif len({fact.period for fact in facts}) != 1:
        return "Input periods differ."
    return None


def _exception(
    result_id: str,
    plan: MetricCalculationPlan,
    definition: MetricDefinition,
    state: ExceptionalState,
    warning: str | None = None,
) -> MetricResult:
    return MetricResult(
        id=result_id,
        metric_id=plan.metric_id,
        formula_id=definition.formula_id,
        input_observation_ids=tuple(item.observation_id for item in plan.inputs),
        exceptional_state=state,
        warnings=(warning,) if warning else (),
    )
