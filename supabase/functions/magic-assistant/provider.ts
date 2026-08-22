import type { ChartProposal, MagicAssistantRequest, NormalizedEvidence } from "./contracts.ts";
import { parseAndResolveProposal, SCHEMA_VERSION } from "./contracts.ts";

export const SUPPORTED_MODELS = ["gemma-4-26b-a4b-it", "gemma-4-31b-it"] as const;
export const GOOGLE_API_ORIGIN = "https://generativelanguage.googleapis.com";
export const MAX_PROVIDER_REQUEST_BYTES = 65_536;
export const MAX_PROVIDER_RESPONSE_BYTES = 65_536;
export const PROVIDER_TIMEOUT_MS = 8_000;
// One call per allowlisted model keeps a single user action from amplifying a
// project-level RPM limit. The UI can ask the user to retry after Google resets
// the quota window.
export const MAX_PROVIDER_RETRIES = 0;

const CHART_RESPONSE_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: [
    "schema_version",
    "chart_type",
    "period_start",
    "period_end",
    "series",
    "source_ids",
  ],
  properties: {
    schema_version: { type: "string", enum: [SCHEMA_VERSION] },
    chart_type: { type: "string", enum: ["line", "bar", "comparison"] },
    period_start: { anyOf: [{ type: "string", format: "date" }, { type: "null" }] },
    period_end: { type: "string", format: "date" },
    series: {
      type: "array",
      minItems: 1,
      maxItems: 4,
      items: {
        type: "object",
        additionalProperties: false,
        required: ["observation_ids", "source_ids"],
        properties: {
          observation_ids: {
            type: "array",
            minItems: 1,
            maxItems: 12,
            items: {
              type: "string",
              pattern: "^fact:[a-f0-9]{20}$",
              minLength: 25,
              maxLength: 25,
            },
          },
          source_ids: {
            type: "array",
            minItems: 1,
            maxItems: 12,
            items: {
              type: "string",
              pattern: "^file-[A-Za-z0-9_-]{24}$",
              minLength: 29,
              maxLength: 29,
            },
          },
        },
      },
    },
    source_ids: {
      type: "array",
      minItems: 1,
      maxItems: 12,
      items: {
        type: "string",
        pattern: "^file-[A-Za-z0-9_-]{24}$",
        minLength: 29,
        maxLength: 29,
      },
    },
  },
} as const;

export interface ProviderConfig {
  apiKey: string;
  model: string;
}

export type FetchLike = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;
export class ProviderUnavailableError extends Error {
  constructor(message: string, public readonly statusCode = 0) {
    super(message);
  }
}
export class ProviderResponseError extends Error {
  constructor(message: string, public readonly statusCode = 0) {
    super(message);
  }
}

function providerEndpoint(model: string): string {
  if (!(SUPPORTED_MODELS as readonly string[]).includes(model)) {
    throw new Error("provider model is not allowlisted");
  }
  return `${GOOGLE_API_ORIGIN}/v1beta/models/${model}:generateContent`;
}

function promptFor(request: MagicAssistantRequest, evidence: NormalizedEvidence[]): string {
  return JSON.stringify({
    task: "Propose one cited chart using only the supplied IDs and metadata.",
    rules: [
      "Return only JSON matching the response schema.",
      "Use only line, bar, or comparison.",
      "Never return numeric values, formulas, code, JavaScript, Vega, HTML, URLs, or actions.",
      "Do not return titles, descriptions, labels, or any display text; the backend owns it.",
      "Every observation_id and source_id must be copied exactly from supplied evidence.",
      "The period range and citations must exactly cover the selected observations.",
    ],
    question: request.question,
    evidence: evidence.map((row) => ({
      observation_id: row.observation_id,
      source_id: row.source_id,
      issuer: row.issuer,
      concept: row.concept,
      period_start: row.period_start,
      period_end: row.period_end,
      duration_weeks: row.duration_weeks,
      unit: row.unit,
      currency: row.currency,
    })),
  });
}

async function boundedText(response: Response): Promise<string> {
  if (!response.body) return "";
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.length;
    if (length > MAX_PROVIDER_RESPONSE_BYTES) {
      await reader.cancel();
      throw new Error("provider response exceeded byte cap");
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  return new TextDecoder().decode(bytes);
}

function candidateText(payload: unknown): string {
  const value = payload as {
    candidates?: Array<{ content?: { parts?: Array<{ text?: unknown }> } }>;
  };
  const text = value.candidates?.[0]?.content?.parts?.[0]?.text;
  if (typeof text !== "string" || text.length === 0 || text.length > 32_000) {
    throw new Error("provider response shape is invalid");
  }
  return text;
}

export async function proposeChart(
  request: MagicAssistantRequest,
  evidence: NormalizedEvidence[],
  config: ProviderConfig,
  fetcher: FetchLike = fetch,
): Promise<ChartProposal> {
  const prompt = promptFor(request, evidence);
  const payload = {
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: {
      responseMimeType: "application/json",
      responseJsonSchema: CHART_RESPONSE_SCHEMA,
      temperature: 0,
      maxOutputTokens: 1_024,
    },
  };
  const encoded = JSON.stringify(payload);
  if (new TextEncoder().encode(encoded).length > MAX_PROVIDER_REQUEST_BYTES) {
    throw new Error("provider request exceeded byte cap");
  }

  const models = [config.model, ...SUPPORTED_MODELS.filter((model) => model !== config.model)];
  let finalStatus = 0;
  for (const [modelIndex, model] of models.entries()) {
    const endpoint = providerEndpoint(model);
    for (let attempt = 0; attempt <= MAX_PROVIDER_RETRIES; attempt += 1) {
      try {
        const response = await fetcher(endpoint, {
          method: "POST",
          redirect: "error",
          signal: AbortSignal.timeout(PROVIDER_TIMEOUT_MS),
          headers: {
            "content-type": "application/json",
            "x-goog-api-key": config.apiKey,
          },
          body: encoded,
        });
        if (!response.ok) {
          finalStatus = response.status;
          await boundedText(response);
          if ([404, 408, 429, 500, 502, 503, 504].includes(response.status)) {
            if (attempt < MAX_PROVIDER_RETRIES) continue;
            break;
          }
          throw new ProviderResponseError("provider rejected request", response.status);
        }
        try {
          const outer = JSON.parse(await boundedText(response)) as unknown;
          const proposal = JSON.parse(candidateText(outer)) as unknown;
          return parseAndResolveProposal(proposal, evidence);
        } catch {
          throw new ProviderResponseError("provider returned invalid chart proposal", response.status);
        }
      } catch (error) {
        if (error instanceof ProviderResponseError) throw error;
        if (attempt < MAX_PROVIDER_RETRIES) continue;
        if (modelIndex < models.length - 1) break;
        throw new ProviderUnavailableError("provider unavailable", finalStatus);
      }
    }
  }
  throw new ProviderUnavailableError("provider unavailable", finalStatus);
}
