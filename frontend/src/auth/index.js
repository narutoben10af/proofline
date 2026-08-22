import { SupabaseAuthAdapter } from "./auth-adapter";
import { readBrowserAuthConfig } from "./auth-config";
import { AuthenticatedPrivateStorageAdapter } from "./private-storage-adapter";
import { createSupabaseAuthClient } from "./supabase-client";

/**
 * Narrow handoff for the UI-owned branch. It contains no rendering or shell assumptions.
 * The UI subscribes to `auth`, routes `/auth/callback` to `handleCallback`, and navigates
 * only to the returned, sanitized `returnTo` path.
 */
export function createMagicFinAuthHandoff({ env, origin, clientFactory } = {}) {
  const config = readBrowserAuthConfig(env || import.meta.env, origin || window.location.origin);
  const client = createSupabaseAuthClient(config, clientFactory);
  const auth = new SupabaseAuthAdapter(config, client);
  return {
    config,
    auth,
    privateStorage: client ? new AuthenticatedPrivateStorageAdapter(client, auth) : null,
    handleCallback: (url) => auth.handleCallback(url),
  };
}
