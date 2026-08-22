/**
 * Reserved integration boundary for the secondary Company Lens view.
 * The Review Desk does not render this contract yet. Macro observations are
 * context only and must never be presented as evidence of cause.
 *
 * @typedef {{ period: string, value: number, unit: string, sourceLabel: string }} TrendPoint
 * @typedef {{ id: string, title: string, observation: string, geography: string, period: string, unit: string, source: string, sourceDate: string, comparability: string, caveat: "Context only; no causal relationship is asserted." }} EconomicContextCard
 * @typedef {{ sessionId: string, reviewedAt: string, findingIds: string[] }} AnalysisHistoryItem
 * @typedef {{ history: AnalysisHistoryItem[], trends: Record<string, TrendPoint[]>, economicContext: EconomicContextCard[] }} CompanyLensContract
 */

/** @param {unknown} response @returns {CompanyLensContract} */
export function adaptCompanyLensContract(response) {
  if (!response || typeof response !== "object") {
    return { history: [], trends: {}, economicContext: [] };
  }
  const candidate = /** @type {Partial<CompanyLensContract>} */ (response);
  return {
    history: Array.isArray(candidate.history) ? candidate.history : [],
    trends: candidate.trends && typeof candidate.trends === "object" ? candidate.trends : {},
    economicContext: Array.isArray(candidate.economicContext)
      ? candidate.economicContext.slice(0, 4).map((card) => ({ ...card, caveat: "Context only; no causal relationship is asserted." }))
      : [],
  };
}
