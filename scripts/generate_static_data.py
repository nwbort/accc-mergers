#!/usr/bin/env python3
"""Generate static JSON data files for Cloudflare Pages deployment.

Thin orchestrator: loads source data, enriches mergers once, then calls the
generators in :mod:`static_data.outputs`. All heavy lifting lives in the
``static_data`` package.

Output files:
  data/output/ (for offline analysis, not deployed):
  - mergers.json      - All mergers wrapped in {mergers: [...]} (full enriched data)

  merger-tracker/frontend/public/data/ (deployed to Cloudflare Pages):
  - mergers/{id}.json           - Individual merger files (one per merger)
  - mergers/list-page-{N}.json  - Paginated lightweight merger lists (50/page)
  - mergers/list-meta.json      - Pagination metadata for merger list
  - stats.json                  - Aggregated statistics
  - timeline-page-{N}.json      - Paginated timeline events (100/page)
  - timeline-meta.json          - Pagination metadata for timeline
  - industries.json             - ANZSIC codes with merger counts
  - industries/{code}.json      - Mergers per industry code
  - upcoming-events.json        - Future consultation/determination dates
  - commentary.json             - Mergers with user commentary
  - analysis.json               - Pre-computed analysis data
  - questionnaires/{id}.json    - Lazy-loaded questionnaire files
  - noccs/{id}.json             - Lazy-loaded NOCC summary files
"""

import json
from pathlib import Path

from static_data.enrichment import enrich_merger, link_related_mergers, link_similar_mergers
from static_data.loaders import (
    load_commentary,
    load_mergers,
    load_nocc_data,
    load_questionnaire_data,
    load_related_mergers,
    load_similar_mergers,
)
from static_data.outputs import (
    analysis,
    commentary as commentary_out,
    individual,
    industries,
    list as list_out,
    noccs,
    questionnaires,
    stats,
    timeline,
    upcoming_events,
)

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = REPO_ROOT / "merger-tracker" / "frontend" / "public" / "data"
DATA_OUTPUT_DIR = REPO_ROOT / "data" / "output"


def main():
    """Generate all static data files."""
    print("Loading mergers.json...")
    mergers = load_mergers()
    print(f"Loaded {len(mergers)} mergers")

    print("Loading commentary.json...")
    commentary = load_commentary()
    print(f"Loaded commentary for {len(commentary)} merger(s)" if commentary else "No commentary found")

    print("Loading questionnaire_data.json...")
    questionnaire_data = load_questionnaire_data()
    print(
        f"Loaded questionnaire data for {len(questionnaire_data)} merger(s)"
        if questionnaire_data else "No questionnaire data found"
    )

    print("Loading nocc_data.json...")
    nocc_data = load_nocc_data()
    print(
        f"Loaded NOCC data for {len(nocc_data)} merger(s)"
        if nocc_data else "No NOCC data found"
    )

    related_mergers = load_related_mergers()
    if related_mergers:
        print(f"Loaded {len(related_mergers) // 2} related merger pair(s)")

    similar_mergers = load_similar_mergers()
    if similar_mergers:
        print(f"Loaded similar merger suggestions for {len(similar_mergers)} merger(s)")

    print("Enriching mergers...")
    enriched = [
        enrich_merger(m, commentary, questionnaire_data, nocc_data) for m in mergers
    ]
    linked = link_related_mergers(enriched, related_mergers)
    if linked:
        print(f"  Linked {linked} related merger pairs")
    similar_linked = link_similar_mergers(enriched, similar_mergers)
    if similar_linked:
        print(f"  Linked similar mergers for {similar_linked} merger(s)")
    print(f"✓ Enriched {len(enriched)} mergers")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Full enriched mergers.json (offline analysis, not deployed)
    mergers_json_path = DATA_OUTPUT_DIR / "mergers.json"
    with open(mergers_json_path, 'w', encoding='utf-8') as f:
        json.dump({"mergers": enriched}, f, indent=2)
    print(f"✓ Generated {mergers_json_path}")

    # Small single-file outputs: call generator → write result
    single_file_outputs = [
        ("stats.json", stats.generate(enriched)),
        ("industries.json", industries.generate_index(enriched)),
        ("upcoming-events.json", upcoming_events.generate(enriched)),
        ("commentary.json", commentary_out.generate(enriched, commentary)),
        ("analysis.json", analysis.generate(enriched)),
    ]
    for filename, payload in single_file_outputs:
        out_path = OUTPUT_DIR / filename
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        print(f"✓ Generated {out_path}")

    print("\nGenerating individual merger files...")
    n = individual.generate(enriched, OUTPUT_DIR)
    print(f"✓ Generated {n} individual merger files in {OUTPUT_DIR / 'mergers'}")

    print("\nGenerating paginated list files...")
    pages = list_out.generate(enriched, OUTPUT_DIR, page_size=50)
    print(f"✓ Generated {pages} paginated list files (50 mergers/page)")

    print("\nGenerating paginated timeline files...")
    pages = timeline.generate(enriched, OUTPUT_DIR, page_size=100)
    print(f"✓ Generated {pages} paginated timeline files (100 events/page)")

    print("\nGenerating individual industry files...")
    n = industries.generate_detail_files(enriched, OUTPUT_DIR)
    print(f"✓ Generated {n} individual industry files in {OUTPUT_DIR / 'industries'}")

    if questionnaire_data:
        print("\nGenerating questionnaire files...")
        q_count = questionnaires.generate(questionnaire_data, OUTPUT_DIR)
        print(f"✓ Generated {q_count} questionnaire files in {OUTPUT_DIR / 'questionnaires'}")

    if nocc_data:
        print("\nGenerating NOCC files...")
        n_count = noccs.generate(nocc_data, OUTPUT_DIR)
        print(f"✓ Generated {n_count} NOCC files in {OUTPUT_DIR / 'noccs'}")

    print("\nDone!")


if __name__ == "__main__":
    main()
