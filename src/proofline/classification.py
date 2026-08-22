from proofline.contracts import (
    Classification,
    FactObservation,
    FinancialClaim,
    Finding,
    MetricResult,
)
from proofline.metrics import REGISTRY


def classify(
    finding_id: str,
    claim: FinancialClaim,
    result: MetricResult,
    input_observations: tuple[FactObservation, ...],
    evidence_source_span_ids: tuple[str, ...],
) -> Finding:
    if result.exceptional_state is not None:
        return Finding(
            id=finding_id,
            claim_id=claim.id,
            metric_result_id=result.id,
            classification=Classification.UNCERTAIN,
            rationale=(
                f"A deterministic comparison was not possible: {result.exceptional_state.value}."
            ),
            evidence_source_span_ids=evidence_source_span_ids,
            warnings=result.warnings,
            suggested_investigation=(
                "Resolve the input exception and verify the cited source evidence."
            ),
        )
    if claim.metric_id != result.metric_id:
        return _uncertain(finding_id, claim, result, evidence_source_span_ids, "Metric IDs differ.")
    if claim.extraction_warnings:
        return _uncertain(
            finding_id,
            claim,
            result,
            evidence_source_span_ids,
            "Extraction warnings require human review before a decisive classification.",
        )
    comparability_warning = _claim_comparability_warning(claim, result, input_observations)
    if comparability_warning:
        return _uncertain(
            finding_id,
            claim,
            result,
            evidence_source_span_ids,
            comparability_warning,
        )
    if claim.asserted_value is None:
        return _uncertain(
            finding_id,
            claim,
            result,
            evidence_source_span_ids,
            "A direction-only claim needs a comparable baseline that is not in this contract.",
        )
    if not claim.asserted_value.is_finite() or (
        not claim.asserted_value.is_zero() and not -50 <= claim.asserted_value.adjusted() <= 50
    ):
        return _uncertain(
            finding_id,
            claim,
            result,
            evidence_source_span_ids,
            "The asserted value exceeds the supported Decimal range.",
        )

    tolerance = REGISTRY[result.metric_id].tolerance
    difference = abs(claim.asserted_value - result.result)  # type: ignore[arg-type]
    classification = (
        Classification.SUPPORTED if difference <= tolerance else Classification.CONTRADICTED
    )
    rationale = (
        f"Claimed {claim.asserted_value} and calculated {result.result} differ by {difference}; "
        f"the absolute tolerance is {tolerance}."
    )
    return Finding(
        id=finding_id,
        claim_id=claim.id,
        metric_result_id=result.id,
        classification=classification,
        rationale=rationale,
        tolerance=tolerance,
        evidence_source_span_ids=evidence_source_span_ids,
        warnings=tuple(claim.extraction_warnings),
        suggested_investigation=(
            "Check the claim definition, rounding, and cited source values."
            if classification == Classification.CONTRADICTED
            else None
        ),
    )


def _claim_comparability_warning(
    claim: FinancialClaim,
    result: MetricResult,
    observations: tuple[FactObservation, ...],
) -> str | None:
    if not observations:
        return "No comparable observations were supplied."
    if claim.unit not in (None, "ratio"):
        return "The asserted value is not normalized to a ratio."
    if claim.entity is not None and any(
        observation.entity_scope != claim.entity for observation in observations
    ):
        return "The claim entity and evidence scope differ."
    if claim.currency is not None and any(
        observation.currency != claim.currency for observation in observations
    ):
        return "The claim and evidence currencies differ."
    comparison_period = observations[0].period
    if claim.period != comparison_period:
        return "The claim and evidence periods differ."
    return None


def _uncertain(
    finding_id: str,
    claim: FinancialClaim,
    result: MetricResult,
    evidence_source_span_ids: tuple[str, ...],
    rationale: str,
) -> Finding:
    return Finding(
        id=finding_id,
        claim_id=claim.id,
        metric_result_id=result.id,
        classification=Classification.UNCERTAIN,
        rationale=rationale,
        evidence_source_span_ids=evidence_source_span_ids,
        warnings=tuple(claim.extraction_warnings),
        suggested_investigation=(
            "Obtain a quantified, comparable claim and verify its source context."
        ),
    )
