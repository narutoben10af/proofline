import { describe, expect, it, vi } from "vitest";
import { createSupabaseAuthClient } from "./supabase-client";

describe("Supabase browser client", () => {
  it("does not construct a client when Google sign-in is not configured", () => {
    const factory = vi.fn();
    expect(createSupabaseAuthClient({ configured: false }, factory)).toBeNull();
    expect(factory).not.toHaveBeenCalled();
  });

  it("uses only the project URL and publishable key with explicit PKCE behavior", () => {
    const factory = vi.fn().mockReturnValue({ auth: {} });
    const config = {
      configured: true,
      projectUrl: "https://qvxohnlboefomtjecxdh.supabase.co",
      publishableKey: "sb_publishable_browser-placeholder-123456",
    };
    createSupabaseAuthClient(config, factory);
    expect(factory).toHaveBeenCalledWith(config.projectUrl, config.publishableKey, {
      auth: {
        flowType: "pkce",
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: false,
      },
    });
    expect(JSON.stringify(factory.mock.calls)).not.toMatch(/service_role|sb_secret_/i);
  });
});
