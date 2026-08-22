const SAFE_ERRORS = {
  ARCHIVE_ENTRY_LIMIT: "The workbook contains too many internal files.",
  ARCHIVE_PATH_SUSPICIOUS: "The workbook contains an unsafe internal path.",
  CSRF_TOKEN_INVALID: "This review could not be verified. Refresh and try again.",
  DECLARED_MIME_MISMATCH: "The selected file type does not match its contents.",
  EXTERNAL_LINKS_NOT_ALLOWED: "Workbooks with external links are not accepted.",
  FILE_EXTENSION_NOT_ALLOWED: "Choose a PDF for the report and an XLSX workbook for evidence.",
  FILE_TOO_LARGE: "The selected file is larger than this demo accepts.",
  MACROS_NOT_ALLOWED: "Macro-enabled workbooks are not accepted.",
  PASSWORD_PROTECTED_INPUT: "Password-protected or encrypted files are not accepted.",
  PDF_ACTIVE_CONTENT: "PDFs with active or embedded content are not accepted.",
  PROVIDER_ACCESS_REQUIRED: "Live review processing is unavailable here. Your files were not replaced with demo data.",
  REQUIRED_FILES_NOT_READY: "Both files must pass checking before review can start.",
  SESSION_GONE: "This temporary review has already been deleted or expired.",
  ZIP_BOMB_DETECTED: "The workbook expands beyond this demo’s safety limits.",
};

async function request(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(SAFE_ERRORS[body.reason_code] || "The request could not be completed safely.");
    error.reasonCode = body.reason_code || "REQUEST_FAILED";
    error.status = response.status;
    throw error;
  }
  return body;
}

export function createSourceSession() {
  return request("/api/sessions", { method: "POST" });
}

export function getSourceSession(session) {
  return request(`/api/sessions/${encodeURIComponent(session.session_id)}`);
}

export function listSourceFiles(session) {
  return request(`/api/sessions/${encodeURIComponent(session.session_id)}/files`);
}
export function sourceContentUrl(session, fileId, disposition = "attachment") {
  if (!["attachment", "inline"].includes(disposition)) throw new Error("Invalid disposition.");
  return `/api/sessions/${encodeURIComponent(session.session_id)}/files/${encodeURIComponent(fileId)}/content?disposition=${disposition}`;
}
export function uploadSource(session, role, file) {
  const body = new FormData();
  body.append("role", role);
  body.append("file", file);
  return request(`/api/sessions/${session.session_id}/files`, {
    method: "POST",
    headers: { "X-Proofline-CSRF": session.csrf_token },
    body,
  });
}

export function removeSource(session, fileId) {
  return request(`/api/sessions/${session.session_id}/files/${fileId}`, {
    method: "DELETE",
    headers: { "X-Proofline-CSRF": session.csrf_token },
  });
}

export function startSourceReview(session) {
  return request(`/api/sessions/${session.session_id}/start`, {
    method: "POST",
    headers: { "X-Proofline-CSRF": session.csrf_token },
  });
}

export function deleteSourceSession(session) {
  return request(`/api/sessions/${session.session_id}`, {
    method: "DELETE",
    headers: { "X-Proofline-CSRF": session.csrf_token },
  });
}

export function loadPublicDemo(fixtureId) {
  return request(`/api/public-demo/${fixtureId}`);
}
