import { describe, expect, test } from 'bun:test';
import { DEFAULT_FILTERS, applyFilters, countValues, parseFilters, serializeFilters } from './filters';
import type { HiringFields, HiringPost, Rates } from './types';

const RATES: Rates = { date: '2026-10-30', cad_per_unit: { CAD: 1, USD: 1.396, GBP: 1.8699 } };

function job(id: number, fields: Partial<HiringFields>, extra: Partial<HiringPost> = {}): HiringPost {
  const base: HiringFields = {
    company: `Company ${id}`, company_website: null, company_description: null, industries: [],
    company_stage: null, funding: null, valuation: null, investors: [], team_size: null, founded_year: null,
    roles: [], locations: [], remote: null, employment_types: [], pay: null, technologies: [],
    min_experience_years: null, languages: [], work_authorization: null, security_clearance: null,
    timezone: null, hours: null, education: null, equity: null, equity_details: null, benefits: [],
    visa_sponsorship: null, relocation_support: null, interview_process: null, contact: null,
    application_instructions: null, applications_closed: null, seniority: [],
  };
  return { id, author: `user${id}`, posted_at: id, html: '', key: null, new: true, repost_of: null, history: [], fields: { ...base, ...fields }, ...extra };
}

const POSTS = [
  job(1, { remote: 'remote', technologies: ['TypeScript', 'React'], pay: { min: 150_000, max: 200_000, currency: 'USD', period: 'year' } }),
  job(2, { remote: 'onsite', locations: ['London, UK'], pay: { min: 100_000, max: 120_000, currency: 'GBP', period: 'year' } }),
  job(3, { remote: 'remote', technologies: ['typescript'], applications_closed: true }),
  job(4, { remote: 'remote' }, { repost_of: 1, new: false }),
];

describe('filters', () => {
  test('round-trip through the URL, leaving out defaults', () => {
    expect(serializeFilters(DEFAULT_FILTERS)).toBe('');
    const filters = { ...DEFAULT_FILTERS, month: '2026-10', remote: ['remote' as const], tech: ['Rust'], minPay: 150000, currency: 'EUR', hideReposts: false };
    const query = serializeFilters(filters);
    expect(query).toBe('?month=2026-10&remote=remote&tech=Rust&reposts=1&cur=EUR&minpay=150000');
    expect(parseFilters(query)).toEqual(filters);
  });

  test('ignores invalid values', () => {
    const filters = parseFilters('?remote=moon,remote&minpay=-5&sort=random');
    expect(filters.remote).toEqual(['remote']);
    expect(filters.minPay).toBeNull();
    expect(filters.sort).toBe('newest');
  });

  test('hides reposts and closed posts by default', () => {
    const ids = applyFilters(POSTS, 'hiring', DEFAULT_FILTERS, RATES, null).map((post) => post.id);
    expect(ids).toEqual([2, 1]);
  });

  test('matches technologies case-insensitively, all required', () => {
    const filters = { ...DEFAULT_FILTERS, hideClosed: false, tech: ['TYPESCRIPT'] };
    expect(applyFilters(POSTS, 'hiring', filters, RATES, null).map((post) => post.id)).toEqual([3, 1]);
  });

  test('compares minimum pay in the chosen currency', () => {
    const filters = { ...DEFAULT_FILTERS, minPay: 160_000 };
    // In USD, £120k is about $161k, so both pass the $160k minimum.
    expect(applyFilters(POSTS, 'hiring', filters, RATES, null).map((post) => post.id)).toEqual([2, 1]);
    // In GBP, $200k is about £149k: it passes a £130k minimum and the £120k post does not.
    const inPounds = { ...filters, currency: 'GBP', minPay: 130_000 };
    expect(applyFilters(POSTS, 'hiring', inPounds, RATES, null).map((post) => post.id)).toEqual([1]);
  });

  test('applies search hits, location and sorting by pay', () => {
    const filters = { ...DEFAULT_FILTERS, sort: 'pay' as const };
    expect(applyFilters(POSTS, 'hiring', filters, RATES, null).map((post) => post.id)).toEqual([1, 2]);
    expect(applyFilters(POSTS, 'hiring', { ...filters, location: 'london' }, RATES, null).map((post) => post.id)).toEqual([2]);
    expect(applyFilters(POSTS, 'hiring', filters, RATES, new Set([2])).map((post) => post.id)).toEqual([2]);
  });

  test('counts values once per post', () => {
    expect(countValues(POSTS, (post) => post.fields.technologies.map((tech) => tech.toLowerCase()))).toEqual([
      ['typescript', 2],
      ['react', 1],
    ]);
  });
});
