import asyncio
import json

import httpx

from hackerjobs import hn
from hackerjobs.hn import Post, Thread, parse_thread
from hackerjobs.models import Kind


def test_parse_thread_recognizes_hiring_and_seeking() -> None:
    assert parse_thread(1, "Ask HN: Who is hiring? (October 2026)") == Thread(
        1, Kind.HIRING, "2026-10"
    )
    assert parse_thread(2, "Ask HN: Who wants to be hired? (January 2026)") == Thread(
        2, Kind.SEEKING, "2026-01"
    )


def test_parse_thread_ignores_other_stories() -> None:
    assert parse_thread(3, "Ask HN: Freelancer? Seeking freelancer? (October 2025)") is None


def test_post_text_uses_full_link_urls_and_paragraphs() -> None:
    post = Post(
        1,
        1,
        "a",
        0,
        '<p>Acme &amp; Co<p>Apply: <a href="https://acme.example/jobs/123">https://acme.example/...</a>',
    )
    assert post.text == "Acme & Co\n\nApply: https://acme.example/jobs/123"


def test_fetch_reads_the_official_api_and_separates_removed_posts(mock_http) -> None:
    january = 1767225600  # 2026-01-01T00:00:00Z
    items = {
        10: {
            "id": 10,
            "type": "story",
            "time": january + 10,
            "title": "Ask HN: Who is hiring? (January 2026)",
            "kids": [20, 21, 22, 23],
        },
        11: {
            "id": 11,
            "type": "story",
            "time": january + 10,
            "title": "Ask HN: Freelancer? Seeking freelancer? (January 2026)",
        },
        12: {
            "id": 12,
            "type": "story",
            "time": january - 10,
            "title": "Ask HN: Who is hiring? (December 2025)",
        },
        20: {
            "id": 20,
            "type": "comment",
            "by": "acme",
            "time": 5,
            "text": "Acme<script>x</script>",
        },
        21: {"id": 21, "type": "comment", "deleted": True, "time": 6},
        22: {"id": 22, "type": "comment", "by": "spam", "time": 7, "text": "spam", "dead": True},
        23: None,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user/whoishiring.json"):
            return httpx.Response(200, json={"submitted": [10, 11, 12]})
        item_id = int(request.url.path.rsplit("/", 1)[1].removesuffix(".json"))
        return httpx.Response(200, content=json.dumps(items[item_id]).encode())

    mock_http(handler)
    [fetched] = asyncio.run(hn.fetch("2026-01"))
    assert fetched.thread == Thread(10, Kind.HIRING, "2026-01")
    assert fetched.posts == [Post(20, 10, "acme", 5, "Acme")]
    assert fetched.removed == {21, 22}
