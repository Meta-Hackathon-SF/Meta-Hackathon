import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { Readable } from "node:stream";
import relay, { isRelayAuthorized } from "../../api/_museRelay.js";
import { makeTranscriptionRelay } from "../../api/muse/v1/asr/transcribe.js";

function request(body = Buffer.from("synthetic wav bytes")) {
  return Object.assign(Readable.from([body]), {
    method: "POST",
    url: "/api/muse/v1/asr/transcribe?sessionId=cst-0123456789abcdef0123456789abcdef",
    headers: { authorization: "Bearer synthetic", "content-type": "multipart/form-data; boundary=cst-test" },
  });
}
function response() {
  return {
    headers: {}, statusCode: null, output: null,
    setHeader(k, v) { this.headers[k] = v; return this; },
    status(s) { this.statusCode = s; return this; },
    json(v) { this.output = v; return this; },
    send(v) { this.output = v; return this; },
  };
}

test("authorization uses the configured digest and fails closed", () => {
  const key = crypto.randomBytes(32).toString("hex");
  const digest = crypto.createHash("sha256").update(key).digest("hex");
  assert.equal(isRelayAuthorized(`Bearer ${key}`, digest), true);
  assert.equal(isRelayAuthorized("Bearer wrong", digest), false);
  assert.equal(isRelayAuthorized("", digest), false);
});

test("existing chat relay still rejects an unauthorized request", async () => {
  const res = response();
  await relay("POST", "/chat/completions")(request(), res);
  assert.equal(res.statusCode, 401);
});

test("forwards the exact multipart bytes and session ID without logging", async () => {
  const bytes = Buffer.from([0, 255, 42, 13, 10]);
  const res = response();
  let called = false;
  const relay = makeTranscriptionRelay({ authorize: () => true, send: async (url, opts) => {
    called = true;
    assert.equal(url, "https://api.meta.ai/v1/asr/transcribe?sessionId=cst-0123456789abcdef0123456789abcdef");
    assert.equal(opts.headers["Content-Type"], "multipart/form-data; boundary=cst-test");
    assert.deepEqual(opts.body, bytes);
    return new Response('{"transcript":"synthetic"}', { status: 200 });
  } });
  await relay(request(bytes), res);
  assert.equal(called, true);
  assert.equal(res.statusCode, 200);
  assert.equal(res.headers["Cache-Control"], "no-store");
  assert.equal(res.output.toString(), '{"transcript":"synthetic"}');
});

test("rejects unauthorized, malformed and oversized requests before upstream", async () => {
  let calls = 0;
  const reject = makeTranscriptionRelay({ authorize: () => false, send: async () => { calls++; } });
  const denied = response();
  await reject(request(), denied);
  assert.equal(denied.statusCode, 401);
  const relay = makeTranscriptionRelay({ authorize: () => true, send: async () => { calls++; } });
  const invalid = request();
  invalid.url += "&extra=1";
  const bad = response();
  await relay(invalid, bad);
  assert.equal(bad.statusCode, 400);
  const large = response();
  await relay(request(Buffer.alloc(4 * 1024 * 1024 + 1)), large);
  assert.equal(large.statusCode, 413);
  assert.equal(calls, 0);
});

test("preserves provider status without returning provider error content", async () => {
  const relay = makeTranscriptionRelay({ authorize: () => true, send: async () =>
    new Response("synthetic sensitive error", { status: 403 }) });
  const res = response();
  await relay(request(), res);
  assert.equal(res.statusCode, 403);
  assert.equal(res.output, "");
});
