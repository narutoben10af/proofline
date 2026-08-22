import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

class ResizeObserver {
  constructor(callback) { this.callback = callback; }
  observe(target) { this.callback([{ target, contentRect: { width: 800, height: 340 } }]); }
  unobserve() {}
  disconnect() {}
}

window.ResizeObserver = ResizeObserver;
globalThis.ResizeObserver = ResizeObserver;
window.matchMedia = window.matchMedia || (() => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
window.scrollTo = vi.fn();
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});
Element.prototype.getBoundingClientRect = () => ({ width: 800, height: 340, top: 0, left: 0, right: 800, bottom: 340, x: 0, y: 0, toJSON() {} });

const PROVIDER_NOT_CONFIGURED = {
  state: "not_configured",
  provider: "gemma_via_gemini_api",
  model: "gemma-4-26b-a4b-it",
  live_transport_enabled: false,
  document_content_sent: false,
  disclosure: "No prompt or document content was sent to an external provider.",
};

// Default so the Magic Assistant provider probe never touches the network.
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(PROVIDER_NOT_CONFIGURED), { status: 200, headers: { "Content-Type": "application/json" } })));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
