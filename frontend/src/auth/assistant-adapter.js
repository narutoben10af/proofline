import { AUTH_REASON, AuthBoundaryError } from "./auth-contract";

const EDGE_FUNCTION = "magic-assistant";
const SESSION_ID = /^src-[A-Za-z0-9_-]{32}$/;
const SOURCE_ID = /^file-[A-Za-z0-9_-]{24}$/;
const MAX_QUESTION = 1_000;
const MAX_SOURCES = 12;

function validQuestion(value) {
  return typeof value === "string" && value.trim().length > 0 && value.length <= MAX_QUESTION && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(value);
}

function validRequest({ question, sessionId, sourceIds }) {
  return validQuestion(question) &&
    typeof sessionId === "string" &&
    SESSION_ID.test(sessionId) &&
    Array.isArray(sourceIds) &&
    sourceIds.length > 0 &&
    sourceIds.length <= MAX_SOURCES &&
    sourceIds.every((id) => typeof id === "string" && SOURCE_ID.test(id)) &&
    new Set(sourceIds).size === sourceIds.length;
}

export class SupabaseAssistantAdapter {
  constructor(client, auth) {
    this.client = client;
    this.auth = auth;
  }

  async request({ question, sessionId, sourceIds }) {
    await this.auth.requireAuthenticatedOwner();
    if (!validRequest({ question, sessionId, sourceIds })) {
      throw new AuthBoundaryError("ASSISTANT_REQUEST_INVALID");
    }
    let result;
    try {
      result = await this.client.functions.invoke(EDGE_FUNCTION, {
        body: {
          schema_version: "1.0.0",
          question: question.trim(),
          session_id: sessionId,
          source_ids: sourceIds,
        },
      });
    } catch {
      throw new AuthBoundaryError("ASSISTANT_REQUEST_FAILED");
    }
    if (result?.error) throw new AuthBoundaryError("ASSISTANT_REQUEST_FAILED");
    const state = result?.data?.state;
    if (!["completed", "not_configured", "offline", "error"].includes(state)) {
      throw new AuthBoundaryError("ASSISTANT_RESPONSE_INVALID");
    }
    return result.data;
  }
}

export const ASSISTANT_REASON = Object.freeze({
  ...AUTH_REASON,
  ASSISTANT_NOT_CONFIGURED: "ASSISTANT_NOT_CONFIGURED",
  ASSISTANT_OFFLINE: "ASSISTANT_OFFLINE",
  ASSISTANT_REQUEST_FAILED: "ASSISTANT_REQUEST_FAILED",
  ASSISTANT_REQUEST_INVALID: "ASSISTANT_REQUEST_INVALID",
  ASSISTANT_RESPONSE_INVALID: "ASSISTANT_RESPONSE_INVALID",
});
