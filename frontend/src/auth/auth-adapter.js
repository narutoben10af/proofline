import {
  AUTH_REASON,
  AUTH_STATUS,
  AuthBoundaryError,
  errorState,
  unauthenticatedState,
} from "./auth-contract";
import { AUTH_CALLBACK_PATH, callbackUrl, safeReturnTo } from "./auth-config";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function callbackParameters(url) {
  const params = new URLSearchParams(url.search);
  const fragment = new URLSearchParams(url.hash.replace(/^#/, ""));
  for (const [key, value] of fragment) {
    if (!params.has(key)) params.set(key, value);
  }
  return params;
}

export class SupabaseAuthAdapter {
  constructor(config, client) {
    this.config = config;
    this.client = client;
    this.state = config.configured
      ? { status: AUTH_STATUS.LOADING }
      : unauthenticatedState(false, config.reasonCode);
    this.session = null;
    this.listeners = new Set();
    this.subscription = null;
  }

  subscribe(listener) {
    this.listeners.add(listener);
    listener(this.state);
    return () => this.listeners.delete(listener);
  }

  emit(state) {
    this.state = state;
    for (const listener of this.listeners) listener(state);
    return state;
  }

  async initialize() {
    if (!this.config.configured || !this.client) return this.state;
    this.emit({ status: AUTH_STATUS.LOADING });
    if (!this.subscription) {
      const { data } = this.client.auth.onAuthStateChange((event, session) => {
        if (event === "SIGNED_OUT") {
          this.session = null;
          this.emit(unauthenticatedState());
        } else if (session) {
          void this.resolveSession(session);
        }
      });
      this.subscription = data.subscription;
    }

    const { data, error } = await this.client.auth.getSession();
    if (error) return this.emit(errorState(AUTH_REASON.AUTH_SESSION_INVALID));
    if (!data.session) {
      this.session = null;
      return this.emit(unauthenticatedState());
    }
    return this.resolveSession(data.session);
  }

  async resolveSession(session) {
    const token = session?.access_token;
    const claimedOwner = session?.user?.id;
    if (typeof token !== "string" || !UUID.test(claimedOwner || "")) {
      this.session = null;
      return this.emit(errorState(AUTH_REASON.AUTH_SESSION_INVALID));
    }

    const { data, error } = await this.client.auth.getUser(token);
    const verifiedOwner = data?.user?.id;
    if (error || verifiedOwner !== claimedOwner || !UUID.test(verifiedOwner || "")) {
      this.session = null;
      return this.emit(errorState(AUTH_REASON.AUTH_SESSION_INVALID));
    }

    this.session = session;
    return this.emit({ status: AUTH_STATUS.AUTHENTICATED, ownerId: verifiedOwner });
  }

  async signInWithGoogle(returnTo = "/") {
    if (!this.config.configured || !this.client) return this.state;
    this.emit({ status: AUTH_STATUS.LOADING });
    const { error } = await this.client.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: callbackUrl(this.config.origin, returnTo),
      },
    });
    if (error) return this.emit(errorState(AUTH_REASON.AUTH_START_FAILED));
    return this.state;
  }

  async handleCallback(rawUrl) {
    if (!this.config.configured || !this.client) {
      return { state: this.state, returnTo: "/" };
    }

    let url;
    try {
      url = new URL(rawUrl);
    } catch {
      return {
        state: this.emit(errorState(AUTH_REASON.AUTH_CALLBACK_INVALID)),
        returnTo: "/",
      };
    }
    const returnTo = safeReturnTo(url.searchParams.get("return_to"));
    if (url.origin !== this.config.origin || url.pathname !== AUTH_CALLBACK_PATH) {
      return {
        state: this.emit(errorState(AUTH_REASON.AUTH_CALLBACK_INVALID)),
        returnTo,
      };
    }

    const params = callbackParameters(url);
    const oauthError = params.get("error") || params.get("error_code");
    if (["access_denied", "user_cancelled", "cancelled"].includes(oauthError)) {
      return {
        state: this.emit({ status: AUTH_STATUS.CANCELLED, reasonCode: AUTH_REASON.AUTH_CANCELLED }),
        returnTo,
      };
    }
    const code = params.get("code");
    if (!code) {
      return {
        state: this.emit(errorState(AUTH_REASON.AUTH_CALLBACK_INVALID)),
        returnTo,
      };
    }

    this.emit({ status: AUTH_STATUS.LOADING });
    const { data, error } = await this.client.auth.exchangeCodeForSession(code);
    if (error || !data.session) {
      return {
        state: this.emit(errorState(AUTH_REASON.AUTH_EXCHANGE_FAILED)),
        returnTo,
      };
    }
    return { state: await this.resolveSession(data.session), returnTo };
  }

  async signOut() {
    if (!this.config.configured || !this.client) return this.state;
    const { error } = await this.client.auth.signOut({ scope: "local" });
    if (error) return this.emit(errorState(AUTH_REASON.AUTH_SIGN_OUT_FAILED));
    this.session = null;
    return this.emit(unauthenticatedState());
  }

  async requireAuthenticatedOwner() {
    if (!this.config.configured || !this.client) {
      throw new AuthBoundaryError(AUTH_REASON.AUTH_REQUIRED);
    }
    const { data, error } = await this.client.auth.getSession();
    if (error || !data.session) throw new AuthBoundaryError(AUTH_REASON.AUTH_REQUIRED);
    const state = await this.resolveSession(data.session);
    if (state.status !== AUTH_STATUS.AUTHENTICATED) {
      throw new AuthBoundaryError(AUTH_REASON.AUTH_REQUIRED);
    }
    return { ownerId: state.ownerId };
  }

  destroy() {
    this.subscription?.unsubscribe();
    this.subscription = null;
    this.listeners.clear();
    this.session = null;
  }
}
