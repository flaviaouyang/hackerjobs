import { useCallback, useEffect, useMemo, useRef, useState } from 'preact/hooks';
import { applyFilters, DEFAULT_FILTERS, isBrief, type Filters as FilterState, parseFilters, serializeFilters } from '../lib/filters';
import { monthLabel } from '../lib/format';
import { pageWindow } from '../lib/pages';
import { buildIndex, searchIds } from '../lib/search';
import type { HiringPost, Index, Kind, Post, SeekingPost } from '../lib/types';
import { BriefList } from './BriefList';
import { CandidateCard } from './CandidateCard';
import { Filters } from './Filters';
import { HistoryDialog } from './HistoryDialog';
import { JobCard } from './JobCard';
import { Out, REPO } from './shared';
import { ThemeSwitch } from './ThemeSwitch';

const BASE = import.meta.env.BASE_URL.replace(/\/?$/, '/');
const PAGE_SIZE = 20;
const COMMON_CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'CHF', 'INR', 'JPY', 'SGD'];
const LABELS: Record<Kind, string> = { hiring: 'Hiring', seeking: 'Seeking' };

const months = new Map<string, Promise<Post[]>>();

/** One month of posts, fetched once per page view. */
function loadMonth(kind: Kind, month: string): Promise<Post[]> {
  const key = `${kind}-${month}`;
  if (!months.has(key)) {
    months.set(
      key,
      fetch(`${BASE}data/${key}.json`).then((response) => {
        if (!response.ok) throw new Error(`Could not load ${monthLabel(month)} (${response.status})`);
        return response.json() as Promise<Post[]>;
      }),
    );
  }
  return months.get(key) as Promise<Post[]>;
}

function Pagination({ page, count, onPage }: { page: number; count: number; onPage: (page: number) => void }) {
  return (
    <nav class="pages" aria-label="Pages">
      <button type="button" disabled={page === 1} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      {pageWindow(page, count).map((number, index) =>
        number === null ? (
          <span key={`gap-${index}`} class="gap" aria-hidden="true">…</span>
        ) : (
          <button key={number} type="button" aria-current={number === page ? 'page' : undefined}
            aria-label={`Page ${number}`} onClick={() => onPage(number)}>
            {number}
          </button>
        ),
      )}
      <button type="button" disabled={page === count} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </nav>
  );
}

function CloseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

