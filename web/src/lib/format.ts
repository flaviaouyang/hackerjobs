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

const RELATIVE = new Intl.RelativeTimeFormat('en-US', { numeric: 'auto' });
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [['day', 86_400], ['hour', 3_600], ['minute', 60]];

/** "2 hours ago" for an ISO timestamp, in the largest whole unit up to days. */
export function agoLabel(iso: string, now = Date.now()): string {
  const seconds = (Date.parse(iso) - now) / 1000;
  const [unit, size] = UNITS.find(([, size]) => Math.abs(seconds) >= size) ?? UNITS[UNITS.length - 1];
  return RELATIVE.format(Math.round(seconds / size), unit);
}

/** Add https:// to bare domains such as "acme.com/jobs". */
export function withScheme(url: string): string {
  return /^https?:\/\//i.test(url) ? url : `https://${url}`;
}

/**
 * Undo the export's scrambling of an email address (Base64 of the reversed address). Addresses
 * are only unscrambled when someone reaches for the link, so harvesters reading the data get none.
 */
export function unscramble(scrambled: string): string {
  const bytes = Uint8Array.from(atob(scrambled), (char) => char.charCodeAt(0));
  return [...new TextDecoder().decode(bytes)].reverse().join('');
}

/** A web link (`href`) or a scrambled email address (`scrambled`). */
export type Link = { label: string } & ({ href: string; scrambled?: never } | { scrambled: string; href?: never });

/** Where to apply: the post's contact (email or URL), else a role's own, else the company site. */
export function applyLink(fields: HiringFields): Link | null {
  if (fields.contact_email) return { scrambled: fields.contact_email, label: 'Email to apply' };
  if (fields.contact) return { href: withScheme(fields.contact), label: 'Apply' };
  const role = fields.roles.find((item) => item.apply_email || item.apply_url);
  if (role?.apply_email) return { scrambled: role.apply_email, label: 'Email to apply' };
  const url = role?.apply_url ?? fields.company_website;
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
