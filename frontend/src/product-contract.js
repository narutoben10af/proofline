import { reviewFixture } from "./mock-contract";
import demoReportSnapshot from "./demo-report-snapshot.json";

export const metricDefinitionRegistry = {
  revenue: { name: "Revenue", definition: "Income earned from ordinary operations before costs and expenses.", formula: "Sum of recognized sales and service income for the reporting period.", unit: "Reporting currency, millions", interpretation: "Compare periods on the same accounting and currency basis.", caveat: "Acquisitions, disposals, currency translation, and accounting changes can affect comparability." },
  "operating-margin": { name: "Operating margin", definition: "The share of revenue remaining after operating costs, before interest and tax.", formula: "Operating profit ÷ revenue × 100", unit: "Percent of revenue", interpretation: "A higher percentage generally indicates more operating profit per unit of revenue.", caveat: "Definitions of operating profit and exceptional items can vary by issuer." },
  "current-ratio": { name: "Current ratio", definition: "A short-term liquidity measure comparing current assets with current liabilities.", formula: "Current assets ÷ current liabilities", unit: "Ratio (times)", interpretation: "Values above 1.0 mean current assets exceed current liabilities at the reporting date.", caveat: "This ratio may be less meaningful for banks, insurers, and businesses with unusual working-capital cycles." },
  "fcf-margin": { name: "Free-cash-flow margin", definition: "The share of revenue converted into the project-defined free-cash-flow measure.", formula: "Project-defined free cash flow ÷ revenue × 100", unit: "Percent of revenue", interpretation: "Use it to compare cash conversion only when the same project definition is applied.", caveat: "Project-defined metric. It may differ from an issuer’s non-GAAP definition and is not universally comparable." },
  "gross-margin": { name: "Gross margin", definition: "Revenue remaining after direct cost of sales.", formula: "Gross profit ÷ revenue × 100", unit: "Percent of revenue", interpretation: "Shows the margin available to cover operating costs and profit.", caveat: "Cost classifications can differ between companies and periods." },
  "quick-ratio": { name: "Quick ratio", definition: "A stricter short-term liquidity measure that excludes inventory.", formula: "(Cash + receivables + other quick assets) ÷ current liabilities", unit: "Ratio (times)", interpretation: "Shows coverage of current liabilities using more liquid current assets.", caveat: "May be less meaningful for financial institutions or sectors with atypical working-capital structures." },
  "cash-conversion": { name: "Cash conversion", definition: "The proportion of operating profit converted into operating cash flow in this demo method.", formula: "Operating cash flow ÷ operating profit × 100", unit: "Percent", interpretation: "Higher values indicate more of accounting operating profit appearing as cash flow.", caveat: "Working-capital timing and one-off cash items can make single-period values volatile." },
  "asset-turnover": { name: "Asset turnover", definition: "Revenue generated for each unit of average assets.", formula: "Revenue ÷ average total assets", unit: "Ratio (times)", interpretation: "Higher values indicate more revenue generated from the asset base.", caveat: "Capital intensity and asset valuation differ substantially by industry." },
  "net-debt-ebitda": { name: "Net debt to EBITDA", definition: "A leverage measure comparing net debt with earnings before interest, tax, depreciation, and amortization.", formula: "(Borrowings − cash) ÷ EBITDA", unit: "Ratio (times)", interpretation: "Lower values generally indicate less debt relative to the selected earnings measure.", caveat: "EBITDA and net-debt definitions can vary; compare only on a consistent basis." },
  "inventory-turns": { name: "Inventory turns", definition: "How many times average inventory is sold or used during the period.", formula: "Cost of sales ÷ average inventory", unit: "Ratio (times)", interpretation: "Higher turnover can indicate faster inventory movement, subject to service-level needs.", caveat: "Seasonality, write-downs, and product mix can distort comparisons." },
};

