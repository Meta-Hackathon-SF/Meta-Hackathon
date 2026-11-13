import { isRelayAuthorized } from "../../../_museRelay.js";

const MAX_REQUEST = 4 * 1024 * 1024;
const MAX_RESPONSE = 256 * 1024;
const UPSTREAM = "https://api.meta.ai/v1/asr/transcribe";

// Vercel's request.body helper is lazy; read the raw stream without accessing it.
export function makeTranscriptionRelay({ authorize = isRelayAuthorized, send = fetch } = {}) {
  return async (req, res) => {
    const fail = (status, code) => res.status(status).json({ error: { code } });
    res.setHeader("Cache-Control", "no-store");
    if (req.method !== "POST") return fail(405, "relay_method_not_allowed");
    const auth = req.headers.authorization || "";
    if (!authorize(auth)) return fail(401, "relay_unauthorized");
    const type = req.headers["content-type"] || "";
    if (!/^multipart\/form-data;\s*boundary=[A-Za-z0-9'()+_,.\/:=?-]{1,70}$/i.test(type)) {
      return fail(400, "relay_invalid_content_type");
    }
    const url = new URL(req.url, "https://relay.invalid");
    const ids = url.searchParams.getAll("sessionId");
    if (ids.length !== 1 || !/^cst-[0-9a-f]{32}$/i.test(ids[0]) || [...url.searchParams.keys()].length !== 1) {
      return fail(400, "relay_invalid_session");
    }
    try {
      const chunks = [];
      let size = 0;
      for await (const chunk of req) {
        size += chunk.length;
        if (size > MAX_REQUEST) return fail(413, "relay_request_too_large");
        chunks.push(chunk);
      }
      const upstream = await send(`${UPSTREAM}?sessionId=${encodeURIComponent(ids[0])}`, {
        method: "POST",
        headers: { Authorization: auth, "Content-Type": type, Accept: "application/json" },
        body: Buffer.concat(chunks, size),
        redirect: "error",
        signal: AbortSignal.timeout(28_000),
      });
      if (upstream.status !== 200) return res.status(upstream.status).send("");
      const parts = [];
      let responseSize = 0;
      for await (const chunk of upstream.body) {
        responseSize += chunk.length;
        if (responseSize > MAX_RESPONSE) return fail(502, "relay_response_too_large");
        parts.push(chunk);
      }
      res.setHeader("Content-Type", "application/json");
      return res.status(200).send(Buffer.concat(parts, responseSize));
    } catch {
      return fail(502, "relay_upstream_unreachable");
    }
  };
}

export default makeTranscriptionRelay();
