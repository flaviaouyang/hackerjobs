import { useState } from 'preact/hooks';
import { applyLink, arrangement, dayLabel, hnItem, hnUser, repostMonth, someOf, withScheme } from '../lib/format';
import { displayPay, formatRange } from '../lib/money';
import type { HiringPost, Money, Rates } from '../lib/types';
import { Details, type Detail, FullPost, HistoryFlag, PayBlock, Tech } from './shared';

interface Props {
  post: HiringPost;
  currency: string;
  rates: Rates;
  onHistory: (post: HiringPost) => void;
}

const STAGES: Record<string, string> = {
  'pre-seed': 'Pre-seed', seed: 'Seed', 'series-a': 'Series A', 'series-b': 'Series B', 'series-c': 'Series C',
  'series-d+': 'Series D+', public: 'Public', bootstrapped: 'Bootstrapped', subsidiary: 'Subsidiary', nonprofit: 'Nonprofit',
};

function money(value: Money | null): string | null {
  return value ? formatRange(value.amount, value.amount, value.currency ?? 'USD') : null;
}

export function JobCard({ post, currency, rates, onHistory }: Props) {
  const [open, setOpen] = useState(false);
  const fields = post.fields;
  const apply = applyLink(fields);
  const repost = post.repost_of !== null ? repostMonth(post) : null;
  const about = [...fields.industries, fields.company_stage ? STAGES[fields.company_stage] : null].filter(Boolean);
  const facts = [
    [someOf(fields.locations), arrangement(fields.remote)].filter(Boolean).join(' · '),
    fields.employment_types.map((type) => type[0].toUpperCase() + type.slice(1)).join(', '),
    fields.equity ? (fields.equity_details ?? 'Equity') : null,
    fields.visa_sponsorship === true ? 'Visa sponsorship' : fields.visa_sponsorship === false ? 'No visa sponsorship' : null,
    fields.min_experience_years ? `${fields.min_experience_years}+ years` : null,
  ].filter(Boolean);
  const details: Detail[] = [
    ['Website', fields.company_website && <a href={withScheme(fields.company_website)}>{fields.company_website}</a>],
    ['Funding', [money(fields.funding), money(fields.valuation) && `${money(fields.valuation)} valuation`].filter(Boolean).join(' · ')],
    ['Investors', fields.investors.join(', ')],
    ['Team', fields.team_size],
    ['Founded', fields.founded_year],
    ['Benefits', fields.benefits.join(' · ')],
    ['Relocation', fields.relocation_support === true ? 'Relocation support' : fields.relocation_support === false ? 'No relocation support' : null],
    ['Work authorization', fields.work_authorization],
    ['Clearance', fields.security_clearance],
    ['Languages', fields.languages.join(', ')],
    ['Timezone', fields.timezone],
    ['Hours', fields.hours],
    ['Education', fields.education],
    ['Interviews', fields.interview_process],
  ];
  return (
    <article class="card">
      <div>
        <div class="card-top">
          <h2>{fields.company ?? post.author}</h2>
          {fields.applications_closed && <span class="flag closed">Applications closed</span>}
          {post.new && <span class="flag new">New company</span>}
          {repost && <span class="flag">Repost of {repost}</span>}
          <HistoryFlag post={post} onOpen={() => onHistory(post)} />
          {about.length > 0 && <span class="flag">{about.join(' · ')}</span>}
          <span class="flag">{dayLabel(post.posted_at)}</span>
        </div>
        {fields.roles.length > 0 && (
          <ul class="roles">
            {fields.roles.map((role) => {
              const pay = role.pay && displayPay(role.pay, currency, rates);
              return (
                <li key={role.title}>
                  {role.apply_url ? <a href={withScheme(role.apply_url)}>{role.title}</a> : role.title}
                  {pay && <span class="role-pay">{pay.main}</span>}
                </li>
              );
            })}
          </ul>
        )}
        {fields.company_description && <p class="desc">{fields.company_description}</p>}
        {facts.length > 0 && <p class="facts">{facts.map((fact) => <span key={fact}>{fact}</span>)}</p>}
        <Tech names={fields.technologies} />
      </div>
      {fields.pay ? <PayBlock pay={fields.pay} currency={currency} rates={rates} /> : <span />}
      {fields.application_instructions && (
        <p class="how"><strong>How to apply:</strong> {fields.application_instructions}</p>
      )}
      <div class="actions">
        {apply && (
          <a class="button" href={apply.href}>
            {apply.label} <span class="arrow" aria-hidden="true">↗</span>
          </a>
        )}
        <a href={hnItem(post.id)}>Original post on HN</a>
        <span>
          by <a href={hnUser(post.author)}>{post.author}</a>
        </span>
        <button class="button quiet expand" type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? 'Hide full post' : 'Show full post'}
        </button>
      </div>
      {open && (
        <div class="details">
          <Details items={details} />
          <FullPost html={post.html} />
        </div>
      )}
    </article>
  );
}
