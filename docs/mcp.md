# MagicFin read-only MCP server

MagicFin exposes a tool-only MCP endpoint at `/mcp`. It is a deliberately small
company-knowledge surface over the repository's public, reviewed FY2025 demo
fixtures. It is **not** access to uploaded files, a private database, live AI,
or user-specific state.

The implementation follows the official OpenAI guidance to build tools before
optional UI and uses the official Python `mcp` SDK with streamable HTTP:

- [Build an MCP server](https://developers.openai.com/apps-sdk/build/mcp-server)
- [Define tools](https://developers.openai.com/apps-sdk/plan/tools)
- [Apps SDK reference](https://developers.openai.com/apps-sdk/reference)

## Tool contract

The server implements the standard read-only company-knowledge tools:

- `search(query: string)` returns exactly one text content item. Its text is a
  JSON object with a `results` array; each result contains only `id`, `title`,
  and a canonical citation `url`.
- `fetch(id: string)` accepts an exact ID returned by `search` and returns
  exactly one text content item. Its text is a JSON object with `id`, `title`,
  `text`, `url`, and fixture-boundary `metadata`.

Both tools are read-only, non-destructive, idempotent, and closed-world. Search
queries are bounded to 200 characters, fetch IDs to 160 characters, and search
returns at most 10 deterministically sorted results.

The catalog covers only:

- Apple Inc. FY2025 and PETRONAS Chemicals Group Berhad FY2025 analysis summaries;
- deterministic reviewed metrics;
- reviewed finding summaries;
- official source metadata and canonical URLs; and
- truthful report metadata.

It never returns issuer document bytes, environment variables, API keys,
private uploads, deletion or review controls, or fabricated database/auth state.

## Run locally

```sh
uv sync --locked --extra dev
uv run --locked uvicorn proofline.api:app --host 127.0.0.1 --port 8000
```

The MCP URL is `http://127.0.0.1:8000/mcp`. The existing REST API and `/health`
route remain available from the same process.

Use MCP Inspector or another streamable-HTTP MCP client to initialize the
server, list tools, call `search`, then pass an exact result ID to `fetch`.

## Connect from ChatGPT Developer Mode

Localhost is not directly reachable by ChatGPT. For development only:

1. Run the server locally as above.
2. Expose port 8000 through a trusted HTTPS tunnel.
3. In ChatGPT, enable Developer Mode under **Settings → Apps & Connectors →
   Advanced settings**.
4. Create an app using `https://<tunnel-host>/mcp` as the remote MCP URL.
5. Refresh the app after tool metadata changes so ChatGPT reloads descriptors.

This repository does not claim that a public MCP deployment or authentication
layer exists. A production connection requires stable HTTPS, authentication,
authorization, rate limits, monitoring, and a reviewed privacy boundary before
anything beyond these public demo fixtures is exposed.

## Generic MCP clients

Configure any streamable-HTTP-capable MCP client with the full `/mcp` URL.
Client configuration names vary, but the transport is streamable HTTP and the
server is stateless. No credentials are required for the current public fixture
demo; do not reuse that unauthenticated posture for private data.

## Verification

```sh
uv run --locked --extra dev pytest tests/test_mcp_server.py
uv run --locked --extra dev ruff check src tests
uv run --locked --extra dev ruff format --check src tests
```

The tests validate exact schemas, annotations, deterministic and bounded search,
canonical provenance, fail-closed fetch behavior, and MCP initialize runtime
sanity at `/mcp`.
