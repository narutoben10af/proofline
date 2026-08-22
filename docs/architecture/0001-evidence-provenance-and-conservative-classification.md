# ADR 0001: Preserve evidence provenance and use conservative classifications

- Status: Accepted
- Date: 2026-08-22

## Context

Proofline's value depends on a reviewer being able to inspect why a narrative claim received a classification. A plausible label without traceable evidence is not sufficient. Missing or ambiguous spreadsheet evidence is also different from evidence that conflicts with a claim.

## Decision

The prototype will:

1. carry PDF page references and spreadsheet sheet/cell references through the comparison workflow;
2. expose a concise rationale and the relevant source values to the reviewer;
3. use `uncertain` when evidence is missing, ambiguous, not comparable, or below an eventual documented confidence threshold; and
4. reserve `contradicted` for cases where comparable evidence conflicts under documented normalization and tolerance rules.

Exact schemas, thresholds, and tolerance rules remain research items in `PLAN.md` and require later decisions.

## Consequences

- The interface and internal data contracts must retain provenance.
- The prototype may classify fewer claims decisively, which is an intentional tradeoff.
- Evaluation must test provenance correctness in addition to classification outcomes.
- No accuracy claim follows from this decision; representative evaluation is still required.
