import { useMemo, useState } from 'preact/hooks';
import { arrangementsOf, countValues, DEFAULT_FILTERS, type Filters as FilterState } from '../lib/filters';
import type { HiringPost, Kind, Post, Remote } from '../lib/types';

interface Props {
  kind: Kind;
  posts: Post[];
  filters: FilterState;
  update: (changes: Partial<FilterState>) => void;
}

const REMOTE: Remote[] = ['remote', 'hybrid', 'onsite'];
const SENIORITY = ['intern', 'junior', 'mid', 'senior', 'staff', 'principal', 'lead', 'manager', 'director', 'executive'];
const EMPLOYMENT = ['full-time', 'part-time', 'contract', 'internship'];
const TOP_TECHNOLOGIES = 12;
const MORE_TECHNOLOGIES = 60;

const capitalize = (value: string) => value[0].toUpperCase() + value.slice(1);

function toggle<T>(values: T[], value: T): T[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function Chip({ pressed, onClick, children, count }: { pressed: boolean; onClick: () => void; children: string; count?: number }) {
  return (
    <button class="chip" type="button" aria-pressed={pressed} onClick={onClick}>
      {children}
      {count !== undefined && <span class="n">{count}</span>}
    </button>
  );
}

function Toggle({ checked, onChange, label, count }: { checked: boolean; onChange: (value: boolean) => void; label: string; count?: number }) {
  return (
    <label class="toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.currentTarget.checked)} />
      {label}
      {count !== undefined && <span class="n">{count}</span>}
    </label>
  );
}

function numberOrNull(value: string): number | null {
  const digits = value.replace(/[^\d]/g, '');
  return digits ? Number(digits) : null;
}

export function Filters({ kind, posts, filters, update }: Props) {
  const [allTech, setAllTech] = useState(false);
  const hiring = kind === 'hiring';
  const counts = useMemo(() => {
    const jobs = posts as HiringPost[];
    return {
      remote: new Map(countValues(posts, arrangementsOf)),
      work: countValues(posts, (post) => post.fields.role_categories),
      tech: countValues(posts, (post) => post.fields.technologies),
      industries: hiring ? countValues(jobs, (post) => post.fields.industries) : [],
      reposts: posts.filter((post) => post.repost_of !== null).length,
      fresh: posts.filter((post) => post.new).length,
      equity: hiring ? jobs.filter((post) => post.fields.equity).length : 0,
      visa: hiring ? jobs.filter((post) => post.fields.visa_sponsorship).length : 0,
      closed: hiring ? jobs.filter((post) => post.fields.applications_closed).length : 0,
    };
  }, [posts, hiring]);
  // Keep selected technologies visible even when they fall outside the shown top list.
  const shown = counts.tech.slice(0, allTech ? MORE_TECHNOLOGIES : TOP_TECHNOLOGIES);
  const extra = filters.tech.filter((tech) => !shown.some(([name]) => name === tech)).map((tech): [string, number] => [tech, 0]);

  return (
    <div class="filters">
      {counts.work.length > 0 && (
        <fieldset class="group">
          <legend class="label">Kind of work</legend>
          <div class="chips">
            {counts.work.map(([name, count]) => (
              <Chip key={name} pressed={filters.work.includes(name)} count={count}
                onClick={() => update({ work: toggle(filters.work, name) })}>
                {name}
              </Chip>
            ))}
          </div>
        </fieldset>
      )}

      <fieldset class="group">
        <legend class="label">{hiring ? 'Arrangement' : 'Wants to work'}</legend>
        <div class="chips">
          {REMOTE.map((value) => (
            <Chip key={value} pressed={filters.remote.includes(value)} count={counts.remote.get(value) ?? 0}
              onClick={() => update({ remote: toggle(filters.remote, value) })}>
              {capitalize(value)}
            </Chip>
          ))}
        </div>
        {!hiring && (
          <Toggle label="Willing to relocate" checked={filters.relocate} onChange={(relocate) => update({ relocate })} />
        )}
      </fieldset>

      {hiring ? (
        <label class="group">
          <span class="label">Minimum pay per year ({filters.currency})</span>
          <input class="input" type="text" inputmode="numeric" placeholder="Any"
            value={filters.minPay === null ? '' : filters.minPay.toLocaleString('en-US')}
            onInput={(event) => update({ minPay: numberOrNull(event.currentTarget.value) })} />
          <span class="label">Hides posts without yearly pay</span>
        </label>
      ) : (
        <label class="group">
          <span class="label">At least this many years of experience</span>
          <input class="input" type="text" inputmode="numeric" placeholder="Any"
            value={filters.minYears === null ? '' : String(filters.minYears)}
            onInput={(event) => update({ minYears: numberOrNull(event.currentTarget.value) })} />
        </label>
      )}

      {hiring ? (
        <fieldset class="group">
          <legend class="label">Seniority</legend>
          <div class="chips">
            {SENIORITY.map((level) => (
              <Chip key={level} pressed={filters.seniority.includes(level)}
                onClick={() => update({ seniority: toggle(filters.seniority, level) })}>
                {capitalize(level)}
              </Chip>
            ))}
          </div>
        </fieldset>
      ) : (
        <fieldset class="group">
          <legend class="label">Employment type</legend>
          <div class="chips">
            {EMPLOYMENT.map((type) => (
              <Chip key={type} pressed={filters.employment.includes(type)}
                onClick={() => update({ employment: toggle(filters.employment, type) })}>
                {capitalize(type)}
              </Chip>
            ))}
          </div>
        </fieldset>
      )}

      <fieldset class="group">
        <legend class="label">Technologies</legend>
        <div class="chips">
          {[...extra, ...shown].map(([name, count]) => (
            <Chip key={name} pressed={filters.tech.includes(name)} count={count || undefined}
              onClick={() => update({ tech: toggle(filters.tech, name) })}>
              {name}
            </Chip>
          ))}
        </div>
        {counts.tech.length > TOP_TECHNOLOGIES && (
          <button class="text-button" type="button" onClick={() => setAllTech(!allTech)}>
            {allTech ? 'Show fewer' : 'Show more technologies'}
          </button>
        )}
      </fieldset>

      {hiring && (
        <label class="group">
          <span class="label">Industry</span>
          <select class="input" value={filters.industry ?? ''}
            onChange={(event) => update({ industry: event.currentTarget.value || null })}>
            <option value="">Any industry</option>
            {counts.industries.map(([name, count]) => (
              <option key={name} value={name}>{`${name} (${count})`}</option>
            ))}
          </select>
        </label>
      )}

      <fieldset class="group">
        <legend class="label">More</legend>
        {hiring && (
          <>
            <Toggle label="Visa sponsorship" count={counts.visa} checked={filters.visa} onChange={(visa) => update({ visa })} />
            <Toggle label="Offers equity" count={counts.equity} checked={filters.equity} onChange={(equity) => update({ equity })} />
            <Toggle label="New companies only" count={counts.fresh} checked={filters.newOnly} onChange={(newOnly) => update({ newOnly })} />
            <Toggle label="Hide closed" count={counts.closed} checked={filters.hideClosed} onChange={(hideClosed) => update({ hideClosed })} />
          </>
        )}
        <Toggle label="Hide reposts" count={counts.reposts} checked={filters.hideReposts}
          onChange={(hideReposts) => update({ hideReposts })} />
      </fieldset>

      <button class="text-button" type="button"
        onClick={() => update({ ...DEFAULT_FILTERS, month: filters.month, currency: filters.currency, q: filters.q, location: filters.location })}>
        Clear filters
      </button>
    </div>
  );
}
