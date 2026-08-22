import {
  type MagicAssistantRequest,
  type NormalizedEvidence,
  parseAndResolveProposal,
  parseEvidenceRows,
  parseRequest,
  VERIFIED_DEMO_SESSION_ID,
  VERIFIED_DEMO_SOURCE_ID,
} from "./contracts.ts";
import {
  AuthenticationError,
  loadOwnedEvidence,
  NotConfiguredError,
  requireSupabaseUser,
} from "./evidence.ts";
import { createHandler } from "./handler.ts";
import {
  GOOGLE_API_ORIGIN,
  MAX_PROVIDER_RETRIES,
  proposeChart,
  ProviderResponseError,
  SUPPORTED_MODELS,
} from "./provider.ts";

const SESSION = "src-A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6";
const SOURCE_A = "file-A1b2C3d4E5f6G7h8I9j0K1l2";
const SOURCE_B = "file-Z9y8X7w6V5u4T3s2R1q0P9o8";
const USER = "44444444-4444-4444-8444-444444444444";
const TOKEN = "header.payload.signature";

function assert(condition: unknown, message = "assertion failed"): asserts condition {
  if (!condition) throw new Error(message);
}

function assertEquals(actual: unknown, expected: unknown): void {
  const left = JSON.stringify(actual);
  const right = JSON.stringify(expected);
  if (left !== right) throw new Error(`expected ${right}, received ${left}`);
}

async function assertRejects(
  operation: () => unknown | Promise<unknown>,
  expected?: (error: unknown) => boolean,
): Promise<void> {
  try {
    await operation();
  } catch (error) {
    if (expected && !expected(error)) {
      throw new Error(`unexpected rejection type: ${String(error)}`);
    }
    return;
  }
  throw new Error("expected operation to reject");
}

function requestPayload(): MagicAssistantRequest {
  return {
    schema_version: "1.0.0",
    question: "Show the revenue trend",
    session_id: SESSION,
    source_ids: [SOURCE_A, SOURCE_B],
  };
}

function evidenceRows(changes: Partial<NormalizedEvidence> = {}): NormalizedEvidence[] {
  return [
    {
      session_id: SESSION,
      source_id: SOURCE_A,
      observation_id: "fact:11111111111111111111",
      issuer: "Example Group",
      concept: "revenue",
      period_start: "2024-01-01",
      period_end: "2024-12-31",
      duration_weeks: 52,
      unit: "USD millions",
      currency: "USD",
      ...changes,
    },
    {
      session_id: SESSION,
      source_id: SOURCE_B,
      observation_id: "fact:22222222222222222222",
      issuer: "Example Group",
      concept: "revenue",
      period_start: "2025-01-01",
      period_end: "2025-12-31",
      duration_weeks: 52,
      unit: "USD millions",
      currency: "USD",
    },
  ];
}

function chartPayload(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema_version: "1.0.0",
    chart_type: "line",
    period_start: "2024-01-01",
    period_end: "2025-12-31",
    series: [
      {
        observation_ids: ["fact:11111111111111111111", "fact:22222222222222222222"],
        source_ids: [SOURCE_A, SOURCE_B],
      },
    ],
    source_ids: [SOURCE_A, SOURCE_B],
    ...overrides,
  };
}

function wrappedProvider(payload: unknown): Response {
  return Response.json({
    candidates: [{ content: { parts: [{ text: JSON.stringify(payload) }] } }],
  });
}

Deno.test("request contract accepts only bounded question, session, and source IDs", async () => {
  assertEquals(parseRequest(requestPayload()), requestPayload());
  await assertRejects(() =>
    parseRequest({ ...requestPayload(), file_url: "https://example.com/a.pdf" })
  );
  await assertRejects(() =>
    parseRequest({ ...requestPayload(), source_ids: Array(13).fill(SOURCE_A) })
  );
  await assertRejects(() => parseRequest({ ...requestPayload(), question: "x".repeat(1_001) }));
  await assertRejects(() =>
    parseRequest({ ...requestPayload(), session_id: "11111111-1111-4111-8111-111111111111" })
  );
  await assertRejects(() => parseRequest({ ...requestPayload(), source_ids: ["source-static"] }));
});

