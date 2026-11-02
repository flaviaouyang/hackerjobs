import { yearlyMax } from './money';
import type { HiringPost, Kind, Post, Rates, Remote, SeekingPost } from './types';

export type Sort = 'newest' | 'pay';

export interface Filters {
  month: string | null;
  q: string;
  location: string;
  remote: Remote[];
  /** Role categories (kinds of work). */
  work: string[];
  tech: string[];
  hideReposts: boolean;
  currency: string;
  sort: Sort;
  /** 1-based results page. */
  page: number;
  // Hiring only
  minPay: number | null;
  seniority: string[];
  industry: string | null;
  visa: boolean;
  equity: boolean;
  newOnly: boolean;
  hideClosed: boolean;
  // Candidates only
  relocate: boolean;
  minYears: number | null;
  employment: string[];
}

export const DEFAULT_FILTERS: Filters = {
  month: null,
  q: '',
  location: '',
  remote: [],
  work: [],
  tech: [],
  hideReposts: true,
  currency: 'USD',
  sort: 'newest',
  page: 1,
  minPay: null,
  seniority: [],
  industry: null,
  visa: false,
  equity: false,
  newOnly: false,
  hideClosed: true,
  relocate: false,
  minYears: null,
  employment: [],
};

const list = (value: string | null): string[] => (value ? value.split(',').filter(Boolean) : []);
const number = (value: string | null): number | null => {
  const parsed = value === null ? NaN : Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
};

/** Read filters from a URL query string; anything missing or invalid keeps its default. */
export function parseFilters(search: string): Filters {
  const params = new URLSearchParams(search);
  const flag = (name: string) => params.get(name) === '1';
  return {
    month: params.get('month'),
    q: params.get('q') ?? '',
    location: params.get('loc') ?? '',
    remote: list(params.get('remote')).filter((value): value is Remote =>
      ['remote', 'hybrid', 'onsite'].includes(value),
    ),
    work: list(params.get('work')),
    tech: list(params.get('tech')),
    hideReposts: !flag('reposts'),
    currency: params.get('cur') ?? DEFAULT_FILTERS.currency,
    sort: params.get('sort') === 'pay' ? 'pay' : 'newest',
    page: Math.max(1, Math.floor(number(params.get('page')) ?? 1)),
    minPay: number(params.get('minpay')),
    seniority: list(params.get('level')),
    industry: params.get('industry'),
    visa: flag('visa'),
    equity: flag('equity'),
    newOnly: flag('new'),
    hideClosed: !flag('closed'),
    relocate: flag('relocate'),
    minYears: number(params.get('years')),
    employment: list(params.get('type')),
  };
}

/** Write filters as a query string, leaving out defaults so URLs stay short. */
export function serializeFilters(filters: Filters): string {
  const params = new URLSearchParams();
  const put = (name: string, value: string | null | undefined) => {
    if (value) params.set(name, value);
  };
  put('month', filters.month);
  put('q', filters.q.trim());
  put('loc', filters.location.trim());
  put('remote', filters.remote.join(','));
  put('work', filters.work.join(','));
  put('tech', filters.tech.join(','));
  put('reposts', filters.hideReposts ? null : '1');
  put('cur', filters.currency === DEFAULT_FILTERS.currency ? null : filters.currency);
  put('sort', filters.sort === 'newest' ? null : filters.sort);
  put('page', filters.page > 1 ? String(filters.page) : null);
  put('minpay', filters.minPay === null ? null : String(filters.minPay));
  put('level', filters.seniority.join(','));
  put('industry', filters.industry);
  put('visa', filters.visa ? '1' : null);
  put('equity', filters.equity ? '1' : null);
  put('new', filters.newOnly ? '1' : null);
  put('closed', filters.hideClosed ? null : '1');
  put('relocate', filters.relocate ? '1' : null);
  put('years', filters.minYears === null ? null : String(filters.minYears));
  put('type', filters.employment.join(','));
  const query = params.toString();
  return query ? `?${query}` : '';
}

