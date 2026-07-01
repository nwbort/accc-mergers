#!/usr/bin/env python3
"""CI helper: print "true" if parsing a pending Phase 2 Notice PDF would need
the Tesseract OCR fallback, else "false".

Lets the pipeline workflow install Tesseract only on the runs that actually
need it, rather than unconditionally on every run.
"""

import json

from extract_mergers import find_pending_phase2_notice_events
from parse_phase2_notice import phase2_notice_needs_ocr

MERGERS_JSON = 'data/processed/mergers.json'


def main():
    try:
        with open(MERGERS_JSON, encoding='utf-8') as f:
            mergers = json.load(f)
    except FileNotFoundError:
        mergers = []

    pending = find_pending_phase2_notice_events(mergers)
    needs_ocr = any(phase2_notice_needs_ocr(path) for _, _, path in pending)
    print('true' if needs_ocr else 'false')


if __name__ == '__main__':
    main()
