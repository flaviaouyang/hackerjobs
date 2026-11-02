import { useEffect, useRef, useState } from 'preact/hooks';
import { hnItem, monthLabel } from '../lib/format';
import { displayPay } from '../lib/money';
import type { Post, Rates } from '../lib/types';

interface Props {
  post: Post | null;
  loadMonth: (month: string) => Promise<Post[]>;
  currency: string;
  rates: Rates;
  onClose: () => void;
}

interface Entry {
  month: string;
  id: number;
  post: Post | null;
}

function summary(post: Post, currency: string, rates: Rates): string {
  const roles = post.fields.roles.map((role) => (typeof role === 'string' ? role : role.title));
  const pay = post.fields.pay && displayPay(post.fields.pay, currency, rates).main;
  return [roles.join(', '), pay].filter(Boolean).join(' · ') || 'No roles listed';
}

/** A company's (or candidate's) posts across months, newest first. */
export function HistoryDialog({ post, loadMonth, currency, rates, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [entries, setEntries] = useState<Entry[]>([]);

  useEffect(() => {
    if (!post) return;
    dialog.current?.showModal();
    const all = [{ month: '', id: post.id }, ...post.history];
    setEntries(all.map(({ month, id }) => ({ month, id, post: id === post.id ? post : null })));
    let cancelled = false;
    Promise.all(
      post.history.map(async ({ month, id }) => ({
        month,
        id,
        post: (await loadMonth(month)).find((other) => other.id === id) ?? null,
      })),
    ).then((loaded) => {
      if (!cancelled) setEntries([{ month: '', id: post.id, post }, ...loaded].sort((a, b) => b.id - a.id));
    });
    return () => {
      cancelled = true;
    };
  }, [post, loadMonth]);

  if (!post) return null;
  const name = 'company' in post.fields ? (post.fields.company ?? 'Company not named') : post.author;
  return (
    <dialog ref={dialog} aria-labelledby="history-title" onClose={onClose}>
      <div class="dialog-head">
        <h2 id="history-title">{name}</h2>
        <button class="close" type="button" aria-label="Close" onClick={() => dialog.current?.close()}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
      <div class="dialog-body">
        <ol class="timeline">
          {entries.map((entry) => (
            <li key={entry.id} aria-current={entry.id === post.id ? 'true' : undefined}>
              <span class="when">{entry.month ? monthLabel(entry.month) : 'This post'}</span>
              <span>{entry.post ? summary(entry.post, currency, rates) : 'Loading…'}</span>
              <a target="_blank" rel="noopener noreferrer" href={hnItem(entry.id)}>Original post on HN</a>
            </li>
          ))}
        </ol>
      </div>
    </dialog>
  );
}