export const productFixture = {
  session: {
    id: "magicfin-demo-2026-08-22",
    mode: "verified_fixture",
    label: "Verified fixture",
    persistence: "Session-local demo",
    entity: "Northstar Industrial plc",
    period: "FY2025",
    lastUpdated: "22 Aug 2026 · 10:24 MYT",
  },
  company: {
    name: "Northstar Industrial plc",
    shortName: "Northstar",
    description: "Industrial systems and service operations",
    currency: "USD millions",
  },
  sources: [
    { id: "annual-report", name: "Annual_Report_2025.pdf", kind: "PDF", date: "FY2025 · uploaded 22 Aug", status: "Validated", provenance: "Public demo fixture", anchor: "Page 14", reviewRoute: "/review#annual-report" },
    { id: "financials", name: "Financials_FY2025.xlsx", kind: "Workbook", date: "FY2024–FY2025", status: "Validated", provenance: "Human-verified cells", anchor: "Income Statement B5:C5", reviewRoute: "/review#financials" },
    { id: "earnings", name: "Earnings_Release_Q4.pdf", kind: "PDF", date: "Published 31 Jul 2026", status: "Review needed", provenance: "Fixture excerpt only", anchor: "Page 3", reviewRoute: "/files#earnings" },
    { id: "notes", name: "Management_Notes.xlsx", kind: "Workbook", date: "FY2025 notes", status: "Validated", provenance: "Fixture metadata", anchor: "Review columns", reviewRoute: "/files#notes" },
  ],
  trend: [
    { period: "FY2022", revenue: 1986.4, operatingMargin: 15.9, currentRatio: 1.61, fcfMargin: 10.2 },
    { period: "FY2023", revenue: 2119.8, operatingMargin: 16.4, currentRatio: 1.55, fcfMargin: 11.1 },
    { period: "FY2024", revenue: 2234.2, operatingMargin: 17.4, currentRatio: 1.5, fcfMargin: 11.9 },
    { period: "FY2025", revenue: 2354.8, operatingMargin: 18.6, currentRatio: 1.42, fcfMargin: 12.8 },
  ],
  metrics: [
    { id: "revenue", label: "Revenue", value: "$2,354.8m", delta: "+5.4%", deltaLabel: "vs FY2024", period: "FY2025", unit: "USD millions", source: "Financials_FY2025.xlsx · B5:C5", tone: "positive" },
    { id: "operating-margin", label: "Operating margin", value: "18.6%", delta: "+1.2 pp", deltaLabel: "vs FY2024", period: "FY2025", unit: "Percent of revenue", source: "Financials_FY2025.xlsx · B8:C8", tone: "positive" },
    { id: "current-ratio", label: "Current ratio", value: "1.42×", delta: "−0.08×", deltaLabel: "vs FY2024", period: "FY2025", unit: "Ratio", source: "Financials_FY2025.xlsx · Balance sheet", tone: "caution" },
    { id: "fcf-margin", label: "Free-cash-flow margin", value: "12.8%", delta: "+0.9 pp", deltaLabel: "vs FY2024", period: "FY2025", unit: "Project-defined metric", source: "Management_Notes.xlsx · FCF bridge", tone: "positive" },
  ],
  secondaryRatios: [
    { id: "gross-margin", label: "Gross margin", value: "34.7%", delta: "+0.4 pp", period: "FY2025", source: "Financials_FY2025.xlsx · B7:C7", category: "Profitability" },
    { id: "quick-ratio", label: "Quick ratio", value: "1.09×", delta: "−0.05×", period: "FY2025", source: "Financials_FY2025.xlsx · Balance sheet", category: "Liquidity" },
    { id: "cash-conversion", label: "Cash conversion", value: "79%", delta: "+3 pp", period: "FY2025", source: "Management_Notes.xlsx · Cash bridge", category: "Cash flow" },
    { id: "asset-turnover", label: "Asset turnover", value: "1.31×", delta: "+0.02×", period: "FY2025", source: "Management_Notes.xlsx · Operating ratios", category: "Operations" },
    { id: "net-debt-ebitda", label: "Net debt / EBITDA", value: "1.8×", delta: "−0.2×", period: "FY2025", source: "Management_Notes.xlsx · Debt bridge", category: "Leverage" },
    { id: "inventory-turns", label: "Inventory turns", value: "5.6×", delta: "+0.3×", period: "FY2025", source: "Management_Notes.xlsx · Operating ratios", category: "Efficiency" },
  ],
  economicContext: [
    { label: "US real GDP growth", value: "2.1%", geography: "United States", period: "2025 annual", unit: "Percent", source: "BEA fixture snapshot", sourceDate: "30 Jan 2026", comparability: "Calendar year; company uses fiscal year" },
    { label: "US CPI inflation", value: "2.7%", geography: "United States", period: "Dec 2025 YoY", unit: "Percent", source: "BLS fixture snapshot", sourceDate: "14 Jan 2026", comparability: "Monthly YoY; contextual only" },
    { label: "Policy rate", value: "4.25%–4.50%", geography: "United States", period: "31 Dec 2025", unit: "Target range", source: "Federal Reserve fixture snapshot", sourceDate: "31 Dec 2025", comparability: "Point-in-time rate" },
    { label: "Broad dollar movement", value: "+3.2%", geography: "United States", period: "2025 annual", unit: "Index change", source: "Federal Reserve fixture snapshot", sourceDate: "7 Jan 2026", comparability: "Broad index; not company-specific" },
  ],
  forecast: {
    minimumHistory: 3,
    method: "Three-period compound-growth baseline with a ±2 percentage-point sensitivity band",
    inputs: "FY2023–FY2025 synthetic reported revenue",
    assumptions: "No acquisitions, currency remeasurement, or causal macro adjustment",
    ranges: [
      { period: "FY2026", low: 2410.2, base: 2481.9, high: 2553.6 },
      { period: "FY2027", low: 2467.0, base: 2616.1, high: 2765.2 },
    ],
  },
  summary: "Reported revenue increased from $2,234.2m to $2,354.8m in FY2025. The cited workbook supports 5.4% growth; the annual report narrative states 8.2%.",
  reviewPriorities: [
    { id: "growth", label: "Reconcile the revenue growth claim", status: "High priority" },
    { id: "margin", label: "Check the operating-margin narrative", status: "Needs source" },
    { id: "period", label: "Confirm all comparisons use FY2025", status: "Ready" },
  ],
  analysisSignals: [
    { label: "Narrative variance", value: "2.8 pp", detail: "8.2% stated versus 5.4% calculated from cited revenue inputs." },
    { label: "Liquidity movement", value: "−0.08×", detail: "Current ratio moved from 1.50× to 1.42× year over year." },
    { label: "Operating margin", value: "+1.2 pp", detail: "Operating margin increased to 18.6% in the reported period." },
  ],
  managementQuestions: [
    "Which operating factors account for the difference between reported revenue growth and the narrative wording?",
    "What explains the year-over-year decline in the current ratio, and is it expected to reverse?",
    "Which assumptions are most sensitive in the illustrative revenue range?",
  ],
  history: [
    { id: "history-current", label: "FY2025 company review", time: "Today · 10:24", status: "Human review required", route: "/company" },
    { id: "history-review", label: "Revenue growth finding", time: "Today · 10:18", status: "Contradicted", route: "/review" },
  ],
  assistant: {
    mode: "verified_demo",
    prompt: "Does the FY2025 release accurately describe revenue growth?",
    calculated: "5.4% revenue growth",
    formula: reviewFixture.formula,
    analysis: "The release states 8.2%, while the cited audited figures calculate to 5.4%. This is a numerical discrepancy; the fixture does not determine why it occurred.",
    citations: [
      { id: "assistant-pdf", label: "Annual Report 2025 · p. 14", detail: "Narrative claim: revenue growth was 8.2%.", anchor: "Page 14 · claim span", period: "FY2025", provenance: "Quoted verified fixture", route: "/review#annual-report" },
      { id: "assistant-sheet", label: "Financials FY2025 · B5:C5", detail: "FY2024 $2,234.2m; FY2025 $2,354.8m.", anchor: "Income Statement · cells B5:C5", period: "FY2024–FY2025", provenance: "Human-verified fixture cells", route: "/review#financials" },
    ],
    chartProposal: {
      type: "line",
      metricKey: "revenue",
      title: "Reported revenue trajectory",
      sourceIds: ["financials"],
    },
    chartProposals: [
      { id: "revenue-trend", type: "line", metricKey: "revenue", title: "Reported revenue trajectory", sourceIds: ["financials"] },
      { id: "margin-trend", type: "line", metricKey: "operatingMargin", title: "Reported operating-margin trajectory", sourceIds: ["financials", "annual-report"] },
    ],
    suggestions: [
      { id: "growth", label: "Why is revenue growth flagged?", calculated: "5.4% revenue growth", formula: reviewFixture.formula, analysis: "The annual report states 8.2%, but the cited FY2024 and FY2025 values calculate to 5.4%. The fixture identifies the discrepancy and does not infer its cause." },
      { id: "sources", label: "Which sources support this result?", calculated: "2 linked anchors", formula: "Annual report claim + workbook inputs", analysis: "The result links the narrative claim on page 14 to the FY2024 and FY2025 workbook cells used in the deterministic calculation." },
      { id: "limits", label: "What can this demo not do?", calculated: "Provider not configured", formula: "No live model or browser API key", analysis: "This public demo uses scripted fixture answers. It does not upload files, persist data, call a live model, or create a live-session report." },
    ],
  },
  review: reviewFixture,
};

