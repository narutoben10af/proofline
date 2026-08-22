import { productionHandler } from "./handler.ts";

function environment(): Record<string, string | undefined> {
  return {
    SUPABASE_URL: Deno.env.get("SUPABASE_URL"),
    SUPABASE_PUBLISHABLE_KEY: Deno.env.get("SUPABASE_PUBLISHABLE_KEY"),
    SUPABASE_PUBLISHABLE_KEYS: Deno.env.get("SUPABASE_PUBLISHABLE_KEYS"),
    SUPABASE_ANON_KEY: Deno.env.get("SUPABASE_ANON_KEY"),
    GEMINI_API_KEY: Deno.env.get("GEMINI_API_KEY"),
    GEMMA_MODEL: Deno.env.get("GEMMA_MODEL"),
    MAGIC_ASSISTANT_ALLOWED_ORIGINS: Deno.env.get("MAGIC_ASSISTANT_ALLOWED_ORIGINS"),
  };
}

export default {
  async fetch(request: Request): Promise<Response> {
    try {
      return await productionHandler(environment())(request);
    } catch {
      return Response.json(
        {
          state: "not_configured",
          code: "not_configured",
          retryable: false,
          disclosure: "No evidence or question was sent to Google Gemma 4.",
        },
        {
          status: 503,
          headers: {
            "cache-control": "no-store, private",
            "x-content-type-options": "nosniff",
          },
        },
      );
    }
  },
};
