import { AUTH_REASON, AuthBoundaryError } from "./auth-contract";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const BUCKET = "proofline-source-library";
const ROLE_CONTENT_TYPES = Object.freeze({
  report_pdf: "application/pdf",
  workbook: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
});
const MAX_BYTES = Object.freeze({
  "application/pdf": 20 * 1024 * 1024,
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": 10 * 1024 * 1024,
});

function rpcRow(data) {
  if (Array.isArray(data)) return data.length === 1 ? data[0] : null;
  return data && typeof data === "object" ? data : null;
}

function assertUuid(value, reasonCode = AUTH_REASON.AUTH_REQUIRED) {
  if (!UUID.test(value || "")) throw new AuthBoundaryError(reasonCode);
  return value;
}

function newDocumentId() {
  const randomUUID = globalThis.crypto?.randomUUID;
  if (typeof randomUUID !== "function") {
    throw new AuthBoundaryError("PRIVATE_STORAGE_ID_UNAVAILABLE");
  }
  return randomUUID.call(globalThis.crypto);
}

async function bodyBytes(body) {
  if (typeof body.arrayBuffer === "function") return body.arrayBuffer();
  if (typeof FileReader === "undefined") throw new AuthBoundaryError("PRIVATE_STORAGE_HASH_UNAVAILABLE");
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new AuthBoundaryError("PRIVATE_STORAGE_HASH_UNAVAILABLE"));
    reader.onload = () => resolve(reader.result);
    reader.readAsArrayBuffer(body);
  });
}

async function sha256(body) {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle || typeof subtle.digest !== "function") {
    throw new AuthBoundaryError("PRIVATE_STORAGE_HASH_UNAVAILABLE");
  }
  const digest = await subtle.digest("SHA-256", await bodyBytes(body));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

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

  async createSession() {
    const { ownerId } = await this.auth.requireAuthenticatedOwner();
    assertUuid(ownerId);
    const { data, error } = await this.client.rpc("create_analysis_session", {});
    const row = rpcRow(data);
    if (error || !row || row.owner_id !== ownerId || !UUID.test(row.id || "") || row.state !== "OPEN") {
      throw new AuthBoundaryError("PRIVATE_STORAGE_SESSION_FAILED");
    }
    return {
      backend: "supabase",
      session_id: row.id,
      owner_id: ownerId,
      state: row.state,
      idle_expires_at: row.idle_expires_at,
      absolute_expires_at: row.absolute_expires_at,
    };
  }

  async uploadSource({ sessionId, role, file }) {
    const { ownerId } = await this.auth.requireAuthenticatedOwner();
    assertUuid(ownerId);
    assertUuid(sessionId);
    const contentType = ROLE_CONTENT_TYPES[role];
    const displayName = typeof file?.name === "string" ? file.name.trim().slice(0, 255) : "";
    if (
      !(file instanceof Blob) ||
      !contentType ||
      !displayName ||
      file.size < 1 ||
      !Number.isSafeInteger(file.size) ||
      !MAX_BYTES[contentType] ||
      file.size > MAX_BYTES[contentType] ||
      file.type !== contentType
    ) {
      throw new AuthBoundaryError("PRIVATE_STORAGE_INPUT_INVALID");
    }
    const documentId = newDocumentId();
    const contentSha256 = await sha256(file);
    const { data, error } = await this.client.rpc("register_source_document", {
      target_session_id: sessionId,
      target_document_id: documentId,
      document_role: role,
      document_display_name: displayName,
      document_canonical_type: contentType,
      document_byte_count: file.size,
      document_content_sha256: contentSha256,
    });
    const row = rpcRow(data);
    const path = `${ownerId}/${sessionId}/${documentId}`;
    if (
      error ||
      !row ||
      row.id !== documentId ||
      row.session_id !== sessionId ||
      row.owner_id !== ownerId ||
      row.storage_object_path !== path ||
      row.validation_status !== "Checking"
    ) {
      throw new AuthBoundaryError("PRIVATE_STORAGE_REGISTER_FAILED");
    }
    await this.upload({ sessionId, documentId, body: file, contentType });
    return {
      document_id: documentId,
      session_id: sessionId,
      role,
      display_name: displayName,
      canonical_type: contentType,
      byte_count: file.size,
      storage_object_path: path,
      validation_status: "Checking",
    };
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
