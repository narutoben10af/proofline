export const SCHEMA_VERSION = "1.0.0" as const;
export const MAX_SOURCES = 12;
export const MAX_EVIDENCE_ROWS = 24;
export const MAX_SERIES = 4;
export const MAX_POINTS_PER_SERIES = 12;
export const MAX_TOTAL_POINTS = 24;

// These prefixes and character bounds mirror the dynamic upload identifiers produced by
// SourceLibraryStore. They are opaque capabilities/scopes, not database UUIDs.
const SESSION_ID_PATTERN = /^src-[A-Za-z0-9_-]{32}$/;
const SOURCE_ID_PATTERN = /^file-[A-Za-z0-9_-]{24}$/;
const OBSERVATION_ID_PATTERN = /^fact:[a-f0-9]{20}$/;
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const CONCEPT_LABELS = {
  revenue: "Revenue",
  operating_profit: "Operating profit",
  current_assets: "Current assets",
  current_liabilities: "Current liabilities",
  operating_cash_flow: "Operating cash flow",
  capex: "Capital expenditure",
} as const;
const CHART_TITLES: Record<ChartType, string> = {
  line: "Verified financial trend",
  bar: "Verified financial values by period",
  comparison: "Verified financial comparison",
};
const CHART_DESCRIPTION = "Values resolve from cited normalized evidence.";

export type ChartType = "line" | "bar" | "comparison";

export interface MagicAssistantRequest {
  schema_version: typeof SCHEMA_VERSION;
  question: string;
  session_id: string;
  source_ids: string[];
}

export interface NormalizedEvidence {
  session_id: string;
  source_id: string;
  observation_id: string;
  issuer: string;
  concept: string;
  period_start: string | null;
  period_end: string;
  duration_weeks: number | null;
  unit: string;
  currency: string | null;
}

export interface ChartSeriesProposal {
  label: string;
  observation_ids: string[];
  source_ids: string[];
}

export interface ChartProposal {
  schema_version: typeof SCHEMA_VERSION;
  chart_type: ChartType;
  title: string;
  description: string;
  period_start: string | null;
  period_end: string;
  series: ChartSeriesProposal[];
  source_ids: string[];
}

function hasControlCharacter(text: string, allowWhitespace: boolean): boolean {
  return [...text].some((character) => {
    const code = character.charCodeAt(0);
    return (code < 32 && !(allowWhitespace && [9, 10, 13].includes(code))) || code === 127;
  });
}

function objectValue(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function exactKeys(value: Record<string, unknown>, keys: readonly string[], label: string): void {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw new Error(`${label} contains unknown or missing fields`);
  }
}

function stringValue(value: unknown, label: string, maxLength: number): string {
  if (typeof value !== "string" || value.length === 0 || value.length > maxLength) {
    throw new Error(`${label} must be a bounded string`);
  }
  return value;
}

function safeText(value: unknown, label: string, maxLength: number): string {
  const text = stringValue(value, label, maxLength).trim();
  if (!text || hasControlCharacter(text, false) || /[<>{}]/u.test(text)) {
    throw new Error(`${label} contains unsafe text`);
  }
  return text;
}

function prefixedIdentifier(
  value: unknown,
  label: string,
  pattern: RegExp,
): string {
  const identifier = stringValue(value, label, 128);
  if (!pattern.test(identifier)) throw new Error(`${label} is not a valid dynamic upload ID`);
  return identifier;
}

function identifierValue(value: unknown, label: string): string {
  const identifier = stringValue(value, label, 128);
  if (!OBSERVATION_ID_PATTERN.test(identifier)) {
    throw new Error(`${label} is not a normalized upload observation ID`);
  }
  return identifier;
}

function sourceIdentifier(value: unknown, label: string): string {
  return prefixedIdentifier(value, label, SOURCE_ID_PATTERN);
}

function conceptValue(value: unknown, label: string): keyof typeof CONCEPT_LABELS {
  const concept = stringValue(value, label, 128);
  if (!(concept in CONCEPT_LABELS)) throw new Error(`${label} is not an allowlisted concept`);
  return concept as keyof typeof CONCEPT_LABELS;
}

function dateValue(value: unknown, label: string): string {
  const date = stringValue(value, label, 10);
  if (!ISO_DATE_PATTERN.test(date) || Number.isNaN(Date.parse(`${date}T00:00:00Z`))) {
    throw new Error(`${label} must be an ISO date`);
  }
  return date;
}

