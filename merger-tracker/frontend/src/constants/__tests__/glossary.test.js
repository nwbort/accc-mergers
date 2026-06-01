import { describe, expect, it } from 'vitest';
import { GLOSSARY, GLOSSARY_BY_ID, GLOSSARY_CATEGORIES } from '../glossary';

const categoryIds = new Set(GLOSSARY_CATEGORIES.map((c) => c.id));

describe('glossary data integrity', () => {
  it('has unique entry ids', () => {
    const ids = GLOSSARY.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('exposes every entry via GLOSSARY_BY_ID', () => {
    expect(Object.keys(GLOSSARY_BY_ID)).toHaveLength(GLOSSARY.length);
    for (const entry of GLOSSARY) {
      expect(GLOSSARY_BY_ID[entry.id]).toBe(entry);
    }
  });

  it('gives every entry a term, a definition and a known category', () => {
    for (const entry of GLOSSARY) {
      expect(entry.term, `term for ${entry.id}`).toBeTruthy();
      expect(entry.definition, `definition for ${entry.id}`).toBeTruthy();
      expect(categoryIds.has(entry.category), `category for ${entry.id}`).toBe(true);
    }
  });

  it('only references related ids that exist', () => {
    for (const entry of GLOSSARY) {
      for (const relId of entry.related || []) {
        expect(GLOSSARY_BY_ID[relId], `${entry.id} -> ${relId}`).toBeDefined();
      }
    }
  });

  it('keeps definitions short enough to read inside a tooltip', () => {
    for (const entry of GLOSSARY) {
      expect(entry.definition.length, `definition for ${entry.id}`).toBeLessThanOrEqual(360);
    }
  });
});