const lower = (values: string[]) => values.map((value) => value.toLowerCase());

function locations(post: Post): string[] {
  const roles = 'company' in post.fields ? post.fields.roles.flatMap((role) => role.locations) : [];
  return [...post.fields.locations, ...roles];
}

/** How a job is worked, or every way a candidate is open to working. */
export function arrangementsOf(post: Post): Remote[] {
  if ('arrangements' in post.fields) return post.fields.arrangements;
  return post.fields.remote ? [post.fields.remote] : [];
}

function matchesShared(post: Post, filters: Filters, hits: Set<number> | null): boolean {
  if (hits && !hits.has(post.id)) return false;
  if (filters.hideReposts && post.repost_of !== null) return false;
  if (filters.remote.length && !arrangementsOf(post).some((value) => filters.remote.includes(value))) return false;
  const place = filters.location.trim().toLowerCase();
  if (place && !locations(post).some((location) => location.toLowerCase().includes(place))) return false;
  if (filters.work.length && !post.fields.role_categories.some((category) => filters.work.includes(category))) return false;
  const techs = lower(post.fields.technologies);
  return lower(filters.tech).every((tech) => techs.includes(tech));
}

function matchesHiring(post: HiringPost, filters: Filters, rates: Rates): boolean {
  const fields = post.fields;
  if (filters.hideClosed && fields.applications_closed) return false;
  if (filters.newOnly && !post.new) return false;
  if (filters.visa && fields.visa_sponsorship !== true) return false;
  if (filters.equity && fields.equity !== true) return false;
  if (filters.industry && !fields.industries.includes(filters.industry)) return false;
  if (filters.seniority.length && !fields.seniority.some((level) => filters.seniority.includes(level))) return false;
  if (filters.minPay !== null) {
    const top = yearlyMax(fields.pay, filters.currency, rates);
    if (top === null || top < filters.minPay) return false;
  }
  return true;
}

function matchesSeeking(post: SeekingPost, filters: Filters): boolean {
  const fields = post.fields;
  if (filters.relocate && fields.willing_to_relocate !== true) return false;
  if (filters.minYears !== null && (fields.experience_years ?? -1) < filters.minYears) return false;
  return !filters.employment.length || fields.employment_types.some((type) => filters.employment.includes(type));
}

/** Whether a post says little beyond who posted it: no roles, pay, description, technologies or interests. */
export function isBrief(post: Post): boolean {
  const fields = post.fields;
  if (fields.roles.length || fields.technologies.length) return false;
  return 'company' in fields ? !fields.pay && !fields.company_description : !fields.interests.length;
}

/**
 * Apply every filter and sort the posts; brief posts come after the detailed ones.
 *
 * @param hits Ids matching the search box, or null when it is empty
 */
export function applyFilters(
  posts: Post[],
  kind: Kind,
  filters: Filters,
  rates: Rates,
  hits: Set<number> | null,
): Post[] {
  const kept = posts.filter(
    (post) =>
      matchesShared(post, filters, hits) &&
      (kind === 'hiring'
        ? matchesHiring(post as HiringPost, filters, rates)
        : matchesSeeking(post as SeekingPost, filters)),
  );
  const brief = new Map(kept.map((post) => [post.id, isBrief(post) ? 1 : 0]));
  const top = (post: Post) => yearlyMax(post.fields.pay, filters.currency, rates) ?? -1;
  const order =
    filters.sort === 'pay' && kind === 'hiring'
      ? (left: Post, right: Post) => top(right) - top(left)
      : (left: Post, right: Post) => right.posted_at - left.posted_at;
  return kept.sort((left, right) => (brief.get(left.id) ?? 0) - (brief.get(right.id) ?? 0) || order(left, right));
}

/** How many posts mention each value, most common first. */
export function countValues<P extends Post>(posts: P[], values: (post: P) => Iterable<string>): [string, number][] {
  const counts = new Map<string, number>();
  for (const post of posts) {
    for (const value of new Set(values(post))) counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
}
