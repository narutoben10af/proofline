# MagicFin Google sign-in — contract prepared, provider not configured

## Current truth

Project `qvxohnlboefomtjecxdh` exists, but this repository does not prove that Google OAuth is
enabled. No Google credential, Supabase secret/service key, user token or user record is included.
With both browser variables empty, Sites and other public previews return the explicit
`unauthenticated` state with reason `GOOGLE_SIGN_IN_NOT_CONFIGURED`.

The standalone handoff is `frontend/src/auth/index.js`. It does not render UI or change the shared
product shell. Its discriminated states are `loading`, `error`, `cancelled`, `unauthenticated` and
`authenticated`; the authenticated UI state contains only the verified Supabase user UUID as
`ownerId`. Tokens remain inside the Supabase client/auth boundary.

## Dashboard setup that is still required

Do not enable the provider until the production and preview origins are known and reviewed.

1. In Google Auth Platform, create an OAuth client of type **Web application**.
2. Add each exact application origin under **Authorized JavaScript origins**. For local review use
   `http://localhost:4173`. Add the exact deployed Sites origin when known; do not invent it here.
3. In that Google client, add this Supabase callback under **Authorized redirect URIs**:
   `https://qvxohnlboefomtjecxdh.supabase.co/auth/v1/callback`.
4. In Supabase Dashboard for project `qvxohnlboefomtjecxdh`, open **Authentication → Providers →
   Google**. Enter the Google client ID and client secret there, then enable Google. The Google
   secret belongs in the provider dashboard only—never in the repository or a `VITE_*` variable.
5. Open **Authentication → URL Configuration**. Set **Site URL** to the exact production origin.
   Add exact redirect allow-list entries for:
   - `http://localhost:4173/auth/callback`
   - `<exact-production-origin>/auth/callback`
   - each reviewed preview origin followed by `/auth/callback`
6. Put only the project URL and current `sb_publishable_...` key in the frontend build environment
   as `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`. Do not use a Google secret,
   `sb_secret_...`, legacy service-role key, access token or refresh token.
7. Run the callback/session tests and a manual disposable-user sign-in/sign-out check before
   describing the provider as configured.

Supabase distinguishes two redirects: Google returns to the Supabase `/auth/v1/callback`; Supabase
then returns to the allow-listed MagicFin `/auth/callback`. Production should use exact URLs rather
than a wildcard. See the current [Google provider guide](https://supabase.com/docs/guides/auth/social-login/auth-google),
[redirect URL guide](https://supabase.com/docs/guides/auth/redirect-urls), and
[JavaScript OAuth reference](https://supabase.com/docs/reference/javascript/auth-signinwithoauth).

## Frontend handoff contract

The UI-owned branch may import `createMagicFinAuthHandoff` and:

1. call `auth.subscribe(listener)` and render the five typed states;
2. call `auth.initialize()` once after constructing the handoff;
3. call `auth.signInWithGoogle(currentRelativeRoute)` from the Google button;
4. route `/auth/callback` to `handleCallback(window.location.href)`, replace the callback URL, and
   navigate only to the returned `returnTo` value;
5. call `auth.signOut()` for a current-browser sign-out; and
6. call `auth.destroy()` when the owning provider unmounts.

Provider error descriptions are never surfaced or logged. Stable reason codes are the UI boundary.
The adapter verifies session ownership using `auth.getUser(accessToken)` before exposing an owner.
Cancellation is distinct from failure, and unsafe absolute/protocol-relative return paths collapse
to `/`.

## Private Storage boundary

`AuthenticatedPrivateStorageAdapter` calls `requireAuthenticatedOwner()` before every operation.
That check requires a current access-token session, verifies the user with Supabase Auth, and
requires the session user UUID to match the verified UUID. The object path is then exactly
`{ownerId}/{sessionId}/{documentId}`. Missing/mismatched Auth or non-UUID identifiers fail before a
Storage request. The private bucket and owner-scoped RLS from the separate persistence proposal
remain the server-side authorization boundary.

The browser size/type checks are defense in depth, not trusted document validation. The existing
backend upload validator remains authoritative before any document is processed, and this module
must not be used to bypass it. No production-privacy, compliance, secure-erasure or provider-enabled
claim is made.
