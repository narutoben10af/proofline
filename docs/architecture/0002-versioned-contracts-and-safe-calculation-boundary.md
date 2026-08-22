# ADR 0002: Version contracts and restrict calculation to typed metric plans

- Status: Accepted
- Date: 2026-08-22

## Context

Frontend and fixture work need a stable JSON boundary before parsers and model integrations exist.
Financial values must avoid binary floating-point drift, and no model output may become executable
code or authoritative arithmetic.

## Decision

The initial API, evidence schema, metric registry, and classification policy are each version
`1.0.0`. Decimal values serialize as JSON strings. Requests reject unknown fields and accept only a
typed calculation plan containing an allowlisted metric ID plus exact role-to-observation mappings.
The server dispatches those plans to four precompiled Decimal functions.

Any missing, incomparable, ambiguous, invalid-plan, non-positive-denominator, or unresolved-sign
case produces an exceptional metric state and an `uncertain` finding. Numeric comparisons use fixed
absolute tolerances recorded on findings. Direction-only claims remain uncertain without a separate
comparable baseline.

## Consequences

- JavaScript consumers must treat decimals as strings until formatting or explicit decimal parsing.
- A breaking field or semantic change requires a new contract version.
- The first API can analyze normalized fixture data while ingestion remains narrow and stubbable.
- The prototype may return more uncertain findings; this is intentional.
- Final issuer fixtures must validate the provisional v1 tolerances before a public accuracy claim.
