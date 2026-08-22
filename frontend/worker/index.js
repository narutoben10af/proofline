// API routes are never client-side app routes. Without this guard a GET /api/* that advertises
// text/html resolves to index.html, and the caller parses markup as JSON.
const API_PREFIXES = ["/api/", "/health"];

function isApiPath(pathname) {
  return API_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(prefix));
}

export default {
  async fetch(request, env) {
    const response = await env.ASSETS.fetch(request);
    const acceptsHtml = request.headers.get("accept")?.includes("text/html");

    if (
      response.status !== 404 ||
      !acceptsHtml ||
      !["GET", "HEAD"].includes(request.method) ||
      isApiPath(new URL(request.url).pathname)
    ) {
      return response;
    }

    const indexUrl = new URL(request.url);
    indexUrl.pathname = "/index.html";
    indexUrl.search = "";
    return env.ASSETS.fetch(new Request(indexUrl, request));
  },
};
