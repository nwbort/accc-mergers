#!/usr/bin/env python3
"""CI helper: print "true" if parsing a pending Phase 2 Notice PDF would need
the Tesseract OCR fallback, else "false".

Lets the pipeline workflow install Tesseract only on the runs that actually
need it, rather than unconditionally on every run.
"""

from scripts.extract_mergers import find_pending_phase2_notice_events
from scripts.merger_filters import load_mergers
from scripts.parse.parse_phase2_notice import phase2_notice_needs_ocr


def main():
    mergers = load_mergers(missing_ok=True)

    pending = find_pending_phase2_notice_events(mergers)
    needs_ocr = any(phase2_notice_needs_ocr(path) for _, _, path in pending)
    print('true' if needs_ocr else 'false')


if __name__ == '__main__':
    main()
