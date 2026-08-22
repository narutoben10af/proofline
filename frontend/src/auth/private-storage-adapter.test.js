import { describe, expect, it, vi } from "vitest";
import { AuthenticatedPrivateStorageAdapter } from "./private-storage-adapter";

const OWNER = "10000000-0000-4000-8000-000000000001";
const SESSION = "11000000-0000-4000-8000-000000000001";
const DOCUMENT = "13000000-0000-4000-8000-000000000001";
const PATH = `${OWNER}/${SESSION}/${DOCUMENT}`;

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
