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
# open http://127.0.0.1:8000
```

## Dependencies

Both tools need `fastapi`, `uvicorn`, and `pydantic` on top of the base
pipeline requirements:

```bash
pip install fastapi uvicorn pydantic
```
