import { applyLink, arrangement, hnItem, hnUser, isEmail, someOf } from '../lib/format';
import type { Post } from '../lib/types';
import { Ext, Out } from './shared';

function Row({ post }: { post: Post }) {
  const fields = post.fields;
  const hiring = 'company' in fields;
  const what = [someOf(fields.locations, 3, ' · '), arrangement(fields.remote)].filter(Boolean).join(' · ');
  const apply = hiring ? applyLink(fields) : fields.contact && isEmail(fields.contact) ? { href: `mailto:${fields.contact}`, label: 'Email' } : null;
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
          <Out href={apply.href} count={hiring ? 'apply' : 'email-candidate'}>
            {hiring ? 'Apply' : apply.label} <Ext />
          </Out>
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
