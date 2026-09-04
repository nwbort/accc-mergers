# Push notifications (ntfy)

Several workflows in this repo open something a human has to look at — a review
PR full of candidate related mergers, a candidate party grouping, a tracking
issue. GitHub will email about all of them, but that mailbox also carries every
pipeline commit and every dependabot bump, so the ones that actually need a
decision get lost.

[ntfy](https://ntfy.sh) is the escape hatch: the workflow POSTs a message to a
topic, and the ntfy Android/iOS app subscribed to that topic shows it as a push
notification. No account, no server to run.

## Setup

1. Install the ntfy app ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy),
   [iOS](https://apps.apple.com/us/app/ntfy/id1625396347), or
   [the web app](https://ntfy.sh/app)).
2. Pick a topic name and subscribe to it in the app. **Make it long and
   unguessable** — something like `accc-mergers-a7f3c1d9b2` rather than
   `accc-mergers`. On the public ntfy.sh server the topic name is the only
   access control there is: anyone who knows it can read your notifications
   *and* publish to them.
3. Add it to the repo as a secret named `NTFY_TOPIC`
   (Settings → Secrets and variables → Actions → New repository secret).

That is the whole setup. Two optional extras:

| Name | Kind | Purpose |
|------|------|---------|
| `NTFY_TOPIC` | secret | The topic to publish to. **Without it every notification is skipped** — the workflows still run and still open their PRs. |
| `NTFY_TOKEN` | secret | Bearer token for a [reserved or protected topic](https://docs.ntfy.sh/publish/#authentication). Not needed for an ordinary public ntfy.sh topic. |
| `NTFY_SERVER` | variable | Base URL of a self-hosted ntfy instance. Defaults to `https://ntfy.sh`. |

A missing `NTFY_TOPIC` is a skip, not a failure, so forks and anyone
re-running these workflows without the secret get the same behaviour as before
this existed. A delivery that is attempted and fails logs a warning and lets
the run continue — a data pipeline should not go red because a phone could not
be reached.

## What sends a notification

| Trigger | Priority | Notes |
|---------|----------|-------|
| Duplicate events review PR opened, or updated with new duplicates | default (3) | `pipeline.yml` |
| Related mergers review PR opened, or updated with new candidates | default (3) | `pipeline.yml` |
| Related parties review PR opened, or updated with new candidates | default (3) | `pipeline.yml` |
| Exact-match waiver refile auto-merged into `main` | 4 (bypasses batching) | `pipeline.yml` — this one merged itself without review |
| Missing notification dates PR opened, or updated with new candidates | default (3) | `fix-missing-notification-dates.yml` |

Tapping a notification opens the PR (or, for the auto-merge, the
`needs-verification` issue list).

### Why "or updated with new candidates" and not "or updated"

`pipeline.yml` runs four or five times a weekday, and each run re-detects
everything the open review PRs are already carrying — an unmerged suggestion
is, by definition, still a valid suggestion. Notifying on every refresh would
mean five identical pushes a day for one finding.

So `.github/actions/detection-pr` fingerprints the suggestions themselves: the
content lines the fix branch adds to or removes from its base, hashed. It parks
that hash in an HTML comment at the bottom of the PR body
(`<!-- detection-fingerprint: … -->`, invisible when rendered) and compares
against it on the next run. A push goes out when the PR is newly opened or when
the fingerprint moved — i.e. when there is genuinely something new in it.

The fingerprint deliberately covers only the suggested *lines*, not the branch
tip. The fix branches are rebuilt from the latest `main` on every run, so their
tree moves whenever `main`'s copy of the data file moves — which for
`mergers.json` is every pipeline run, and would make every run look "new".

## Adding a notification somewhere else

`.github/actions/ntfy` is a plain composite action; wire it into any workflow:

```yaml
      - name: Notify (ntfy)
        if: steps.something.outputs.worth_knowing == 'true'
        uses: ./.github/actions/ntfy
        with:
          topic: ${{ secrets.NTFY_TOPIC }}
          token: ${{ secrets.NTFY_TOKEN }}
          server: ${{ vars.NTFY_SERVER || 'https://ntfy.sh' }}
          title: Deployment over the file cap
          message: The next Pages upload will be refused.
          tags: warning
          priority: '5'
          click: ${{ github.server_url }}/${{ github.repository }}/issues
```

The three `topic`/`token`/`server` lines are boilerplate on every call —
secrets are not visible inside a composite action, so they have to be passed
in explicitly.

Inputs: `topic`, `message` (required), `title`, `tags` (comma-separated;
[emoji shortcodes](https://docs.ntfy.sh/emojis/) render as the notification's
icon), `priority` (1–5), `click` (URL opened on tap), `actions` (raw JSON array
of [action buttons](https://docs.ntfy.sh/publish/#action-buttons)), `server`,
`token`.

Candidates worth considering if the current set proves too quiet:
`check-deploy-assets.yml`'s two tracking issues (both guard failures that
otherwise leave every workflow green while the site silently stops updating),
and a `pipeline.yml` job failure.

Keep priority 4 and 5 for things genuinely worth interrupting for — on Android
they bypass notification batching and, at 5, vibrate insistently.