function uniqueStrings(
  value: unknown,
  label: string,
  maximum: number,
  parser: (item: unknown, label: string) => string,
): string[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > maximum) {
    throw new Error(`${label} must contain between 1 and ${maximum} IDs`);
  }
  const identifiers = value.map((item, index) => parser(item, `${label}[${index}]`));
  if (new Set(identifiers).size !== identifiers.length) {
    throw new Error(`${label} must contain unique IDs`);
  }
  return identifiers;
}

export function parseRequest(value: unknown): MagicAssistantRequest {
  const record = objectValue(value, "request");
  exactKeys(record, ["schema_version", "question", "session_id", "source_ids"], "request");
  if (record.schema_version !== SCHEMA_VERSION) throw new Error("unsupported schema version");
  const question = stringValue(record.question, "question", 1_000).trim();
  if (!question || hasControlCharacter(question, true)) {
    throw new Error("question contains invalid control characters");
  }
  return {
    schema_version: SCHEMA_VERSION,
    question,
    session_id: prefixedIdentifier(record.session_id, "session_id", SESSION_ID_PATTERN),
    source_ids: uniqueStrings(
      record.source_ids,
      "source_ids",
      MAX_SOURCES,
      sourceIdentifier,
    ),
  };
}

export function parseEvidenceRows(
  value: unknown,
  request: MagicAssistantRequest,
): NormalizedEvidence[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > MAX_EVIDENCE_ROWS) {
    throw new Error("evidence must contain between 1 and 24 normalized rows");
  }
  const rows = value.map((item, index): NormalizedEvidence => {
    const record = objectValue(item, `evidence[${index}]`);
    exactKeys(
      record,
      [
        "session_id",
        "source_id",
        "observation_id",
        "issuer",
        "concept",
        "period_start",
        "period_end",
        "duration_weeks",
        "unit",
        "currency",
      ],
      `evidence[${index}]`,
    );
    const periodStart = record.period_start === null
      ? null
      : dateValue(record.period_start, `evidence[${index}].period_start`);
    const periodEnd = dateValue(record.period_end, `evidence[${index}].period_end`);
    if (periodStart !== null && periodStart > periodEnd) {
      throw new Error("evidence period is reversed");
    }
    const durationWeeks = record.duration_weeks;
    if (
      durationWeeks !== null &&
      (typeof durationWeeks !== "number" ||
        !Number.isInteger(durationWeeks) ||
        durationWeeks < 1 ||
        durationWeeks > 54)
    ) {
      throw new Error("evidence duration_weeks is invalid");
    }
    const currency = record.currency === null
      ? null
      : stringValue(record.currency, `evidence[${index}].currency`, 3);
    if (currency !== null && !/^[A-Z]{3}$/.test(currency)) throw new Error("currency is invalid");
    return {
      session_id: prefixedIdentifier(
        record.session_id,
        `evidence[${index}].session_id`,
        SESSION_ID_PATTERN,
      ),
      source_id: prefixedIdentifier(
        record.source_id,
        `evidence[${index}].source_id`,
        SOURCE_ID_PATTERN,
      ),
      observation_id: identifierValue(record.observation_id, `evidence[${index}].observation_id`),
      issuer: safeText(record.issuer, `evidence[${index}].issuer`, 256),
      concept: conceptValue(record.concept, `evidence[${index}].concept`),
      period_start: periodStart,
      period_end: periodEnd,
      duration_weeks: durationWeeks as number | null,
      unit: safeText(record.unit, `evidence[${index}].unit`, 64),
      currency,
    };
  });
  if (new Set(rows.map((row) => row.observation_id)).size !== rows.length) {
    throw new Error("evidence observation IDs must be unique");
  }
  if (rows.some((row) => row.session_id !== request.session_id)) {
    throw new Error("evidence escaped the requested session");
  }
  const requestedSources = new Set(request.source_ids);
  if (rows.some((row) => !requestedSources.has(row.source_id))) {
    throw new Error("evidence escaped the requested source scope");
  }
  if (new Set(rows.map((row) => row.source_id)).size !== requestedSources.size) {
    throw new Error("one or more requested sources were not resolved");
  }
  return rows;
}

function sameDimension(rows: NormalizedEvidence[], key: keyof NormalizedEvidence): boolean {
  return new Set(rows.map((row) => row[key])).size === 1;
}

