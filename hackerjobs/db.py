import json
import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from hackerjobs.fx import Rates
from hackerjobs.hn import Post, Thread
from hackerjobs.models import POSTING_ADAPTERS, Kind, Posting, Review

SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    month TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES threads (id),
    author TEXT NOT NULL,
    posted_at INTEGER NOT NULL,
    html TEXT NOT NULL,
    text TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS posts_thread_id ON posts (thread_id);

CREATE TABLE IF NOT EXISTS extractions (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts (id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
    UNIQUE (post_id, model, prompt_version)
);

CREATE INDEX IF NOT EXISTS extractions_model ON extractions (model, post_id);

-- data holds the corrected Posting when the verdict is "corrected", otherwise NULL.
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    extraction_id INTEGER NOT NULL REFERENCES extractions (id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    verdict TEXT NOT NULL,
    data TEXT,
    issues TEXT NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
    UNIQUE (extraction_id, model, prompt_version)
);

CREATE TABLE IF NOT EXISTS fx_rates (
    currency TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    cad_per_unit REAL NOT NULL
);

-- An edited post must be parsed again; reviews go with their extractions by cascade.
CREATE TRIGGER IF NOT EXISTS posts_edited AFTER UPDATE OF html ON posts BEGIN
    DELETE FROM extractions WHERE post_id = new.id;
END;
"""

UPSERT_POST = """
INSERT INTO posts (id, thread_id, author, posted_at, html, text) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT (id) DO UPDATE SET html = excluded.html, text = excluded.text
WHERE posts.html != excluded.html
"""

# The latest extraction by a model for each post.
LATEST_EXTRACTION = "SELECT MAX(id) FROM extractions WHERE post_id = p.id AND model = ?"
# The latest review's corrections of an extraction; NULL if it was judged correct.
LATEST_REVIEW_DATA = "SELECT data FROM reviews WHERE extraction_id = e.id ORDER BY id DESC LIMIT 1"


@dataclass(frozen=True, slots=True)
class PendingPost:
    """A post waiting to be parsed."""

    id: int
    kind: Kind
    text: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PendingReview:
    """An extraction waiting to be reviewed."""

    extraction_id: int
    kind: Kind
    text: str = field(repr=False)
    posting: Posting = field(repr=False)


@dataclass(frozen=True, slots=True)
class PublishedPost:
    """A post with the extraction to publish, or None if it has not been parsed.

    Attributes:
        kind: Thread kind
        month: Thread month, formatted YYYY-MM
        id: HN item id
        author: HN username of the poster
        posted_at: Unix timestamp of the post
        html: Sanitized post HTML
        text: Plain text of the post
        posting: The model's extraction with review corrections applied
    """

    kind: Kind
    month: str
    id: int
    author: str
    posted_at: int
    html: str
    text: str = field(repr=False)
    posting: Posting | None = field(repr=False)


def connect(path: Path) -> sqlite3.Connection:
    """Open the database, creating the schema if needed.

    Args:
        path: SQLite database file; its directory is created if missing

    Returns:
        An open connection with foreign keys enforced
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def save_thread(
    conn: sqlite3.Connection, thread: Thread, posts: list[Post], removed: Iterable[int] = ()
) -> None:
    """Insert a thread, upsert its posts and delete the ones HN removed, in one transaction.

    Args:
        conn: Database connection
        thread: Thread to save
        posts: Live posts of the thread
        removed: Ids of posts HN reports as dead (flagged) or deleted; their extractions and
            reviews go with them
    """
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO threads (id, kind, month) VALUES (?, ?, ?)",
            (thread.id, thread.kind, thread.month),
        )
        conn.executemany(
            UPSERT_POST,
            (
                (post.id, post.thread_id, post.author, post.posted_at, post.html, post.text)
                for post in posts
            ),
        )
        conn.executemany("DELETE FROM posts WHERE id = ?", ((post_id,) for post_id in removed))


def posts_to_parse(
    conn: sqlite3.Connection, model: str, kind: Kind, prompt_version: str
) -> list[PendingPost]:
    """List posts of a kind without an extraction by a model at a prompt version, newest first.

    Args:
        conn: Database connection
        model: Model reference
        kind: Thread kind
        prompt_version: Version of that kind's extraction prompt

    Returns:
        Posts to parse
    """
    rows = conn.execute(
        "SELECT p.id, t.kind, p.text FROM posts p JOIN threads t ON t.id = p.thread_id "
        "WHERE t.kind = ? AND NOT EXISTS (SELECT 1 FROM extractions e "
        "WHERE e.post_id = p.id AND e.model = ? AND e.prompt_version = ?) "
        "ORDER BY t.month DESC, p.id",
        (kind, model, prompt_version),
    )
    return [PendingPost(post_id, Kind(kind), text) for post_id, kind, text in rows]


