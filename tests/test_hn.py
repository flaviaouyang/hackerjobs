import asyncio

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


def test_fetch_skips_deleted_comments_and_sanitizes(mock_http) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("search_by_date"):
            assert request.url.params["numericFilters"] == "created_at_i>=1767225600"
            return httpx.Response(
                200,
                json={
                    "hits": [
                        {"objectID": "10", "title": "Ask HN: Who is hiring? (January 2026)"},
                        {
                            "objectID": "11",
                            "title": "Ask HN: Freelancer? Seeking freelancer? (January 2026)",
                        },
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "children": [
                    {
                        "id": 20,
                        "author": "acme",
                        "created_at_i": 5,
                        "text": "Acme<script>x</script>",
                    },
                    {"id": 21, "author": None, "created_at_i": 6, "text": None},
                ]
            },
        )

    mock_http(handler)
    [(thread, posts)] = asyncio.run(hn.fetch("2026-01"))
    assert thread == Thread(10, Kind.HIRING, "2026-01")
    assert posts == [Post(20, 10, "acme", 5, "Acme")]
