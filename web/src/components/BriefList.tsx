import { applyLink, arrangement, hnItem, hnUser, type Link, someOf } from '../lib/format';
import type { Post } from '../lib/types';
import { Ext, LinkTo, Out } from './shared';

function Row({ post }: { post: Post }) {
  const fields = post.fields;
  const hiring = 'company' in fields;
  const what = [someOf(fields.locations, 3, ' · '), arrangement(fields.remote)].filter(Boolean).join(' · ');
  const apply: Link | null = hiring
    ? applyLink(fields)
    : fields.contact_email
      ? { scrambled: fields.contact_email, label: 'Email' }
      : null;
  return (
    <li>
      <div>
        <span class="who">
          {hiring ? (fields.company ?? <span class="unnamed">Company not named</span>) : <Out href={hnUser(post.author)}>{post.author}</Out>}
        </span>
        {what && <span class="what"> · {what}</span>}
      </div>
      <div class="links">
        {apply && (
          <LinkTo link={apply} count={hiring ? 'apply' : 'email-candidate'}>
            {hiring ? 'Apply' : apply.label} <Ext />
          </LinkTo>
        )}
        <Out href={hnItem(post.id)} count="hn-post">
          HN post <Ext />
        </Out>
      </div>
    </li>
  );
}

/** Posts that say little beyond who posted them, one line each. */
export function BriefList({ posts, total }: { posts: Post[]; total: number }) {
  return (
    <section class="brief" aria-labelledby="brief-title">
      <h2 id="brief-title">Brief posts · {total}</h2>
      <p>These posts say little beyond who posted them, so they're listed last. Open the post on HN for details.</p>
      <ul>
        {posts.map((post) => <Row key={post.id} post={post} />)}
      </ul>
    </section>
  );
}
