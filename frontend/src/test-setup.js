import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

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

afterEach(() => cleanup());
