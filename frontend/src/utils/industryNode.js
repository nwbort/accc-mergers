// Reading one ANZSIC node out of its division file.
//
// `industries/{division}.json` packs every node under a division into a single
// payload — `{ division, nodes, mergers }` — with each merger summary stored
// once and referenced by id from the nodes that carry it. See
// `industryDivision.js` for why the files are cut that way.
//
// Everything downstream (IndustryDetail, pageMeta.industryMeta, prerender.js)
// still wants one node's worth of data in the shape the per-node files used to
// have, so this module is the only place that knows about the packing:
// `readIndustryNode` rehydrates a node, re-expanding the merger ids and
// rebuilding the two things the file deliberately does not store — the
// breadcrumb ancestors (walked up the parent chain) and each child's merger
// count (read off the sibling node entries).

import { divisionFileName, industryDivisionUrl } from './industryDivision.js';
import { dataCache } from './dataCache.js';

/**
 * dataCache key for that file. Shared by every node in the division, which is
 * the point: a page and its parent comparison, or a dozen followed industries
 * under the one division, all read a single fetch.
 *
 * @param {string} code
 * @returns {string}
 */
export function industryDivisionCacheKey(code) {
  return `industry-division-${divisionFileName(code)}`;
}

/** A node's compact reference form, as used for parent/child/breadcrumb links. */
function nodeRef(nodes, code, withCount) {
  const node = nodes[code];
  if (!node) return null;
  const ref = { code, name: node.name, level: node.level };
  if (withCount) ref.merger_count = node.count ?? 0;
  return ref;
}

/**
 * Rehydrate one node from its division payload, or null if it isn't there.
 *
 * The returned object is the shape the rest of the app reads: hierarchy
 * metadata, the full merger summaries in display order, the stat counts and the
 * duration blocks (null when the node has no completed reviews of that kind,
 * which the file records by omitting them).
 *
 * @param {object|null|undefined} payload - a parsed division file
 * @param {string} code - the ANZSIC code to read out of it
 * @returns {object|null}
 */
export function readIndustryNode(payload, code) {
  const nodes = payload?.nodes;
  const node = nodes?.[code];
  if (!node) return null;

  // Breadcrumb trail, division first. Walking the parent chain rather than
  // storing it keeps the same ancestor names from being repeated on every one
  // of a division's ~200 nodes. The seen-set is belt and braces: a malformed
  // parent cycle would otherwise hang the page rather than render it short.
  const ancestors = [];
  const seen = new Set([code]);
  let parentCode = node.parent;
  while (parentCode && !seen.has(parentCode)) {
    seen.add(parentCode);
    const ref = nodeRef(nodes, parentCode);
    if (!ref) break;
    ancestors.unshift(ref);
    parentCode = nodes[parentCode].parent;
  }

  const summaries = payload.mergers || {};

  return {
    code,
    name: node.name ?? null,
    level: node.level ?? null,
    ancestors,
    parent: node.parent ? nodeRef(nodes, node.parent) : null,
    children: (node.children || [])
      .map((childCode) => nodeRef(nodes, childCode, true))
      .filter(Boolean),
    // Ids the division file doesn't carry a summary for are dropped rather
    // than rendered as blanks; `count` stays the node's own tally so a partial
    // payload can't quietly understate an industry.
    mergers: (node.mergers || []).map((id) => summaries[id]).filter(Boolean),
    count: node.count ?? 0,
    phase_1_count: node.phase_1_count ?? 0,
    phase_2_count: node.phase_2_count ?? 0,
    waiver_count: node.waiver_count ?? 0,
    active_count: node.active_count ?? 0,
    phase_duration: node.phase_duration ?? null,
    waiver_duration: node.waiver_duration ?? null,
  };
}

/**
 * Fetch and rehydrate one industry node, going through dataCache so repeated
 * reads of the same division cost one request.
 *
 * Resolves to null when the division file is missing or holds no such node —
 * i.e. the code isn't a real industry — so callers can treat that as "not
 * found" without distinguishing it from a 404.
 *
 * @param {string} code
 * @returns {Promise<object|null>}
 */
export async function fetchIndustryNode(code) {
  const key = industryDivisionCacheKey(code);
  let payload = dataCache.get(key);
  if (!payload) {
    const response = await fetch(industryDivisionUrl(code));
    if (!response.ok) return null;
    try {
      payload = await response.json();
    } catch {
      // A missing file is served as the SPA's index.html with HTTP 200 on
      // Cloudflare Pages, so a parse failure here is a 404 in disguise.
      return null;
    }
    dataCache.set(key, payload);
  }
  return readIndustryNode(payload, code);
}
