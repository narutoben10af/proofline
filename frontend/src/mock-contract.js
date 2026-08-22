// Stable frontend boundary for the hackathon. Replace this adapter's input when
// the backend session/finding schema lands; presentation components consume only
// the normalized shape returned here.
export const mockApiResponse = {
  session: { id: "demo-session", sourceMode: "verified_fixture", lifecycle: "ready" },
  finding: {
    id: "finding-revenue-growth",
    entity: "Northstar Industrial plc",
    period: "FY2025",
    metric: "Revenue growth",
    registryVersion: "revenue_growth_yoy@1.0.0",
    counts: { supported: 6, uncertain: 2, contradicted: 1 },
    claim: { text: "Revenue growth was 8.2% in FY2025.", value: "+8.2%", sourceLabel: "Annual Report 2025, p. 14", sourceSpanId: "pdf-page-14-span-3" },
    comparison: { value: "+5.4%", difference: "2.8", tolerance: "±0.5 percentage points", rationale: "The narrative is outside the documented tolerance when compared with the cited audited revenue figures." },
    inputs: [
      { period: "FY2024", value: "$2,234.2m", sourceLabel: "Income Statement!B5", sourceSpanId: "sheet-income-b5" },
      { period: "FY2025", value: "$2,354.8m", sourceLabel: "Income Statement!C5", sourceSpanId: "sheet-income-c5" },
    ],
    formula: "(2,354.8 − 2,234.2) ÷ 2,234.2 = 0.0540 → 5.4%",
  },
};

export function adaptReviewContract(response) {
  const { session, finding } = response;
  return {
    session,
    meta: { entity: finding.entity, period: finding.period, metric: finding.metric, registryVersion: finding.registryVersion, provenance: "Human-verified public demo fixture" },
    summary: finding.counts,
    claim: { ...finding.claim, source: finding.claim.sourceLabel },
    result: finding.comparison,
    inputs: finding.inputs.map((input) => ({ ...input, cell: input.sourceLabel })),
    formula: finding.formula,
  };
}

export const reviewFixture = adaptReviewContract(mockApiResponse);
