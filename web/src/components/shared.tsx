import type { ComponentChildren } from 'preact';
import { monthLabel } from '../lib/format';
import { displayPay } from '../lib/money';
import type { Pay, Post, Rates } from '../lib/types';

export type Detail = [string, ComponentChildren];

/** A label/value list that skips empty values. */
export function Details({ items }: { items: Detail[] }) {
  const shown = items.filter(([, value]) => value !== null && value !== undefined && value !== '');
  if (!shown.length) return null;
  return (
    <dl>
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

/** "Also posted in May, Jun", opening the poster's history. */
export function HistoryFlag({ post, onOpen, verb = 'posted' }: { post: Post; onOpen: () => void; verb?: string }) {
  const others = [...new Set(post.history.map((entry) => entry.month))].sort();
  if (!others.length) return null;
  return (
    <button class="flag" type="button" onClick={onOpen}>
      Also {verb} in {others.map((month) => monthLabel(month, 'short')).join(', ')}
    </button>
  );
}
