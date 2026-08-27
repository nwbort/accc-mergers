"""Delete generated JSON files that a generator no longer produces.

Every per-item output directory (``mergers/``, ``parties/``, ``industries/``,
``timeline/``, ``questionnaires/``, ``noccs/``) is written file-by-file, so a
file that stops being generated is simply left behind and keeps being served.
That happens whenever the underlying set of ids shrinks — most often when a
party is folded into a canonical group in ``related_parties.json`` (the old
one-merger party page lingers), but also when a matter is deduped away, an
ANZSIC tag is corrected, or a paginated list loses its last page.

:func:`prune_stale_files` is called by each generator with the exact set of
names it just wrote, so pruning always reflects what the generator itself
considers current — no second copy of the naming rules to drift out of sync.
"""

from pathlib import Path


def prune_stale_files(
    directory: Path,
    keep: set[str],
    *,
    pattern: str = "*.json",
    exclude: tuple[str, ...] = (),
    label: str | None = None,
) -> list[str]:
    """Delete files in ``directory`` matching ``pattern`` that aren't in ``keep``.

    ``keep`` holds the file *names* (``"MN-60026.json"``) written by the
    current run. ``exclude`` is a tuple of globs for files another generator
    owns — ``mergers/`` is shared by the per-merger files and the paginated
    list, so neither may prune the other's output.

    Returns the names removed, sorted. An empty ``keep`` prunes nothing: a
    generator that wrote no files is far more likely to be looking at a failed
    or empty load than at a directory that genuinely should be emptied, and
    deleting the whole directory on that basis would take the site down.
    """
    directory = Path(directory)
    if not keep or not directory.is_dir():
        return []

    removed = []
    for path in sorted(directory.glob(pattern)):
        if not path.is_file() or path.name in keep:
            continue
        if any(path.match(glob) for glob in exclude):
            continue
        path.unlink()
        removed.append(path.name)

    if removed:
        where = label or directory.name
        print(f"  ✓ Pruned {len(removed)} stale file(s) from {where}/: {', '.join(removed)}")

    return removed
