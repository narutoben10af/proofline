from proofline.classification import classify
from proofline.contracts import AnalysisRequest, AnalysisResponse
from proofline.metrics import calculate_metric


def analyze(request: AnalysisRequest) -> AnalysisResponse:
    claims = {claim.id: claim for claim in request.claims}
    observations = {observation.id: observation for observation in request.observations}
    metric_results = []
    findings = []
    for index, item in enumerate(request.items, start=1):
        claim = claims.get(item.claim_id)
        result_id = f"metric-result-{index}"
        if claim is None:
            # Request-level referential integrity failures are malformed input, not findings.
            raise ValueError(f"unknown claim_id: {item.claim_id}")
        result = calculate_metric(result_id, item.calculation_plan, observations)
        evidence = tuple(
            observations[input_item.observation_id].source_span_id
            for input_item in item.calculation_plan.inputs
            if input_item.observation_id in observations
        )
        input_observations = tuple(
            observations[observation_id]
            for observation_id in result.input_observation_ids
            if observation_id in observations
        )
        metric_results.append(result)
        findings.append(classify(f"finding-{index}", claim, result, input_observations, evidence))
    return AnalysisResponse(metric_results=tuple(metric_results), findings=tuple(findings))
