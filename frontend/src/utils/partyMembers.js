/**
 * Collapse a canonical party group's member list for display.
 *
 * `parties/{id}.json` records one member per (name, identifier) pair seen on a
 * filing, so a single real-world entity often appears several times over: the
 * same company written with and without its legal form, in ALL CAPS on one
 * filing and title case on the next, or with the same registration number
 * labelled four different ways ("140080", "JFSC  140080", "JFSC - 140080",
 * "Registration number (Jersey)  140080"). Grouping is a display concern only —
 * nothing here rewrites the underlying data, and every raw record stays
 * available behind the "recorded variants" toggle on the party page.
 *
 * Two records are treated as the same entity when either
 *
 *   - their names match: same base name (case, accents, punctuation and
 *     spacing ignored) and compatible legal forms, meaning identical forms or
 *     one record omitting the form entirely ("CVC Capital Partners" vs "CVC
 *     Capital Partners plc"). Differing forms are a real distinction and are
 *     kept apart ("Accenture Inc." is not "Accenture plc"); or
 *   - their identifiers match: the same digits, ignoring whatever prose label
 *     surrounds them, or an ABN whose last nine digits are the other record's
 *     ACN.
 *
 * Names alone never merge records with conflicting legal forms, and identifiers
 * alone never merge records that share no digits, so distinct subsidiaries
 * inside a group (Zurich's, Blackbird's) stay on their own rows.
 */

/** Legal-form tokens, mapped to a canonical spelling where they have variants. */
const LEGAL_FORM_CANON = {
  limited: 'ltd',
  ltda: 'ltd',
  incorporated: 'inc',
  corporation: 'corp',
  company: 'co',
};

const LEGAL_FORMS = new Set([
  'pty', 'ltd', 'limited', 'ltda', 'inc', 'incorporated', 'llc', 'llp', 'lp',
  'plc', 'gmbh', 'mbh', 'ag', 'kgaa', 'kg', 'bv', 'nv', 'sa', 'sas', 'sarl',
  'srl', 'spa', 'aps', 'ab', 'oy', 'oyj', 'asa', 'pte', 'sdn', 'bhd', 'co',
  'corp', 'corporation', 'company', 'kk', 'sl', 'slu', 'ulc', 'pc', 'se', 'dac',
]);

/** Identifier values recorded in place of "we don't have one". */
const PLACEHOLDER_IDENTIFIERS = new Set(['na', 'none', 'unknown', 'nil', 'tbc']);

