"""ANZSIC industry hierarchy.

The ACCC tags mergers with ANZSIC codes, mostly at the 4-digit *class* level
but occasionally at the 3-digit *group* or 2-digit *subdivision* level. ANZSIC
is a four-level tree:

    division     (one letter, e.g. ``A``)
      subdivision  (2 digits,   e.g. ``01``)
        group        (3 digits,   e.g. ``017``)
          class        (4 digits,   e.g. ``0172``)

The numeric levels nest by prefix (a class's group is its first 3 digits, its
subdivision its first 2); divisions map up from their subdivisions.

This module loads ``anzsic_codes.json`` (the official class list) and exposes a
``HIERARCHY`` of :class:`Node` objects keyed by code — one node per division,
subdivision, group and class — with parent/child/ancestor links so the data
pipeline can build a page for every node in the tree.
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "anzsic_codes.json"

# Ordered most-general → most-specific. Used for breadcrumbs and labelling.
LEVELS = ("division", "subdivision", "group", "class")


@dataclass
class Node:
    """A single node in the ANZSIC tree (division/subdivision/group/class)."""

    code: str
    name: str
    level: str
    parent_code: str | None = None
    child_codes: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def _raw_rows() -> list[dict]:
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def hierarchy() -> dict[str, Node]:
    """Return ``{code: Node}`` for every node in the ANZSIC tree.

    Built from the flat class list: each row names a class plus its group,
    subdivision and division, so walking the rows yields every node and its
    parent. Children are recorded in first-seen (i.e. code) order.
    """
    nodes: dict[str, Node] = {}

    def ensure(code: str, name: str, level: str, parent_code: str | None) -> None:
        node = nodes.get(code)
        if node is None:
            nodes[code] = Node(code=code, name=name, level=level, parent_code=parent_code)
            if parent_code is not None:
                parent = nodes.get(parent_code)
                if parent is not None and code not in parent.child_codes:
                    parent.child_codes.append(code)

    for row in _raw_rows():
        div = row["anzsic_division_code"]
        sub = row["anzsic_subdivision_code"]
        grp = row["anzsic_group_code"]
        cls = row["anzsic_class_code"]
        # Parents must exist before children so child lists populate correctly.
        ensure(div, row["anzsic_division"], "division", None)
        ensure(sub, row["anzsic_subdivision"], "subdivision", div)
        ensure(grp, row["anzsic_group"], "group", sub)
        ensure(cls, row["anzsic_class"], "class", grp)

    return nodes


def get(code: str) -> Node | None:
    """Look up a node by code, or ``None`` if the code isn't a known ANZSIC node."""
    return hierarchy().get(code)


def ancestors(code: str) -> list[Node]:
    """Return a node's ancestors, top-most (division) first, excluding itself.

    Empty if the code is unknown or is a division (which has no parent).
    """
    chain: list[Node] = []
    node = get(code)
    if node is None:
        return chain
    parent_code = node.parent_code
    while parent_code is not None:
        parent = get(parent_code)
        if parent is None:
            break
        chain.append(parent)
        parent_code = parent.parent_code
    chain.reverse()
    return chain


def descendant_class_codes(code: str) -> set[str]:
    """Return all class (leaf) codes at or below ``code``.

    For a class this is ``{code}``; for higher levels it's every leaf in the
    subtree. Empty if the code is unknown.
    """
    node = get(code)
    if node is None:
        return set()
    if node.level == "class":
        return {code}
    leaves: set[str] = set()
    stack = list(node.child_codes)
    while stack:
        child = get(stack.pop())
        if child is None:
            continue
        if child.level == "class":
            leaves.add(child.code)
        else:
            stack.extend(child.child_codes)
    return leaves


def subtree_codes(code: str) -> set[str]:
    """Return ``code`` plus every descendant code (all levels). Empty if unknown."""
    node = get(code)
    if node is None:
        return set()
    result = {code}
    stack = list(node.child_codes)
    while stack:
        cur = stack.pop()
        result.add(cur)
        child = get(cur)
        if child is not None:
            stack.extend(child.child_codes)
    return result