export const runMagicStages = [
  "Extract reported figures",
  "Calculate performance metrics",
  "Compare narrative with numbers",
  "Update dashboard and report",
];

const metricPresentation = {
  revenue_growth_yoy: { id: "revenue", label: "Revenue growth", unit: "Percent", suffix: "%" },
  operating_margin: { id: "operating-margin", label: "Operating margin", unit: "Percent of revenue", suffix: "%" },
  current_ratio: { id: "current-ratio", label: "Current ratio", unit: "Ratio", suffix: "×" },
  fcf_margin: { id: "fcf-margin", label: "Free-cash-flow margin", unit: "Project-defined percent", suffix: "%" },
};

function sourceAnchor(source) {
  if (!source) return "Source span unavailable";
  return source.kind === "pdf" ? `Page ${source.page}` : `${source.sheet} ${source.cell}`;
}

function formatMetricValue(metricId, rawValue) {
  if (rawValue == null) return "Unavailable";
  const presentation = metricPresentation[metricId] || { suffix: "" };
  const number = Number(rawValue);
  if (!Number.isFinite(number)) return String(rawValue);
  const isPercent = ["revenue_growth_yoy", "operating_margin", "fcf_margin"].includes(metricId);
  const displayNumber = isPercent && Math.abs(number) <= 1 ? number * 100 : number;
  return `${displayNumber.toLocaleString(undefined, { maximumFractionDigits: 2 })}${presentation.suffix}`;
}

