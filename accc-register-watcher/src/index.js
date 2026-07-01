/**
 * Cloudflare Email Worker — ACCC register update watcher
 *
 * Bound (via Cloudflare Email Routing, see ../README.md) to a dedicated
 * inbox address subscribed to the ACCC's merger register update mailing
 * list. Every email received fires a `repository_dispatch` event so the
 * "Merger Pipeline" GitHub Actions workflow (.github/workflows/pipeline.yml)
 * runs immediately, instead of waiting for its next scheduled run.
 *
 * Required Worker secrets (set via `wrangler secret put`):
 *   GITHUB_TOKEN  — fine-grained PAT scoped to this repo only, with
 *                   "Contents: Read and write" permission (required by the
 *                   /dispatches endpoint).
 *
 * Required Worker vars (wrangler.toml):
 *   GITHUB_REPO      — "owner/repo" to dispatch to
 *   ALLOWED_SENDERS  — comma-separated allowlist of sender addresses/domains
 *                      for the ACCC mailing list (blank = accept any sender),
 *                      checked against both the envelope sender and the
 *                      From: header
 */

const DISPATCH_EVENT_TYPE = "new_merger_detected";

// Pulls the bare address out of either a plain "user@domain" string or a
// display-name form like "ACCC <user@domain>".
function extractAddress(value) {
  const match = (value || "").match(/<([^>]+)>/);
  return (match ? match[1] : value || "").trim().toLowerCase();
}

function isAllowedSender(candidates, allowedSendersVar) {
  const allowed = (allowedSendersVar || "")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);

  if (allowed.length === 0) return true;

  return candidates.some((candidate) =>
    allowed.some((entry) =>
      entry.startsWith("@") ? candidate.endsWith(entry) : candidate === entry
    )
  );
}

export default {
  async email(message, env, ctx) {
    // The envelope sender (message.from) and the From: header can differ for
    // bulk mail senders — check both against the allowlist.
    const envelopeFrom = extractAddress(message.from);
    const headerFrom = extractAddress(message.headers.get("from"));
    const subject = message.headers.get("subject") || "(no subject)";

    if (!isAllowedSender([envelopeFrom, headerFrom], env.ALLOWED_SENDERS)) {
      console.warn(
        `Ignoring email from unrecognised sender (envelope: ${envelopeFrom}, header: ${headerFrom})`
      );
      return;
    }

    const from = message.headers.get("from") || message.from;

    console.log(`ACCC register update email received from ${from}: ${subject}`);

    const resp = await fetch(
      `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "accc-register-watcher",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          event_type: DISPATCH_EVENT_TYPE,
          client_payload: {
            custom_title: `Merger pipeline (ACCC register update email)`,
            source: "accc-register-watcher",
            email_from: from,
            email_subject: subject,
            received_at: new Date().toISOString(),
          },
        }),
      }
    );

    if (!resp.ok) {
      const body = await resp.text().catch(() => "");
      console.error(
        `GitHub dispatch failed: ${resp.status} ${resp.statusText} — ${body}`
      );
    }
  },
};
