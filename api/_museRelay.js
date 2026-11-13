/*
 * Muse relay (server-side only). api.meta.ai lists zero models for our key from
 * Railway's datacenter IPs, so the Railway API sets MUSE_BASE_URL to
 * https://<this site>/api/muse/v1 and calls Meta through here.
 *
 * - Forwards only the explicit models, chat completions and transcription routes.
 * - Forwards only when the caller's bearer token hashes to KEY_SHA256, so the
 *   relay holds no key and is useless without ours.
 * - Logs nothing: no bodies, headers or tokens.
 */
import crypto from "node:crypto";

const UPSTREAM = "https://api.meta.ai/v1";
const KEY_SHA256 = "8f3d0f75dd9e32f54da09f2adffa7e4d394b5282bb8be956594eec1d74614413";

export function isRelayAuthorized(auth, expectedDigest = KEY_SHA256) {
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  const digest = crypto.createHash("sha256").update(token).digest();
  return Boolean(token) && crypto.timingSafeEqual(digest, Buffer.from(expectedDigest, "hex"));
}

export default function relay(method, path) {
  return async (req, res) => {
    const fail = (status, code) => res.status(status).json({ error: { code } });
    if (req.method !== method) return fail(405, "relay_method_not_allowed");
    const auth = req.headers.authorization || "";
    if (!isRelayAuthorized(auth)) return fail(401, "relay_unauthorized");
    try {
      const upstream = await fetch(UPSTREAM + path, {
        method,
        headers: { Authorization: auth, "Content-Type": "application/json", Accept: "application/json", "User-Agent": "constellations-server" },
        body: method === "POST" ? JSON.stringify(req.body ?? {}) : undefined,
        signal: AbortSignal.timeout(58_000),
      });
      const text = await upstream.text();
      res.status(upstream.status).setHeader("Content-Type", upstream.headers.get("content-type") || "application/json");
      res.setHeader("Cache-Control", "no-store");
      return res.send(text);
    } catch {
      return fail(502, "relay_upstream_unreachable");
    }
  };
}
