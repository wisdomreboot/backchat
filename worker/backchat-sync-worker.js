/*
  Backchat sync relay  (for Backchat 1.0.52 and later)
  ----------------------------------------------------
  A private mailbox for your own devices. Each device keeps one "slot":
  it writes its own slot and reads everyone else's. The relay never sees
  your notes: Backchat encrypts everything on the device before upload,
  so this Worker only ever stores scrambled bytes.

  Setup (Cloudflare dashboard, no command line):
    1. Create a KV namespace (any name, e.g. backchat-sync).
    2. Create a Worker, paste this whole file over the starter code, Deploy.
    3. Worker > Bindings > Add binding > KV namespace.
         Variable name:  SYNC      (exactly this, capitals)
         KV namespace:   the one from step 1
    4. Worker > Settings > Variables and Secrets > Add > type Secret.
         Variable name:  SYNC_TOKEN (exactly this)
         Value:          the access token Backchat generated for you
    5. Deploy.

  Open the Worker's address in a browser: it reports whether setup is complete.

  Copyright (c) 2026 Jonathan du Toit. MIT License.
*/

const MAX_BYTES = 20 * 1024 * 1024;          // KV allows 25 MiB per value; keep headroom
const SLOT_RE = /^[A-Za-z0-9_-]{1,64}$/;

function cors(request) {
  const origin = request.headers.get("Origin");
  return {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Methods": "GET, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Device-Name",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function json(request, status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...cors(request) },
  });
}

// Compare tokens without leaking where they differ.
function sameToken(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(request) });

    const hasKV = !!(env.SYNC && typeof env.SYNC.get === "function");
    const hasToken = typeof env.SYNC_TOKEN === "string" && env.SYNC_TOKEN.length >= 16;

    // Health check: safe to open in a browser, reveals nothing but setup status.
    if (path === "/" && request.method === "GET") {
      return json(request, 200, {
        app: "backchat-sync", version: 1, ok: hasKV && hasToken,
        setup: { kv_binding_SYNC: hasKV, secret_SYNC_TOKEN: hasToken },
        message: hasKV && hasToken
          ? "Ready. Paste this address into Backchat."
          : "Setup incomplete. " + (hasKV ? "" : "Add a KV binding named SYNC. ") + (hasToken ? "" : "Add a secret named SYNC_TOKEN (at least 16 characters)."),
      });
    }

    if (!hasKV || !hasToken) return json(request, 503, { error: "setup_incomplete", setup: { kv_binding_SYNC: hasKV, secret_SYNC_TOKEN: hasToken } });

    const auth = request.headers.get("Authorization") || "";
    const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
    if (!sameToken(token, env.SYNC_TOKEN)) return json(request, 401, { error: "bad_token" });

    // List every device slot with when it last wrote.
    if (path === "/slots" && request.method === "GET") {
      const out = [];
      let cursor;
      do {
        const page = await env.SYNC.list({ prefix: "slot:", cursor });
        for (const k of page.keys) out.push({ id: k.name.slice(5), ...(k.metadata || {}) });
        cursor = page.list_complete ? undefined : page.cursor;
      } while (cursor);
      return json(request, 200, { slots: out });
    }

    const m = path.match(/^\/slot\/([^/]+)$/);
    if (!m) return json(request, 404, { error: "not_found" });
    const id = decodeURIComponent(m[1]);
    if (!SLOT_RE.test(id)) return json(request, 400, { error: "bad_slot" });
    const key = "slot:" + id;

    if (request.method === "GET") {
      // Value and its timestamp come back together, so the device always knows
      // exactly which version it received (KV is eventually consistent).
      const got = await env.SYNC.getWithMetadata(key, { type: "arrayBuffer" });
      if (!got || got.value === null) return json(request, 404, { error: "empty" });
      const updated = String((got.metadata && got.metadata.updated) || 0);
      return new Response(got.value, {
        status: 200,
        headers: {
          "Content-Type": "application/octet-stream", "Cache-Control": "no-store",
          "X-Slot-Updated": updated, "Access-Control-Expose-Headers": "X-Slot-Updated",
          ...cors(request),
        },
      });
    }

    if (request.method === "PUT") {
      const body = await request.arrayBuffer();
      if (!body.byteLength) return json(request, 400, { error: "empty_body" });
      if (body.byteLength > MAX_BYTES) return json(request, 413, { error: "too_large", max: MAX_BYTES });
      let name = "";
      try { name = decodeURIComponent(request.headers.get("X-Device-Name") || "").slice(0, 60); } catch (e) {}
      const meta = { updated: Date.now(), size: body.byteLength, name };
      await env.SYNC.put(key, body, { metadata: meta });
      return json(request, 200, { ok: true, ...meta });
    }

    if (request.method === "DELETE") {
      await env.SYNC.delete(key);
      return json(request, 200, { ok: true });
    }

    return json(request, 405, { error: "method_not_allowed" });
  },
};
