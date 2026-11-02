import { describe, expect, test } from 'bun:test';
import { applyLink, dayLabel, monthLabel, someOf, withScheme } from './format';
import type { HiringFields } from './types';

const fields = (overrides: Partial<HiringFields>) => ({ roles: [], contact: null, company_website: null, ...overrides }) as HiringFields;

describe('format', () => {
  test('labels months and days', () => {
    expect(monthLabel('2026-10')).toBe('October 2026');
    expect(monthLabel('2026-10', 'short')).toBe('Oct');
    expect(dayLabel(1_791_000_000)).toBe('Oct 3');
  });

  test('picks where to apply', () => {
    expect(applyLink(fields({ contact: 'jobs@acme.com' }))).toEqual({ href: 'mailto:jobs@acme.com', label: 'Email to apply' });
    expect(applyLink(fields({ contact: 'acme.com/careers' }))).toEqual({ href: 'https://acme.com/careers', label: 'Apply' });
    expect(applyLink(fields({ company_website: 'https://acme.com' }))?.href).toBe('https://acme.com');
    expect(applyLink(fields({}))).toBeNull();
  });

  test('shortens long lists', () => {
    expect(someOf(['a', 'b'])).toBe('a, b');
    expect(someOf(['a', 'b', 'c', 'd', 'e'])).toBe('a, b, c +2 more');
    expect(withScheme('http://x.io')).toBe('http://x.io');
  });
});
