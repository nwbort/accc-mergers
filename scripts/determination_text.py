"""
Clean PDF-extracted determination text for the CLI bundle.

PDFs are extracted with pdfplumber in parse_determination.py, which preserves
the raw layout newlines from the source document. The frontend strips those
newlines at render time in DeterminationExplanationSection.jsx, but the CLI
bundle is consumed by a tool that has no JavaScript layer, so the same
heuristics need to be applied here.

This module mirrors the JS heuristics so that fields under
``determination_table_content`` arrive at the CLI already-cleaned.

Heuristics for body text (in priority order):
  1. Hyphen before ``\\n`` -> word-wrap split, join with no space
     (e.g. "post-\\nacquisition" -> "post-acquisition").
  2. ``\\n`` followed by a bullet character (``•`` or ``▪``)
     -> real paragraph break (rendered as ``\\n\\n``).
  3. ``\\n`` followed by ``[a-z].`` -> real paragraph break (lettered list item).
  4. ``\\n`` preceded by ``.`` or ``)`` and followed by an uppercase letter
     -> real paragraph break.
  5. Anything else -> layout break, replaced with a single space.

Labels (the ``item`` column of the determination table) are pure layout text
and are collapsed to single-spaced strings.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

_LETTER_LIST = re.compile(r"^[a-z]\.")
_UPPERCASE = re.compile(r"^[A-Z]")
_BULLET_CHARS = ("•", "▪")  # • and ▪


def clean_explanation(text: str) -> str:
    """Apply the layout-vs-paragraph heuristics to PDF-extracted body text."""
    if not isinstance(text, str) or "\n" not in text:
        return text

    out: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        if ch != "\n":
            out.append(ch)
            continue
        before = text[i - 1] if i > 0 else ""
        after = text[i + 1 : i + 3] if i + 1 < n else ""

        if before == "-":
            continue
        if after[:1] in _BULLET_CHARS:
            out.append("\n\n")
            continue
        if _LETTER_LIST.match(after):
            out.append("\n\n")
            continue
        if before in (".", ")") and _UPPERCASE.match(after):
            out.append("\n\n")
            continue
        out.append(" ")

    return "".join(out)


def clean_label(text: str) -> str:
    """Collapse all whitespace in a table label (e.g. ``Explanation for\\ndetermination``)."""
    if not isinstance(text, str):
        return text
    return re.sub(r"\s+", " ", text).strip()


def clean_merger(merger: dict[str, Any]) -> dict[str, Any]:
    """Clean ``determination_table_content`` on every event of ``merger`` in place."""
    for event in merger.get("events") or []:
        for row in event.get("determination_table_content") or []:
            if not isinstance(row, dict):
                continue
            if "item" in row:
                row["item"] = clean_label(row["item"])
            if "details" in row:
                row["details"] = clean_explanation(row["details"])
    return merger


def _main(paths: list[str]) -> None:
    """Aggregate merger JSON files into a single cleaned array on stdout.

    Used by ``generate-cli-data.sh`` as a drop-in replacement for
    ``jq -s '.' <files>``.
    """
    result = []
    for path in paths:
        with open(path) as f:
            merger = json.load(f)
        clean_merger(merger)
        result.append(merger)
    json.dump(result, sys.stdout, separators=(",", ":"), ensure_ascii=False)


if __name__ == "__main__":
    _main(sys.argv[1:])
