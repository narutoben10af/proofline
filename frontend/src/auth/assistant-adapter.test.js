import { describe, expect, it, vi } from "vitest";
import { SupabaseAssistantAdapter } from "./assistant-adapter";

const SESSION = "src-12345678901234567890123456789012";
const SOURCES = ["file-123456789012345678901234", "file-abcdefghijklmnopqrstuvwx"];

function client(result = { state: "not_configured", code: "not_configured" }) {
  return {
    functions: { invoke: vi.fn().mockResolvedValue({ data: result, error: null }) },
  };
}

describe("Supabase Magic Assistant handoff", () => {
  it("requires verified ownership and invokes the deployed function with bounded IDs", async () => {
    const sdk = client({ state: "not_configured", code: "not_configured" });
    const auth = { requireAuthenticatedOwner: vi.fn().mockResolvedValue({ ownerId: "owner" }) };
    const assistant = new SupabaseAssistantAdapter(sdk, auth);
    await expect(assistant.request({ question: "Summarize the cited trend", sessionId: SESSION, sourceIds: SOURCES })).resolves.toMatchObject({ state: "not_configured" });
    expect(auth.requireAuthenticatedOwner).toHaveBeenCalledOnce();
    expect(sdk.functions.invoke).toHaveBeenCalledWith("magic-assistant", {
      body: { schema_version: "1.0.0", question: "Summarize the cited trend", session_id: SESSION, source_ids: SOURCES },
    });
  });

  it("rejects fixture, UUID, duplicate, and oversized source identifiers before the network", async () => {
    const sdk = client({ state: "completed" });
    const auth = { requireAuthenticatedOwner: vi.fn().mockResolvedValue({ ownerId: "owner" }) };
    const assistant = new SupabaseAssistantAdapter(sdk, auth);
    for (const request of [
      { question: "valid", sessionId: "magicfin-demo", sourceIds: SOURCES },
      { question: "valid", sessionId: SESSION, sourceIds: ["annual-report"] },
      { question: "valid", sessionId: SESSION, sourceIds: [SOURCES[0], SOURCES[0]] },
      { question: "x".repeat(1001), sessionId: SESSION, sourceIds: SOURCES },
    ]) {
      await expect(assistant.request(request)).rejects.toMatchObject({ reasonCode: "ASSISTANT_REQUEST_INVALID" });
    }
    expect(sdk.functions.invoke).not.toHaveBeenCalled();
  });

  it("maps an unavailable function without exposing provider details", async () => {
    const sdk = client();
    sdk.functions.invoke.mockRejectedValue(new Error("secret provider detail"));
    const assistant = new SupabaseAssistantAdapter(sdk, { requireAuthenticatedOwner: vi.fn().mockResolvedValue({ ownerId: "owner" }) });
    await expect(assistant.request({ question: "valid", sessionId: SESSION, sourceIds: SOURCES })).rejects.toMatchObject({ reasonCode: "ASSISTANT_REQUEST_FAILED" });
  });
});
