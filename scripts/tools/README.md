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

The passphrase comes from the `ADVISORS_PASSPHRASE` environment variable; if
it is unset and you are at a terminal, the tool prompts for it. Set it once
per shell session (keep it secret — it is the only thing protecting the
data, so store it in a password manager):

```bash
export ADVISORS_PASSPHRASE='choose-a-strong-passphrase'
python scripts/tools/advisors.py
# open http://127.0.0.1:8002
```

The tool reads/writes `advisors.json.enc` directly; commit that file after
editing. There is no committed `.enc` to start with — bootstrap it once from
the plaintext template (or any existing plaintext `advisors.json`):

```bash
export ADVISORS_PASSPHRASE='choose-a-strong-passphrase'
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