function displayMetric(result) {
  const presentation = metricPresentation[result.metric_id] || { id: result.metric_id, label: result.metric_id, unit: "Reported unit", suffix: "" };
  return {
    ...presentation,
    value: formatMetricValue(result.metric_id, result.result),
    delta: result.exceptional_state ? "Needs attention" : "Calculated",
    deltaLabel: result.exceptional_state || "deterministic backend",
    tone: result.exceptional_state ? "caution" : "positive",
  };
}

export function adaptAnalysisResponse(response) {
  const documents = Array.isArray(response?.documents) ? response.documents : [];
  const spans = Array.isArray(response?.source_spans) ? response.source_spans : [];
  const observations = Array.isArray(response?.observations) ? response.observations : [];
  const results = Array.isArray(response?.metric_results) ? response.metric_results : [];
  const findings = Array.isArray(response?.findings) ? response.findings : [];
  const claims = Array.isArray(response?.claims) ? response.claims : [];
  if (!documents.length || !results.length || !findings.length) throw new Error("The analysis response is incomplete.");
  const issuer = documents[0].issuer;
  const latestEnd = observations.map((item) => item.period?.end).filter(Boolean).sort().at(-1) || "Current period";
  const spanById = new Map(spans.map((item) => [item.id, item]));
  const observationById = new Map(observations.map((item) => [item.id, item]));
  const resultById = new Map(results.map((item) => [item.id, item]));
  const claimById = new Map(claims.map((item) => [item.id, item]));
  const sources = documents.map((document) => {
    const span = spans.find((item) => item.document_version_id === document.id);
    const kind = span?.source?.kind === "pdf" ? "PDF" : "Workbook";
    return { id: document.id, name: document.version_label, kind, date: latestEnd, status: "Validated", provenance: document.source_url, anchor: sourceAnchor(span?.source), route: `/files#${document.id}` };
  });
  const metrics = results.slice(0, 4).map((result) => {
    const input = observationById.get(result.input_observation_ids?.[0]);
    const span = spanById.get(input?.source_span_id);
    return { ...displayMetric(result), period: input?.period?.end || latestEnd, source: `${sources.find((item) => item.id === span?.document_version_id)?.name || "Validated source"} · ${sourceAnchor(span?.source)}` };
  });
  const revenueObservations = observations.filter((item) => /revenue/i.test(item.concept)).sort((a, b) => String(a.period?.end).localeCompare(String(b.period?.end)));
  const fallbackMetric = (id) => Number(results.find((item) => item.metric_id === id)?.result) || 0;
  const trend = revenueObservations.map((item) => ({ period: item.period?.end || "Reported period", revenue: Number(item.numeric_value), operatingMargin: fallbackMetric("operating_margin") * (Math.abs(fallbackMetric("operating_margin")) <= 1 ? 100 : 1), currentRatio: fallbackMetric("current_ratio"), fcfMargin: fallbackMetric("fcf_margin") * (Math.abs(fallbackMetric("fcf_margin")) <= 1 ? 100 : 1) }));
  const finding = findings[0];
  const claim = claimById.get(finding.claim_id) || claims[0];
  const result = resultById.get(finding.metric_result_id) || results[0];
  const inputs = (result.input_observation_ids || []).map((id) => observationById.get(id)).filter(Boolean);
  const paddedInputs = inputs.length >= 2 ? inputs.slice(0, 2) : [inputs[0], inputs[0]].filter(Boolean);
  const reviewInputs = paddedInputs.map((item) => ({ period: item.period?.end || latestEnd, value: item.display_value, cell: sourceAnchor(spanById.get(item.source_span_id)?.source) }));
  const classification = finding.classification || "uncertain";
  const review = {
    meta: { entity: issuer, period: latestEnd, registryVersion: response.metric_registry_version },
    summary: { supported: findings.filter((item) => item.classification === "supported").length, uncertain: findings.filter((item) => item.classification === "uncertain").length, contradicted: findings.filter((item) => item.classification === "contradicted").length },
    claim: { text: claim?.text || "No narrative claim supplied", value: claim?.asserted_value == null ? "Direction-only claim" : formatMetricValue(claim.metric_id, claim.asserted_value), source: sourceAnchor(spanById.get(claim?.source_span_id)?.source) },
    result: { status: classification, value: formatMetricValue(result?.metric_id, result?.result), difference: classification === "supported" ? "Within tolerance" : "Outside tolerance", rationale: finding.rationale, tolerance: finding.tolerance == null ? "Policy-defined" : String(finding.tolerance) },
    inputs: reviewInputs.length === 2 ? reviewInputs : [{ period: latestEnd, value: "Unavailable", cell: "Unavailable" }, { period: latestEnd, value: "Unavailable", cell: "Unavailable" }],
    formula: result?.formula_id || "Allowlisted deterministic formula",
  };
  const citations = finding.evidence_source_span_ids.map((id) => {
    const span = spanById.get(id);
    const source = sources.find((item) => item.id === span?.document_version_id);
    return { id, label: source?.name || id, detail: finding.rationale, anchor: sourceAnchor(span?.source), period: latestEnd, provenance: source?.provenance, route: source?.route || "/files#sources" };
  });
  return {
    session: { id: `analysis:${findings[0].id}`, mode: "live", label: "Validated analysis", persistence: "Temporary analysis response", entity: issuer, period: latestEnd, lastUpdated: "Current session" },
    company: { name: issuer, shortName: issuer.split(/\s+/)[0], description: documents[0].reporting_basis, currency: `${observations.find((item) => item.currency)?.currency || "Reported"} units` },
    sources,
    trend: trend.length >= 2 ? trend : [{ period: "Prior", revenue: 0, operatingMargin: 0, currentRatio: 0, fcfMargin: 0 }, { period: latestEnd, revenue: trend[0]?.revenue || 0, operatingMargin: trend[0]?.operatingMargin || 0, currentRatio: trend[0]?.currentRatio || 0, fcfMargin: trend[0]?.fcfMargin || 0 }],
    metrics,
    secondaryRatios: [], economicContext: [],
    forecast: { minimumHistory: 99, method: "Unavailable for uploaded analysis", inputs: "Reported observations only", assumptions: "No unsupported outlook generated", ranges: [] },
    summary: finding.rationale,
    reviewPriorities: findings.map((item) => ({ id: item.id, label: item.suggested_investigation || item.rationale, status: item.classification })),
    analysisSignals: findings.map((item) => ({ label: item.classification, value: item.id, detail: item.rationale })),
    managementQuestions: findings.map((item) => item.suggested_investigation).filter(Boolean),
    history: [{ id: findings[0].id, label: `${latestEnd} analysis`, time: "Current session", status: classification, route: "/review" }],
    assistant: { ...productFixture.assistant, mode: "validated_analysis", analysis: finding.rationale, citations, suggestions: [{ id: "finding", label: "What did the deterministic analysis find?", calculated: formatMetricValue(result?.metric_id, result?.result), formula: result?.formula_id, analysis: finding.rationale }], chartProposals: [], chartSpecs: response.chart_specs || [] },
    review,
    analysisResponse: response,
    reportBundle: response.report_bundle,
  };
}

