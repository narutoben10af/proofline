import { describe, expect, it, vi } from "vitest";
import { SupabaseAuthAdapter } from "./auth-adapter";

const OWNER = "10000000-0000-4000-8000-000000000001";
const SESSION = { access_token: "signed-user-jwt", user: { id: OWNER } };
const CONFIG = {
  configured: true,
  projectUrl: "https://qvxohnlboefomtjecxdh.supabase.co",
  publishableKey: "sb_publishable_browser-placeholder-123456",
  origin: "https://magicfin.example",
  callbackPath: "/auth/callback",
};

function client({ session = null, verifiedOwner = OWNER, verifiedUser = {} } = {}) {
  const unsubscribe = vi.fn();
  return {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session }, error: null }),
      getUser: vi.fn().mockResolvedValue({ data: { user: { id: verifiedOwner, ...verifiedUser } }, error: null }),
      onAuthStateChange: vi.fn().mockReturnValue({ data: { subscription: { unsubscribe } } }),
      signInWithOAuth: vi.fn().mockResolvedValue({ data: {}, error: null }),
      exchangeCodeForSession: vi.fn().mockResolvedValue({ data: { session: SESSION }, error: null }),
      signOut: vi.fn().mockResolvedValue({ error: null }),
    },
  };
}

describe("Supabase Auth adapter", () => {
  it("exposes a truthful not-configured state without constructing a session", async () => {
    const adapter = new SupabaseAuthAdapter(
      { configured: false, reasonCode: "GOOGLE_SIGN_IN_NOT_CONFIGURED" },
      null,
    );
    expect(await adapter.initialize()).toEqual({
      status: "unauthenticated",
      configured: false,
      reasonCode: "GOOGLE_SIGN_IN_NOT_CONFIGURED",
    });
  });

  it("starts Google OAuth with a same-origin callback and safe return-to route", async () => {
    const sdk = client();
    const adapter = new SupabaseAuthAdapter(CONFIG, sdk);
    await adapter.signInWithGoogle("/review/current");
    expect(sdk.auth.signInWithOAuth).toHaveBeenCalledWith({
      provider: "google",
      options: {
        redirectTo:
          "https://magicfin.example/auth/callback?return_to=%2Freview%2Fcurrent",
      },
    });
  });

  it("exchanges the callback code, verifies the user, and returns a local route", async () => {
    const sdk = client();
    const adapter = new SupabaseAuthAdapter(CONFIG, sdk);
    const result = await adapter.handleCallback(
      "https://magicfin.example/auth/callback?code=one-time-code&return_to=%2Freview",
    );
    expect(sdk.auth.exchangeCodeForSession).toHaveBeenCalledWith("one-time-code");
    expect(sdk.auth.getUser).toHaveBeenCalledWith("signed-user-jwt");
    expect(result).toEqual({
      state: { status: "authenticated", ownerId: OWNER },
      returnTo: "/review",
    });
    expect(JSON.stringify(result)).not.toContain("signed-user-jwt");
  });

  it("exposes only safe verified profile fields for the visible account state", async () => {
    const sdk = client({ session: SESSION, verifiedUser: { email: "ada@example.com", user_metadata: { full_name: "Ada Lovelace" } } });
    const adapter = new SupabaseAuthAdapter(CONFIG, sdk);
    await expect(adapter.initialize()).resolves.toEqual({
      status: "authenticated",
      ownerId: OWNER,
      email: "ada@example.com",
      displayName: "Ada Lovelace",
    });
  });

  it("does not let an in-flight empty initialization overwrite callback authentication", async () => {
    const sdk = client();
    let releaseInitialSession;
    sdk.auth.getSession = vi.fn().mockImplementationOnce(
      () => new Promise((resolve) => { releaseInitialSession = resolve; }),
    );
    const adapter = new SupabaseAuthAdapter(CONFIG, sdk);
    const initialize = adapter.initialize();
    const callback = await adapter.handleCallback(
      "https://magicfin.example/auth/callback?code=one-time-code&return_to=%2Fsign-in",
    );
    releaseInitialSession({ data: { session: null }, error: null });
    await initialize;
    expect(callback.state).toEqual({ status: "authenticated", ownerId: OWNER });
    expect(adapter.state).toEqual(callback.state);
  });

  it("maps provider cancellation without exposing the provider error description", async () => {
    const adapter = new SupabaseAuthAdapter(CONFIG, client());
    const result = await adapter.handleCallback(
      "https://magicfin.example/auth/callback?error=access_denied&error_description=sensitive",
    );
    expect(result.state).toEqual({ status: "cancelled", reasonCode: "AUTH_CANCELLED" });
    expect(JSON.stringify(result)).not.toContain("sensitive");
  });

  it("fails closed when the stored session owner does not match the verified user", async () => {
    const sdk = client({ session: SESSION, verifiedOwner: "20000000-0000-4000-8000-000000000002" });
    const adapter = new SupabaseAuthAdapter(CONFIG, sdk);
    await expect(adapter.requireAuthenticatedOwner()).rejects.toMatchObject({
      reasonCode: "AUTH_REQUIRED",
    });
  });

  it("signs out only the current browser session and clears adapter ownership", async () => {
    const sdk = client({ session: SESSION });
    const adapter = new SupabaseAuthAdapter(CONFIG, sdk);
    await adapter.initialize();
    expect(await adapter.signOut()).toEqual({ status: "unauthenticated", configured: true });
    expect(sdk.auth.signOut).toHaveBeenCalledWith({ scope: "local" });
  });
});
