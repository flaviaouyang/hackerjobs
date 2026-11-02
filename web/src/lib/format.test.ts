import { describe, expect, test } from 'bun:test';
import { applyLink, dayLabel, monthLabel, someOf, unscramble, withScheme } from './format';
import type { HiringFields } from './types';

const fields = (overrides: Partial<HiringFields>) => ({ roles: [], contact: null, company_website: null, ...overrides }) as HiringFields;

describe('format', () => {
  test('labels months and days', () => {
    expect(monthLabel('2026-10')).toBe('October 2026');
    expect(monthLabel('2026-10', 'short')).toBe('Oct');
    expect(dayLabel(1_791_000_000)).toBe('Oct 3');
  });

  test('picks where to apply', () => {
    expect(applyLink(fields({ contact_email: 'bW9jLmVscG1heGVAb2o=' }))).toEqual({ scrambled: 'bW9jLmVscG1heGVAb2o=', label: 'Email to apply' });
    expect(applyLink(fields({ contact: 'acme.com/careers' }))).toEqual({ href: 'https://acme.com/careers', label: 'Apply' });
    expect(applyLink(fields({ company_website: 'https://acme.com' }))?.href).toBe('https://acme.com');
    expect(applyLink(fields({}))).toBeNull();
    const role = { title: 'Engineer', pay: null, locations: [], apply_url: null, apply_email: 'bW9jLmVscG1heGVAb2o=', seniority: null, category: 'Engineering' };
    expect(applyLink(fields({ roles: [role] }))).toEqual({ scrambled: 'bW9jLmVscG1heGVAb2o=', label: 'Email to apply' });
  });

  test('unscrambles what the export scrambled', () => {
    // Same value as the doctest of hackerjobs.export.scramble.
    expect(unscramble('bW9jLmVscG1heGVAb2o=')).toBe('jo@example.com');
  });

  test('shortens long lists', () => {
    expect(someOf(['a', 'b'])).toBe('a, b');
    expect(someOf(['a', 'b', 'c', 'd', 'e'])).toBe('a, b, c +2 more');
    expect(someOf(['Paris, France', 'France'], 3, ' · ')).toBe('Paris, France · France');
    expect(withScheme('http://x.io')).toBe('http://x.io');
  });
});
