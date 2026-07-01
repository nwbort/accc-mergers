#!/usr/bin/env python3
"""Phase-2 enrichment: parse questionnaire / NOCC / Phase 2 Notice PDFs into
existing mergers.

The pipeline runs ``extract_mergers.py --skip-pdf-enrich`` first to download
HTML pages and attachment files (PDF and DOCX), then converts any new DOCX
files to PDF, then runs this script to:

1. Parse questionnaire PDFs and update each merger's consultation deadline
   if it was missing.
2. Parse NOCC summary PDFs into the standalone manifest.
3. Parse pending Phase 2 Notice PDFs into their events.
4. Auto-fix questionnaire events whose date is missing on the ACCC page.

Splitting these steps out of ``extract_mergers.py`` lets the workflow run
the expensive HTML parse / download phase once, do DOCX conversion in the
middle, then run the cheap PDF-parse phase once — instead of running the
full extract twice.
"""

import argparse
import json
import os
import sys

from cutoff import is_waiver_merger
from extract_mergers import (
    MATTERS_DIR,
    _load_frozen_events_mergers,
    auto_fix_missing_event_dates,
    detect_inferred_phase_2,
    enrich_with_questionnaire_data,
    extract_nocc_data,
    extract_phase2_notice_data,
)

MERGERS_JSON = 'data/processed/mergers.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    if not os.path.isdir(MATTERS_DIR):
        print(f"Error: Directory '{MATTERS_DIR}' not found.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(MERGERS_JSON):
        print(
            f"Error: {MERGERS_JSON} does not exist. Run extract_mergers.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(MERGERS_JSON, 'r', encoding='utf-8') as f:
        all_mergers_data = json.load(f)

    if not all_mergers_data:
        print(f"Warning: {MERGERS_JSON} is empty; nothing to enrich.", file=sys.stderr)
        sys.exit(0)

    frozen_events_mergers, _ = _load_frozen_events_mergers()

    # 1. Questionnaire enrichment (consultation deadlines).
    all_mergers_data = enrich_with_questionnaire_data(all_mergers_data)

    # 2. NOCC manifest.
    extract_nocc_data()

    # 2b. Parse pending Phase 2 Notice PDFs into their events.
    extract_phase2_notice_data(all_mergers_data)

    # 3. Auto-fix catchable events (questionnaire, remedy offer) whose date is missing.
    auto_fix_missing_event_dates(all_mergers_data, frozen_events_mergers)

    # 4. Detect mergers carrying a Phase 2 notice whose ACCC stage still shows
    #    Phase 1 (the site treats these as Phase 2; the pipeline opens/closes a
    #    tracking issue accordingly). Reads the genuine stage from mergers.json.
    detect_inferred_phase_2(all_mergers_data)

    # is_waiver may shift if enrichment changed a date that affects classification.
    for merger in all_mergers_data:
        merger['is_waiver'] = is_waiver_merger(merger)

    all_mergers_data.sort(key=lambda x: x.get('merger_id', ''))

    with open(MERGERS_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_mergers_data, f, indent=2)


if __name__ == "__main__":
    main()
