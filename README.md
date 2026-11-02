# hackerjobs

A job board for Hacker News' monthly **"Who is hiring?"** and **"Who wants to be hired?"** threads.
Every post is turned into searchable, filterable fields (roles, pay, location, remote or not,
technologies, company stage, industry and more), and every entry links back to its original post
and its author on HN.

Data starts from January 2026.

## How it works

1. **Ingest**: fetches the threads posted by the `whoishiring` account and their top-level
   comments from the [official HN API](https://github.com/HackerNews/API). Posts that are deleted
   or flagged dead are removed.
2. **Parse**: each post's fields are extracted twice, by simple rules (the candidate template, the
   `Company | Role | Location` header, pay and email patterns) and by a model with schema-constrained
   output. The model only copies what the post states; it never writes. Rules and model are merged
   per field, using whichever scored better on a labelled benchmark (`eval/benchmark.jsonl`).
3. **Clean up**: text the post doesn't contain is dropped, technologies get canonical names
   (`hackerjobs/technologies.toml`), currencies become ISO codes, and companies are matched across
   months by website, then by name.
4. **Export**: one JSON file per thread and month, plus an index with exchange rates from the
   [Bank of Canada](https://www.bankofcanada.ca/rates/exchange/), for converting pay.
5. **Site**: a static [Astro](https://astro.build) site with one [Preact](https://preactjs.com)
   island for search, filters and pagination. Everything runs in the browser; there is no server.

Posts in the wrong thread (a candidate in a hiring thread, questions, jokes) are left out.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh)
- A model to parse with, either:
  - an [Anthropic API key](https://console.anthropic.com/) in `ANTHROPIC_API_KEY` (the published
    site uses Claude Haiku 5.5; parsing every post since January 2026 costs about $3), or
  - [LM Studio](https://lmstudio.ai) running locally, free, with any model that supports
    structured output

## Getting started

```sh
uv sync
cd web && bun install && cd ..

uv run hackerjobs sync          # ingest, exchange rates, parse, export
cd web && bun run dev           # http://localhost:4321/hackerjobs/
```

`sync` only parses posts it hasn't parsed before, so running it again is cheap. The SQLite
database lives in `data/` and the exported site data in `web/public/data/`; neither is committed.

## Configuration

`hackerjobs.toml`:

| Setting | Meaning |
|---|---|
| `since` | First month to ingest (`YYYY-MM`) |
| `parse.models` | Models to parse with, as `provider:model`, e.g. `anthropic:claude-haiku-5-5` or `lmstudio:google/gemma-4-e4b` |
| `publish.models` | Whose extractions go on the site, in order of preference: each post uses the first model that has parsed it |
| `review` | Optional: have one model review another's extractions |
| `anthropic.concurrency`, `lmstudio.concurrency` | Parallel requests per provider |
| `lmstudio.url` | LM Studio's server address |

## Commands

| Command | What it does |
|---|---|
| `hackerjobs ingest` | Fetch threads and posts from Hacker News |
| `hackerjobs fx` | Fetch the latest exchange rates |
| `hackerjobs parse` | Extract fields from posts not yet parsed at the current prompt version |
| `hackerjobs review` | Review one model's extractions with another |
| `hackerjobs export` | Write the site's data files |
| `hackerjobs sync` | Ingest, fx, parse, review (if configured) and export, in order |
| `hackerjobs eval` | Score extraction on the labelled benchmark, per field and per source |
| `hackerjobs companies` | List similar company names that are kept apart, for review |

Run any of them with `--help` for options.

## Development

```sh
uv run pytest                   # Python tests
uv run ruff check . && uv run ruff format --check .

cd web
bun test                        # site logic tests
bun run check                   # type check
bun run build                   # static site in web/dist/
```

Changing a prompt or the output schema changes that thread kind's prompt version, so the next
`parse` re-parses only that kind. Run `hackerjobs eval` before and after to compare.

## License

[MIT](LICENSE). Posts belong to their authors on Hacker News; the board links to every original.
