import { afterEach, describe, expect, it, vi } from "vitest";
import {
  analyzeAuthenticatedSourceSession,
  analyzeSourceSession,
  createAuthenticatedSourceSession,
  createSourceSession,
  deleteSourceSession,
  getSourceSession,
  listSourceFiles,
  loadPublicDemo,
  sourceContentUrl,
  uploadAuthenticatedSource,
  uploadSource,
} from "./session-api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Source Library API adapter", () => {
  it("uses relative same-origin requests and keeps the capability out of JavaScript", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ session_id: "src-opaque" }) }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createSourceSession();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sessions",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.stringify(fetchMock.mock.calls)).not.toContain("capability");
  });

  it("sends CSRF only as a header for upload and deletion", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ status: "complete" }) }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const session = { session_id: "src-opaque", csrf_token: "csrf-memory-only" };
    const file = new File(["%PDF"], "report.pdf", { type: "application/pdf" });

    await uploadSource(session, "report_pdf", file);
    await analyzeSourceSession(session);
    await deleteSourceSession(session);

    expect(fetchMock.mock.calls[0][1].headers).toEqual({
      "X-Proofline-CSRF": "csrf-memory-only",
    });
    expect(fetchMock.mock.calls[0][1].body.get("role")).toBe("report_pdf");
    expect(fetchMock.mock.calls[1]).toEqual([
      "/api/sessions/src-opaque/analysis",
      expect.objectContaining({ method: "POST", headers: { "X-Proofline-CSRF": "csrf-memory-only" } }),
    ]);
    expect(fetchMock.mock.calls[2][1]).toEqual(
      expect.objectContaining({
        method: "DELETE",
        credentials: "same-origin",
        headers: { "X-Proofline-CSRF": "csrf-memory-only" },
      }),
    );
  });

  it("uses the verified user token for owner-scoped session RPC, upload, and analysis", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ session_id: "session-uuid" }) }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const auth = {
      requireAuthenticatedOwner: vi.fn().mockResolvedValue({
        ownerId: "10000000-0000-4000-8000-000000000001",
        accessToken: "verified.user.access-token",
      }),
    };
    const session = { session_id: "11000000-0000-4000-8000-000000000001" };
    const file = new File(["%PDF"], "report.pdf", { type: "application/pdf" });

    await createAuthenticatedSourceSession(auth);
    await uploadAuthenticatedSource(auth, session, "report_pdf", file);
    await analyzeAuthenticatedSourceSession(auth, session);

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "/api/authenticated/sessions",
      "/api/authenticated/sessions/11000000-0000-4000-8000-000000000001/files",
      "/api/authenticated/sessions/11000000-0000-4000-8000-000000000001/analysis",
    ]);
    for (const [, options] of fetchMock.mock.calls) {
      expect(options.credentials).toBe("omit");
      expect(options.headers.Authorization).toBe("Bearer verified.user.access-token");
      expect(JSON.stringify(options.headers)).not.toMatch(/secret|service.role|gemini/i);
    }
  });

  it("keeps public demo selection explicit and surfaces stable safe errors", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ verified_cached_output: true }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ reason_code: "MACROS_NOT_ALLOWED" }),
      });
    vi.stubGlobal("fetch", fetchMock);

    await loadPublicDemo("apple-fy2025");
    await expect(loadPublicDemo("bad-input")).rejects.toMatchObject({
      reasonCode: "MACROS_NOT_ALLOWED",
      message: "Macro-enabled workbooks are not accepted.",
    });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/public-demo/apple-fy2025");
  });

  it("provides encoded status, list, preview, and download seams", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ files: [] }) }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const session = { session_id: "src-safe/segment" };

    await getSourceSession(session);
    await listSourceFiles(session);

    expect(fetchMock.mock.calls[0][0]).toBe("/api/sessions/src-safe%2Fsegment");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/sessions/src-safe%2Fsegment/files");
    expect(sourceContentUrl(session, "file/a", "inline")).toBe(
      "/api/sessions/src-safe%2Fsegment/files/file%2Fa/content?disposition=inline",
    );
    expect(() => sourceContentUrl(session, "file", "unsafe")).toThrow("Invalid disposition");
  });
});
