import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthenticatedPrivateStorageAdapter } from "./private-storage-adapter";

const OWNER = "10000000-0000-4000-8000-000000000001";
const SESSION = "11000000-0000-4000-8000-000000000001";
const DOCUMENT = "13000000-0000-4000-8000-000000000001";
const PATH = `${OWNER}/${SESSION}/${DOCUMENT}`;

afterEach(() => vi.unstubAllGlobals());

function storageClient() {
  const bucket = {
    upload: vi.fn().mockResolvedValue({ data: { path: PATH }, error: null }),
    download: vi.fn().mockResolvedValue({ data: new Blob(["safe"]), error: null }),
    remove: vi.fn().mockResolvedValue({ data: [{ name: PATH }], error: null }),
  };
  return {
    bucket,
    client: { storage: { from: vi.fn().mockReturnValue(bucket) } },
  };
}

describe("authenticated private Storage adapter", () => {
  it("creates an owner-scoped session and registers bytes before private upload", async () => {
    const { client, bucket } = storageClient();
    const auth = { requireAuthenticatedOwner: vi.fn().mockResolvedValue({ ownerId: OWNER }) };
    const rpc = vi
      .fn()
      .mockResolvedValueOnce({
        data: { id: SESSION, owner_id: OWNER, state: "OPEN", idle_expires_at: "later", absolute_expires_at: "latest" },
        error: null,
      })
      .mockResolvedValueOnce({
        data: {
          id: DOCUMENT,
          session_id: SESSION,
          owner_id: OWNER,
          storage_object_path: PATH,
          validation_status: "Checking",
        },
        error: null,
      });
    client.rpc = rpc;
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn(() => DOCUMENT),
      subtle: { digest: vi.fn().mockResolvedValue(new Uint8Array([0xab, 0xcd]).buffer) },
    });
    const storage = new AuthenticatedPrivateStorageAdapter(client, auth);

    await expect(storage.createSession()).resolves.toMatchObject({
      backend: "supabase",
      session_id: SESSION,
      owner_id: OWNER,
      state: "OPEN",
    });
    await expect(
      storage.uploadSource({
        sessionId: SESSION,
        role: "report_pdf",
        file: new File(["%PDF"], "report.pdf", { type: "application/pdf" }),
      }),
    ).resolves.toMatchObject({ document_id: DOCUMENT, validation_status: "Checking" });

    expect(rpc).toHaveBeenNthCalledWith(1, "create_analysis_session", {});
    expect(rpc).toHaveBeenNthCalledWith(2, "register_source_document", expect.objectContaining({
      target_session_id: SESSION,
      target_document_id: DOCUMENT,
      document_role: "report_pdf",
      document_canonical_type: "application/pdf",
      document_content_sha256: "abcd",
    }));
    expect(bucket.upload).toHaveBeenCalledWith(PATH, expect.any(Blob), expect.objectContaining({ upsert: false }));
  });

  it("fails closed when the RPC returns a path outside the verified owner scope", async () => {
    const { client, bucket } = storageClient();
    const auth = { requireAuthenticatedOwner: vi.fn().mockResolvedValue({ ownerId: OWNER }) };
    client.rpc = vi.fn().mockResolvedValue({
      data: {
        id: DOCUMENT,
        session_id: SESSION,
        owner_id: OWNER,
        storage_object_path: `other-owner/${SESSION}/${DOCUMENT}`,
        validation_status: "Checking",
      },
      error: null,
    });
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn(() => DOCUMENT),
      subtle: { digest: vi.fn().mockResolvedValue(new Uint8Array([0xab]).buffer) },
    });
    const storage = new AuthenticatedPrivateStorageAdapter(client, auth);
    await expect(
      storage.uploadSource({
        sessionId: SESSION,
        role: "report_pdf",
        file: new File(["%PDF"], "report.pdf", { type: "application/pdf" }),
      }),
    ).rejects.toMatchObject({ reasonCode: "PRIVATE_STORAGE_REGISTER_FAILED" });
    expect(bucket.upload).not.toHaveBeenCalled();
  });

  it("requires verified ownership before every private operation", async () => {
    const { client, bucket } = storageClient();
    const auth = { requireAuthenticatedOwner: vi.fn().mockResolvedValue({ ownerId: OWNER }) };
    const storage = new AuthenticatedPrivateStorageAdapter(client, auth);

    await storage.upload({
      sessionId: SESSION,
      documentId: DOCUMENT,
      body: new Blob(["%PDF"], { type: "application/pdf" }),
      contentType: "application/pdf",
    });
    await storage.download({ sessionId: SESSION, documentId: DOCUMENT });
    await storage.remove({ sessionId: SESSION, documentId: DOCUMENT });

    expect(auth.requireAuthenticatedOwner).toHaveBeenCalledTimes(3);
    expect(client.storage.from).toHaveBeenCalledWith("proofline-source-library");
    expect(bucket.upload).toHaveBeenCalledWith(
      PATH,
      expect.any(Blob),
      expect.objectContaining({ upsert: false }),
    );
    expect(bucket.download).toHaveBeenCalledWith(PATH);
    expect(bucket.remove).toHaveBeenCalledWith([PATH]);
  });

  it("makes no Storage call when authentication is absent", async () => {
    const { client, bucket } = storageClient();
    const auth = {
      requireAuthenticatedOwner: vi
        .fn()
        .mockRejectedValue(Object.assign(new Error("AUTH_REQUIRED"), { reasonCode: "AUTH_REQUIRED" })),
    };
    const storage = new AuthenticatedPrivateStorageAdapter(client, auth);
    await expect(
      storage.download({ sessionId: SESSION, documentId: DOCUMENT }),
    ).rejects.toMatchObject({ reasonCode: "AUTH_REQUIRED" });
    expect(bucket.download).not.toHaveBeenCalled();
  });

  it("rejects non-UUID owner or object identifiers before Storage", async () => {
    const { client, bucket } = storageClient();
    const auth = { requireAuthenticatedOwner: vi.fn().mockResolvedValue({ ownerId: "not-an-owner" }) };
    const storage = new AuthenticatedPrivateStorageAdapter(client, auth);
    await expect(
      storage.remove({ sessionId: SESSION, documentId: DOCUMENT }),
    ).rejects.toMatchObject({ reasonCode: "AUTH_REQUIRED" });
    expect(bucket.remove).not.toHaveBeenCalled();
  });
});
