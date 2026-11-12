// The Android app's double opt-in signup (POST /app-signup, GET/POST /confirm),
// run against the Worker's own fetch handler with Resend, Turnstile and KV faked.
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import worker, { signConfirmation, verifyConfirmation, CONFIRM_DAILY_CAP } from "../src/index.js";

const ENV_BASE = { RESEND_API_KEY: "re_test", RESEND_AUDIENCE_ID: "aud_1", ENVIRONMENT: "production" };

function kv() {
  const store = new Map();
  return { get: async (k) => store.get(k) ?? null, put: async (k, v) => void store.set(k, v), store };
}

let env;
let calls;
let resendStatus;

beforeEach(() => {
  env = { ...ENV_BASE, RATE_LIMIT_KV: kv() };
  calls = [];
  resendStatus = 200;
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), body: init.body ? JSON.parse(init.body) : null });
    return new Response(JSON.stringify({ id: "x" }), { status: resendStatus });
  };
});

const call = (path, init = {}) =>
  worker.fetch(new Request(`https://signup.mergers.fyi${path}`, init), env);

const appSignup = (email, ip = "1.2.3.4") =>
  call("/app-signup", {
    method: "POST",
    headers: { "Content-Type": "application/json", "CF-Connecting-IP": ip },
    body: JSON.stringify({ email }),
  });

function linkFrom(email) {
  const text = email.body.text;
  return new URL(text.match(/https:\/\/signup\.mergers\.fyi\/confirm\?\S+/)[0]);
}

test("app signup sends a confirmation email and adds no contact", async () => {
  const resp = await appSignup("  Someone@Example.com ");
  assert.equal(resp.status, 200);
  assert.equal((await resp.json()).success, true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://api.resend.com/emails");
  assert.deepEqual(calls[0].body.to, ["someone@example.com"]);
  assert.match(calls[0].body.from, /digest@mergers\.fyi/);
  assert.ok(!calls.some((c) => c.url.includes("/contacts")));
});

test("app signup needs no Turnstile token, but a valid email", async () => {
  assert.equal((await appSignup("not-an-email")).status, 400);
  assert.equal((await appSignup("")).status, 400);
  assert.equal(calls.length, 0);
});

test("one confirmation per address per hour, however often it's asked for", async () => {
  await appSignup("a@example.com", "1.1.1.1");
  const again = await appSignup("a@example.com", "2.2.2.2");
  assert.equal(again.status, 200);
  assert.equal(calls.length, 1);
});

test("per-IP limit on the app route", async () => {
  for (let i = 0; i < 5; i++) assert.equal((await appSignup(`p${i}@example.com`)).status, 200);
  assert.equal((await appSignup("p5@example.com")).status, 429);
});

test("no more than the daily cap of confirmation emails across everyone", async () => {
  assert.equal(CONFIRM_DAILY_CAP, 50);
  // A new IP every few, so the per-IP limit isn't what stops it.
  for (let i = 0; i < CONFIRM_DAILY_CAP; i++) {
    assert.equal((await appSignup(`d${i}@example.com`, `10.0.0.${Math.floor(i / 5)}`)).status, 200);
  }
  assert.equal((await appSignup("over@example.com", "10.0.1.1")).status, 503);
  assert.equal(calls.length, CONFIRM_DAILY_CAP);
});

test("a failed send is reported, not claimed as sent", async () => {
  resendStatus = 500;
  assert.equal((await appSignup("b@example.com")).status, 503);
});

test("the link's page confirms by posting its form; fetching it subscribes nobody", async () => {
  await appSignup("c@example.com");
  const link = linkFrom(calls[0]);
  const pageResp = await call(link.pathname + link.search);
  assert.equal(pageResp.status, 200);
  const html = await pageResp.text();
  assert.match(html, /c@example\.com/);
  assert.match(html, /<form id="confirm" method="post" action="\/confirm">/);
  // In a browser the page posts that form itself, so the reader isn't asked twice.
  assert.match(html, /f\.submit\(\)/);
  // Opening the link (as a mail scanner would) added nobody.
  assert.ok(!calls.some((c) => c.url.includes("/contacts")));

  const form = new URLSearchParams({ t: link.searchParams.get("t"), s: link.searchParams.get("s") });
  const done = await call("/confirm", { method: "POST", body: form });
  assert.equal(done.status, 200);
  assert.match(await done.text(), /subscribed/);
  const add = calls.find((c) => c.url.endsWith("/audiences/aud_1/contacts"));
  assert.deepEqual(add.body, { email: "c@example.com", unsubscribed: false });
});

test("a forged, altered or expired link is refused", async () => {
  const { t, s } = await signConfirmation("d@example.com", env);
  assert.equal(await verifyConfirmation(t, s, env), "d@example.com");
  // Another address's payload under this signature.
  const other = await signConfirmation("e@example.com", env);
  assert.equal(await verifyConfirmation(other.t, s, env), null);
  // Signed with another key.
  assert.equal(await verifyConfirmation(t, s, { ...env, RESEND_API_KEY: "re_other" }), null);
  // Past its week.
  const old = await signConfirmation("d@example.com", env, Date.now() - 8 * 86400 * 1000);
  assert.equal(await verifyConfirmation(old.t, old.s, env), null);
  assert.equal((await call(`/confirm?t=${t}&s=garbage`)).status, 400);
  const form = new URLSearchParams({ t: other.t, s });
  assert.equal((await call("/confirm", { method: "POST", body: form })).status, 400);
  assert.ok(!calls.some((c) => c.url.includes("/contacts")));
});

test("the website's route still requires Turnstile", async () => {
  const resp = await call("/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "CF-Connecting-IP": "9.9.9.9" },
    body: JSON.stringify({ email: "f@example.com" }),
  });
  assert.equal(resp.status, 400);
  assert.match((await resp.json()).error, /CAPTCHA/);
});
