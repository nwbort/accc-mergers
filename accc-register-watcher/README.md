# Cloudflare Email Worker — `accc-register-watcher`

Watches for emails from the ACCC's merger register update mailing list and
fires a `repository_dispatch` event (`new_merger_detected`) so the [Merger
Pipeline](../.github/workflows/pipeline.yml) workflow runs immediately,
instead of waiting for its next scheduled run (see the pipeline's
`on.repository_dispatch` trigger and the `custom_title` run-name, both
already wired up to receive this).

## How it fits together

```
ACCC mailing list
    ↓ email
Cloudflare Email Routing (custom address on your domain)
    ↓ routes to
accc-register-watcher (this Worker)
    ↓ POST /repos/{owner}/{repo}/dispatches
GitHub Actions — pipeline.yml (repository_dispatch: new_merger_detected)
```

## Setup

Steps 1–3 are one-time dashboard/account configuration outside this repo;
Cloudflare Email Routing rules aren't expressible in `wrangler.toml`.

1. **Enable Email Routing** on the Cloudflare zone you want to receive mail
   on (e.g. `mergers.fyi`): dashboard → your zone → Email → Email Routing →
   Enable.

2. **Deploy the Worker**:
   ```bash
   cd accc-register-watcher
   npm install
   npx wrangler deploy
   ```

3. **Set the GitHub token secret**. Create a fine-grained personal access
   token scoped to only this repository, with the **Contents: Read and
   write** repository permission (this is what the `/dispatches` endpoint
   requires — Metadata: read is auto-selected alongside it):
   ```bash
   npx wrangler secret put GITHUB_TOKEN
   ```

4. **Add a routing rule**: dashboard → Email → Email Routing → Routing
   rules → Create address → pick/create the address you'll subscribe to
   the ACCC mailing list (e.g. `accc-register@mergers.fyi`) → Action →
   **Send to a Worker** → select `accc-register-watcher`.

5. **Subscribe that address** to the ACCC's register update mailing list.
   Most mailing lists email a confirmation link before activating the
   subscription — the Worker only dispatches to GitHub, it doesn't put
   anything in an inbox you can read, so you won't see that email by
   default. To catch it:

   1. Under Email → Email Routing → **Destination addresses**, add and
      verify your own personal email address (Cloudflare emails you a
      verification link — click it there first).
   2. Go back to the routing rule from step 4 and temporarily change its
      action from **Send to a Worker** to **Send to an email** → your
      verified personal address.
   3. Submit the ACCC mailing list signup using the Cloudflare address.
      The confirmation email will forward straight to your inbox — open
      it and click the confirmation link.
   4. Switch the routing rule's action back to **Send to a Worker** →
      `accc-register-watcher`, so subsequent update emails go to the
      dispatch logic instead of your inbox.

6. `ALLOWED_SENDERS` in `wrangler.toml` is already set to the mailing
   list's real sender, `do-not-reply@accc.gov.au` — redeploy after any
   changes to it. It's checked against both the envelope sender and the
   `From:` header, so it stays effective even if the list sends through a
   third-party bulk mailer with a different envelope address.

## Verify

```bash
npx wrangler tail
```

Send (or wait for) an email to the configured address, then check the
"Merger Pipeline" workflow's Actions tab for a new run triggered by
`repository_dispatch`.

## Files

| File | Purpose |
| --- | --- |
| `src/index.js` | Worker `email()` handler — sender allowlist check, dispatches to GitHub. |
| `wrangler.toml` | Worker config: target repo, sender allowlist, secret documentation. |
