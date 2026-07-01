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
 *                      for the ACCC mailing list (blank = accept any sender)
 */

const DISPATCH_EVENT_TYPE = "new_merger_detected";

function isAllowedSender(from, allowedSendersVar) {
  const allowed = (allowedSendersVar || "")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);

  if (allowed.length === 0) return true;

  const sender = (from || "").toLowerCase();
  return allowed.some((entry) =>
    entry.startsWith("@") ? sender.endsWith(entry) : sender === entry
  );
}

export default {
  async email(message, env, ctx) {
    const from = message.from;
    const subject = message.headers.get("subject") || "(no subject)";

    if (!isAllowedSender(from, env.ALLOWED_SENDERS)) {
      console.warn(`Ignoring email from unrecognised sender: ${from}`);
      return;
    }

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
