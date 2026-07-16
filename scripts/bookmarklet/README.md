# Tribunal scrape bookmarklet

An alternative to running `scripts/scrape_tribunal.py` locally. Instead of a
script fetching the matter page itself (and having to get past Cloudflare),
you load the page in your own browser as normal, click a bookmark, and it
downloads a JSON snapshot of that page's document table(s) — using the same
parsing rules as `parse_matter_page()` in `scrape_tribunal.py`, ported to
JS. `scripts/ingest_tribunal_snapshot.py` then folds that snapshot into
`data/processed/tribunal_appeals.json`.

Useful when even a local/residential run of `scrape_tribunal.py` gets
JS-challenged — a bookmarklet runs *inside* the page after your actual
browser has already solved that challenge, so it never makes a request of
its own for Cloudflare to see.

## 1. Install the bookmarklet

Open [`install.html`](install.html) in your browser (double-click the file,
or `open scripts/bookmarklet/install.html`) and drag the "Scrape tribunal
page" link to your bookmarks bar.

If your browser strips `javascript:` links when dragging, create a new
bookmark by hand instead and paste the contents of
[`bookmarklet.txt`](bookmarklet.txt) as its URL.

## 2. Capture a snapshot

Navigate to a tribunal matter page, e.g.
`https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026`, wait
for it to finish loading, then click the bookmark. It downloads a file like
`tribunal-act-1-of-2026.json` to your usual downloads folder, containing:

```json
{
  "tribunal_url": "https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026",
  "scraped_at": "2026-07-16T06:02:56.227Z",
  "documents": [
    {
      "date": "2026-07-15",
      "filed_by": "Coles",
      "description": "Application for Review",
      "confidentiality": "Non-confidential",
      "url": "https://www.competitiontribunal.gov.au/__data/assets/pdf_file/.../Application-for-Review.pdf"
    }
  ]
}
```

Repeat for each matter page you need to refresh — one snapshot per page.

## 3. Ingest it

```bash
pip install -r scripts/requirements.txt   # requests, beautifulsoup4, lxml
python scripts/ingest_tribunal_snapshot.py ~/Downloads/tribunal-act-1-of-2026.json
```

This matches the snapshot to the `tribunal_appeals.json` entry with the same
`tribunal_url`, merges its `documents[]` in (carrying over any existing
`url_gh` local-mirror path, same as `scrape_tribunal.py`), downloads each
linked file into `data/raw/matters/{merger_id}/`, and writes the JSON back.
It fails with a clear message (and lists the known `tribunal_url`s) if
nothing matches — that usually means the entry's `tribunal_url` needs
adding/fixing by hand first, or you're looking at the wrong matter page.

Pass multiple snapshot files at once, or `--dry-run` to preview without
writing, or `--no-download` to record metadata only:

```bash
python scripts/ingest_tribunal_snapshot.py snap1.json snap2.json
python scripts/ingest_tribunal_snapshot.py --dry-run snap.json
python scripts/ingest_tribunal_snapshot.py --no-download snap.json
```

Then commit as usual:

```bash
git add data/processed/tribunal_appeals.json data/raw/matters
git commit -m "Update scraped tribunal data"
git push
```

## Maintaining the bookmarklet

`scrape_tribunal_page.js` is the source of truth — readable and commented,
deliberately kept in step with the parsing functions in
`../scrape_tribunal.py` (see the comment at the top of each). If you change
the parsing rules on the Python side (new column keyword, date format,
etc.), update this file to match, then regenerate the installable copies:

```bash
python scripts/bookmarklet/build.py
```

which rewrites `bookmarklet.txt` and `install.html` from the current
`scrape_tribunal_page.js`. Commit all three together.