export function adaptProductContract(response = productFixture) {
  if (response?.output_status === "calculated" && Array.isArray(response.documents)) return adaptAnalysisResponse(response);
  return response;
}

export function getAssistantAdapter(mode = "verified_demo", response = productFixture) {
  const base = response.assistant;
  const states = {
    verified_demo: { ...base, mode, notice: response.session?.mode === "live" ? "Validated analysis response" : "Verified scripted demo · provider not configured" },
    not_configured: { mode, notice: "Assistant provider not configured", analysis: "Free-form questions are unavailable until a server-side provider is configured.", citations: [] },
    offline: { mode, notice: "Offline", analysis: "The scripted demo is unavailable while this session is offline.", citations: [] },
    error: { mode, notice: "Assistant unavailable", analysis: "The fixture response could not be loaded. Retry the verified demo.", citations: [] },
    loading: { mode, notice: "Loading verified demo", analysis: "Retrieving the scripted response and its source links.", citations: [] },
  };
  return states[mode] ?? states.not_configured;
}

/** @typedef {{type: "line", metricKey: "revenue"|"operatingMargin"|"currentRatio"|"fcfMargin", title: string, sourceIds: string[]}} ChartProposal */
/** @param {typeof productFixture} response @param {ChartProposal | undefined} proposal */
export function getAssistantChartSpec(response = productFixture, proposal = response.assistant?.chartProposal) {
  if (!proposal || proposal.type !== "line") return null;
  const allowedKeys = new Set(["revenue", "operatingMargin", "currentRatio", "fcfMargin"]);
  if (!allowedKeys.has(proposal.metricKey)) return null;
  const sources = proposal.sourceIds?.map((id) => response.sources.find((source) => source.id === id)).filter(Boolean) ?? [];
  if (!sources.length || !Array.isArray(response.trend) || response.trend.length < 2) return null;
  const series = response.trend.map((row) => ({ period: row.period, value: Number(row[proposal.metricKey]) }));
  if (series.some((row) => !row.period || !Number.isFinite(row.value))) return null;
  const metric = response.metrics.find((item) => item.id === proposal.metricKey || item.id === proposal.metricKey.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`));
  return {
    id: proposal.id || `${proposal.metricKey}-chart`,
    type: "line",
    title: proposal.title,
    metricKey: proposal.metricKey,
    label: metric?.label ?? proposal.metricKey,
    unit: metric?.unit ?? response.company.currency,
    currency: response.company.currency,
    series,
    sources,
  };
}

export function getAssistantChartSpecs(response = productFixture) {
  const backendSpecs = response.assistant?.chartSpecs || response.chartSpecs;
  if (Array.isArray(backendSpecs) && backendSpecs.length) {
    return backendSpecs.filter((spec) => spec?.authoritative_values === "deterministic_backend" && ["line", "bar", "comparison"].includes(spec.chart_type)).map((spec, index) => {
      const firstSeries = spec.series?.[0];
      const citations = spec.citations || [];
      const sources = citations.map((citation) => response.sources.find((source) => source.id === citation.evidence_id || source.sourceSpanId === citation.source_span_id) || { id: citation.evidence_id, name: citation.label, anchor: citation.source_span_id, provenance: "Validated backend citation", route: `/files#${citation.evidence_id}` });
      return {
        id: `backend-chart-${index + 1}`,
        type: spec.chart_type,
        title: spec.title,
        metricKey: "backend",
        label: firstSeries?.label || spec.title,
        unit: firstSeries?.unit || "Reported unit",
        currency: firstSeries?.currency || response.company.currency,
        series: (firstSeries?.points || []).map((point) => ({ period: point.period_end, value: Number(point.value), sourceSpanIds: point.source_span_ids })),
        sources,
        authoritativeValues: spec.authoritative_values,
      };
    }).filter((spec) => spec.series.length && spec.sources.length);
  }
  const proposals = Array.isArray(response.assistant?.chartProposals) && response.assistant.chartProposals.length
    ? response.assistant.chartProposals
    : [response.assistant?.chartProposal].filter(Boolean);
  return proposals.map((proposal) => getAssistantChartSpec(response, proposal)).filter(Boolean);
}