Deno.test("evidence contract enforces requested session and source scope", async () => {
  assertEquals(parseEvidenceRows(evidenceRows(), requestPayload()), evidenceRows());
  await assertRejects(() =>
    parseEvidenceRows(
      evidenceRows({ session_id: "src-a2345678901234567890" }),
      requestPayload(),
    )
  );
  await assertRejects(() => parseEvidenceRows([evidenceRows()[0]], requestPayload()));
});

Deno.test("chart proposal returns IDs and citations without authoritative values", () => {
  const proposal = parseAndResolveProposal(chartPayload(), evidenceRows());
  assertEquals(proposal.series[0].observation_ids, [
    "fact:11111111111111111111",
    "fact:22222222222222222222",
  ]);
  assertEquals(proposal.source_ids, [SOURCE_A, SOURCE_B]);
  assertEquals(proposal.title, "Verified financial trend");
  assertEquals(proposal.description, "Values resolve from cited normalized evidence.");
  assertEquals(proposal.series[0].label, "Revenue");
  assert(!JSON.stringify(proposal).includes("numeric_value"));
  assert(!JSON.stringify(proposal).includes('"values"'));
});

Deno.test("chart proposal rejects invented IDs, model values, unsafe content, and excess series", async () => {
  await assertRejects(() =>
    parseAndResolveProposal(
      chartPayload({
        series: [{ observation_ids: ["invented"], source_ids: [SOURCE_A] }],
      }),
      evidenceRows(),
    )
  );
  await assertRejects(() =>
    parseAndResolveProposal(chartPayload({ values: [1, 2] }), evidenceRows())
  );
  await assertRejects(() =>
    parseAndResolveProposal(
      chartPayload({
        series: Array.from({ length: 5 }, () => ({
          observation_ids: ["fact:11111111111111111111"],
          source_ids: [SOURCE_A],
        })),
      }),
      evidenceRows(),
    )
  );
});

Deno.test("chart proposal rejects all model-authored display text", async () => {
  await assertRejects(() =>
    parseAndResolveProposal(
      chartPayload({ title: "Revenue was 123.45 million" }),
      evidenceRows(),
    )
  );
  await assertRejects(() =>
    parseAndResolveProposal(
      chartPayload({ description: "Open https://attacker.example/report.pdf" }),
      evidenceRows(),
    )
  );
  await assertRejects(() =>
    parseAndResolveProposal(
      chartPayload({
        series: [{
          label: "Compute revenue / shares outstanding",
          observation_ids: ["fact:11111111111111111111", "fact:22222222222222222222"],
          source_ids: [SOURCE_A, SOURCE_B],
        }],
      }),
      evidenceRows(),
    )
  );
});

Deno.test("chart proposal rejects mixed issuer, unit, currency, and period basis", async () => {
  for (
    const changes of [
      { issuer: "Different Issuer" },
      { unit: "shares", currency: null },
      { currency: "EUR" },
      { duration_weeks: 53 },
    ]
  ) {
    const rows = evidenceRows();
    rows[0] = { ...rows[0], ...changes };
    await assertRejects(() => parseAndResolveProposal(chartPayload(), rows));
  }
});

Deno.test("auth validation requires bearer JWT and uses only publishable RLS credentials", async () => {
  let recorded: { url?: string; authorization?: string; apikey?: string } = {};
  const fetcher = (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    recorded = {
      url: String(input),
      authorization: new Headers(init?.headers).get("authorization") ?? undefined,
      apikey: new Headers(init?.headers).get("apikey") ?? undefined,
    };
    return Promise.resolve(Response.json({ id: USER }));
  };
  const request = new Request("https://function.example/magic-assistant", {
    headers: { authorization: `Bearer ${TOKEN}` },
  });
  const authenticated = await requireSupabaseUser(
    request,
    { url: "https://project.supabase.co", publishableKey: "publishable-test-key" },
    fetcher,
  );
  assertEquals(authenticated, { token: TOKEN, userId: USER });
  assertEquals(recorded.url, "https://project.supabase.co/auth/v1/user");
  assertEquals(recorded.authorization, `Bearer ${TOKEN}`);
  assertEquals(recorded.apikey, "publishable-test-key");
  await assertRejects(
    () =>
      requireSupabaseUser(
        new Request("https://function.example"),
        { url: "https://project.supabase.co", publishableKey: "publishable-test-key" },
        fetcher,
      ),
    (error) => error instanceof AuthenticationError,
  );
});

