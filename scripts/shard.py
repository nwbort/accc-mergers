"""Bucket assignment for the sharded party detail files.

``parties/`` used to hold one JSON file per party. Those files are tiny (a
kilobyte apiece) but there is one per party, and Cloudflare Pages caps a
deployment at 20,000 files — a limit counted in *files*, not bytes, so ~2,200
one-kilobyte party files cost as much of the budget as ~2,200 large ones. The
per-party payloads are now packed into a fixed set of ``shard-{nn}.json``
buckets instead, keyed by party id.

The bucket is derived from the id alone so a client can compute it without
consulting an index — no extra round trip on the way to a party page. That
makes this algorithm load-bearing in the same way ``slug.py`` is: it MUST stay
in sync with the JavaScript implementation in ``frontend/src/utils/shard.js``
(used by the SPA to pick the bucket to fetch, and by ``frontend/prerender.js``
to walk them at build time). If the two diverge the SPA fetches the wrong
bucket and every party page 404s. ``fixtures/shard-cases.json`` pins the pair
together; both test suites read it.

FNV-1a is used rather than a language built-in because Python's ``hash()`` is
salted per process and JavaScript has none — the mapping has to be identical
across languages, runs and versions. It is not a security primitive and is not
used as one; it only needs to be stable and to spread ids evenly.
"""

# Number of buckets. Keep it a power of two no greater than 256 so the bucket
# index is exactly one byte and the two-hex-digit file name below is total.
#
# Changing this reshuffles every party into a different bucket. That is safe
# (the generator rewrites all buckets and prunes the old names, and the
# frontend derives the same value) but it invalidates every cached bucket and
# rewrites the whole directory in one commit, so it should be a deliberate
# choice rather than a tweak. 256 buckets holds ~2,200 parties at ~9 KB each
# and stays comfortable as that grows.
SHARD_COUNT = 256

_FNV_OFFSET_BASIS_32 = 0x811C9DC5
_FNV_PRIME_32 = 0x01000193
_UINT32_MASK = 0xFFFFFFFF


def fnv1a_32(text: str) -> int:
    """32-bit FNV-1a hash of ``text``'s UTF-8 bytes."""
    h = _FNV_OFFSET_BASIS_32
    for byte in str(text).encode("utf-8"):
        h ^= byte
        h = (h * _FNV_PRIME_32) & _UINT32_MASK
    return h


def party_shard(party_id: str) -> int:
    """Bucket index (0 .. ``SHARD_COUNT`` - 1) holding ``party_id``'s record."""
    return fnv1a_32(party_id or "") % SHARD_COUNT


def party_shard_name(party_id: str) -> str:
    """File name of the bucket holding ``party_id``, e.g. ``shard-c5.json``."""
    return shard_name(party_shard(party_id))


def shard_name(index: int) -> str:
    """File name for bucket ``index``, e.g. ``shard-00.json``."""
    return f"shard-{index:02x}.json"


def all_shard_names() -> list[str]:
    """Every bucket file name, in order — the full set the generator writes."""
    return [shard_name(i) for i in range(SHARD_COUNT)]