export function getProviderConnectionAdapter(mode = "not_configured") {
  const states = {
    not_configured: {
      mode,
      status: "Not configured",
      tone: "warning",
      description: "The deployment owner must configure the provider key on the server before live questions can be enabled.",
      lastSuccessfulTest: "Never",
    },
    loading: {
      mode,
      status: "Testing connection…",
      tone: "neutral",
      description: "MagicFin is checking its authenticated, provider-neutral server endpoint.",
      lastSuccessfulTest: "Never",
    },
    success: {
      mode,
      status: "Connected",
      tone: "success",
      description: "The authenticated server endpoint responded successfully. No provider credential reached this browser.",
      lastSuccessfulTest: "22 Aug 2026 · 12:00 MYT",
    },
    error: {
      mode,
      status: "Connection failed",
      tone: "warning",
      description: "The server endpoint could not confirm the configured provider. Check the deployment configuration and retry.",
      lastSuccessfulTest: "Never",
    },
  };
  return states[mode] ?? states.not_configured;
}

export function buildReviewedReport(response = productFixture) {
  if (response.session?.id === productFixture.session.id && response.session?.mode === "verified_fixture") return demoReportSnapshot;
  return {
    product: "MagicFin",
    exportedAt: "2026-08-22T10:24:00+08:00",
    session: response.session,
    reviewStatus: "human_review_required",
    finding: response.review,
    limitations: [
      "Authenticated upload-derived analysis; human review is required",
      "Only cited native-text PDF and structural XLSX evidence was used",
      "No causal explanation, forecast, or investment recommendation is asserted",
      "Live PDF export requires a separately validated server-side report bundle",
    ],
  };
}

