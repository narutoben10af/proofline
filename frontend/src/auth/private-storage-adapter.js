import { AUTH_REASON, AuthBoundaryError } from "./auth-contract";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const BUCKET = "proofline-source-library";
const MAX_BYTES = Object.freeze({
  "application/pdf": 20 * 1024 * 1024,
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": 10 * 1024 * 1024,
});

function objectPath(ownerId, sessionId, documentId) {
  if (![ownerId, sessionId, documentId].every((value) => UUID.test(value || ""))) {
    throw new AuthBoundaryError(AUTH_REASON.AUTH_REQUIRED);
  }
  return `${ownerId}/${sessionId}/${documentId}`;
}

export class AuthenticatedPrivateStorageAdapter {
  constructor(client, auth) {
    this.client = client;
    this.auth = auth;
  }

  async upload({ sessionId, documentId, body, contentType }) {
    const { ownerId } = await this.auth.requireAuthenticatedOwner();
    const path = objectPath(ownerId, sessionId, documentId);
    if (
      !(body instanceof Blob) ||
      !MAX_BYTES[contentType] ||
      body.type !== contentType ||
      body.size > MAX_BYTES[contentType]
    ) {
      throw new AuthBoundaryError("PRIVATE_STORAGE_INPUT_INVALID");
    }
    const { data, error } = await this.client.storage.from(BUCKET).upload(path, body, {
      contentType,
      upsert: false,
    });
    if (error) throw new AuthBoundaryError("PRIVATE_STORAGE_UPLOAD_FAILED");
    return data;
  }

  async download({ sessionId, documentId }) {
    const { ownerId } = await this.auth.requireAuthenticatedOwner();
    const { data, error } = await this.client.storage
      .from(BUCKET)
      .download(objectPath(ownerId, sessionId, documentId));
    if (error) throw new AuthBoundaryError("PRIVATE_STORAGE_DOWNLOAD_FAILED");
    return data;
  }

  async remove({ sessionId, documentId }) {
    const { ownerId } = await this.auth.requireAuthenticatedOwner();
    const path = objectPath(ownerId, sessionId, documentId);
    const { data, error } = await this.client.storage.from(BUCKET).remove([path]);
    if (error) throw new AuthBoundaryError("PRIVATE_STORAGE_DELETE_FAILED");
    return data;
  }
}
