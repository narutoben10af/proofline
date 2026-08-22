import { createClient } from "@supabase/supabase-js";

export function createSupabaseAuthClient(config, clientFactory = createClient) {
  if (!config.configured) return null;
  return clientFactory(config.projectUrl, config.publishableKey, {
    auth: {
      flowType: "pkce",
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: false,
    },
  });
}