/** Lower-case and strip accents, so "L'Oréal" and "L'Oreal" compare equal. */
function fold(value) {
  return (value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

/** Collapse runs of single letters ("l p", "b v") into one token ("lp", "bv"). */
function joinInitials(tokens) {
  const out = [];
  let i = 0;
  while (i < tokens.length) {
    if (tokens[i].length === 1 && tokens[i + 1]?.length === 1) {
      let run = '';
      while (i < tokens.length && tokens[i].length === 1) {
        run += tokens[i];
        i += 1;
      }
      out.push(run);
    } else {
      out.push(tokens[i]);
      i += 1;
    }
  }
  return out;
}

/**
 * Split a party name into its comparable base and its legal form.
 *
 * "Bain Capital Investors, LLC." -> { base: 'bain capital investors', form: 'llc' }
 */
export function splitPartyName(name) {
  const tokens = joinInitials(
    fold(name).replace(/&/g, ' and ').replace(/[^a-z0-9]+/g, ' ').split(' ').filter(Boolean)
  );
  const base = [];
  const form = [];
  tokens.forEach((token) => {
    const canon = LEGAL_FORM_CANON[token] || token;
    if (LEGAL_FORMS.has(token)) form.push(canon);
    else base.push(canon);
  });
  return { base: base.join(' '), form: [...new Set(form)].sort().join(' ') };
}

/**
 * Reduce an identifier to the digits that identify it.
 *
 * Registration numbers are recorded with all manner of surrounding prose, so
 * the digits are the only stable part. Identifiers with too few digits to be a
 * registration number (and placeholders like "N/A") fall back to their
 * alphanumeric characters, or to "" when nothing usable is left.
 */
export function identifierCore(identifier) {
  if (!identifier) return '';
  const digits = identifier.replace(/\D/g, '').replace(/^0+/, '');
  if (digits.length >= 4) return digits;
  const cleaned = fold(identifier).replace(/[^0-9a-z]/g, '');
  return PLACEHOLDER_IDENTIFIERS.has(cleaned) ? '' : cleaned;
}

/** True when two identifier cores denote the same registration. */
function sameIdentifier(a, b) {
  if (!a || !b) return false;
  if (a === b) return true;
  // An ABN is two check digits followed by the company's ACN.
  if (a.length === 11 && b.length === 9) return a.endsWith(b);
  if (b.length === 11 && a.length === 9) return b.endsWith(a);
  return false;
}

function sameEntity(a, b) {
  if (a.base && a.base === b.base && (a.form === b.form || !a.form || !b.form)) return true;
  return sameIdentifier(a.core, b.core);
}

/** Collapse runs of whitespace, for identifiers recorded with stray spacing. */
function tidy(value) {
  return (value || '').replace(/\s+/g, ' ').trim();
}

/** The prose around an identifier's digits — "JFSC", "Delaware File Number". */
function identifierLabel(identifier) {
  return tidy((identifier || '').replace(/[0-9]+/g, ' '));
}

/**
 * Pick the display name for a cluster: prefer a name that isn't shouted, then
 * the most frequently recorded, then the longest, then alphabetical so the
 * choice is stable.
 */
function pickName(records) {
  const names = records.map((r) => r.name).filter(Boolean);
  if (names.length === 0) return '';
  const freq = new Map();
  names.forEach((name) => freq.set(name, (freq.get(name) || 0) + 1));
  const isShouted = (name) => name === name.toUpperCase() && /[A-Z]/.test(name);
  return [...freq.keys()].sort((a, b) => (
    (isShouted(a) ? 1 : 0) - (isShouted(b) ? 1 : 0)
    || freq.get(b) - freq.get(a)
    || b.length - a.length
    || a.localeCompare(b)
  ))[0];
}

/**
 * One entry per distinct registration held by a cluster, each shown in its most
 * informative recorded form (the variant carrying the longest label, so
 * "Registration number (Jersey) 140080" wins over a bare "140080").
 */
function pickIdentifiers(records) {
  const groups = [];
  records.forEach((record) => {
    if (!record.identifier || !record.core) return;
    const group = groups.find((g) => sameIdentifier(g.core, record.core));
    if (group) group.records.push(record);
    else groups.push({ core: record.core, records: [record] });
  });
  return groups.map(({ records: variants }) => {
    const best = [...variants].sort((a, b) => (
      identifierLabel(b.identifier).length - identifierLabel(a.identifier).length
      || b.identifier.length - a.identifier.length
      || a.identifier.localeCompare(b.identifier)
    ))[0];
    return { type: best.identifier_type || null, value: tidy(best.identifier) };
  });
}

/**
 * Group a party's members into one row per entity.
 *
 * Returns `[{ name, identifiers: [{ type, value }], members }]` in the order the
 * entities first appear, where `members` is every raw record the row stands for.
 */
export function collapsePartyMembers(members) {
  const records = (members || [])
    .filter((member) => member && (member.name || member.identifier))
    .map((member) => ({
      ...member,
      ...splitPartyName(member.name),
      core: identifierCore(member.identifier),
    }));

  const clusters = [];
  records.forEach((record) => {
    const matches = clusters.filter((cluster) => cluster.some((other) => sameEntity(record, other)));
    if (matches.length === 0) {
      clusters.push([record]);
      return;
    }
    // A record can bridge clusters that had nothing in common until it arrived
    // (a name variant carrying an identifier seen elsewhere in the group).
    const [first, ...rest] = matches;
    first.push(record);
    rest.forEach((cluster) => {
      first.push(...cluster);
      clusters.splice(clusters.indexOf(cluster), 1);
    });
  });

  return clusters.map((cluster) => ({
    name: pickName(cluster),
    identifiers: pickIdentifiers(cluster),
    members: cluster.map(({ base: _base, form: _form, core: _core, ...member }) => member),
  }));
}
