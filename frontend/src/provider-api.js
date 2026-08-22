const DEFAULT_ERROR = "The assistant service is unavailable.";

async function jsonRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { credentials: "same-origin", ...options });
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

export function getModelProviderStatus() {
  return jsonRequest("/api/v1/providers/model");
}

export function testModelProvider() {
  return jsonRequest("/api/v1/providers/model/test", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
}

export function requestAssistant(request) {
  return jsonRequest("/api/v1/assistant", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request) });
}

export function requestAssistantChart(request) {
  return jsonRequest("/api/v1/assistant/chart", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request) });
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