Deno.test("evidence loader is fixed to RLS relation and returns not-configured before migration", async () => {
  let requestedUrl = "";
  let authorization = "";
  const fetcher = (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    requestedUrl = String(input);
    authorization = new Headers(init?.headers).get("authorization") ?? "";
    return Promise.resolve(Response.json({ code: "PGRST205" }, { status: 404 }));
  };
  await assertRejects(
    () =>
      loadOwnedEvidence(
        requestPayload(),
        TOKEN,
        { url: "https://project.supabase.co", publishableKey: "publishable-test-key" },
        fetcher,
      ),
    (error) => error instanceof NotConfiguredError,
  );
  assert(requestedUrl.startsWith("https://project.supabase.co/rest/v1/magic_assistant_evidence?"));
  assert(requestedUrl.includes(encodeURIComponent(`eq.${SESSION}`)));
  assertEquals(authorization, `Bearer ${TOKEN}`);
  assert(!requestedUrl.includes("http://"));
});

Deno.test("Gemma call uses fixed endpoint, no redirects, structured schema, and metadata only", async () => {
  let recordedUrl = "";
  let recordedInit: RequestInit | undefined;
  const secret = "server-secret-sentinel";
  const fetcher = (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    recordedUrl = String(input);
    recordedInit = init;
    return Promise.resolve(wrappedProvider(chartPayload()));
  };
  const proposal = await proposeChart(
    requestPayload(),
    evidenceRows(),
    { apiKey: secret, model: "gemma-4-26b-a4b-it" },
    fetcher,
  );
  assertEquals(
    recordedUrl,
    `${GOOGLE_API_ORIGIN}/v1beta/models/gemma-4-26b-a4b-it:generateContent`,
  );
  assertEquals(recordedInit?.redirect, "error");
  assertEquals(new Headers(recordedInit?.headers).get("x-goog-api-key"), secret);
  const body = String(recordedInit?.body);
  assert(body.includes("responseJsonSchema"));
  assert(body.includes("Never return numeric values"));
  const providerRequest = JSON.parse(body);
  const schema = providerRequest.generationConfig.responseJsonSchema;
  assert(!("title" in schema.properties));
  assert(!("description" in schema.properties));
  assert(!("label" in schema.properties.series.items.properties));
  assert(!body.includes(secret));
  assert(!body.includes("numeric_value"));
  assert(!JSON.stringify(proposal).includes(secret));
});

Deno.test("Gemma failures are bounded and invented IDs are rejected locally", async () => {
  let transientCalls = 0;
  await assertRejects(async () => {
    await proposeChart(
      requestPayload(),
      evidenceRows(),
      { apiKey: "secret", model: "gemma-4-26b-a4b-it" },
      () => {
        transientCalls += 1;
        return Promise.resolve(new Response("unavailable", { status: 503 }));
      },
    );
  });
  assertEquals(transientCalls, (MAX_PROVIDER_RETRIES + 1) * SUPPORTED_MODELS.length);

  let malformedCalls = 0;
  await assertRejects(
    () =>
      proposeChart(
        requestPayload(),
        evidenceRows(),
        { apiKey: "secret", model: "gemma-4-26b-a4b-it" },
        () => {
          malformedCalls += 1;
          return Promise.resolve(wrappedProvider({ ...chartPayload(), values: [999] }));
        },
      ),
    (error) => error instanceof ProviderResponseError,
  );
  assertEquals(malformedCalls, 1);
});

