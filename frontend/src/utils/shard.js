// Bucket assignment for the sharded party detail files.
//
// `parties/` used to hold one JSON file per party. Those files are tiny (a
// kilobyte apiece) but there is one per party, and Cloudflare Pages caps a
// deployment at 20,000 files — a limit counted in *files*, not bytes, so
// ~2,200 one-kilobyte party files cost as much of the budget as ~2,200 large
// ones. The per-party payloads are now packed into a fixed set of
// `shard-{nn}.json` buckets instead, keyed by party id.
//
// The bucket is derived from the id alone so the SPA can compute it without
// consulting an index — no extra round trip on the way to a party page. That
// makes this algorithm load-bearing in the same way `slug.js` is: it MUST stay
// in sync with the Python implementation in `scripts/shard.py` (which writes
// the buckets). If the two diverge the SPA fetches the wrong bucket and every
// party page 404s. `fixtures/shard-cases.json` pins the pair together; both
// test suites read it.
//
// FNV-1a is used rather than a language built-in because Python's `hash()` is
// salted per process and JavaScript has none — the mapping has to be identical
// across languages, runs and versions. It is not a security primitive and is
// not used as one; it only needs to be stable and to spread ids evenly.

// Keep in step with SHARD_COUNT in scripts/shard.py. See that file for what
// changing it costs.
export const SHARD_COUNT = 256;

const FNV_OFFSET_BASIS_32 = 0x811c9dc5;
const FNV_PRIME_32 = 0x01000193;

const encoder = new TextEncoder();

/**
 * 32-bit FNV-1a hash of `text`'s UTF-8 bytes.
 *
 * `Math.imul` does the multiply as a true 32-bit operation (a plain `*` would
 * lose the low bits to float64 rounding once the product exceeds 2^53), and
 * `>>> 0` brings the signed result back to unsigned.
 *
 * @param {string} text
 * @returns {number} unsigned 32-bit integer
 */
export function fnv1a32(text) {
  let h = FNV_OFFSET_BASIS_32;
  for (const byte of encoder.encode(String(text))) {
    h ^= byte;
    h = Math.imul(h, FNV_PRIME_32) >>> 0;
  }
  return h >>> 0;
}

/**
 * Bucket index (0 .. SHARD_COUNT - 1) holding `partyId`'s record.
 *
 * @param {string} partyId
 * @returns {number}
 */
export function partyShard(partyId) {
  return fnv1a32(partyId || '') % SHARD_COUNT;
}

/**
 * File name for bucket `index`, e.g. "shard-00.json".
 *
 * @param {number} index
 * @returns {string}
 */
export function shardName(index) {
  return `shard-${index.toString(16).padStart(2, '0')}.json`;
}

/**
 * File name of the bucket holding `partyId`, e.g. "shard-c5.json".
 *
 * @param {string} partyId
 * @returns {string}
 */
export function partyShardName(partyId) {
  return shardName(partyShard(partyId));
}
