// Human-readable URL slugs for merger detail pages.
//
// The slug is purely decorative — merger pages are always looked up by their
// `merger_id` (e.g. MN-01016). The slug exists for SEO/readability, so the
// algorithm here MUST stay in sync with the Python implementation in
// `scripts/slug.py` (used by the sitemap generator) and the inline copy in
// `functions/mergers/[matter]/[[path]].js` (used by the social-bot OG handler).
// If these diverge, the sitemap, canonical tags and rendered URLs disagree.

const MAX_SLUG_LENGTH = 80;

/**
 * Convert a merger name into a lowercase, hyphen-separated slug.
 * Returns an empty string when no usable characters remain.
 *
 * @param {string} name
 * @returns {string}
 */
export function slugify(name) {
  if (!name) return '';
  return String(name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')   // any run of non-alphanumerics -> single hyphen
    .replace(/^-+|-+$/g, '')        // trim leading/trailing hyphens
    .slice(0, MAX_SLUG_LENGTH)      // keep URLs to a sensible length
    .replace(/-+$/g, '');           // re-trim if the truncation landed on a hyphen
}

/**
 * Build the canonical path for a merger detail page, including the readable
 * slug when one can be derived. Falls back to the bare `/mergers/{id}` form.
 *
 * @param {string} id - merger_id (e.g. "MN-01016")
 * @param {string} [name] - merger_name used to derive the slug
 * @returns {string}
 */
export function mergerPath(id, name) {
  const slug = slugify(name);
  return slug ? `/mergers/${id}/${slug}` : `/mergers/${id}`;
}
