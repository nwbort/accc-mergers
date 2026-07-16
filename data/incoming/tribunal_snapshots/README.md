# Tribunal snapshots (drop folder)

Drop bookmarklet-downloaded JSON snapshots here (see
`scripts/bookmarklet/README.md`) — e.g. via the GitHub web UI's "Add
file → Upload files", or a normal `git add`/commit/push. Any `*.json` file
added or changed here on `main` is picked up by the **Ingest Tribunal
Snapshots** workflow, which runs `scripts/ingest_tribunal_snapshot.py`
against it, folds the result into `data/processed/tribunal_appeals.json`
(and mirrors the linked PDFs into `data/raw/matters/`), and then deletes the
snapshot file — the commit it produces is the record of what happened.

If a file's `tribunal_url` doesn't match any `tribunal_appeals.json` entry
(typo, or a new matter that hasn't been added by hand yet), it's left in
place rather than deleted, and the workflow run is flagged so you can fix
the entry and let the next push retry it.

This file itself keeps the otherwise-empty directory tracked in git — it is
never picked up by the ingest workflow (only `*.json` files are).
