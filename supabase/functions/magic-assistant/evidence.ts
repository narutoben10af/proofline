import type { MagicAssistantRequest, NormalizedEvidence } from "./contracts.ts";
import { parseEvidenceRows } from "./contracts.ts";
import type { FetchLike } from "./provider.ts";

const EVIDENCE_RELATION = "magic_assistant_evidence";
const EVIDENCE_SELECT = [
  "session_id",
  "source_id",
  "observation_id",
  "issuer",
  "concept",
  "period_start",
  "period_end",
  "duration_weeks",
  "unit",
  "currency",
].join(",");

export class NotConfiguredError extends Error {}
export class AuthenticationError extends Error {}
export class EvidenceNotFoundError extends Error {}

export interface SupabaseConfig {
  url: string;
  publishableKey: string;
}

function bearerToken(request: Request): string {
  const authorization = request.headers.get("authorization") ?? "";
  const match = /^Bearer ([A-Za-z0-9._~-]+)$/.exec(authorization);
  if (!match || match[1].length > 4_096) throw new AuthenticationError("valid user JWT required");
  return match[1];
}

function projectUrl(value: string): URL {
  const url = new URL(value);
  if (url.protocol !== "https:" && url.hostname !== "127.0.0.1" && url.hostname !== "localhost") {
    throw new NotConfiguredError("Supabase URL must use HTTPS");
  }
  url.pathname = "/";
  url.search = "";
  url.hash = "";
  return url;
}

function scopedHeaders(token: string, key: string): HeadersInit {
  return {
    accept: "application/json",
    apikey: key,
    authorization: `Bearer ${token}`,
  };
}

export async function requireSupabaseUser(
  request: Request,
  config: SupabaseConfig,
  fetcher: FetchLike = fetch,
): Promise<{ token: string; userId: string }> {
  const token = bearerToken(request);
  const base = projectUrl(config.url);
  const endpoint = new URL("auth/v1/user", base);
  const response = await fetcher(endpoint, {
    method: "GET",
    redirect: "error",
    headers: scopedHeaders(token, config.publishableKey),
  });
  if (!response.ok) throw new AuthenticationError("valid user JWT required");
  const payload = await response.json() as { id?: unknown };
  if (
    typeof payload.id !== "string" ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      payload.id,
    )
  ) {
    throw new AuthenticationError("valid user JWT required");
  }
  return { token, userId: payload.id };
}

export async function loadOwnedEvidence(
  request: MagicAssistantRequest,
  token: string,
  config: SupabaseConfig,
  fetcher: FetchLike = fetch,
): Promise<NormalizedEvidence[]> {
  const base = projectUrl(config.url);
  const endpoint = new URL(`rest/v1/${EVIDENCE_RELATION}`, base);
  endpoint.searchParams.set("select", EVIDENCE_SELECT);
  endpoint.searchParams.set("session_id", `eq.${request.session_id}`);
  endpoint.searchParams.set("source_id", `in.(${request.source_ids.join(",")})`);
  endpoint.searchParams.set("limit", "25");
  const response = await fetcher(endpoint, {
    method: "GET",
    redirect: "error",
    headers: scopedHeaders(token, config.publishableKey),
  });
  if (!response.ok) {
    const code = response.headers.get("content-type")?.includes("application/json")
      ? ((await response.json()) as { code?: unknown }).code
      : undefined;
    if (response.status === 404 || code === "PGRST205" || code === "42P01") {
      throw new NotConfiguredError("normalized evidence relation is not configured");
    }
    throw new EvidenceNotFoundError("authorized evidence could not be loaded");
  }
  const payload = await response.json() as unknown;
  if (Array.isArray(payload) && payload.length === 0) {
    throw new EvidenceNotFoundError("authorized evidence was not found");
  }
  return parseEvidenceRows(payload, request);
}

export function readSupabaseConfig(env: Record<string, string | undefined>): SupabaseConfig {
  const url = env.SUPABASE_URL?.trim();
  let publishableKey = env.SUPABASE_PUBLISHABLE_KEY?.trim() || env.SUPABASE_ANON_KEY?.trim();
  if (!publishableKey && env.SUPABASE_PUBLISHABLE_KEYS) {
    try {
      const keys = JSON.parse(env.SUPABASE_PUBLISHABLE_KEYS) as { default?: unknown };
      if (typeof keys.default === "string") publishableKey = keys.default.trim();
    } catch {
      throw new NotConfiguredError("publishable key configuration is invalid");
    }
  }
  if (!url || !publishableKey) throw new NotConfiguredError("Supabase user auth is not configured");
  return { url, publishableKey };
}
