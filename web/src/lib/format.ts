import type { HiringFields, Post } from './types';

/** "October 2026" for "2026-10". */
export function monthLabel(month: string, style: 'long' | 'short' = 'long'): string {
  const [year, number] = month.split('-').map(Number);
  const name = new Date(Date.UTC(year, number - 1, 1)).toLocaleString('en-US', { month: style, timeZone: 'UTC' });
  return style === 'long' ? `${name} ${year}` : name;
}

/** "Oct 21" for a Unix timestamp. */
export function dayLabel(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
}

/** Add https:// to bare domains such as "acme.com/jobs". */
export function withScheme(url: string): string {
  return /^https?:\/\//i.test(url) ? url : `https://${url}`;
}

export function isEmail(value: string): boolean {
  return /^[^\s@/]+@[^\s@/]+\.[^\s@/]+$/.test(value);
}

export interface Link {
  href: string;
  label: string;
}

/** Where to apply: the contact (email or URL), else a role's own link, else the company site. */
export function applyLink(fields: HiringFields): Link | null {
  if (fields.contact && isEmail(fields.contact)) return { href: `mailto:${fields.contact}`, label: 'Email to apply' };
  const url = fields.contact ?? fields.roles.find((role) => role.apply_url)?.apply_url ?? fields.company_website;
  return url ? { href: withScheme(url), label: 'Apply' } : null;
}

/** "Remote", "Hybrid", "Onsite". */
export function arrangement(remote: string | null): string | null {
  return remote ? remote[0].toUpperCase() + remote.slice(1) : null;
}

/** Up to three items joined with `separator`, then "+N more". */
export function someOf(items: string[], limit = 3, separator = ', '): string {
  return items.length > limit
    ? `${items.slice(0, limit).join(separator)} +${items.length - limit} more`
    : items.join(separator);
}

/** The month of the earlier post this one repeats, from its history. */
export function repostMonth(post: Post): string | null {
  const original = post.history.find((entry) => entry.id === post.repost_of);
  return original ? monthLabel(original.month, 'short') : null;
}

export function hnItem(id: number): string {
  return `https://news.ycombinator.com/item?id=${id}`;
}

export function hnUser(name: string): string {
  return `https://news.ycombinator.com/user?id=${encodeURIComponent(name)}`;
}
