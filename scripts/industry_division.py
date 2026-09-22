"""Which file an ANZSIC node's page data is packed into.

``industries/`` used to hold one JSON file per ANZSIC node — 825 of them, one
for every division, subdivision, group and class in the tree. Cloudflare Pages
caps a deployment at 20,000 *files*, and most of those 825 were a couple of
kilobytes, so they cost as much of the budget as large ones. Worse, a merger
tagged at a class had its whole summary written four times over — into the
class, its group, its subdivision and its division — because every node lists
the mergers rolled up from its subtree.

The nodes are now packed one file per **division**: ``industries/B.json`` holds
every node under Mining, with each merger summary stored once and referenced by
id from the nodes that carry it. That is 19 files instead of 825, and about a
third of the bytes.

A division is the right seam because every node has exactly one division
ancestor, and because the frontend needs the *parent* node's durations to draw
its comparison chart — a node's parent is always in the same file, so the page
went from two fetches to one.

The catch is that the SPA is handed a bare code by the router (``/industries/
4520``) and has to know which file to ask for without consulting an index. That
is not derivable from the code itself: ``45`` lives under ``H`` only because of
how ANZSIC numbers its subdivisions. Hence the table below, which makes this
module load-bearing in the same way ``slug.py`` and ``shard.py`` are: it MUST
stay in sync with ``frontend/src/utils/industryDivision.js``. If the two
diverge the SPA fetches the wrong division file and every industry page 404s.
``fixtures/industry-division-cases.json`` pins the pair together; both test
suites read it.

Each division covers a contiguous, non-overlapping run of subdivisions, so a
19-row range table is exact rather than an approximation of a lookup — and
``scripts/tests/test_industry_division.py`` asserts it against the real ANZSIC
tree, so it cannot drift from ``anzsic_codes.json`` either. ANZSIC 2006 is a
frozen standard; the gaps between the ranges (61, 65, 68, 71, 74, 78-79, 83,
88, 93, 97-99) are subdivision numbers the standard simply does not use.
"""

# (division letter, first subdivision, last subdivision), inclusive.
# Keep in step with DIVISION_SUBDIVISION_RANGES in
# frontend/src/utils/industryDivision.js.
DIVISION_SUBDIVISION_RANGES: tuple[tuple[str, int, int], ...] = (
    ("A", 1, 5),    # Agriculture, Forestry and Fishing
    ("B", 6, 10),   # Mining
    ("C", 11, 25),  # Manufacturing
    ("D", 26, 29),  # Electricity, Gas, Water and Waste Services
    ("E", 30, 32),  # Construction
    ("F", 33, 38),  # Wholesale Trade
    ("G", 39, 43),  # Retail Trade
    ("H", 44, 45),  # Accommodation and Food Services
    ("I", 46, 53),  # Transport, Postal and Warehousing
    ("J", 54, 60),  # Information Media and Telecommunications
    ("K", 62, 64),  # Financial and Insurance Services
    ("L", 66, 67),  # Rental, Hiring and Real Estate Services
    ("M", 69, 70),  # Professional, Scientific and Technical Services
    ("N", 72, 73),  # Administrative and Support Services
    ("O", 75, 77),  # Public Administration and Safety
    ("P", 80, 82),  # Education and Training
    ("Q", 84, 87),  # Health Care and Social Assistance
    ("R", 89, 92),  # Arts and Recreation Services
    ("S", 94, 96),  # Other Services
)

# Where a code with no derivable division goes. Note that a code the ACCC has
# mistyped is *not* automatically one of these: "5400" looks like a class and
# resolves to division J without being a real ANZSIC node, so it is filed under
# J like everything else — placement follows this module's rule and nothing
# else, because that rule is all the frontend has to go on. Only a code the
# table can't place at all (an unused subdivision number, a slashed tag, junk)
# lands here. The file is written even when it holds nothing, so the fallback
# the frontend reaches for always exists.
ORPHAN_FILE_STEM = "_orphans"


def division_for(code: str) -> str | None:
    """Return the ANZSIC division letter ``code`` belongs to, or ``None``.

    ``None`` means the code is not part of the tree — either a division letter
    that doesn't exist, or a numeric code whose subdivision falls in one of the
    unused gaps, or something that isn't an ANZSIC code at all. Those live in
    the orphan file.

    >>> division_for("4520")
    'H'
    >>> division_for("H")
    'H'
    >>> division_for("9999") is None
    True
    """
    code = (code or "").strip()
    if len(code) == 1:
        return code if any(code == d for d, _, _ in DIVISION_SUBDIVISION_RANGES) else None
    if not (2 <= len(code) <= 4) or not code.isdigit():
        return None
    subdivision = int(code[:2])
    for division, low, high in DIVISION_SUBDIVISION_RANGES:
        if low <= subdivision <= high:
            return division
    return None


def division_file_stem(code: str) -> str:
    """File stem (no ``.json``) of the file holding ``code``'s node data."""
    return division_for(code) or ORPHAN_FILE_STEM


def division_file_name(code: str) -> str:
    """File name holding ``code``'s node data, e.g. ``"H.json"``."""
    return f"{division_file_stem(code)}.json"


def all_file_names() -> list[str]:
    """Every file the industries directory holds: one per division, plus orphans."""
    return [f"{d}.json" for d, _, _ in DIVISION_SUBDIVISION_RANGES] + [
        f"{ORPHAN_FILE_STEM}.json"
    ]
