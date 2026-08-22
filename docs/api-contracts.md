# API and evidence contracts

The first public contract is version `1.0.0`. Checked-in JSON Schemas and OpenAPI are in
`contracts/v1/`. Breaking changes require a new URL/schema version; adding optional fields may be
made within v1 only when old consumers continue to validate.

## Endpoints

- `GET /health` reports service health, contract/registry versions, and whether the optional model
  provider is configured. It never returns a key.
- `POST /api/v1/analyses` accepts validated claims, normalized observations, and typed calculation
  plans. It returns deterministic metric results and conservative findings.

Decimal values cross the JSON boundary as strings so JavaScript consumers do not silently lose
precision. Dates use ISO 8601. Unknown fields are rejected. Source pages are one-based and workbook
cells use uppercase A1 references.

## Stable evidence chain

The encoded lineage is append-only:

`DocumentVersion -> SourceSpan -> FactObservation -> MetricResult -> Finding`

`evidence-chain.schema.json` encodes the complete portable snapshot. `metric-registry.json` exposes
the exact four metric IDs, formula IDs, input roles, applicability notes, and v1 tolerances for
fixture and frontend consumers.

The analysis request begins at claims and observations because document ingestion is deliberately
stubbable in this PR. Frontend consumers should key evidence by IDs and must not infer provenance
from display text.

## Typed calculation plans

A plan selects one of four allowlisted metric IDs and maps exact input roles to observation IDs.
There is no expression, code, query, or arbitrary operator field. Missing, duplicate, or unexpected
roles fail closed. Model output is never executed and never controls arithmetic or classification.

## Classification policy

Numeric assertions are `supported` when their absolute difference from the deterministic result is
within the metric's fixed tolerance; otherwise they are `contradicted`. Missing inputs,
comparability failures, denominator exceptions, unresolved capex sign, and direction-only claims
without a baseline are `uncertain`.

The fixed v1 tolerances are 0.005 for revenue growth, operating margin, and FCF margin, and 0.01 for
current ratio. These are prototype decisions that require fixture review before any production use.
