# Tests

Pytest suite for the data pipeline. Run from the repo root:

```bash
python -m pytest scripts/tests/
```

The pipeline is imported as a package (`from scripts.cutoff import ...`), so
the repo root has to be on `sys.path`; `conftest.py` puts it there, which is
why the suite also runs from any other working directory. Heavy transitive
dependencies (`pdfplumber`, `markdownify`, `requests`) are stubbed out so the
tests run without network or PDF tooling installed.

## Files

| File | Covers |
| --- | --- |
| `test_pipeline.py` | End-to-end extraction behaviour against fixture HTML. |
| `test_cutoff_io.py` | `cutoff.py` skip logic and CLI output. |
| `test_scrape_targets.py` | Fetch-list selection in `scrape/scrape_targets.py`: cutoff skipping, de-duplication, and recovery of matters the register listing drops. |
| `test_scrape_summary.py` | Run-summary rendering in `scrape/scrape_summary.py`: scraped merger IDs, changed pages, cutoff skips and fetch failures. |
| `test_generate_weekly_digest.py` | Bucketing + dedup vs. the prior week's digest. |
| `test_merger_filters.py` | Canonical loaders and predicates in `merger_filters.py`. |
| `test_resolver.py` | Duplicate-detection logic that backs `scripts/tools/resolver.py`. |
| `test_static_data_filters.py` | `generate/static_data/filters.py`. |
| `test_static_data_outputs.py` | Per-merger / list / stats writers in `generate/static_data/outputs/`. |
| `test_utils.py` | `date_utils.py` and `normalization.py`. |
| `test_commit_message_hook.py` | `.claude/hooks/check_commit_message.py` — which commit messages the Claude Code hook blocks. |
