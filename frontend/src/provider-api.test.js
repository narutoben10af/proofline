import { describe, expect, it, vi } from "vitest";
import { AssistantNotConfiguredError, buildAssistantEvidence, buildAssistantRequest, requestAssistant, resolveAssistantTransport } from "./provider-api";
import { productFixture } from "./product-contract";

const REMOTE = "https://qvxohnlboefomtjecxdh.supabase.co/functions/v1/magic-assistant";

function jsonResponse(payload) {
  return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
}

describe("assistant transport resolution", () => {
  it("uses the same-origin dev proxy only in development", () => {
    expect(resolveAssistantTransport({ DEV: true })).toEqual({ mode: "same_origin", origin: "" });
  });

  it("treats a production build with no configured endpoint as not configured", () => {
    expect(resolveAssistantTransport({ DEV: false })).toEqual({ mode: "unconfigured", origin: "" });
  });

  it("prefers an explicitly configured remote endpoint and trims trailing slashes", () => {
    expect(resolveAssistantTransport({ DEV: true, VITE_ASSISTANT_ENDPOINT: `${REMOTE}/` })).toEqual({ mode: "remote", origin: REMOTE });
  });

  it("refuses to call a same-origin API path that the deployment does not route", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(requestAssistant({ prompt: "hi" }, { transport: resolveAssistantTransport({ DEV: false }) })).rejects.toBeInstanceOf(AssistantNotConfiguredError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends the caller JWT to a remote runtime and omits ambient credentials", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ state: "not_configured", provider: "p", model: "m", disclosure: "d" }));
    vi.stubGlobal("fetch", fetchMock);
    await requestAssistant({ prompt: "hi" }, { transport: { mode: "remote", origin: REMOTE }, getAccessToken: async () => "signed-user-jwt" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe(`${REMOTE}/assistant`);
    expect(options.headers.Authorization).toBe("Bearer signed-user-jwt");
    expect(options.credentials).toBe("omit");
  });

  it("does not send an unauthenticated request to a remote runtime", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(requestAssistant({ prompt: "hi" }, { transport: { mode: "remote", origin: REMOTE }, getAccessToken: async () => null })).rejects.toThrow(/sign in/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("reports an app-shell HTML response as a failure instead of a parsed answer", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<!doctype html><div id=root>", { status: 200, headers: { "Content-Type": "text/html" } })));
    await expect(requestAssistant({ prompt: "hi" }, { transport: { mode: "same_origin", origin: "" } })).rejects.toThrow(/unreadable/i);
  });
});

describe("assistant evidence", () => {
  it("emits contract-valid, unique, bounded evidence from cited fixture sources", () => {
    const body = buildAssistantRequest("Why is revenue growth flagged?", productFixture);
    expect(body.evidence.length).toBeGreaterThan(0);
    expect(body.evidence.length).toBeLessThanOrEqual(12);
    expect(new Set(body.evidence.map((item) => item.evidence_id)).size).toBe(body.evidence.length);
    expect(new Set(body.evidence.map((item) => item.source_span_id)).size).toBe(body.evidence.length);
    body.evidence.forEach((item) => {
      expect(item.evidence_id).toMatch(/^[A-Za-z0-9._:-]{1,128}$/);
      expect(item.source_span_id).toMatch(/^[A-Za-z0-9._:-]{1,128}$/);
    });
    expect(body.evidence.reduce((total, item) => total + item.text.length, 0)).toBeLessThanOrEqual(16_000);
  });

  it("returns no evidence when the session has no cited sources", () => {
    expect(buildAssistantEvidence({ assistant: { citations: [] }, sources: [] })).toEqual([]);
  });
});
