import dataclasses
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing
from functools import partial
from pathlib import Path

import httpx
import pytest

from hackerjobs import db
from hackerjobs.config import AnthropicConfig, Config, LMStudioConfig, ParseConfig, PublishConfig
from hackerjobs.hn import Post, Thread
from hackerjobs.models import EMPTY_POSTINGS, HiringPosting, Kind, Pay, Role

THREAD = Thread(100, Kind.HIRING, "2026-10")
CONFIG = Config(
    since="2026-01",
    parse=ParseConfig(("lmstudio:m",)),
    publish=PublishConfig("lmstudio:m"),
    lmstudio=LMStudioConfig("http://lm/v1", 2),
    anthropic=AnthropicConfig(4),
)


def make_posting(company: str = "Acme") -> HiringPosting:
    """Build a hiring posting with a company, one role, pay and a technology."""
    return dataclasses.replace(
        EMPTY_POSTINGS[Kind.HIRING],
        company=company,
        roles=(Role("Engineer", None, (), None),),
        locations=("Berlin, Germany",),
        remote="remote",
        employment_types=("full-time",),
        pay=Pay(100000, 150000, "EUR", "year"),
        technologies=("Python",),
        contact="jobs@acme.example",
    )


def make_post(post_id: int, html: str = "<p>Acme | Engineer | Berlin") -> Post:
    """Build a post in THREAD."""
    return Post(post_id, THREAD.id, f"user{post_id}", 1_790_000_000 + post_id, html)


def pending(post_id: int) -> db.PendingPost:
    """A hiring post waiting to be parsed."""
    return db.PendingPost(post_id, Kind.HIRING, "")


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    """In-memory database with one thread of two posts."""
    with closing(db.connect(Path(":memory:"))) as connection:
        db.save_thread(connection, THREAD, [make_post(1), make_post(2)])
        yield connection


@pytest.fixture
def mock_http(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Callable[[httpx.Request], httpx.Response]], None]:
    """Route every httpx.AsyncClient created by the app through a request handler."""

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> None:
        monkeypatch.setattr(
            httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(handler))
        )

    return install
