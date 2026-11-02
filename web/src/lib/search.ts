import MiniSearch from 'minisearch';
import type { Post } from './types';

interface Document {
  id: number;
  heading: string;
  technologies: string;
  body: string;
}

const TAGS = /<[^>]+>/g;

function document(post: Post): Document {
  const fields = post.fields;
  const roles = fields.roles.map((role) => (typeof role === 'string' ? role : role.title));
  const name = 'company' in fields ? (fields.company ?? '') : post.author;
  return {
    id: post.id,
    heading: [name, ...roles].join(' '),
    technologies: fields.technologies.join(' '),
    body: post.html.replace(TAGS, ' '),
  };
}

export type SearchIndex = MiniSearch<Document>;

/** Build a full-text index over one month's posts; names, roles and technologies rank highest. */
export function buildIndex(posts: Post[]): SearchIndex {
  const index = new MiniSearch<Document>({
    fields: ['heading', 'technologies', 'body'],
    searchOptions: { boost: { heading: 3, technologies: 2 }, prefix: true, fuzzy: 0.15, combineWith: 'AND' },
  });
  index.addAll(posts.map(document));
  return index;
}

/** Ids of posts matching a query, or null when the query is empty. */
export function searchIds(index: SearchIndex, query: string): Set<number> | null {
  const trimmed = query.trim();
  return trimmed ? new Set(index.search(trimmed).map((result) => result.id as number)) : null;
}
