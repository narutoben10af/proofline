import { parseRequest, VERIFIED_DEMO_SESSION_ID } from "./contracts.ts";
import type { ChartProposal, MagicAssistantRequest, NormalizedEvidence } from "./contracts.ts";
import {
  AuthenticationError,
  EvidenceNotFoundError,
  loadOwnedEvidence,
  NotConfiguredError,
  readSupabaseConfig,
  requireSupabaseUser,
} from "./evidence.ts";
import {
  proposeChart,
  ProviderResponseError,
  ProviderUnavailableError,
  SUPPORTED_MODELS,
} from "./provider.ts";
import type { FetchLike, ProviderConfig } from "./provider.ts";

const MAX_HTTP_BODY_BYTES = 8_192;
// Keep this synchronized with the browser headers sent by supabase-js. Without
// x-client-info the browser accepts the OPTIONS response but blocks the POST.
const CORS_ALLOW_HEADERS = "authorization, x-client-info, apikey, content-type";
const NO_SEND_DISCLOSURE = "No evidence or question was sent to Google Gemma 4.";
const SENT_DISCLOSURE =
  "Only the bounded question and RLS-authorized evidence metadata were sent to Google Gemma 4.";

type Environment = Record<string, string | undefined>;

export interface HandlerDependencies {
  authenticate: (request: Request) => Promise<{ token: string; userId: string }>;
  loadEvidence: (
    request: MagicAssistantRequest,
    token: string,
    userId: string,
  ) => Promise<NormalizedEvidence[]>;
  propose: (
    request: MagicAssistantRequest,
    evidence: NormalizedEvidence[],
    config: ProviderConfig,
  ) => Promise<ChartProposal>;
  env: Environment;
}

function jsonResponse(
  payload: Record<string, unknown>,
  status: number,
  origin: string | null,
): Response {
  const headers = new Headers({
    "cache-control": "no-store, private",
    "content-type": "application/json; charset=utf-8",
    "x-content-type-options": "nosniff",
  });
  if (origin) {
    headers.set("access-control-allow-origin", origin);
    headers.set("vary", "Origin");
  }
  return new Response(JSON.stringify(payload), { status, headers });
}

