import { useState } from 'preact/hooks';
import { arrangement, dayLabel, hnItem, hnUser, repostMonth, withScheme } from '../lib/format';
import type { Rates, SeekingPost } from '../lib/types';
import { Details, type Detail, Ext, FullPost, HistoryBadge, MailLink, Out, PayBlock, Tech } from './shared';

interface Props {
  post: SeekingPost;
  currency: string;
  rates: Rates;
  onHistory: (post: SeekingPost) => void;
}

const capitalize = (value: string) => value[0].toUpperCase() + value.slice(1);

/** Where a candidate is, with their timezone unless a location already says it. */
export function candidatePlace(locations: string[], timezone: string | null): string {
  // The candidate template's Location line often carries the timezone too; don't say it twice.
  const zone = timezone?.toLowerCase();
  const zoneShown = zone !== undefined && locations.some((location) => location.toLowerCase().includes(zone));
  return [locations.join(' · '), !zoneShown && timezone && `(${timezone})`].filter(Boolean).join(' ');
}

export function CandidateCard({ post, currency, rates, onHistory }: Props) {
  const [open, setOpen] = useState(false);
  const fields = post.fields;
  const repost = post.repost_of !== null ? repostMonth(post) : null;
  const how = [
    ...fields.arrangements.map(arrangement),
    fields.willing_to_relocate ? 'Open to relocation' : null,
    ...fields.employment_types.map(capitalize),
  ].filter(Boolean);
  const facts: Detail[] = [
    ['Where', candidatePlace(fields.locations, fields.timezone)],
    ['How', how.join(' · ')],
    ['Experience', fields.experience_years !== null && `${fields.experience_years} years`],
    ['Wants', fields.interests.join(', ')],
    ['Authorization', fields.work_authorization],
    ['Available', fields.availability],
    ['Stack', fields.technologies.length > 0 && <Tech names={fields.technologies} />],
  ];
  const links = [
    fields.resume_url && ['Résumé', fields.resume_url],
    fields.github && ['GitHub', fields.github],
    fields.linkedin && ['LinkedIn', fields.linkedin],
    fields.website && ['Website', fields.website],
  ].filter((link): link is [string, string] => Boolean(link));
  const details: Detail[] = [
    ['Education', fields.education],
    ['Languages', fields.languages.join(', ')],
  ];
  return (
    <article class="card">
      <div class="card-head">
        {/* Candidates keep their flags beside the name, as small labels rather than badges. */}
        <div class="card-top">
          <h2>
            <Out href={hnUser(post.author)}>{post.author}</Out>
          </h2>
          {post.new && <span class="flag">First post</span>}
          {repost && <span class="flag">Repost of {repost}</span>}
          <HistoryBadge post={post} verb="looking" class="flag" onOpen={() => onHistory(post)} />
          <time class="flag" dateTime={new Date(post.posted_at * 1000).toISOString()}>{dayLabel(post.posted_at)}</time>
        </div>
        {fields.pay ? <PayBlock pay={fields.pay} currency={currency} rates={rates} /> : <span />}
      </div>
      {fields.roles.length > 0 && <p class="wants">{fields.roles.join(' · ')}</p>}
      <Details items={facts} class="facts" />
      <div class="actions">
        {fields.contact_email && (
          <MailLink class="button" scrambled={fields.contact_email} count="email-candidate">
            Email <span class="arrow" aria-hidden="true">↗</span>
          </MailLink>
        )}
        {links.map(([label, url]) => (
          <Out key={label} href={withScheme(url)}>
            {label} <Ext />
          </Out>
        ))}
        <Out href={hnItem(post.id)} count="hn-post">
          Original post on HN <Ext />
        </Out>
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
