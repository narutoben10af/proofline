# ADR 0003: Provider-neutral, server-only model boundary

- Status: accepted for prototype contracts
- Date: 2026-08-22

## Decision

Model-authored assistant and extraction work crosses a provider-neutral server interface. The
default Gemma-via-Gemini-API adapter truthfully reports not configured until a server credential is
present. Its executable transport is injected, time-bounded, response-bounded, and restricted to
Google's documented `generateContent` endpoint. A deterministic, citation-backed fixture supports
offline tests and demos.

Requests and responses are immutable, schema constrained, size bounded, and provenance checked.
Document text is eligible for the provider only when the request explicitly records
`provider_sent: true`. The adapter receives only already-selected bounded evidence, cannot read
files or databases, and accepts only locally validated cited JSON. No API key crosses the server
boundary, and connection status never returns raw upstream errors.

## Consequences

The UI can implement loading, offline, error, fallback, and cited-answer states without pretending
that live AI exists when it is not configured. Production deployment still requires provider-term,
data-use, egress, and incident review. The boundary prevents arbitrary file/database access,
browser-secret exposure, uncited output, and silently changing providers.
