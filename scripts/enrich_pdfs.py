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
import os
import sys

from scripts.cutoff import is_waiver_merger
from scripts.extract_mergers import (
    MATTERS_DIR,
    _load_frozen_events_mergers,
    run_pdf_enrichment,
)
from scripts.merger_filters import DEFAULT_MERGERS_JSON as MERGERS_JSON, load_mergers, save_mergers


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

    all_mergers_data = load_mergers(MERGERS_JSON)

    if not all_mergers_data:
        print(f"Warning: {MERGERS_JSON} is empty; nothing to enrich.", file=sys.stderr)
        sys.exit(0)

    frozen_events_mergers, _ = _load_frozen_events_mergers()

    # The enrichment sequence itself lives in extract_mergers.py, which runs the
    # identical pass when it is not handing the job over to this script.
    all_mergers_data = run_pdf_enrichment(all_mergers_data, frozen_events_mergers)

    # is_waiver may shift if enrichment changed a date that affects classification.
    for merger in all_mergers_data:
        merger['is_waiver'] = is_waiver_merger(merger)

    all_mergers_data.sort(key=lambda x: x.get('merger_id', ''))

    save_mergers(all_mergers_data, MERGERS_JSON)


if __name__ == "__main__":
    main()
