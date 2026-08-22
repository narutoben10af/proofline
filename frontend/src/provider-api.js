async function jsonRequest(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.error?.message || "The assistant service is unavailable.");
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