export const REVIEWED_REPORT_PDF_ENDPOINT = "/api/v1/reports/pdf";
export const MAX_REVIEWED_REPORT_PDF_BYTES = 8_000_000;

export function buildDeterministicDemoPdf(response = productFixture) {
  const safe = (value) => String(value ?? "").normalize("NFKD").replace(/[^\x20-\x7e]/g, "-").replace(/[()\\]/g, (match) => `\\${match}`);
  const lines = [
    "MagicFin Board Performance Brief",
    `${safe(response.company?.name)} | ${safe(response.session?.period)}`,
    "Deterministic demo fixture - not investment advice",
    ...response.metrics.slice(0, 4).map((metric) => `${safe(metric.label)}: ${safe(metric.value)} (${safe(metric.delta)})`),
    `Narrative outcome: ${safe(response.review?.result?.status)}; calculated ${safe(response.review?.result?.value)}`,
  ];
  const commands = lines.map((line, index) => `BT /F1 ${index === 0 ? 18 : 11} Tf 54 ${748 - index * 30} Td (${line}) Tj ET`).join("\n");
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
    `<< /Length ${commands.length} >>\nstream\n${commands}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(pdf.length); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.slice(1).map((offset) => `${String(offset).padStart(10, "0")} 00000 n `).join("\n")}\ntrailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return new Blob([pdf], { type: "application/pdf" });
}

function safePdfFilename(contentDisposition) {
  const encoded = contentDisposition?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const quoted = contentDisposition?.match(/filename="([^"]+)"/i)?.[1];
  const plain = contentDisposition?.match(/filename=([^;]+)/i)?.[1];
  let candidate = encoded ? decodeURIComponent(encoded) : quoted || plain || "magicfin-reviewed-report.pdf";
  candidate = candidate.trim().replace(/[\\/\u0000-\u001f\u007f]/g, "-");
  if (!candidate.toLowerCase().endsWith(".pdf")) candidate += ".pdf";
  return candidate.slice(0, 180) || "magicfin-reviewed-report.pdf";
}

export function getReviewedReportBundle(response) {
  if (!response?.reportBundle || typeof response.reportBundle !== "object" || Array.isArray(response.reportBundle)) {
    throw new Error("This review is not ready for a PDF download yet.");
  }
  return response.reportBundle;
}

export async function requestReviewedPdf({
  bundle,
  fetchImpl = globalThis.fetch,
  endpoint = REVIEWED_REPORT_PDF_ENDPOINT,
  maxBytes = MAX_REVIEWED_REPORT_PDF_BYTES,
  createObjectURL = URL.createObjectURL.bind(URL),
  revokeObjectURL = URL.revokeObjectURL.bind(URL),
} = {}) {
  if (!bundle || typeof bundle !== "object" || Array.isArray(bundle)) throw new Error("This review is not ready for a PDF download yet.");
  if (typeof fetchImpl !== "function") throw new Error("The reviewed PDF could not be prepared. Please try again.");
  const response = await fetchImpl(endpoint, {
    method: "POST",
    credentials: "same-origin",
    headers: { Accept: "application/pdf", "Content-Type": "application/json" },
    body: JSON.stringify(bundle),
  });
  if (!response.ok) throw new Error("The reviewed PDF could not be prepared. Please try again.");
  const contentType = (response.headers.get("content-type") || "").split(";", 1)[0].trim().toLowerCase();
  if (contentType !== "application/pdf") throw new Error("The report service returned an unsupported file. Please try again.");
  const declaredSize = Number(response.headers.get("content-length") || 0);
  if (Number.isFinite(declaredSize) && declaredSize > maxBytes) throw new Error("The reviewed PDF is too large to download safely.");
  const blob = await response.blob();
  if (!blob.size) throw new Error("The reviewed PDF was empty. Please try again.");
  if (blob.size > maxBytes) throw new Error("The reviewed PDF is too large to download safely.");
  const filename = safePdfFilename(response.headers.get("content-disposition"));
  const objectUrl = createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.hidden = true;
  document.body.append(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    revokeObjectURL(objectUrl);
  }
  return { filename, size: blob.size };
}
