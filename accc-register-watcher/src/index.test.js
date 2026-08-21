import { test } from "node:test";
import assert from "node:assert/strict";
import { isAllowedSender, extractMatterIds } from "./index.js";

test("rejects everything when ALLOWED_SENDERS is blank/unset", () => {
  assert.equal(isAllowedSender(["someone@example.com"], ""), false);
  assert.equal(isAllowedSender(["someone@example.com"], undefined), false);
});

test("allows an exact address match", () => {
  assert.equal(
    isAllowedSender(
      ["do-not-reply@accc.gov.au"],
      "do-not-reply@accc.gov.au"
    ),
    true
  );
});

test("allows a domain match via @domain entries", () => {
  assert.equal(
    isAllowedSender(["bulk-mailer@accc.gov.au"], "@accc.gov.au"),
    true
  );
});

test("rejects senders not in the allowlist", () => {
  assert.equal(
    isAllowedSender(["attacker@evil.example"], "do-not-reply@accc.gov.au"),
    false
  );
});

test("matches if any candidate (envelope or header from) is allowed", () => {
  assert.equal(
    isAllowedSender(
      ["bulk-mailer@example.com", "do-not-reply@accc.gov.au"],
      "do-not-reply@accc.gov.au"
    ),
    true
  );
});

test("extractMatterIds finds the ID from a real ACCC update email body", () => {
  const body = `
You have subscribed to receive email alerts when there's an update to
Acclime Corporate Services Australia – Polar 993 Group - WA-45025 in the
register.

Acclime Corporate Services Australia – Polar 993 Group
Acclime Corporate Services Australia Pty Ltd (Acclime), an indirect wholly
owned subsidiary of Acclime Holdings HK Limited and of Achronite Bidco Ltd,
proposes to acquire 100% of the shares in Polar 993 Limited.
`;
  assert.deepEqual(extractMatterIds(body), ["WA-45025"]);
});

test("extractMatterIds dedupes and preserves first-seen order across multiple matters", () => {
  const body = "Updates to MN-30022 and WA-05037, and again MN-30022 below.";
  assert.deepEqual(extractMatterIds(body), ["MN-30022", "WA-05037"]);
});

test("extractMatterIds returns an empty array when nothing matches", () => {
  assert.deepEqual(extractMatterIds("No matter references in this text."), []);
  assert.deepEqual(extractMatterIds(""), []);
  assert.deepEqual(extractMatterIds(undefined), []);
});

test("extractMatterIds ignores tokens embedded in tracking URLs", () => {
  const body =
    "https://accc.us10.list-manage.com/track/click?u=2d4af35bb8&id=fee568f528&e=471668ed0b";
  assert.deepEqual(extractMatterIds(body), []);
});
