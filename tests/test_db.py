import dataclasses
import sqlite3

from conftest import THREAD, make_post, make_posting, pending

from hackerjobs import db
from hackerjobs.fx import Rates
from hackerjobs.models import Kind, Review


def published(conn: sqlite3.Connection) -> dict[int, str | None]:
    return {
        post.id: post.posting and post.posting.company for post in db.published_posts(conn, ["m"])
    }


def test_posts_to_parse_is_per_model_and_prompt_version(conn: sqlite3.Connection) -> None:
    db.save_extraction(conn, pending(1), "m", "v1", make_posting())
    assert [post.id for post in db.posts_to_parse(conn, "m", Kind.HIRING, "v1")] == [2]
    assert [post.id for post in db.posts_to_parse(conn, "m", Kind.HIRING, "v2")] == [1, 2]
    assert [post.id for post in db.posts_to_parse(conn, "other", Kind.HIRING, "v1")] == [1, 2]
    assert db.posts_to_parse(conn, "m", Kind.SEEKING, "v1") == []


def test_editing_a_post_drops_its_extractions_and_reviews(conn: sqlite3.Connection) -> None:
    db.save_extraction(conn, pending(1), "m", "v1", make_posting())
    [item] = db.extractions_to_review(conn, "r", "m", "v1")
    db.save_review(conn, item, "r", "v1", Review("correct", (), make_posting()))
    db.save_thread(conn, THREAD, [make_post(1)])
    assert conn.execute("SELECT COUNT(*) FROM extractions").fetchone() == (1,)

    db.save_thread(conn, THREAD, [make_post(1, "<p>Acme | edited")])
    assert conn.execute("SELECT COUNT(*) FROM extractions").fetchone() == (0,)
    assert conn.execute("SELECT COUNT(*) FROM reviews").fetchone() == (0,)
    assert conn.execute("SELECT text FROM posts WHERE id = 1").fetchone() == ("Acme | edited",)


def test_published_uses_latest_extraction_and_review_corrections(conn: sqlite3.Connection) -> None:
    db.save_extraction(conn, pending(1), "m", "v1", make_posting("Old"))
    db.save_extraction(conn, pending(1), "m", "v2", make_posting("New"))
    db.save_extraction(conn, pending(2), "other", "v1", make_posting("Other"))
    assert published(conn) == {1: "New", 2: None}

    [item] = db.extractions_to_review(conn, "r", "m", "rv1")
    assert item.posting == make_posting("New")
    corrected = Review("corrected", ("company",), make_posting("Fixed"))
    db.save_review(conn, item, "r", "rv1", corrected)
    assert published(conn) == {1: "Fixed", 2: None}
    assert db.extractions_to_review(conn, "r", "m", "rv1") == []

    db.save_review(conn, item, "r", "rv2", dataclasses.replace(corrected, verdict="correct"))
    assert published(conn) == {1: "New", 2: None}


def test_published_prefers_earlier_models(conn: sqlite3.Connection) -> None:
    db.save_extraction(conn, pending(1), "local", "v1", make_posting("Local"))
    db.save_extraction(conn, pending(1), "better", "v1", make_posting("Better"))
    db.save_extraction(conn, pending(2), "local", "v1", make_posting("Only local"))
    posts = db.published_posts(conn, ["better", "local"])
    assert {post.id: post.posting and post.posting.company for post in posts} == {
        1: "Better",
        2: "Only local",
    }


def test_posts_covered_by_a_preferred_model_are_not_parsed(conn: sqlite3.Connection) -> None:
    db.save_extraction(conn, pending(1), "better", "old", make_posting())
    ids = [post.id for post in db.posts_to_parse(conn, "local", Kind.HIRING, "v1", ["better"])]
    assert ids == [2]
    every = [post.id for post in db.posts_to_parse(conn, "local", Kind.HIRING, "v1")]
    assert sorted(every) == [1, 2]


def test_rates_round_trip(conn: sqlite3.Connection) -> None:
    assert db.load_rates(conn) is None
    db.save_rates(conn, Rates("2026-10-30", {"USD": 1.396, "CAD": 1.0}))
    db.save_rates(conn, Rates("2026-10-31", {"EUR": 1.5, "CAD": 1.0}))
    assert db.load_rates(conn) == Rates("2026-10-31", {"EUR": 1.5, "CAD": 1.0})


def test_posts_removed_on_hn_are_deleted_with_their_extractions(conn: sqlite3.Connection) -> None:
    db.save_extraction(conn, pending(1), "m", "v1", make_posting())
    db.save_thread(conn, THREAD, [make_post(2)], removed=[1])
    assert conn.execute("SELECT id FROM posts").fetchall() == [(2,)]
    assert conn.execute("SELECT COUNT(*) FROM extractions").fetchone() == (0,)
