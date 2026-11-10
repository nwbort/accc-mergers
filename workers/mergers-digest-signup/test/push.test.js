import { test } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, createVerify } from "node:crypto";
import { applyTopicChanges, MAX_CHANGES, parseTopicChanges, serviceAccount, signedJwt } from "../src/push.js";

const TOKEN = "dGVzdA:APA91b" + "x".repeat(100);

test("accepts the topic names fcm.py sends to", () => {
  const changes = parseTopicChanges({
    token: TOKEN,
    add: ["all", "list", "merger-MN-01016", "merger-WA-15020", "industry-G", "industry-_orphans"],
    remove: ["merger-MN-01016"],
  });
  assert.equal(changes.error, undefined);
  assert.deepEqual(changes.remove, ["merger-MN-01016"]);
});

test("refuses any other topic, a bad token, or too many changes", () => {
  for (const topic of ["news", "merger-MN-1", "industry-Z", "industry-4520", "/topics/all"]) {
    assert.ok(parseTopicChanges({ token: TOKEN, add: [topic] }).error, topic);
  }
  assert.ok(parseTopicChanges({ token: "short", add: ["all"] }).error);
  assert.ok(parseTopicChanges({ token: `${TOKEN}<`, add: ["all"] }).error);
  assert.ok(parseTopicChanges({ token: TOKEN }).error);
  assert.ok(parseTopicChanges({ token: TOKEN, add: "all" }).error);
  const many = Array.from({ length: MAX_CHANGES + 1 }, (_, i) => `merger-MN-${String(i).padStart(5, "0")}`);
  assert.ok(parseTopicChanges({ token: TOKEN, add: many }).error);
});

const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const account = {
  client_email: "push@example.iam.gserviceaccount.com",
  private_key: privateKey.export({ type: "pkcs8", format: "pem" }),
  private_key_id: "kid",
};

test("signs a JWT Google's token endpoint can verify", async () => {
  const jwt = await signedJwt(account, 1000);
  const [header, claims, signature] = jwt.split(".");
  const verify = createVerify("RSA-SHA256");
  verify.update(`${header}.${claims}`);
  assert.ok(verify.verify(publicKey, Buffer.from(signature, "base64url")));
  const decoded = JSON.parse(Buffer.from(claims, "base64url"));
  assert.equal(decoded.iss, account.client_email);
  assert.equal(decoded.exp, 4600);
});

test("reads the service account from the secret, if it's there", () => {
  assert.equal(serviceAccount({}), null);
  assert.equal(serviceAccount({ FCM_SERVICE_ACCOUNT: "{not json" }), null);
  assert.equal(serviceAccount({ FCM_SERVICE_ACCOUNT: JSON.stringify(account) }).client_email, account.client_email);
});

function fakeGoogle(topicResult = {}) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    if (url.includes("oauth2")) return Response.json({ access_token: "bearer", expires_in: 3600 });
    return Response.json({ results: [topicResult] });
  };
  return { calls, fetchImpl };
}

test("adds and removes one topic per call, keeping nothing", async () => {
  const { calls, fetchImpl } = fakeGoogle();
  const result = await applyTopicChanges(
    { token: TOKEN, add: ["all", "merger-MN-01016"], remove: ["industry-G"] },
    account,
    fetchImpl
  );
  assert.equal(result, "ok");
  const iid = calls.filter((c) => c.url.includes("iid"));
  assert.deepEqual(
    iid.map((c) => [c.url.split(":").pop(), JSON.parse(c.init.body).to]),
    [
      ["batchAdd", "/topics/all"],
      ["batchAdd", "/topics/merger-MN-01016"],
      ["batchRemove", "/topics/industry-G"],
    ]
  );
  assert.equal(iid[0].init.headers.Authorization, "Bearer bearer");
  assert.equal(iid[0].init.headers.access_token_auth, "true");
  assert.deepEqual(JSON.parse(iid[0].init.body).registration_tokens, [TOKEN]);
});

test("reports a token Google doesn't know", async () => {
  const { fetchImpl } = fakeGoogle({ error: "NOT_FOUND" });
  assert.equal(await applyTopicChanges({ token: TOKEN, add: ["all"], remove: [] }, account, fetchImpl), "invalid-token");
});
