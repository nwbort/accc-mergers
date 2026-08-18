# Admin tools

Interactive developer/admin tools that are **not** part of the automated
data pipeline. Each one boots a small FastAPI web UI that writes
directly back to the JSON files under `data/processed/`.

Run from the repo root.

## `resolver.py`

Web UI for resolving duplicate event entries within a merger record.
Reads `data/processed/mergers.json`, surfaces "certain" and "likely"
duplicates (using the detector in `scripts/detect_duplicates.py`), and
lets you delete individual events. Writes back to `mergers.json`.

```bash
python scripts/tools/resolver.py
# open http://127.0.0.1:8000
```

## `commentary.py`

Web UI for adding and editing the hand-authored commentary that the
frontend renders on `/commentary` and on each merger detail page.
Writes back to `data/processed/commentary.json`.

```bash
python scripts/tools/commentary.py
# open http://127.0.0.1:8001
```

## `related_parties.py`

Web UI for linking party identities that are the same real-world entity into
canonical *groups*. Reads every acquirer/target/other party across
`data/processed/mergers.json`, shows which are already grouped and which are
still ungrouped, and lets you select ungrouped parties to form a new group or
fold into an existing one (plus rename/delete groups and remove members).
Both the ungrouped-party list and the canonical-groups list have their own
search box (name, ABN, or group id). You can also select two or more
canonical groups (checkbox on each card) and **merge** them into one — members
are combined and de-duplicated, and you're prompted for the merged canonical
name. Writes back to `data/processed/related_parties.json`.

This is the hand-editing counterpart to `scripts/detect_related_parties.py`,
which suggests new groups daily via a pull request. The grouping rules — how a
party is matched to a group by ABN or normalised name — live in
`scripts/party_matching.py`; once a group is recorded, each matching party on a
merger detail page links to the register filtered by the group's canonical name.

```bash
python scripts/tools/related_parties.py
# open http://127.0.0.1:8003
```

To find *existing* canonical groups that look like the same entity and are
candidates to merge (e.g. two groups recorded separately before anyone
noticed they were the same company), run the detector in group-merge mode:

```bash
python scripts/detect_related_parties.py --group-merge-candidates
```

This clusters every member across all recorded groups using the same
identifier/name/name-variant/fuzzy signals as the normal detector, and reports
clusters that span more than one group id. As with the normal detector, the
`fuzzy` signal is the weakest — it clusters merely similar names sharing a
distinctive token, which can produce false positives (e.g. two unrelated
companies that each have a subsidiary named "... Operations Pty Ltd"), so
treat fuzzy hits as leads to check by hand in the tool, not groups to merge
automatically.

### Reviewing a batch of recent mergers by hand

To work through the register newest-first and decide new groupings from the
`merger_description` text (rather than from name-similarity signals), use
`../related_parties_batch.py` — a plain CLI, not a web UI:

```bash
# Mergers ranked 31st-40th by notification date, newest first
python scripts/related_parties_batch.py --start 31 --count 10

# Re-check specific mergers by id, e.g. after editing related_parties.json
python scripts/related_parties_batch.py --ids MN-50032,MN-60031
```

For each merger in range it prints every acquirer/target/other party plus
whether it already resolves to a canonical group (via the same
`party_matching.match_party` the site uses), and the full description — the
usual source of "X, a subsidiary of Y" / "together, Z" evidence. It only
*reports*; nothing is written. Once you've decided which groupings to apply,
either use this web UI, or write a short script against the same functions it
now shares with `related_parties_batch.py` — `party_matching.load_parties_doc`,
`.create_group`, `.add_members_to_group` and `.save_parties_doc` — so the file
is read, mutated and written back identically either way.

## `advisors.py`

Web UI for recording the legal (and other) advisors who worked on each
merger. For each advisor you capture a firm/advisor name, a type
(Legal / Financial / Economic / PR / Other), optional individuals and
notes, and the party (or parties) they acted for — chosen from the
merger's own acquirers/targets/other parties, or flagged as "party
unknown" when you only know the advisor worked on the deal.

Unlike `commentary.py`, this data is **backend only**: it is deliberately
not consumed by `generate_static_data.py` and is never published to
`merger-tracker/frontend/public/data`, so it is not loaded by the
front-end.

Because this repo is **public**, the advisor data is stored **encrypted at
rest** as `data/processed/advisors.json.enc` — a small JSON text envelope
(salt + Fernet ciphertext, all ASCII) that is safe to commit. The cleartext
`advisors.json` is gitignored and never committed. Encryption is handled by
`advisors_crypto.py`, which derives a key from a passphrase via
PBKDF2-HMAC-SHA256.

By default you just type the passphrase into the web UI's **unlock screen** —
nothing to set up first:

```bash
python scripts/tools/advisors.py
# open http://127.0.0.1:8002 and enter the passphrase to unlock
```

The passphrase is held only in the server's memory for that run (a `Lock`
button in the header clears it). It is the only thing protecting the data, so
keep it secret and store it in a password manager — it is **unrecoverable**.

To skip the unlock screen (scripts, or just convenience), set
`ADVISORS_PASSPHRASE` in the environment and the tool auto-unlocks at startup:

```bash
export ADVISORS_PASSPHRASE='choose-a-strong-passphrase'
python scripts/tools/advisors.py   # opens already unlocked
```

The tool reads/writes `advisors.json.enc` directly; commit that file after
editing. There is no committed `.enc` to start with — the first save creates
it. To bootstrap from the existing plaintext template instead, use the CLI
(which honours `ADVISORS_PASSPHRASE` or prompts):

```bash
python scripts/tools/advisors_crypto.py encrypt   # advisors.json -> advisors.json.enc
git add data/processed/advisors.json.enc           # commit the encrypted blob
```

To read the data outside the web UI, decrypt to stdout:

```bash
python scripts/tools/advisors_crypto.py decrypt            # print JSON
python scripts/tools/advisors_crypto.py decrypt --out /tmp/advisors.json
```

**GitHub Actions:** if a workflow ever needs this data, add the passphrase as
a repository secret and expose it as the env var — the same code decrypts:

```yaml
env:
  ADVISORS_PASSPHRASE: ${{ secrets.ADVISORS_PASSPHRASE }}
```

> ⚠️ The passphrase is unrecoverable. If you lose it, the encrypted data
> cannot be decrypted. To change it, `decrypt` with the old passphrase, then
> `encrypt` with the new one set in `ADVISORS_PASSPHRASE`.

## Dependencies

All three tools need `fastapi`, `uvicorn`, and `pydantic` on top of the base
pipeline requirements. `advisors.py` additionally needs `cryptography` (it is
pinned in `scripts/requirements.txt`):

```bash
pip install fastapi uvicorn pydantic cryptography
```
