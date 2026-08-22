import { AUTH_REASON } from "./auth-contract";

export const MAGICFIN_SUPABASE_PROJECT_REF = "qvxohnlboefomtjecxdh";
export const AUTH_CALLBACK_PATH = "/auth/callback";

const PROJECT_URL = `https://${MAGICFIN_SUPABASE_PROJECT_REF}.supabase.co`;
const PUBLISHABLE_KEY = /^sb_publishable_[A-Za-z0-9_-]{8,}$/;

export function safeReturnTo(value, fallback = "/") {
  if (
    typeof value !== "string" ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    value.includes("\\") ||
    /[\u0000-\u001f\u007f]/.test(value) ||
    value.startsWith(AUTH_CALLBACK_PATH)
  ) {
    return fallback;
  }
  return value;
}

export function callbackUrl(origin, returnTo = "/") {
  const url = new URL(AUTH_CALLBACK_PATH, origin);
  url.searchParams.set("return_to", safeReturnTo(returnTo));
  return url.toString();
}

export function readBrowserAuthConfig(env, origin) {
  const projectUrl = env.VITE_SUPABASE_URL?.trim() || "";
  const publishableKey = env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim() || "";

  if (!projectUrl && !publishableKey) {
    return {
      configured: false,
      reasonCode: AUTH_REASON.GOOGLE_SIGN_IN_NOT_CONFIGURED,
    };
  }

  let parsedOrigin = "";
  try {
    const parsed = new URL(origin);
    const localDevelopment =
      parsed.protocol === "http:" && ["localhost", "127.0.0.1"].includes(parsed.hostname);
    if (parsed.protocol === "https:" || localDevelopment) parsedOrigin = parsed.origin;
  } catch {
    // Invalid origins are represented by the stable configuration error below.
  }

  if (projectUrl !== PROJECT_URL || !PUBLISHABLE_KEY.test(publishableKey) || !parsedOrigin) {
    return {
      configured: false,
      reasonCode: AUTH_REASON.AUTH_CONFIGURATION_INVALID,
    };
  }

  return {
    configured: true,
    projectUrl,
    publishableKey,
    origin: parsedOrigin,
    callbackPath: AUTH_CALLBACK_PATH,
  };
}
