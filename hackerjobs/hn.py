import asyncio
import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import nh3

from hackerjobs.models import Kind

ALGOLIA_URL = "https://hn.algolia.com/api/v1"
MAX_HITS = 1000
THREAD_TITLE = re.compile(r"Ask HN: Who (is hiring|wants to be hired)\? \((\w+ \d{4})\)")
KIND_BY_PHRASE = {"is hiring": Kind.HIRING, "wants to be hired": Kind.SEEKING}
ALLOWED_TAGS = {"p", "a", "i", "pre", "code"}
# HN truncates long link text with "...", so plain text uses the full href instead.
ANCHOR = re.compile(r'<a [^>]*href="([^"]*)"[^>]*>.*?</a>', re.DOTALL)


@dataclass(frozen=True, slots=True)
class Thread:
    """A monthly "Ask HN" thread.

    Attributes:
        id: HN item id of the thread
        kind: Whether the thread lists jobs or candidates
        month: Month the thread covers, formatted YYYY-MM
    """

    id: int
    kind: Kind
    month: str


@dataclass(frozen=True, slots=True)
class Post:
    """A top-level comment in a thread.

    Attributes:
        id: HN item id of the comment
        thread_id: HN item id of the parent thread
        author: HN username of the poster
        posted_at: Unix timestamp of the comment
        html: Sanitized comment HTML
    """

    id: int
    thread_id: int
    author: str
    posted_at: int
    html: str

    @property
    def text(self) -> str:
        """Plain-text rendering of the post, with links replaced by their URLs."""
        flattened = ANCHOR.sub(r"\1", self.html).replace("<p>", "\n\n")
        return html.unescape(nh3.clean(flattened, tags=set())).strip()


def parse_thread(item_id: int, title: str) -> Thread | None:
    """Build a Thread from a whoishiring story title.

    Args:
        item_id: HN item id of the story
        title: Story title, e.g. "Ask HN: Who is hiring? (October 2026)"

    Returns:
        The thread, or None if the title is not a hiring or seeking thread
    """
    match = THREAD_TITLE.fullmatch(title)
    if match is None:
        return None
    phrase, month = match.groups()
    return Thread(
        item_id, KIND_BY_PHRASE[phrase], datetime.strptime(month, "%B %Y").strftime("%Y-%m")
    )


async def fetch_threads(client: httpx.AsyncClient, since: str) -> list[Thread]:
    """Find the hiring and seeking threads posted since the start of a month.

    Args:
        client: HTTP client
        since: First month to include, formatted YYYY-MM

    Returns:
        Matching threads

    Raises:
        httpx.HTTPStatusError: If the Algolia API returns an error
    """
    start = int(datetime.strptime(since, "%Y-%m").replace(tzinfo=UTC).timestamp())
    response = await client.get(
        f"{ALGOLIA_URL}/search_by_date",
        params={
            "tags": "story,author_whoishiring",
            "numericFilters": f"created_at_i>={start}",
            "hitsPerPage": MAX_HITS,
        },
    )
    response.raise_for_status()
    return [
        thread
        for hit in response.json()["hits"]
        if (thread := parse_thread(int(hit["objectID"]), hit["title"])) is not None
    ]


async def fetch_posts(client: httpx.AsyncClient, thread: Thread) -> list[Post]:
    """Fetch the live top-level comments of a thread.

    Args:
        client: HTTP client
        thread: Thread to fetch

    Returns:
        Posts with sanitized HTML, excluding deleted comments

    Raises:
        httpx.HTTPStatusError: If the Algolia API returns an error
    """
    response = await client.get(f"{ALGOLIA_URL}/items/{thread.id}")
    response.raise_for_status()
    return [
        Post(
            child["id"],
            thread.id,
            child["author"],
            child["created_at_i"],
            nh3.clean(child["text"], tags=ALLOWED_TAGS),
        )
        for child in response.json()["children"]
        if child.get("text") and child.get("author")
    ]


async def fetch(since: str) -> list[tuple[Thread, list[Post]]]:
    """Fetch the threads posted since a month and their posts concurrently.

    Args:
        since: First month to include, formatted YYYY-MM

    Returns:
        Each thread paired with its posts
    """
    async with httpx.AsyncClient(timeout=60) as client:
        threads = await fetch_threads(client, since)
        posts = await asyncio.gather(*(fetch_posts(client, thread) for thread in threads))
    return list(zip(threads, posts, strict=True))
