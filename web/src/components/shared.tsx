import type { ComponentChildren } from 'preact';
import { monthLabel } from '../lib/format';
import { displayPay } from '../lib/money';
import type { Pay, Post, Rates } from '../lib/types';

export type Detail = [string, ComponentChildren];

/** A label/value list that skips empty values. */
export function Details({ items, class: className }: { items: Detail[]; class?: string }) {
  const shown = items.filter(([, value]) => value !== null && value !== undefined && value !== '' && value !== false);
  if (!shown.length) return null;
  return (
    <dl class={className}>
      {shown.map(([label, value]) => [
        <dt key={`${label}-t`} class="label">{label}</dt>,
        <dd key={`${label}-d`}>{value}</dd>,
      ])}
    </dl>
  );
}

/** The post as written on HN; its HTML was sanitized with nh3 when it was ingested. */
export function FullPost({ html }: { html: string }) {
  return <div class="post-body" dangerouslySetInnerHTML={{ __html: html }} />;
}

export function Tech({ names }: { names: string[] }) {
  if (!names.length) return null;
  return (
    <ul class="tech" aria-label="Technologies">
      {names.map((name) => <li key={name}>{name}</li>)}
    </ul>
  );
}

export function PayBlock({ pay, currency, rates }: { pay: Pay; currency: string; rates: Rates }) {
  const shown = displayPay(pay, currency, rates);
  return (
    <div class="pay">
      <strong>{shown.main}</strong>
      <span class="label">{shown.original ? `${shown.original} ${shown.period}` : shown.period}</span>
    </div>
  );
}

/** "Also posted in Oct" or "Also posted in 6 months", opening the poster's history. */
export function HistoryBadge({ post, onOpen, verb = 'posted', class: className = 'badge history' }: {
  post: Post;
  onOpen: () => void;
  verb?: string;
  class?: string;
}) {
  const others = [...new Set(post.history.map((entry) => entry.month))].sort();
  if (!others.length) return null;
  const when = others.length === 1 ? monthLabel(others[0], 'short') : `${others.length} months`;
  return (
    <button class={className} type="button" onClick={onOpen}
      title={others.map((month) => monthLabel(month)).join(', ')}>
      Also {verb} in {when}
    </button>
  );
}

/** The arrow after links that open a new tab. */
export function Ext() {
  return <span class="ext" aria-hidden="true">↗</span>;
}

/** A link that opens in a new tab. */
export function Out({ href, class: className, children }: { href: string; class?: string; children: ComponentChildren }) {
  return (
    <a class={className} target="_blank" rel="noopener noreferrer" href={href}>
      {children}
    </a>
  );
}
