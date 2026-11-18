import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

import {
  KEY_PREFIX,
  checkLabel,
  createSql,
  generateKey,
  hashKey,
  keyHint,
  revokeSql,
  usageSql,
} from '../scripts/api-keys.mjs';

test('keys are prefixed, long and unique', () => {
  const a = generateKey();
  const b = generateKey();
  assert.ok(a.startsWith(KEY_PREFIX));
  assert.equal(a.length, KEY_PREFIX.length + 40);
  assert.notEqual(a, b);
});

test('the stored hash is the hex SHA-256 the Pages Function computes', () => {
  const key = 'mfyi_live_abc';
  assert.equal(hashKey(key), createHash('sha256').update(key).digest('hex'));
});

test('the hint is the prefix plus six characters, never the whole key', () => {
  const key = generateKey();
  assert.equal(keyHint(key), key.slice(0, KEY_PREFIX.length + 6));
});

test('create stores the hash and hint, never the key', () => {
  const key = generateKey();
  const sql = createSql('smith-legal', key);
  assert.ok(sql.includes(hashKey(key)));
  assert.ok(sql.includes(keyHint(key)));
  assert.ok(!sql.includes(key));
});

test('labels that could break out of the SQL are refused', () => {
  for (const bad of ["x'; DROP TABLE api_keys; --", 'Smith', '', '-x', 'a b', undefined]) {
    assert.throws(() => checkLabel(bad));
  }
  assert.equal(checkLabel('smith-legal-2'), 'smith-legal-2');
});

test('revoke targets one key only with a well-formed hint', () => {
  assert.match(revokeSql('smith-legal'), /label = 'smith-legal' AND revoked_at IS NULL RETURNING key_hint$/);
  assert.match(revokeSql('smith-legal', 'mfyi_live_3f9a1c'), /key_hint = 'mfyi_live_3f9a1c' RETURNING key_hint$/);
  assert.throws(() => revokeSql('smith-legal', "mfyi_live_3f9a1c' OR 1=1 --"));
});

test('usage takes only a sane number of days', () => {
  assert.match(usageSql(30), /-30 days/);
  assert.throws(() => usageSql('30; DROP TABLE api_usage'));
  assert.throws(() => usageSql(0));
});
