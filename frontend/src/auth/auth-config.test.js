import { describe, expect, it } from "vitest";
import {
  AUTH_CALLBACK_PATH,
  callbackUrl,
  readBrowserAuthConfig,
  safeReturnTo,
} from "./auth-config";

const ORIGIN = "https://magicfin.example";
const URL = "https://qvxohnlboefomtjecxdh.supabase.co";
const KEY = "sb_publishable_browser-placeholder-123456";

describe("browser auth configuration", () => {
  it("is truthfully not configured when public values are absent", () => {
    expect(readBrowserAuthConfig({}, ORIGIN)).toEqual({
      configured: false,
      reasonCode: "GOOGLE_SIGN_IN_NOT_CONFIGURED",
    });
  });

  it("accepts only the MagicFin project URL and a publishable key", () => {
    expect(
      readBrowserAuthConfig(
        { VITE_SUPABASE_URL: URL, VITE_SUPABASE_PUBLISHABLE_KEY: KEY },
        ORIGIN,
      ),
    ).toMatchObject({ configured: true, projectUrl: URL, publishableKey: KEY });

    for (const env of [
      { VITE_SUPABASE_URL: URL },
      { VITE_SUPABASE_URL: URL, VITE_SUPABASE_PUBLISHABLE_KEY: "sb_secret_never-browser" },
      {
        VITE_SUPABASE_URL: "https://other-project.supabase.co",
        VITE_SUPABASE_PUBLISHABLE_KEY: KEY,
      },
    ]) {
      expect(readBrowserAuthConfig(env, ORIGIN)).toEqual({
        configured: false,
        reasonCode: "AUTH_CONFIGURATION_INVALID",
      });
    }
    expect(
      readBrowserAuthConfig(
        { VITE_SUPABASE_URL: URL, VITE_SUPABASE_PUBLISHABLE_KEY: KEY },
        "http://public-preview.example",
      ),
    ).toEqual({ configured: false, reasonCode: "AUTH_CONFIGURATION_INVALID" });
  });

  it("keeps callback and return-to navigation same-origin", () => {
    expect(callbackUrl(ORIGIN, "/review/active")).toBe(
      `${ORIGIN}${AUTH_CALLBACK_PATH}?return_to=%2Freview%2Factive`,
    );
    expect(safeReturnTo("https://attacker.example")).toBe("/");
    expect(safeReturnTo("//attacker.example/path")).toBe("/");
    expect(safeReturnTo("/\\attacker.example/path")).toBe("/");
    expect(safeReturnTo("/auth/callback?loop=1")).toBe("/");
  });
});
