import { useState } from 'preact/hooks';
import { applyLink, arrangement, dayLabel, hnItem, hnUser, repostMonth, withScheme } from '../lib/format';
import { displayPay, formatRange } from '../lib/money';
import type { HiringPost, Money, Rates } from '../lib/types';
import { Details, type Detail, Ext, FullPost, HistoryBadge, LinkTo, MailLink, Out, PayBlock, Tech } from './shared';

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
// Longer role lists show this many until expanded; one hidden role is not worth a button.
const ROLES_SHOWN = 3;

function money(value: Money | null): string | null {
  return value ? formatRange(value.amount, value.amount, value.currency ?? 'USD') : null;
}

const capitalize = (value: string) => value[0].toUpperCase() + value.slice(1);

export function JobCard({ post, currency, rates, onHistory }: Props) {
  const [open, setOpen] = useState(false);
  const [allRoles, setAllRoles] = useState(false);
  const fields = post.fields;
  const apply = applyLink(fields);
  const repost = post.repost_of !== null ? repostMonth(post) : null;
  const about = [...fields.industries, fields.company_stage ? STAGES[fields.company_stage] : null].filter(Boolean);
  const how = [
    arrangement(fields.remote),
    ...fields.employment_types.map(capitalize),
    fields.min_experience_years ? `${fields.min_experience_years}+ years` : null,
    fields.visa_sponsorship === true ? 'Visa sponsorship' : fields.visa_sponsorship === false ? 'No visa sponsorship' : null,
    fields.equity ? (fields.equity_details ? `Equity ${fields.equity_details}` : 'Equity') : null,
  ].filter(Boolean);
  const facts: Detail[] = [
    ['Where', fields.locations.join(' · ')],
    ['How', how.join(' · ')],
    ['Stack', fields.technologies.length > 0 && <Tech names={fields.technologies} />],
  ];
  const collapsible = fields.roles.length > ROLES_SHOWN + 1;
  const roles = collapsible && !allRoles ? fields.roles.slice(0, ROLES_SHOWN) : fields.roles;
  const details: Detail[] = [
    ['Website', fields.company_website && <Out href={withScheme(fields.company_website)}>{fields.company_website}</Out>],
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
      <div class="card-head">
        <h2>{fields.company ?? <span class="unnamed">Company not named</span>}</h2>
        {fields.pay ? <PayBlock pay={fields.pay} currency={currency} rates={rates} /> : <span />}
        <div class="meta">
          {fields.applications_closed && <span class="badge closed">Applications closed</span>}
          {post.new && <span class="badge new">New company</span>}
          {repost && <span class="badge repost">Repost of {repost}</span>}
          <HistoryBadge post={post} onOpen={() => onHistory(post)} />
          {about.length > 0 && <span class="tags">{about.join(' · ')}</span>}
          <time dateTime={new Date(post.posted_at * 1000).toISOString()}>{dayLabel(post.posted_at)}</time>
        </div>
      </div>
      {fields.company_description && <p class="desc">{fields.company_description}</p>}
      {fields.roles.length > 0 && (
        <div>
          <p class="label section-label">
            {fields.roles.length} {fields.roles.length === 1 ? 'role' : 'roles'}
          </p>
          <ul class="roles">
            {roles.map((role) => {
              const pay = role.pay && displayPay(role.pay, currency, rates);
              return (
                <li key={role.title}>
                  {role.apply_email ? (
                    <MailLink scrambled={role.apply_email} count="apply">
                      {role.title} <Ext />
                    </MailLink>
                  ) : role.apply_url ? (
                    <Out href={withScheme(role.apply_url)} count="apply">
                      {role.title} <Ext />
                    </Out>
                  ) : (
                    <span>{role.title}</span>
                  )}
                  {pay && <span class="role-pay">{pay.main}</span>}
                </li>
              );
            })}
          </ul>
          {collapsible && (
            <button class="text-button more-roles" type="button" aria-expanded={allRoles} onClick={() => setAllRoles(!allRoles)}>
              {allRoles ? 'Show fewer roles' : `Show all ${fields.roles.length} roles`}
            </button>
          )}
        </div>
      )}
      <Details items={facts} class="facts" />
      {fields.application_instructions && (
        <p class="how">
          <strong>How to apply:</strong> {fields.application_instructions}
        </p>
      )}
      <div class="actions">
        {apply && (
          <LinkTo class="button" link={apply} count="apply">
            {apply.label} <span class="arrow" aria-hidden="true">↗</span>
          </LinkTo>
        )}
        <Out href={hnItem(post.id)} count="hn-post">
          Original post on HN <Ext />
        </Out>
        <span>
          by <Out href={hnUser(post.author)}>{post.author}</Out>
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
