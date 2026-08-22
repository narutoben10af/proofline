import assert from "node:assert/strict";
import { access } from "node:fs/promises";
import test from "node:test";
import worker from "../worker/index.js";

test("serves existing static assets without a fallback", async () => {
  const calls = [];
  const response = await worker.fetch(new Request("https://example.test/assets/app.js"), {
    ASSETS: {
      fetch: async (request) => {
        calls.push(new URL(request.url).pathname);
        return new Response("asset", { status: 200 });
      },
    },
  });

  assert.equal(response.status, 200);
  assert.deepEqual(calls, ["/assets/app.js"]);
});

test("falls back to index.html for an unknown app route", async () => {
  const calls = [];
  const response = await worker.fetch(
    new Request("https://example.test/flow/step-two?source=share", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async (request) => {
          const url = new URL(request.url);
          calls.push(url.pathname + url.search);
          return new Response(url.pathname === "/index.html" ? "app" : "missing", {
            status: url.pathname === "/index.html" ? 200 : 404,
          });
        },
      },
    },
  );

  assert.equal(response.status, 200);
  assert.deepEqual(calls, ["/flow/step-two?source=share", "/index.html"]);
});

test("does not turn missing API or write requests into the app shell", async () => {
  for (const request of [
    new Request("https://example.test/api/missing", { headers: { accept: "application/json" } }),
    new Request("https://example.test/flow", { method: "POST", headers: { accept: "text/html" } }),
  ]) {
    let calls = 0;
    const response = await worker.fetch(request, {
      ASSETS: {
        fetch: async () => {
          calls += 1;
          return new Response("missing", { status: 404 });
        },
      },
    });

    assert.equal(response.status, 404);
    assert.equal(calls, 1);
  }
});

test("emits the files required by Sites packaging", async () => {
  await access(new URL("../dist/client/index.html", import.meta.url));
  await access(new URL("../dist/server/index.js", import.meta.url));
  await access(new URL("../dist/.openai/hosting.json", import.meta.url));
});

test("never answers an assistant API request with the app shell", async () => {
  // The Sites worker serves static assets only. If a same-origin assistant call ever resolved to
  // index.html, the client would parse markup as JSON and report a bogus assistant failure.
  for (const request of [
    new Request("https://example.test/api/v1/assistant", {
      method: "POST",
      headers: { accept: "text/html", "content-type": "application/json" },
      body: JSON.stringify({ prompt: "hi" }),
    }),
    new Request("https://example.test/api/v1/providers/model", { headers: { accept: "text/html" } }),
  ]) {
    const served = [];
    const response = await worker.fetch(request, {
      ASSETS: {
        fetch: async (assetRequest) => {
          const url = new URL(assetRequest.url);
          served.push(url.pathname);
          return new Response(url.pathname === "/index.html" ? "<!doctype html><div id=root>" : "missing", {
            status: url.pathname === "/index.html" ? 200 : 404,
            headers: { "content-type": url.pathname === "/index.html" ? "text/html" : "text/plain" },
          });
        },
      },
    });

    assert.equal(response.status, 404, `${request.method} ${new URL(request.url).pathname} must not be rewritten`);
    assert.ok(!served.includes("/index.html"), "assistant routes must never fall back to the app shell");
    assert.ok(!(await response.text()).includes("<!doctype html"), "assistant routes must not return HTML");
  }
});