Deno.test("handler requires auth, reports not-configured honestly, and returns cited IDs", async () => {
  const baseRequest = () =>
    new Request("https://function.example/magic-assistant", {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${TOKEN}` },
      body: JSON.stringify(requestPayload()),
    });
  const unauthenticated = createHandler({
    env: { GEMINI_API_KEY: "secret" },
    authenticate: () => Promise.reject(new AuthenticationError("bad token")),
    loadEvidence: () => Promise.resolve(evidenceRows()),
    propose: () => Promise.resolve(parseAndResolveProposal(chartPayload(), evidenceRows())),
  });
  const unauthorized = await unauthenticated(baseRequest());
  assertEquals(unauthorized.status, 401);
  assertEquals((await unauthorized.json()).code, "unauthorized");

  const notConfigured = createHandler({
    env: {},
    authenticate: () => Promise.resolve({ token: TOKEN, userId: USER }),
    loadEvidence: () => Promise.resolve(evidenceRows()),
    propose: () => Promise.resolve(parseAndResolveProposal(chartPayload(), evidenceRows())),
  });
  const unavailable = await notConfigured(baseRequest());
  assertEquals(unavailable.status, 503);
  assertEquals((await unavailable.json()).state, "not_configured");

  const completed = createHandler({
    env: { GEMINI_API_KEY: "secret", GEMMA_MODEL: "gemma-4-26b-a4b-it" },
    authenticate: () => Promise.resolve({ token: TOKEN, userId: USER }),
    loadEvidence: () => Promise.resolve(evidenceRows()),
    propose: () => Promise.resolve(parseAndResolveProposal(chartPayload(), evidenceRows())),
  });
  const response = await completed(baseRequest());
  const payload = await response.json();
  assertEquals(response.status, 200);
  assertEquals(payload.authoritative_values, "frontend_resolves_from_rls_evidence");
  assertEquals(payload.data_mode, "live_evidence");
  assertEquals(payload.proposal.source_ids, [SOURCE_A, SOURCE_B]);
  assert(!JSON.stringify(payload).includes('"values"'));
});

Deno.test("handler labels the stable owner-scoped bootstrap context as verified demo", async () => {
  const demoRequest = {
    ...requestPayload(),
    session_id: VERIFIED_DEMO_SESSION_ID,
    source_ids: [VERIFIED_DEMO_SOURCE_ID],
  };
  const demoEvidence = evidenceRows().slice(0, 1).map((row) => ({
    ...row,
    session_id: VERIFIED_DEMO_SESSION_ID,
    source_id: VERIFIED_DEMO_SOURCE_ID,
  }));
  const handler = createHandler({
    env: { GEMINI_API_KEY: "secret", GEMMA_MODEL: "gemma-4-26b-a4b-it" },
    authenticate: () => Promise.resolve({ token: TOKEN, userId: USER }),
    loadEvidence: () => Promise.resolve(demoEvidence),
    propose: () =>
      Promise.resolve(
        parseAndResolveProposal({
          ...chartPayload(),
          period_start: "2024-01-01",
          period_end: "2024-12-31",
          series: [{
            observation_ids: [demoEvidence[0].observation_id],
            source_ids: [VERIFIED_DEMO_SOURCE_ID],
          }],
          source_ids: [VERIFIED_DEMO_SOURCE_ID],
        }, demoEvidence),
      ),
  });
  const response = await handler(
    new Request("https://function.example/magic-assistant", {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${TOKEN}` },
      body: JSON.stringify(demoRequest),
    }),
  );
  const payload = await response.json();
  assertEquals(response.status, 200);
  assertEquals(payload.data_mode, "verified_demo");
  assert(!JSON.stringify(payload).includes("numeric_value"));
});

Deno.test("browser preflight allows every header emitted by supabase-js", async () => {
  const origin = "https://magicfin.narutoxkillua.chatgpt.site";
  const handler = createHandler({
    env: { MAGIC_ASSISTANT_ALLOWED_ORIGINS: origin },
    authenticate: () => Promise.reject(new Error("preflight must not authenticate")),
    loadEvidence: () => Promise.reject(new Error("preflight must not load evidence")),
    propose: () => Promise.reject(new Error("preflight must not call the provider")),
  });
  const response = await handler(
    new Request("https://function.example/magic-assistant", {
      method: "OPTIONS",
      headers: {
        origin,
        "access-control-request-method": "POST",
        "access-control-request-headers": "apikey,authorization,content-type,x-client-info",
      },
    }),
  );
  const allowed = new Set(
    (response.headers.get("access-control-allow-headers") ?? "")
      .split(",")
      .map((header) => header.trim().toLowerCase()),
  );
  assertEquals(response.status, 204);
  assertEquals(response.headers.get("access-control-allow-origin"), origin);
  for (const header of ["apikey", "authorization", "content-type", "x-client-info"]) {
    assert(allowed.has(header), `preflight omitted ${header}`);
  }
});
