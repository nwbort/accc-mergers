/**
 * POST /push/topics: subscribe a browser to the Firebase Cloud Messaging
 * topics for what it follows, and unsubscribe it from the rest.
 *
 * The browser half of the site's notifications (frontend/src/push/) can get
 * itself a token, but FCM's web SDK, unlike the Android one, can't subscribe
 * that token to a topic: only a server holding the project's credentials can.
 * This is that server, and nothing more. Body: {token, add: [...], remove: [...]}.
 * It passes each change to Google's topic API and keeps nothing: no token, no
 * topic list, no log of either. Google holds the subscriptions, as it does for
 * the Android app's.
 *
 * Topics are only the names scripts/push/fcm.py sends to, so the route can't
 * be used to subscribe anything to anything else.
 *
 * Secret: FCM_SERVICE_ACCOUNT, the same Firebase service account key the
 * site's android-push.yml uses (its JSON, whole). Without it the route answers
 * 503 and the page leaves notifications off.
 */

const IID_BASE = "https://iid.googleapis.com/iid/v1";
const SCOPE = "https://www.googleapis.com/auth/firebase.messaging";

// The topic names in scripts/push/fcm.py and the app's notify/Push.kt.
const TOPIC_RE = /^(all|list|merger-(MN|WA)-\d{5}|industry-([A-S]|_orphans))$/;

// An FCM registration token: long, URL-safe base64 with a colon.
const TOKEN_RE = /^[A-Za-z0-9_:\-]{20,4096}$/;

// One call to Google per topic, and a Worker request may make only 50
// subrequests (one more goes on the access token). The page sends batches of
// at most this many.
export const MAX_CHANGES = 40;

/**
 * The request's changes, or an error message.
 * @returns {{token: string, add: string[], remove: string[]} | {error: string}}
 */
export function parseTopicChanges(body) {
  const token = typeof body?.token === "string" ? body.token : "";
  if (!TOKEN_RE.test(token)) return { error: "Invalid token" };
  const list = (key) => (Array.isArray(body[key]) ? body[key] : body[key] === undefined ? [] : null);
  const add = list("add");
  const remove = list("remove");
  if (!add || !remove) return { error: "add and remove must be lists" };
  if (!add.length && !remove.length) return { error: "Nothing to change" };
  if (add.length + remove.length > MAX_CHANGES) return { error: `At most ${MAX_CHANGES} changes at a time` };
  if (![...add, ...remove].every((t) => typeof t === "string" && TOPIC_RE.test(t))) {
    return { error: "Unknown topic" };
  }
  return { token, add: [...new Set(add)], remove: [...new Set(remove)] };
}

// --- Google OAuth from the service account (RS256 JWT, WebCrypto) ----------

const b64url = (bytes) =>
  btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const b64urlText = (text) => b64url(new TextEncoder().encode(text));

function pemToDer(pem) {
  const base64 = pem.replace(/-----[^-]+-----/g, "").replace(/\s+/g, "");
  return Uint8Array.from(atob(base64), (c) => c.charCodeAt(0)).buffer;
}

export async function signedJwt(account, now) {
  const header = { alg: "RS256", typ: "JWT", kid: account.private_key_id || "" };
  const claims = {
    iss: account.client_email,
    scope: SCOPE,
    aud: account.token_uri || "https://oauth2.googleapis.com/token",
    iat: now,
    exp: now + 3600,
  };
  const input = `${b64urlText(JSON.stringify(header))}.${b64urlText(JSON.stringify(claims))}`;
  const key = await crypto.subtle.importKey(
    "pkcs8",
    pemToDer(account.private_key),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(input));
  return `${input}.${b64url(signature)}`;
}

// Reused while it lasts, for as long as this isolate does.
let cachedToken = null;

async function accessToken(account, fetchImpl) {
  const now = Math.floor(Date.now() / 1000);
  if (cachedToken && cachedToken.email === account.client_email && cachedToken.expires > now + 60) {
    return cachedToken.value;
  }
  const resp = await fetchImpl(account.token_uri || "https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion: await signedJwt(account, now),
    }),
  });
  if (!resp.ok) throw new Error(`Google token endpoint: HTTP ${resp.status}`);
  const data = await resp.json();
  cachedToken = { email: account.client_email, value: data.access_token, expires: now + (data.expires_in || 3600) };
  return cachedToken.value;
}

/**
 * Apply the changes: one batchAdd/batchRemove per topic, all at once.
 * Resolves to "ok", "invalid-token" (Google doesn't know it, so the page
 * should get a new one) or throws.
 */
export async function applyTopicChanges({ token, add, remove }, account, fetchImpl = fetch) {
  const bearer = await accessToken(account, fetchImpl);
  const call = (op, topic) =>
    fetchImpl(`${IID_BASE}:${op}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${bearer}`,
        "Content-Type": "application/json",
        access_token_auth: "true",
      },
      body: JSON.stringify({ to: `/topics/${topic}`, registration_tokens: [token] }),
    }).then(async (resp) => {
      if (!resp.ok) throw new Error(`${op} ${topic}: HTTP ${resp.status}`);
      const data = await resp.json().catch(() => ({}));
      return data?.results?.[0]?.error || null;
    });
  const errors = await Promise.all([
    ...add.map((t) => call("batchAdd", t)),
    ...remove.map((t) => call("batchRemove", t)),
  ]);
  if (errors.some((e) => e === "NOT_FOUND" || e === "INVALID_ARGUMENT")) return "invalid-token";
  const other = errors.find(Boolean);
  if (other) throw new Error(`Topic change refused: ${other}`);
  return "ok";
}

/** The service account from the Worker secret, or null. */
export function serviceAccount(env) {
  try {
    const account = JSON.parse(env.FCM_SERVICE_ACCOUNT || "null");
    return account && account.client_email && account.private_key ? account : null;
  } catch {
    return null;
  }
}
