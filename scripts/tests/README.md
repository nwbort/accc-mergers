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
| `test_atproto_lexicons.py` | The `fyi.mergers.*` schemas in `atproto/lexicons/`: filename/id agreement, the NSID authority, and that every `ref` resolves. |
| `test_atproto_records.py` | `atproto/records.py` — the merger → `fyi.mergers.matter` mapping, including the date-not-timestamp rule and the content digest. |
| `test_atproto_client.py` | `atproto/client.py` — the XRPC client's session, retries and rate-limit handling, against a fake transport. |
| `test_atproto_publish.py` | Incremental publishing in `atproto/publish_matters.py`, and the credential gate in `atproto/connect.py`. |
| `test_atproto_posts.py` | `atproto/post_bluesky.py` — which milestones are posted, the 300-character budget, and the seeding rule that stops a backfill. |
| `test_linkedin_posts.py` | `linkedin/post_linkedin.py` and its client — little-text escaping, the article card, seeding, read-back (and posting on when a token can't read back), token refresh. |
| `test_linkedin_share_links.py` | `linkedin/share_links.py` — the composer link, recording only what ntfy delivered, and standing down once API posting is on. |
| `test_scrape_tribunal.py` | `scrape/scrape_tribunal.py`'s parsing and download helpers. |
| `test_parse_phase2_notice.py` | `parse/parse_phase2_notice.py` — the referral details read off a Phase 2 Notice. |
| `test_determination_text.py` | `parse/determination_text.py`'s cleaning heuristics. |
| `test_questionnaire_cache.py` | The questionnaire parse cache, and the re-downloads the dedup step drops. |
| `test_questionnaire_probe.py` | `questionnaire_probe.py` — the guessed-questionnaire-URL probe and its use by the detector. |
| `test_detect_duplicates.py` | Event-level duplicate detection in `detect/detect_duplicates.py`. |
| `test_related_mergers.py` | Related-merger (waiver → notification) detection and linking. |
| `test_related_parties.py` | Related-party detection, matching and linking. |
| `test_related_parties_batch.py` | The `detect/related_parties_batch.py` batch-review CLI. |
| `test_fix_missing_notification_dates.py` | `fix_missing_notification_dates.py` — the missing-notification-date detector. |
| `test_public_benefit.py` | The public benefit phase, end to end through the pipeline. |
| `test_tribunal_appeals.py` | The Australian Competition Tribunal appeal overlay. |
| `test_judicial_reviews.py` | The Federal Court judicial review overlay. |
| `test_phase1_estimate.py` | `generate/static_data/phase1_estimate.py`. |
| `test_prenotification.py` | `generate/static_data/prenotification.py`. |
| `test_prune.py` | `generate/static_data/prune.py` — removal of no-longer-generated output files. |
| `test_list_output.py` | The merger list output (`mergers/list.json`). |
| `test_site_payload_trimming.py` | The trimming that separates deployed payloads from the full record. |
| `test_similar_mergers_cards.py` | The compact `similar_mergers` cards attached to each merger. |
| `test_phase2.py` | The Phase 2 tracker output (`phase2.json`). |
| `test_refiled.py` | The waiver-refile tracker output (`refiled-notifications.json`). |
| `test_serial_acquirers.py` | Serial-acquirer ("creeping acquisitions") detection. |
| `test_quarterly.py` | The quarterly report output (`quarterly.json`). |
| `test_quarterly_pdf.py` | The quarterly report PDFs (`generate/quarterly_pdf.py`). |
| `test_og_cards.py` | `generate/og_cards.py` — the generic link-preview cards. |
| `test_generate_sitemap.py` | The sitemap's party and industry inclusion rules. |
| `test_rss_feed.py` | `generate/generate_rss_feed.py`'s entry ids. |
| `test_build_cli_sqlite.py` | `generate/build_cli_sqlite.py`'s derived columns. |
| `test_send_weekly_email.py` | The weekly digest email (`send_weekly_email.py`). |
| `test_slug.py` | `slug.py`, pinned to `fixtures/slug-cases.json`. |
| `test_shard.py` | `shard.py`, pinned to `fixtures/shard-cases.json`. |
| `test_industry_division.py` | `industry_division.py`, pinned to `fixtures/industry-division-cases.json` and checked against the real ANZSIC tree. |
| `test_extension_titles.py` | The timeline-extension title rules, pinned to `fixtures/extension-title-cases.json`. |
| `test_check_deploy_assets.py` | `check_deploy_assets.py` — both Cloudflare Pages limits. |
| `test_compress_pdfs.py` | `compress_pdfs.py`'s preset-selection policy. |
| `test_check_watchlist.py` | The watchlist diff in `check_watchlist.py`. |
| `test_commit_message_hook.py` | `.claude/hooks/check_commit_message.py` — which commit messages the Claude Code hook blocks. |
