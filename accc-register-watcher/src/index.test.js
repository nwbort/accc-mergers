import { test } from "node:test";
import assert from "node:assert/strict";
import { isAllowedSender } from "./index.js";

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