function allowedOrigin(request: Request, env: Environment): string | null {
  const origin = request.headers.get("origin");
  if (!origin) return null;
  const allowed = new Set(
    (env.MAGIC_ASSISTANT_ALLOWED_ORIGINS ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  if (!allowed.has(origin)) throw new AuthenticationError("origin is not allowlisted");
  return origin;
}

async function boundedJson(request: Request): Promise<unknown> {
  const contentLength = request.headers.get("content-length");
  if (contentLength !== null && Number(contentLength) > MAX_HTTP_BODY_BYTES) {
    throw new Error("request body is too large");
  }
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
    throw new Error("content type must be application/json");
  }
  if (!request.body) throw new Error("request body is required");
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.length;
    if (length > MAX_HTTP_BODY_BYTES) {
      await reader.cancel();
      throw new Error("request body is too large");
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  return JSON.parse(new TextDecoder().decode(bytes));
}

function providerConfig(env: Environment): ProviderConfig {
  const apiKey = env.GEMINI_API_KEY?.trim() || env.GOOGLE_API_KEY?.trim();
  if (!apiKey) throw new NotConfiguredError("Gemma provider is not configured");
  const model = env.GEMMA_MODEL?.trim() || "gemma-4-26b-a4b-it";
  if (!(SUPPORTED_MODELS as readonly string[]).includes(model)) {
    throw new NotConfiguredError("Gemma model is not allowlisted");
  }
  return { apiKey, model };
}

export function createHandler(dependencies: HandlerDependencies) {
  return async (request: Request): Promise<Response> => {
    let origin: string | null = null;
    let providerSent = false;
    try {
      origin = allowedOrigin(request, dependencies.env);
      if (request.method === "OPTIONS") {
        if (!origin) throw new AuthenticationError("origin is required for preflight");
        return new Response(null, {
          status: 204,
          headers: {
            "access-control-allow-origin": origin,
            "access-control-allow-headers": CORS_ALLOW_HEADERS,
            "access-control-allow-methods": "POST, OPTIONS",
            "access-control-max-age": "600",
            vary: "Origin",
          },
        });
      }
      if (request.method !== "POST") {
        return jsonResponse(
          {
            state: "error",
            code: "method_not_allowed",
            retryable: false,
            disclosure: NO_SEND_DISCLOSURE,
          },
          405,
          origin,
        );
      }
      const declaredLength = Number(request.headers.get("content-length") ?? "0");
      if (Number.isFinite(declaredLength) && declaredLength > MAX_HTTP_BODY_BYTES) {
        throw new Error("request body is too large");
      }
      const { token, userId } = await dependencies.authenticate(request);
      const parsed = parseRequest(await boundedJson(request));
      const config = providerConfig(dependencies.env);
      const evidence = await dependencies.loadEvidence(parsed, token, userId);
      providerSent = true;
      const proposal = await dependencies.propose(parsed, evidence, config);
      return jsonResponse(
        {
          state: "completed",
          data_mode: parsed.session_id === VERIFIED_DEMO_SESSION_ID
            ? "verified_demo"
            : "live_evidence",
          proposal,
          authoritative_values: "frontend_resolves_from_rls_evidence",
          disclosure: SENT_DISCLOSURE,
        },
        200,
        origin,
      );
    } catch (error) {
      if (error instanceof AuthenticationError) {
        return jsonResponse(
          {
            state: "error",
            code: "unauthorized",
            retryable: false,
            disclosure: NO_SEND_DISCLOSURE,
          },
          401,
          origin,
        );
      }
      if (error instanceof NotConfiguredError) {
        return jsonResponse(
          {
            state: "not_configured",
            code: "not_configured",
            retryable: false,
            disclosure: NO_SEND_DISCLOSURE,
          },
          503,
          origin,
        );
      }
      if (error instanceof EvidenceNotFoundError) {
        return jsonResponse(
          {
            state: "error",
            code: "evidence_not_found",
            retryable: false,
            disclosure: NO_SEND_DISCLOSURE,
          },
          404,
          origin,
        );
      }
      if (error instanceof ProviderUnavailableError) {
        console.error(JSON.stringify({
          event: "magic_assistant_provider_unavailable",
          status: error.statusCode,
          reason: error.diagnostic?.reason ?? "temporarily_unavailable",
          provider_status: error.diagnostic?.providerStatus ?? null,
          quota_id: error.diagnostic?.quotaId ?? null,
          model: error.diagnostic?.model ?? null,
        }));
        const quotaReason = error.diagnostic?.reason;
        const code = error.statusCode === 429 &&
            quotaReason !== "quota_rejected" &&
            quotaReason !== "temporarily_unavailable"
          ? "provider_rate_limited"
          : "provider_temporarily_unavailable";
        return jsonResponse(
          {
            state: "offline",
            code,
            retryable: true,
            disclosure: SENT_DISCLOSURE,
          },
          503,
          origin,
        );
      }
      if (error instanceof ProviderResponseError) {
        console.error(JSON.stringify({
          event: "magic_assistant_provider_rejected_response",
          status: error.statusCode,
        }));
        return jsonResponse(
          {
            state: "error",
            code: "invalid_provider_response",
            retryable: false,
            disclosure: SENT_DISCLOSURE,
          },
          502,
          origin,
        );
      }
      return jsonResponse(
        {
          state: "error",
          code: "invalid_request",
          retryable: false,
          disclosure: providerSent ? SENT_DISCLOSURE : NO_SEND_DISCLOSURE,
        },
        400,
        origin,
      );
    }
  };
}

export function productionHandler(env: Environment, fetcher: FetchLike = fetch) {
  const supabase = readSupabaseConfig(env);
  return createHandler({
    env,
    authenticate: (request) => requireSupabaseUser(request, supabase, fetcher),
    loadEvidence: (request, token) => loadOwnedEvidence(request, token, supabase, fetcher),
    propose: (request, evidence, config) => proposeChart(request, evidence, config, fetcher),
  });
}
