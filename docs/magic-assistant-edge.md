# Magic Assistant Edge handoff

The deployable function source and exact contract are in
[`supabase/functions/magic-assistant/`](../supabase/functions/magic-assistant/README.md). This slice
does not deploy Supabase, create a project, request credentials, or modify the separately owned
storage migration.

For the public demo, the required sequence is:

1. Apply the reviewed authenticated storage migrations for UUID sessions/documents and
   deterministic `fact:…` normalized observations.
2. Confirm the owner-RLS-protected `magic_assistant_evidence` relation is populated only by the
   completed analysis transaction.
3. Confirm Edge Function gateway JWT verification remains enabled and configure exact frontend
   origins.
4. Add `GEMINI_API_KEY` through Supabase Edge Function secrets and deploy the backend function.
5. Invoke with a signed-in user's JWT and only session/source IDs already visible to that user.
6. Resolve returned observation IDs to numeric values through the authenticated deterministic
   evidence path; never accept a model-supplied number.

Without all six steps, product copy must say **Not configured** rather than implying a live
assistant. The key and provider call are server-side; a static frontend deployment alone cannot
make this feature live.
