# Tests

Pytest suite for the data pipeline. Run from the repo root:

```bash
python -m pytest scripts/tests/
```

The tests add `scripts/` to `sys.path` and stub out heavy transitive
dependencies (`pdfplumber`, `markdownify`, `requests`) so they can run
without network or PDF tooling installed.

## Files

| File | Covers |
| --- | --- |
| `test_pipeline.py` | End-to-end extraction behaviour against fixture HTML. |
| `test_cutoff_io.py` | `cutoff.py` skip logic and CLI output. |
| `test_embed.py` | `embed.py` chunking and metadata serialisation. |
| `test_generate_weekly_digest.py` | Bucketing + dedup vs. the prior week's digest. |
| `test_merger_filters.py` | Canonical loaders and predicates in `merger_filters.py`. |
| `test_resolver.py` | Duplicate-detection logic that backs `scripts/tools/resolver.py`. |
| `test_static_data_filters.py` | `static_data/filters.py`. |
| `test_static_data_outputs.py` | Per-merger / list / stats writers in `static_data/outputs/`. |
| `test_utils.py` | `date_utils.py` and `normalization.py`. |