def save_extraction(
    conn: sqlite3.Connection, post: PendingPost, model: str, prompt_version: str, posting: Posting
) -> None:
    """Store a model's extraction of a post.

    Args:
        conn: Database connection
        post: The parsed post
        model: Model reference
        prompt_version: Version of the extraction prompt
        posting: Extracted fields
    """
    with conn:
        conn.execute(
            "INSERT INTO extractions (post_id, model, prompt_version, data) VALUES (?, ?, ?, ?)",
            (post.id, model, prompt_version, POSTING_ADAPTERS[post.kind].dump_json(posting)),
        )


def extractions_to_review(
    conn: sqlite3.Connection, reviewer: str, model: str, prompt_version: str
) -> list[PendingReview]:
    """List each post's latest extraction by a model that a reviewer has not yet reviewed.

    Args:
        conn: Database connection
        reviewer: Reviewer model identifier
        model: Identifier of the model whose extractions are reviewed
        prompt_version: Version of the review prompt

    Returns:
        Extractions to review, newest month first
    """
    rows = conn.execute(
        "SELECT e.id, t.kind, p.text, e.data FROM posts p JOIN threads t ON t.id = p.thread_id "
        f"JOIN extractions e ON e.id = ({LATEST_EXTRACTION}) "
        "WHERE NOT EXISTS (SELECT 1 FROM reviews r "
        "WHERE r.extraction_id = e.id AND r.model = ? AND r.prompt_version = ?) "
        "ORDER BY t.month DESC, p.id",
        (model, reviewer, prompt_version),
    )
    return [
        PendingReview(
            extraction_id, Kind(kind), text, POSTING_ADAPTERS[Kind(kind)].validate_json(data)
        )
        for extraction_id, kind, text, data in rows
    ]


def save_review(
    conn: sqlite3.Connection, item: PendingReview, model: str, prompt_version: str, review: Review
) -> None:
    """Store a reviewer's assessment of an extraction.

    Args:
        conn: Database connection
        item: The reviewed extraction
        model: Reviewer model reference
        prompt_version: Version of the review prompt
        review: The assessment
    """
    adapter = POSTING_ADAPTERS[item.kind]
    corrected = adapter.dump_json(review.posting) if review.verdict == "corrected" else None
    with conn:
        conn.execute(
            "INSERT INTO reviews (extraction_id, model, prompt_version, verdict, data, issues) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                item.extraction_id,
                model,
                prompt_version,
                review.verdict,
                corrected,
                json.dumps(review.issues),
            ),
        )


def save_rates(conn: sqlite3.Connection, rates: Rates) -> None:
    """Replace the stored exchange rates.

    Args:
        conn: Database connection
        rates: Latest rates
    """
    with conn:
        conn.execute("DELETE FROM fx_rates")
        conn.executemany(
            "INSERT INTO fx_rates (currency, date, cad_per_unit) VALUES (?, ?, ?)",
            ((currency, rates.date, rate) for currency, rate in rates.cad_per_unit.items()),
        )


def load_rates(conn: sqlite3.Connection) -> Rates | None:
    """Load the stored exchange rates.

    Args:
        conn: Database connection

    Returns:
        The stored rates, or None if none have been fetched
    """
    rows = conn.execute("SELECT currency, date, cad_per_unit FROM fx_rates").fetchall()
    if not rows:
        return None
    return Rates(rows[0][1], {currency: rate for currency, _, rate in rows})


def published_posts(conn: sqlite3.Connection, models: Sequence[str]) -> Iterator[PublishedPost]:
    """Yield every post with its extraction to publish, ordered by kind, month and newest first.

    The extraction is the latest one by the first of `models` that parsed the post, replaced by the
    latest review's corrections when that review corrected it.

    Args:
        conn: Database connection
        models: Models whose extractions are published, in order of preference

    Yields:
        Posts with their extraction; None for posts no listed model has parsed
    """
    marks = ", ".join("?" * len(models))
    preferred = (
        f"SELECT id FROM extractions WHERE post_id = p.id AND model IN ({marks}) "
        f"ORDER BY instr(?, '|' || model || '|'), id DESC LIMIT 1"
    )
    rows = conn.execute(
        "SELECT t.kind, t.month, p.id, p.author, p.posted_at, p.html, p.text, "
        f"COALESCE(({LATEST_REVIEW_DATA}), e.data) "
        "FROM posts p JOIN threads t ON t.id = p.thread_id "
        f"LEFT JOIN extractions e ON e.id = ({preferred}) "
        "ORDER BY t.kind, t.month, p.posted_at DESC",
        (*models, f"|{'|'.join(models)}|"),
    )
    for kind, month, post_id, author, posted_at, markup, text, data in rows:
        yield PublishedPost(
            Kind(kind),
            month,
            post_id,
            author,
            posted_at,
            markup,
            text,
            POSTING_ADAPTERS[Kind(kind)].validate_json(data) if data else None,
        )
