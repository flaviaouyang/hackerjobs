import asyncio
import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import nh3

from hackerjobs.models import Kind

HN_URL = "https://hacker-news.firebaseio.com/v0"
# Submissions are fetched newest first in batches until one predates the start month.
SUBMISSIONS_BATCH = 30
CONCURRENCY = 50
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


@dataclass(frozen=True, slots=True)
class ThreadPosts:
    """A thread's live posts, and the ids HN reports as dead (flagged) or deleted.

    Attributes:
        thread: The thread
        posts: Top-level comments that are visible on HN
        removed: Ids of top-level comments HN has hidden or deleted
    """

    thread: Thread
    posts: list[Post]
    removed: frozenset[int]


async def _item(
    client: httpx.AsyncClient, limit: asyncio.Semaphore, item_id: int
) -> dict[str, Any] | None:
    async with limit:
        response = await client.get(f"{HN_URL}/item/{item_id}.json")
    response.raise_for_status()
    return response.json()


async def fetch_threads(
    client: httpx.AsyncClient, limit: asyncio.Semaphore, since: str
) -> list[Thread]:
    """Find the whoishiring account's hiring and seeking threads posted since the start of a month.

    Args:
        client: HTTP client
        limit: Bounds concurrent requests
        since: First month to include, formatted YYYY-MM

    Returns:
        Matching threads

    Raises:
        httpx.HTTPStatusError: If the HN API returns an error
    """
    start = int(datetime.strptime(since, "%Y-%m").replace(tzinfo=UTC).timestamp())
    response = await client.get(f"{HN_URL}/user/whoishiring.json")
    response.raise_for_status()
    submitted = response.json()["submitted"]
    threads: list[Thread] = []
    for offset in range(0, len(submitted), SUBMISSIONS_BATCH):
        batch = submitted[offset : offset + SUBMISSIONS_BATCH]
        stories = [
            item
            for item in await asyncio.gather(*(_item(client, limit, item_id) for item_id in batch))
            if item and item.get("type") == "story"
        ]
        threads += [
            thread
            for story in stories
            if story["time"] >= start
            and (thread := parse_thread(story["id"], story.get("title", "")))
        ]
        if any(story["time"] < start for story in stories):
            break
    return threads


async def fetch_posts(
    client: httpx.AsyncClient, limit: asyncio.Semaphore, thread: Thread
) -> ThreadPosts:
    """Fetch a thread's top-level comments, separating live posts from dead or deleted ones.

    Args:
        client: HTTP client
        limit: Bounds concurrent requests
        thread: Thread to fetch

    Returns:
        Live posts with sanitized HTML, and the ids HN has hidden or deleted

    Raises:
        httpx.HTTPStatusError: If the HN API returns an error
    """
    story = await _item(client, limit, thread.id)
    kids = story.get("kids", []) if story else []
    posts: list[Post] = []
    removed: set[int] = set()
    for item in await asyncio.gather(*(_item(client, limit, kid) for kid in kids)):
        if item is None:
            continue
        if item.get("dead") or item.get("deleted"):
            removed.add(item["id"])
        elif item.get("text") and item.get("by"):
            html = nh3.clean(item["text"], tags=ALLOWED_TAGS)
            posts.append(Post(item["id"], thread.id, item["by"], item["time"], html))
    return ThreadPosts(thread, posts, frozenset(removed))


async def fetch(since: str) -> list[ThreadPosts]:
    """Fetch the threads posted since a month and their posts from the official HN API.

    Args:
        since: First month to include, formatted YYYY-MM

    Returns:
        Each thread with its live posts and removed post ids
    """
    limit = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(
        timeout=60, limits=httpx.Limits(max_connections=CONCURRENCY)
    ) as client:
        threads = await fetch_threads(client, limit, since)
        return list(
            await asyncio.gather(*(fetch_posts(client, limit, thread) for thread in threads))
        )