/** Whether the header should step aside: true while scrolling down past it, false on any scroll up. */
function useScrollingDown(header: { current: HTMLElement | null }): boolean {
  const [down, setDown] = useState(false);
  useEffect(() => {
    let last = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY;
      setDown(y > last && y > (header.current?.offsetHeight ?? 0));
      last = y;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [header]);
  return down;
}

/** The whole board for one thread kind: header controls, search, filters and results. */
export function Board({ kind }: { kind: Kind }) {
  const [index, setIndex] = useState<Index | null>(null);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [ready, setReady] = useState(false);
  const [posts, setPosts] = useState<Post[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resultsTop = useRef<HTMLElement>(null);
  const [history, setHistory] = useState<Post | null>(null);
  const drawer = useRef<HTMLDialogElement>(null);
  const hiring = kind === 'hiring';
  const bar = useRef<HTMLElement>(null);
  const hideBar = useScrollingDown(bar);

  useEffect(() => {
    setFilters(parseFilters(window.location.search));
    setReady(true);
    fetch(`${BASE}data/index.json`)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('Could not load the board'))))
      .then(setIndex, (failure: Error) => setError(failure.message));
  }, []);

  const available = useMemo(() => (index ? Object.keys(index.months).sort().reverse() : []), [index]);
  const month = filters.month && available.includes(filters.month) ? filters.month : (available[0] ?? null);

  useEffect(() => {
    if (!month) return;
    setPosts(null);
    loadMonth(kind, month).then(setPosts, (failure: Error) => setError(failure.message));
  }, [kind, month]);

  useEffect(() => {
    if (ready) window.history.replaceState(null, '', `${window.location.pathname}${serializeFilters(filters)}`);
  }, [filters, ready]);

  const searchIndex = useMemo(() => (posts ? buildIndex(posts) : null), [posts]);
  const results = useMemo(() => {
    if (!posts || !index || !searchIndex) return [];
    return applyFilters(posts, kind, filters, index.rates, searchIds(searchIndex, filters.q));
  }, [posts, index, searchIndex, kind, filters]);
  const currencies = useMemo(() => {
    const known = index ? Object.keys(index.rates.cad_per_unit) : COMMON_CURRENCIES;
    return [...COMMON_CURRENCIES.filter((code) => known.includes(code)), ...known.filter((code) => !COMMON_CURRENCIES.includes(code)).sort()];
  }, [index]);

  // Any change other than turning the page starts again from the first page.
  const update = useCallback((changes: Partial<FilterState>) => {
    setFilters((current) => ({ ...current, page: 1, ...changes }));
  }, []);
  const pageCount = Math.max(1, Math.ceil(results.length / PAGE_SIZE));
  const page = Math.min(filters.page, pageCount);
  const shown = results.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const detailed = shown.filter((post) => !isBrief(post));
  const briefShown = shown.filter(isBrief);
  const briefTotal = useMemo(() => results.filter(isBrief).length, [results]);
  const turnPage = (next: number) => {
    update({ page: next });
    resultsTop.current?.scrollIntoView({ block: 'start' });
  };
  const loadHistory = useCallback((other: string) => loadMonth(kind, other), [kind]);
  const tabLink = (other: Kind) => `${BASE}${other}/${month ? `?month=${month}` : ''}`;
  const filterPanel = <Filters kind={kind} posts={posts ?? []} filters={filters} update={update} />;

  return (
    <>
      <header class={hideBar ? 'bar hidden' : 'bar'} ref={bar}>
        <div class="wrap">
          <a class="mark" href={`${BASE}hiring/`}>
            hacker<span>jobs</span>
          </a>
          <nav class="tabs" aria-label="Board">
            {(['hiring', 'seeking'] as Kind[]).map((other) => (
              <a key={other} href={tabLink(other)} aria-current={other === kind ? 'page' : undefined}>
                {LABELS[other]}
                {month && index?.months[month]?.[other] !== undefined && (
                  <span class="count">{index.months[month][other]}</span>
                )}
              </a>
            ))}
          </nav>
          <div class="controls">
            <label class="field">
              <span class="label">Month</span>
              <select class="input" value={month ?? ''} onChange={(event) => update({ month: event.currentTarget.value })}>
                {available.map((value) => <option key={value} value={value}>{`${monthLabel(value, 'short')} ${value.slice(0, 4)}`}</option>)}
              </select>
            </label>
            <label class="field">
              <span class="label">Currency</span>
              <select class="input" value={filters.currency} onChange={(event) => update({ currency: event.currentTarget.value })}>
                {currencies.map((code) => <option key={code} value={code}>{code}</option>)}
              </select>
            </label>
            <ThemeSwitch />
            <Out href={REPO} class="repo">
              <svg width="20" height="20" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
              </svg>
              <span class="visually-hidden">Source on GitHub</span>
            </Out>
          </div>
        </div>
      </header>

      <main id="main" class="wrap">
        <form class="search" role="search" onSubmit={(event) => event.preventDefault()}>
          <label class="field">
            <span class="label">Search</span>
            <input class="input" type="search" value={filters.q}
              placeholder={hiring ? 'Roles, companies, technologies' : 'Roles, technologies, interests'}
              onInput={(event) => update({ q: event.currentTarget.value })} />
          </label>
          <label class="field">
            <span class="label">Location</span>
            <input class="input" type="text" value={filters.location} placeholder="City, country or region"
              onInput={(event) => update({ location: event.currentTarget.value })} />
          </label>
        </form>

        <div class="layout">
          <aside class="sidebar" aria-label="Filters">{filterPanel}</aside>
          <section class="results" aria-label="Results" aria-busy={!posts && !error} ref={resultsTop}>
            <div class="summary">
              <h1>
                {posts ? results.length.toLocaleString('en-US') : '…'} {hiring ? 'jobs' : 'candidates'}
              </h1>
              {month && <span class="label">{monthLabel(month)}</span>}
              <p class="notice">
                Details are read from each post by rules and AI, which can make mistakes. Check the original post
                before you apply or reach out.
              </p>
              <button class="button quiet filters-button" type="button" onClick={() => drawer.current?.showModal()}>
                Filters
              </button>
              {hiring && (
                <label class="sort">
                  <span class="label">Sort</span>
                  <select class="input" value={filters.sort}
                    onChange={(event) => update({ sort: event.currentTarget.value === 'pay' ? 'pay' : 'newest' })}>
                    <option value="newest">Newest</option>
                    <option value="pay">Highest pay</option>
                  </select>
                </label>
              )}
            </div>
            {error && <p class="status" role="alert">{error}</p>}
            {!error && !posts && <p class="status">Loading…</p>}
            {posts && !results.length && <p class="status">No posts match these filters.</p>}
            {index &&
              detailed.map((post) =>
                hiring ? (
                  <JobCard key={post.id} post={post as HiringPost} currency={filters.currency} rates={index.rates} onHistory={setHistory} />
                ) : (
                  <CandidateCard key={post.id} post={post as SeekingPost} currency={filters.currency} rates={index.rates} onHistory={setHistory} />
                ),
              )}
            {briefShown.length > 0 && <BriefList posts={briefShown} total={briefTotal} />}
            {pageCount > 1 && <Pagination page={page} count={pageCount} onPage={turnPage} />}
          </section>
        </div>
      </main>

      <dialog ref={drawer} class="drawer" aria-labelledby="filters-title">
        <div class="dialog-head">
          <h2 id="filters-title">Filters</h2>
          <button class="close" type="button" aria-label="Close" onClick={() => drawer.current?.close()}>
            <CloseIcon />
          </button>
        </div>
        <div class="dialog-body">{filterPanel}</div>
      </dialog>

      {index && (
        <HistoryDialog post={history} loadMonth={loadHistory} currency={filters.currency} rates={index.rates}
          onClose={() => setHistory(null)} />
      )}
    </>
  );
}
