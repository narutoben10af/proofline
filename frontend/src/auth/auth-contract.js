export const AUTH_STATUS = Object.freeze({
  LOADING: "loading",
  ERROR: "error",
  CANCELLED: "cancelled",
  UNAUTHENTICATED: "unauthenticated",
  AUTHENTICATED: "authenticated",
});

export const AUTH_REASON = Object.freeze({
  AUTH_CANCELLED: "AUTH_CANCELLED",
  AUTH_CALLBACK_INVALID: "AUTH_CALLBACK_INVALID",
  AUTH_CONFIGURATION_INVALID: "AUTH_CONFIGURATION_INVALID",
  AUTH_EXCHANGE_FAILED: "AUTH_EXCHANGE_FAILED",
  AUTH_REQUIRED: "AUTH_REQUIRED",
  AUTH_SESSION_INVALID: "AUTH_SESSION_INVALID",
  AUTH_SIGN_OUT_FAILED: "AUTH_SIGN_OUT_FAILED",
  AUTH_START_FAILED: "AUTH_START_FAILED",
  GOOGLE_SIGN_IN_NOT_CONFIGURED: "GOOGLE_SIGN_IN_NOT_CONFIGURED",
});

/**
 * @typedef {{status: "loading"} |
 * {status: "error", reasonCode: string} |
 * {status: "cancelled", reasonCode: "AUTH_CANCELLED"} |
 * {status: "unauthenticated", configured: boolean, reasonCode?: string} |
 * {status: "authenticated", ownerId: string, email?: string, displayName?: string}} AuthState
 */

export class AuthBoundaryError extends Error {
  constructor(reasonCode) {
    super(reasonCode);
    this.name = "AuthBoundaryError";
    this.reasonCode = reasonCode;
  }
}

export function unauthenticatedState(configured = true, reasonCode) {
  return {
    status: AUTH_STATUS.UNAUTHENTICATED,
    configured,
    ...(reasonCode ? { reasonCode } : {}),
  };
}

export function errorState(reasonCode) {
  return { status: AUTH_STATUS.ERROR, reasonCode };
}