export function parseAndResolveProposal(
  value: unknown,
  evidence: NormalizedEvidence[],
): ChartProposal {
  const record = objectValue(value, "chart proposal");
  exactKeys(
    record,
    [
      "schema_version",
      "chart_type",
      "period_start",
      "period_end",
      "series",
      "source_ids",
    ],
    "chart proposal",
  );
  if (record.schema_version !== SCHEMA_VERSION) throw new Error("unsupported chart schema version");
  if (!(["line", "bar", "comparison"] as unknown[]).includes(record.chart_type)) {
    throw new Error("chart_type is not allowlisted");
  }
  const chartType = record.chart_type as ChartType;
  const periodStart = record.period_start === null
    ? null
    : dateValue(record.period_start, "period_start");
  const periodEnd = dateValue(record.period_end, "period_end");
  if (periodStart !== null && periodStart > periodEnd) throw new Error("chart period is reversed");
  if (
    !Array.isArray(record.series) || record.series.length < 1 || record.series.length > MAX_SERIES
  ) {
    throw new Error("chart must contain between 1 and 4 series");
  }
  const evidenceById = new Map(evidence.map((row) => [row.observation_id, row]));
  let totalPoints = 0;
  const selectedRows: NormalizedEvidence[] = [];
  const series = record.series.map((item, index): ChartSeriesProposal => {
    const proposed = objectValue(item, `series[${index}]`);
    exactKeys(proposed, ["observation_ids", "source_ids"], `series[${index}]`);
    const observationIds = uniqueStrings(
      proposed.observation_ids,
      `series[${index}].observation_ids`,
      MAX_POINTS_PER_SERIES,
      identifierValue,
    );
    totalPoints += observationIds.length;
    const rows = observationIds.map((identifier) => {
      const row = evidenceById.get(identifier);
      if (!row) throw new Error("chart references an unknown observation ID");
      return row;
    });
    if (new Set(rows.map((row) => row.period_end)).size !== rows.length) {
      throw new Error("a chart series cannot repeat a period");
    }
    const concepts = new Set(rows.map((row) => row.concept));
    if (concepts.size !== 1) throw new Error("a chart series cannot mix concepts");
    const concept = rows[0].concept as keyof typeof CONCEPT_LABELS;
    const sourceIds = uniqueStrings(
      proposed.source_ids,
      `series[${index}].source_ids`,
      MAX_POINTS_PER_SERIES,
      sourceIdentifier,
    );
    const expectedSources = [...new Set(rows.map((row) => row.source_id))].sort();
    if (sourceIds.slice().sort().join(",") !== expectedSources.join(",")) {
      throw new Error("series citations do not match normalized evidence");
    }
    selectedRows.push(...rows);
    return {
      label: CONCEPT_LABELS[concept],
      observation_ids: observationIds,
      source_ids: sourceIds,
    };
  });
  if (totalPoints > MAX_TOTAL_POINTS) throw new Error("chart exceeds 24 total points");
  for (
    const [key, label] of [
      ["issuer", "issuer"],
      ["unit", "unit"],
      ["currency", "currency"],
      ["duration_weeks", "period basis"],
    ] as const
  ) {
    if (!sameDimension(selectedRows, key)) throw new Error(`chart evidence has mixed ${label}`);
  }
  if (new Set(selectedRows.map((row) => row.period_start === null)).size !== 1) {
    throw new Error("chart evidence has mixed instant and duration periods");
  }
  const expectedStart = selectedRows[0].period_start === null
    ? null
    : selectedRows.map((row) => row.period_start as string).sort()[0];
  const expectedEnd = selectedRows.map((row) => row.period_end).sort().at(-1) as string;
  if (periodStart !== expectedStart || periodEnd !== expectedEnd) {
    throw new Error("chart period range does not match normalized evidence");
  }
  const sourceIds = uniqueStrings(record.source_ids, "source_ids", MAX_SOURCES, sourceIdentifier);
  const expectedSources = [...new Set(selectedRows.map((row) => row.source_id))].sort();
  if (sourceIds.slice().sort().join(",") !== expectedSources.join(",")) {
    throw new Error("chart citations do not match normalized evidence");
  }
  return {
    schema_version: SCHEMA_VERSION,
    chart_type: chartType,
    title: CHART_TITLES[chartType],
    description: CHART_DESCRIPTION,
    period_start: periodStart,
    period_end: periodEnd,
    series,
    source_ids: sourceIds,
  };
}
