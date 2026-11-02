import { useState } from 'preact/hooks';
import { arrangement, dayLabel, hnItem, hnUser, isEmail, repostMonth, someOf, withScheme } from '../lib/format';
import { displayPay } from '../lib/money';
import type { Rates, SeekingPost } from '../lib/types';
import { Details, type Detail, FullPost, HistoryFlag, Tech } from './shared';

interface Props {
  post: SeekingPost;
  currency: string;
  rates: Rates;
  onHistory: (post: SeekingPost) => void;
}

export function CandidateCard({ post, currency, rates, onHistory }: Props) {
  const [open, setOpen] = useState(false);
  const fields = post.fields;
  const repost = post.repost_of !== null ? repostMonth(post) : null;
  const place = [someOf(fields.locations), fields.timezone && `(${fields.timezone})`].filter(Boolean).join(' ');
  const facts = [
    place,
    [arrangement(fields.remote), fields.willing_to_relocate ? 'open to relocation' : null].filter(Boolean).join(' · '),
    fields.experience_years !== null ? `${fields.experience_years} years` : null,
    fields.employment_types.map((type) => type[0].toUpperCase() + type.slice(1)).join(', '),
    fields.work_authorization,
    fields.availability,
  ].filter(Boolean);
  const pay = fields.pay && displayPay(fields.pay, currency, rates);
  const links = [
    fields.resume_url && ['Résumé', fields.resume_url],
    fields.github && ['GitHub', fields.github],
    fields.linkedin && ['LinkedIn', fields.linkedin],
    fields.website && ['Website', fields.website],
  ].filter((link): link is [string, string] => Boolean(link));
  const details: Detail[] = [
    ['Expected pay', pay && `${pay.main} ${pay.period}${pay.original ? ` (${pay.original})` : ''}`],
    ['Education', fields.education],
    ['Languages', fields.languages.join(', ')],
  ];
  return (
    <article class="card">
      <div>
        <div class="card-top">
          <h2>
            <a href={hnUser(post.author)}>{post.author}</a>
          </h2>
          {post.new && <span class="flag new">First post</span>}
          {repost && <span class="flag">Repost of {repost}</span>}
          <HistoryFlag post={post} verb="looking" onOpen={() => onHistory(post)} />
          <span class="flag">{dayLabel(post.posted_at)}</span>
        </div>
        {fields.roles.length > 0 && <p class="roles">{fields.roles.join(' · ')}</p>}
        {facts.length > 0 && <p class="facts">{facts.map((fact) => <span key={fact}>{fact}</span>)}</p>}
        {fields.interests.length > 0 && (
          <p class="interests">
            <strong>Wants to work on:</strong> {fields.interests.join(', ')}
          </p>
        )}
        <Tech names={fields.technologies} />
      </div>
      <span />
      <div class="actions">
        {fields.contact && isEmail(fields.contact) && (
          <a class="button" href={`mailto:${fields.contact}`}>
            Email <span class="arrow" aria-hidden="true">↗</span>
          </a>
        )}
        {links.map(([label, url]) => <a key={label} href={withScheme(url)}>{label}</a>)}
        <a href={hnItem(post.id)}>Original post on HN</a>
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
