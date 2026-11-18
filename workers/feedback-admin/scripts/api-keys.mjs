#!/usr/bin/env node
// Issue, revoke and inspect keys for the key-gated API (docs/api.md).
//
//   npm run api-key:create -- smith-legal     prints a new key ONCE
//   npm run api-key:revoke -- smith-legal     revokes all of the client's keys
//   npm run api-key:revoke -- smith-legal --key mfyi_live_3f9a1c
//                                             revokes just that key (rotation)
//   npm run api-key:list                      every key, with its usage
//   npm run api-usage                         per-day counts, last 30 days
//   npm run api-usage -- --days 90
//
// Add --local to any of them to work against `wrangler dev`'s local D1 instead
// of the real database.
//
// Only the key's SHA-256 is stored (plus its first few characters, to tell a
// client's keys apart), so a key is shown once at creation and can't be looked
// up again: a lost key is revoked and reissued.
//
// Runs `wrangler d1 execute` against the mergers-feedback database, so it needs
// the same Cloudflare login as deploying this Worker. Every value spliced into
// SQL is validated against a strict pattern first (labels, hints) or generated
// here (hashes), so nothing user-typed reaches the SQL unchecked.

import { createHash, randomBytes } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

export const DATABASE = 'mergers-feedback';
export const KEY_PREFIX = 'mfyi_live_';
const HINT_LENGTH = KEY_PREFIX.length + 6;
const LABEL_RE = /^[a-z0-9][a-z0-9-]{0,47}$/;
const HINT_RE = new RegExp(`^${KEY_PREFIX}[0-9a-f]{6}$`);

export function generateKey() {
  return KEY_PREFIX + randomBytes(20).toString('hex');
}

export function hashKey(key) {
  return createHash('sha256').update(key).digest('hex');
}

export function keyHint(key) {
  return key.slice(0, HINT_LENGTH);
}

export function checkLabel(label) {
  if (!LABEL_RE.test(label || '')) {
    throw new Error(
      `Label must be lower-case letters, digits and hyphens, starting with a letter or digit (got ${JSON.stringify(label)})`,
    );
  }
  return label;
}

export function checkHint(hint) {
  if (!HINT_RE.test(hint || '')) {
    throw new Error(`--key takes the hint shown by api-key:list, like ${KEY_PREFIX}3f9a1c`);
  }
  return hint;
}

export function createSql(label, key) {
  return `INSERT INTO api_keys (label, key_hash, key_hint) VALUES ('${checkLabel(label)}', '${hashKey(key)}', '${keyHint(key)}')`;
}

export function revokeSql(label, hint) {
  const which = hint ? ` AND key_hint = '${checkHint(hint)}'` : '';
  return `UPDATE api_keys SET revoked_at = datetime('now') WHERE label = '${checkLabel(label)}' AND revoked_at IS NULL${which} RETURNING key_hint`;
}

export const LIST_SQL = `
SELECT k.label, k.key_hint, k.created_at, k.revoked_at,
       (SELECT COALESCE(SUM(u.count), 0) FROM api_usage u WHERE u.label = k.label) AS client_requests,
       (SELECT MAX(u.day) FROM api_usage u WHERE u.label = k.label) AS client_last_day
FROM api_keys k
ORDER BY k.label, k.created_at`;

export function usageSql(days) {
  const n = /^\d+$/.test(String(days)) ? Number(days) : NaN;
  if (!(n >= 1 && n <= 3650)) throw new Error('--days takes a whole number from 1 to 3650');
  return `SELECT label, day, count FROM api_usage WHERE day >= date('now', '-${n} days') ORDER BY day DESC, label`;
}

function d1(sql, { local }) {
  const args = ['wrangler', 'd1', 'execute', DATABASE, local ? '--local' : '--remote', '--json', '--command', sql];
  const out = execFileSync('npx', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'inherit'] });
  const parsed = JSON.parse(out);
  const first = Array.isArray(parsed) ? parsed[0] : parsed;
  return first || { results: [], meta: {} };
}

function main(argv) {
  const local = argv.includes('--local');
  const rest = argv.filter((a) => a !== '--local');
  const flag = (name) => {
    const i = rest.indexOf(name);
    return i === -1 ? undefined : rest[i + 1];
  };
  const [command, label] = rest;

  switch (command) {
    case 'create': {
      checkLabel(label);
      const key = generateKey();
      d1(createSql(label, key), { local });
      console.log(`\nAPI key for ${label} (shown once; only its hash is stored):\n\n  ${key}\n`);
      console.log('Send it to the client over a secure channel. They use it as:');
      console.log(`  curl -H "Authorization: Bearer ${key}" https://mergers.fyi/data/api/v1/mergers.json\n`);
      return;
    }
    case 'revoke': {
      const hint = flag('--key');
      // RETURNING rather than meta.changes, which local D1 doesn't report.
      const { results } = d1(revokeSql(label, hint), { local });
      console.log(
        results.length
          ? `Revoked ${results.map((r) => r.key_hint).join(', ')} for ${label}.`
          : `No active key for ${label}${hint ? ` matching ${hint}` : ''}.`,
      );
      return;
    }
    case 'list': {
      const { results } = d1(LIST_SQL, { local });
      if (!results.length) return console.log('No API keys yet.');
      console.table(results);
      return;
    }
    case 'usage': {
      const { results } = d1(usageSql(flag('--days') ?? 30), { local });
      if (!results.length) return console.log('No API requests in that period.');
      console.table(results);
      return;
    }
    default:
      console.error('Usage: api-keys.mjs create <label> | revoke <label> [--key <hint>] | list | usage [--days N]  [--local]');
      process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    main(process.argv.slice(2));
  } catch (err) {
    console.error(err.message);
    process.exitCode = 1;
  }
}
