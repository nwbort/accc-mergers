#!/usr/bin/env python3
"""Generate semantic embeddings for ACCC merger determinations.

Reads ``data/processed/mergers.json``, splits each merger into section-level
chunks (overview, parties, overlap, reasons, ...), embeds each chunk with a
``sentence-transformers`` model, and writes ``data/embeddings.json``.

The output is a JSON array of objects, one per chunk:

    {
      "merger_id": "MN-01016",
      "section": "reasons",
      "vector": [...768 floats...],
      "merger_name": "Asahi - Warehouse site ...",
      "parties": ["ASAHI HOLDINGS (AUSTRALIA) PTY LTD", "GPT PLATFORM PTY LIMITED"],
      "industry": [{"code": "121", "name": "Beverage Manufacturing"}, ...],
      "outcome": "Approved",
      "date": "2025-09-05",
      "year": 2025
    }

The chunk text itself is not stored in the output — it can be reconstructed
from the source data. Stage 1 only: this file is consumed by future search /
RAG features but produces no UI changes itself.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
INPUT_PATH = REPO_ROOT / "data" / "processed" / "mergers.json"
OUTPUT_PATH = REPO_ROOT / "data" / "embeddings.json"

# Single source of truth for the model. Swap to e.g.
# ``sentence-transformers/all-MiniLM-L6-v2`` (384 dims, ~80MB, no auth) for a
# lighter / unauthenticated alternative.
#
# EmbeddingGemma is gated: you must accept Google's Gemma license on
# huggingface.co/google/embeddinggemma-300m once, then expose an HF access
# token to the embed job as ``HF_TOKEN`` (env var or repo secret).
# Produces 768-dim Matryoshka-trained vectors.
MODEL_NAME = "google/embeddinggemma-300m"

# Mapping from normalised determination-table item names to canonical section
# keys. Multiple rows that map to the same section get combined into one chunk.
ITEM_TO_SECTION: dict[str, str] = {
    "notified acquisition": "overview",
    "acquisition": "overview",
    "parties to the acquisition": "parties",
    "overlap and relationship between the parties": "overlap",
    "overlap between the parties": "overlap",
    "relationship between the parties": "overlap",
    "industry background": "industry_background",
    "explanation for determination": "reasons",
    "reasons for determination": "reasons",
}

# Boilerplate / low-signal items that aren't worth their own chunk.
SKIP_ITEMS: set[str] = {
    "date of determination",
    "applications for review",
    "determination",
}

# Sections shorter than this many characters are skipped — usually a
# fragment from a malformed table row.
MIN_CHUNK_CHARS = 50


def _normalise_item(item: str) -> str:
    """Collapse whitespace and lowercase a determination-table item name."""
    return re.sub(r"\s+", " ", item or "").strip().lower()


def _classify_item(item: str) -> str | None:
    """Return the canonical section key for a table item, or ``None`` to skip.

    Handles common malformations like ``"explanation for determination •"``
    or ``"explanation for determination 1. 2."`` by prefix-matching after the
    direct lookup fails.
    """
    norm = _normalise_item(item)
    if not norm or norm in SKIP_ITEMS:
        return None
    if norm in ITEM_TO_SECTION:
        return ITEM_TO_SECTION[norm]
    for prefix, section in ITEM_TO_SECTION.items():
        if norm.startswith(prefix):
            return section
    return None


def _clean_text(text: str) -> str:
    """Tidy whitespace inside a chunk: collapse runs of blank space, strip."""
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    # Collapse runs of whitespace within a line, but keep paragraph breaks.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _determination_event(merger: dict) -> dict | None:
    """Return the event holding the determination table, if any."""
    for event in merger.get("events", []) or []:
        if event.get("determination_table_content"):
            return event
    return None


def _metadata(merger: dict) -> dict:
    """Extract the per-chunk metadata fields."""
    parties: list[str] = []
    for key in ("acquirers", "targets", "other_parties"):
        for party in merger.get(key, []) or []:
            name = (party or {}).get("name")
            if name:
                parties.append(name)

    date = (
        merger.get("determination_publication_date")
        or merger.get("effective_notification_datetime")
        or merger.get("original_notification_datetime")
        or ""
    )
    year: int | None = None
    iso_date: str | None = None
    if date:
        iso_date = date[:10]
        try:
            year = int(date[:4])
        except ValueError:
            year = None

    return {
        "merger_name": merger.get("merger_name") or "",
        "parties": parties,
        "industry": merger.get("anzsic_codes") or [],
        "outcome": merger.get("accc_determination") or "",
        "date": iso_date,
        "year": year,
    }


def build_chunks(mergers: Iterable[dict]) -> list[dict]:
    """Turn raw mergers into a list of ``{merger_id, section, text, ...meta}``.

    No embedding model is loaded here, so this is cheap and unit-testable.
    """
    chunks: list[dict] = []

    for merger in mergers:
        merger_id = merger.get("merger_id")
        if not merger_id:
            continue

        meta = _metadata(merger)
        sections: dict[str, list[str]] = {}

        event = _determination_event(merger)
        if event:
            for row in event.get("determination_table_content") or []:
                section = _classify_item(row.get("item", ""))
                if section is None:
                    continue
                details = _clean_text(row.get("details", ""))
                if details:
                    sections.setdefault(section, []).append(details)

        # Always include the human-written summary as part of the overview if
        # present — it's typically the cleanest description of the deal.
        description = _clean_text(merger.get("merger_description") or "")
        if description:
            sections.setdefault("overview", []).insert(0, description)

        if not sections:
            # Fall back: short / waiver-style entries with no determination
            # table and no description get no chunks rather than empty ones.
            continue

        for section, parts in sections.items():
            text = _clean_text("\n\n".join(parts))
            if len(text) < MIN_CHUNK_CHARS:
                continue
            chunks.append({
                "merger_id": merger_id,
                "section": section,
                "text": text,
                **meta,
            })

    return chunks


def embed_chunks(chunks: list[dict], model_name: str) -> list[dict]:
    """Embed each chunk's text and return the chunks with ``vector`` added.

    The ``text`` field is dropped from the output — it can be reconstructed
    from the source data and keeping it would multiply the file size.
    """
    # Imported lazily so chunk-building can be tested without the heavy deps.
    from sentence_transformers import SentenceTransformer

    print(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)

    texts = [c["text"] for c in chunks]
    print(f"Embedding {len(texts)} chunks...")
    # Asymmetric retrieval models (EmbeddingGemma, e5, bge) want different
    # prompt prefixes for documents vs queries. ``encode_document`` picks the
    # right one when configured on the model and falls back to plain
    # encoding otherwise — so this works for all three model families
    # without branching here.
    encode_fn = getattr(model, "encode_document", model.encode)
    vectors = encode_fn(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    out: list[dict] = []
    for chunk, vector in zip(chunks, vectors):
        record = {k: v for k, v in chunk.items() if k != "text"}
        record["vector"] = [round(float(x), 6) for x in vector.tolist()]
        out.append(record)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=MODEL_NAME,
        help=f"sentence-transformers model name (default: {MODEL_NAME})",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_PATH,
        help=f"input mergers JSON (default: {INPUT_PATH.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"output embeddings JSON (default: {OUTPUT_PATH.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build chunks and report counts but skip embedding / writing",
    )
    args = parser.parse_args()

    print(f"Loading mergers from {args.input}")
    mergers = json.loads(args.input.read_text())
    print(f"Loaded {len(mergers)} mergers")

    chunks = build_chunks(mergers)
    print(f"Built {len(chunks)} chunks across {len({c['merger_id'] for c in chunks})} mergers")
    by_section: dict[str, int] = {}
    for c in chunks:
        by_section[c["section"]] = by_section.get(c["section"], 0) + 1
    for section, count in sorted(by_section.items(), key=lambda x: -x[1]):
        print(f"  {section}: {count}")

    if args.dry_run:
        return

    records = embed_chunks(chunks, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records))
    size_kb = args.output.stat().st_size / 1024
    print(f"Wrote {len(records)} records to {args.output} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
