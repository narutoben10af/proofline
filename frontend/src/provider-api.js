const DEFAULT_ERROR = "The assistant service is unavailable.";

const SAME_ORIGIN_PREFIX = "/api/v1";

/**
 * Same-origin /api/* only exists where something actually routes it: the Vite dev proxy, or a
 * deployment that binds the FastAPI app under the same origin. The public Sites worker serves
 * static assets and an SPA fallback only, so a same-origin assistant call there resolves to a
 * 404 rather than the API. A deployed build must therefore name its endpoint explicitly.
 */
export function resolveAssistantTransport(env = import.meta.env) {
  const configured = env?.VITE_ASSISTANT_ENDPOINT?.trim();
  if (configured) return { mode: "remote", origin: configured.replace(/\/+$/, "") };
  if (env?.DEV) return { mode: "same_origin", origin: "" };
  return { mode: "unconfigured", origin: "" };
}

export class AssistantNotConfiguredError extends Error {
  constructor() {
    super("No assistant endpoint is configured for this deployment.");
    this.name = "AssistantNotConfiguredError";
  }
}

function endpointFor(path, transport) {
  if (transport.mode === "unconfigured") throw new AssistantNotConfiguredError();
  if (transport.mode === "same_origin") return path;
  // A named remote runtime (e.g. a Supabase Edge Function) owns its own route names.
  return `${transport.origin}${path.startsWith(SAME_ORIGIN_PREFIX) ? path.slice(SAME_ORIGIN_PREFIX.length) : path}`;
}

async function jsonRequest(path, options = {}, transport = { mode: "same_origin" }) {
  let response;
  try {
    const credentials = transport.mode === "remote" ? "omit" : "same-origin";
    response = await fetch(path, { credentials, ...options });
  } catch {
    throw new Error("Could not reach the MagicFin server. Is the backend running?");
  }
  const raw = await response.text().catch(() => "");
  let body = {};
  try {
    body = raw ? JSON.parse(raw) : {};
  } catch {
    // A non-JSON body means we hit something other than the API (dev proxy missing, HTML 404).
    if (!response.ok) throw new Error(`${DEFAULT_ERROR} (HTTP ${response.status})`);
    throw new Error("The assistant service returned an unreadable response.");
  }
  if (!response.ok) {
    const detail = Array.isArray(body?.detail) ? body.detail[0]?.msg : body?.detail;
    throw new Error(body?.error?.message || detail || `${DEFAULT_ERROR} (HTTP ${response.status})`);
  }
  return body;
}

async function authorizedHeaders(transport, getAccessToken) {
  const headers = { "Content-Type": "application/json" };
  // A cross-origin runtime is authenticated by the caller's JWT; same-origin uses the session cookie.
  if (transport.mode !== "remote" || !getAccessToken) return headers;
  const token = await getAccessToken();
  if (!token) throw new Error("Sign in to ask the assistant on this deployment.");
  return { ...headers, Authorization: `Bearer ${token}` };
}

export function getModelProviderStatus({ transport = resolveAssistantTransport() } = {}) {
  return jsonRequest(endpointFor("/api/v1/providers/model", transport), {}, transport);
}

export async function testModelProvider({ transport = resolveAssistantTransport(), getAccessToken } = {}) {
  const path = endpointFor("/api/v1/providers/model/test", transport);
  return jsonRequest(path, { method: "POST", headers: await authorizedHeaders(transport, getAccessToken), body: "{}" }, transport);
}

export async function requestAssistant(request, { transport = resolveAssistantTransport(), getAccessToken } = {}) {
  const path = endpointFor("/api/v1/assistant", transport);
  return jsonRequest(path, { method: "POST", headers: await authorizedHeaders(transport, getAccessToken), body: JSON.stringify(request) }, transport);
}

export async function requestAssistantChart(request, { transport = resolveAssistantTransport(), getAccessToken } = {}) {
  const path = endpointFor("/api/v1/assistant/chart", transport);
  return jsonRequest(path, { method: "POST", headers: await authorizedHeaders(transport, getAccessToken), body: JSON.stringify(request) }, transport);
}

/** Backend Identifier = ^[A-Za-z0-9._:-]{1,128}$ */
export function toIdentifier(value, fallback) {
  const cleaned = String(value ?? "")
    .replace(/[^A-Za-z0-9._:-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 128);
  return cleaned || fallback;
}

/**
 * AssistantRequest.evidence requires 1–12 excerpts with unique evidence_id and
 * source_span_id, each with non-empty text and 16000 characters combined.
 */
export function buildAssistantEvidence(data) {
  const citations = data?.assistant?.citations ?? [];
  const sources = data?.sources ?? [];
  const evidenceIds = new Set();
  const spanIds = new Set();
  const evidence = [];
  let budget = 16_000;
  const push = (rawId, rawSpan, parts) => {
    if (evidence.length >= 12) return;
    const evidenceId = toIdentifier(rawId, `evidence-${evidence.length + 1}`);
    const spanId = toIdentifier(rawSpan || rawId, `span-${evidence.length + 1}`);
    if (evidenceIds.has(evidenceId) || spanIds.has(spanId)) return;
    const text = parts.filter(Boolean).join(" — ").slice(0, Math.min(4_000, budget));
    if (!text) return;
    evidenceIds.add(evidenceId);
    spanIds.add(spanId);
    budget -= text.length;
    evidence.push({ evidence_id: evidenceId, source_span_id: spanId, text });
  };
  for (const citation of citations) push(citation.id, citation.anchor, [citation.label, citation.detail, citation.provenance]);
  for (const source of sources) push(source.id, source.anchor, [source.name, source.provenance, source.anchor]);
  return evidence;
}

export function buildAssistantRequest(prompt, data) {
  return { prompt: String(prompt).slice(0, 2_000), evidence: buildAssistantEvidence(data), provider_sent: true };
}
