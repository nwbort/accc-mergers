#!/usr/bin/env python3
"""Generate semantic embeddings for ACCC merger determinations.

Reads ``data/processed/mergers.json``, splits each merger into section-level
chunks (overview, parties, overlap, reasons, ...), embeds each chunk with a
``sentence-transformers`` model, and writes two companion files:

  - ``data/embeddings.json`` — metadata, one record per line, JSON array.
    Diffable in git; consumers read this for the section labels / merger
    info.
  - ``data/embeddings.bin`` — packed little-endian Float32 vectors,
    contiguous, in the same order as the JSON. Aligns to ``dim`` floats
    per record. The frontend reads it as a single ``ArrayBuffer`` and
    views slices as ``Float32Array`` rows.

A metadata record looks like:

    {
      "merger_id": "MN-01016",
      "section": "reasons",
      "merger_name": "Asahi - Warehouse site ...",
      "parties": ["ASAHI HOLDINGS (AUSTRALIA) PTY LTD", "GPT PLATFORM PTY LIMITED"],
      "industry": [{"code": "121", "name": "Beverage Manufacturing"}, ...],
      "outcome": "Approved",
      "date": "2025-09-05",
      "year": 2025,
      "hash": "ab12cd34ef567890"
    }

The ``hash`` field is a content fingerprint that lets repeat runs reuse
vectors for chunks whose text didn't change — only new or modified chunks
are sent to the model.

The chunk text itself is not stored in the output — it can be reconstructed
from the source data. Stage 1 only: these files are consumed by future
search / RAG features but produce no UI changes themselves.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
INPUT_PATH = REPO_ROOT / "data" / "processed" / "mergers.json"
OUTPUT_PATH = REPO_ROOT / "data" / "embeddings.json"
# Vectors are written separately as a packed Float32Array. The JSON file is
# diff-friendly (one record per line) and the binary file is small and fast
# to load on the frontend (single ``ArrayBuffer`` + ``Float32Array`` view).
OUTPUT_BIN_PATH = REPO_ROOT / "data" / "embeddings.bin"

# Single source of truth for the model. Swap to e.g.
# ``sentence-transformers/all-MiniLM-L6-v2`` (384 dims, ~80MB, no auth) for a
# lighter / unauthenticated alternative.
#
# EmbeddingGemma is gated: you must accept Google's Gemma license on
# huggingface.co/google/embeddinggemma-300m once, then expose an HF access
# token to the embed job as ``HF_TOKEN`` (env var or repo secret).
# Produces 768-dim Matryoshka-trained vectors that we truncate to
# ``EMBEDDING_DIM`` below.
MODEL_NAME = "google/embeddinggemma-300m"

# EmbeddingGemma is trained with Matryoshka Representation Learning, so
# truncating the 768-dim vector to a smaller prefix and renormalising
# preserves most of the retrieval quality. 256 dims gives ~3x smaller
# embeddings.bin (and a smaller browser download for the future search UI)
# at near-full quality. Set to ``None`` to keep the model's native
# dimension. The chosen dim is mixed into the content hash so changes
# invalidate the cache automatically.
EMBEDDING_DIM: int | None = 256

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

# Length of the truncated sha1 hash stored on each record. 16 hex chars
# (64 bits) makes accidental collisions vanishingly unlikely at our scale
# (~600 chunks) while keeping the JSON small.
HASH_LEN = 16


def _content_hash(model_name: str, dim: int | None, text: str) -> str:
    """Stable hash for caching embeddings.

    Mixes in both the model name and the truncation dim so that swapping
    ``MODEL_NAME`` or ``EMBEDDING_DIM`` invalidates every record on the
    next run — different models / dims produce different vectors and
    mixing them in one file would corrupt similarity scores.
    """
    h = hashlib.sha1()
    h.update(model_name.encode("utf-8"))
    h.update(b"\n")
    h.update(str(dim if dim is not None else "").encode("utf-8"))
    h.update(b"\n")
    h.update(text.encode("utf-8"))
    return h.hexdigest()[:HASH_LEN]


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


def plan_embedding(
    chunks: list[dict],
    existing: list[dict] | None,
    model_name: str,
    dim: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """Split current chunks into (reusable_records, chunks_needing_embedding).

    Each chunk gets a content hash that mixes in the model name, then we
    look it up in the cache built from ``existing``. A cache hit means the
    chunk text is byte-identical to the last run for the same model — its
    vector can be reused verbatim. A miss means we need to call the model.

    Records in ``existing`` whose ``(merger_id, section)`` no longer appear
    in ``chunks`` are silently dropped (e.g. a merger was withdrawn, or a
    section's text fell below ``MIN_CHUNK_CHARS``).
    """
    cache: dict[tuple[str, str], dict] = {}
    if existing:
        for record in existing:
            key = (record.get("merger_id"), record.get("section"))
            if record.get("hash") and record.get("vector") and all(key):
                cache[key] = record

    reused: list[dict] = []
    pending: list[dict] = []
    for chunk in chunks:
        chunk["hash"] = _content_hash(model_name, dim, chunk["text"])
        cached = cache.get((chunk["merger_id"], chunk["section"]))
        if cached and cached.get("hash") == chunk["hash"]:
            # Reuse the vector but refresh the metadata fields — the merger's
            # ``outcome`` / ``date`` / parties may have changed even when the
            # section text didn't (e.g. a status update on the merger row).
            refreshed = {k: v for k, v in chunk.items() if k != "text"}
            refreshed["vector"] = cached["vector"]
            reused.append(refreshed)
        else:
            pending.append(chunk)
    return reused, pending


def embed_chunks(
    chunks: list[dict],
    model_name: str,
    existing: list[dict] | None = None,
    dim: int | None = None,
) -> list[dict]:
    """Embed each chunk's text and return the chunks with ``vector`` added.

    Reuses vectors from ``existing`` for chunks whose text, model, and dim
    haven't changed; only newly added or modified chunks are sent to the
    model. The ``text`` field is dropped from the output — it can be
    reconstructed from the source data and keeping it would multiply the
    file size.
    """
    reused, pending = plan_embedding(chunks, existing, model_name, dim)
    print(f"Reusing {len(reused)} cached vectors, embedding {len(pending)} new/changed")

    fresh: list[dict] = []
    if pending:
        # Imported lazily so chunk-building / cache logic can be tested
        # without the heavy deps.
        from sentence_transformers import SentenceTransformer

        print(f"Loading model: {model_name} (truncate_dim={dim})")
        # ``truncate_dim`` is applied by sentence-transformers after the
        # forward pass; with ``normalize_embeddings=True`` the truncated
        # vectors are renormalised so they're still unit-length.
        model = SentenceTransformer(model_name, truncate_dim=dim)

        texts = [c["text"] for c in pending]
        # Asymmetric retrieval models (EmbeddingGemma, e5, bge) want
        # different prompt prefixes for documents vs queries.
        # ``encode_document`` picks the right one when configured on the
        # model and falls back to plain encoding otherwise — so this works
        # for all three model families without branching here.
        encode_fn = getattr(model, "encode_document", model.encode)
        vectors = encode_fn(
            texts,
            batch_size=32,
            show_progress_bar=True,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        for chunk, vector in zip(pending, vectors):
            record = {k: v for k, v in chunk.items() if k != "text"}
            record["vector"] = [float(x) for x in vector.tolist()]
            fresh.append(record)

    combined = reused + fresh
    # Sort by (merger_id, section) so the on-disk order is stable across
    # runs — without this, every run would shuffle the file and produce a
    # massive but meaningless git diff.
    combined.sort(key=lambda r: (r["merger_id"], r["section"]))
    return combined


def _format_metadata(records: list[dict]) -> str:
    """Serialise the metadata as a JSON array with one record per line.

    Excludes the ``vector`` field — vectors live in the companion ``.bin``
    file. Keeping the JSON metadata-only makes git diffs show only the
    fields humans actually care about (merger renamed, outcome updated,
    new chunk hash) rather than 256 floats per record.
    """
    if not records:
        return "[]\n"
    cleaned = [{k: v for k, v in r.items() if k != "vector"} for r in records]
    lines = [json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in cleaned]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def _pack_vectors(records: list[dict]) -> bytes:
    """Pack record vectors as little-endian Float32, contiguous, in order.

    The frontend reads this as a single ``ArrayBuffer`` and views slices of
    ``dim`` floats as ``Float32Array`` rows aligned to the metadata JSON.
    All records must share the same dimension (the embedder enforces this).
    """
    if not records:
        return b""
    dim = len(records[0]["vector"])
    flat: list[float] = []
    for r in records:
        if len(r["vector"]) != dim:
            raise ValueError(
                f"Inconsistent vector dim: {r['merger_id']}/{r['section']} "
                f"has {len(r['vector'])}, expected {dim}"
            )
        flat.extend(r["vector"])
    return struct.pack(f"<{len(flat)}f", *flat)


def _load_existing(json_path: Path, bin_path: Path) -> list[dict] | None:
    """Inverse of the ``_format_metadata`` / ``_pack_vectors`` split.

    Returns records with their ``vector`` field rehydrated from the binary
    file, or ``None`` if either file is missing / unparseable.
    """
    if not json_path.exists():
        return None
    try:
        records = json.loads(json_path.read_text())
    except json.JSONDecodeError:
        print(f"Could not parse {json_path}, ignoring cache")
        return None
    if not records:
        return []
    if not bin_path.exists():
        print(f"{bin_path} missing, ignoring cache")
        return None
    raw = bin_path.read_bytes()
    floats_per_record, remainder = divmod(len(raw) // 4, len(records))
    if remainder != 0:
        print(f"{bin_path} size doesn't divide evenly into {len(records)} records, ignoring cache")
        return None
    flat = struct.unpack(f"<{len(raw) // 4}f", raw)
    for i, record in enumerate(records):
        start = i * floats_per_record
        record["vector"] = list(flat[start:start + floats_per_record])
    return records


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
        help=f"output metadata JSON (default: {OUTPUT_PATH.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--bin-output",
        type=Path,
        default=OUTPUT_BIN_PATH,
        help=f"output packed Float32 vectors (default: {OUTPUT_BIN_PATH.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=EMBEDDING_DIM,
        help=f"truncate to this Matryoshka dim, or 0 for native (default: {EMBEDDING_DIM})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build chunks and report counts but skip embedding / writing",
    )
    args = parser.parse_args()
    dim: int | None = args.dim if args.dim and args.dim > 0 else None

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

    existing = _load_existing(args.output, args.bin_output)
    if existing is not None:
        print(f"Loaded {len(existing)} existing records from {args.output} + {args.bin_output.name}")

    records = embed_chunks(chunks, args.model, existing=existing, dim=dim)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_format_metadata(records))
    args.bin_output.write_bytes(_pack_vectors(records))

    json_kb = args.output.stat().st_size / 1024
    bin_kb = args.bin_output.stat().st_size / 1024
    actual_dim = len(records[0]["vector"]) if records else 0
    print(f"Wrote {len(records)} records ({actual_dim}-dim): "
          f"{args.output.name} {json_kb:.1f} KB, {args.bin_output.name} {bin_kb:.1f} KB")


if __name__ == "__main__":
    main()
