import json
import sqlite3
from pathlib import Path

import pytest
from conftest import THREAD, make_post, make_posting, pending

from hackerjobs import db
from hackerjobs.export import _move_email, export_site_data, scramble
from hackerjobs.fx import Rates


def test_export_writes_month_files_and_index(conn: sqlite3.Connection, tmp_path: Path) -> None:
    db.save_rates(conn, Rates("2026-10-30", {"USD": 1.396, "CAD": 1.0}))
    db.save_extraction(conn, pending(1), "m", "v1", make_posting())
    export_site_data(conn, ["m"], tmp_path)

    posts = json.loads((tmp_path / "hiring-2026-10.json").read_text())
    assert [post["id"] for post in posts] == [2, 1]
    # Unparsed posts still get rule-based fields from the "Acme | Engineer | Berlin" header.
    assert posts[0]["fields"]["company"] == "Acme"
    assert posts[0]["fields"]["roles"] == []
    assert posts[1]["fields"]["technologies"] == ["Python"]
    assert posts[1]["fields"]["roles"] == [
        {
            "title": "Engineer",
            "category": "Engineering",
            "pay": None,
            "locations": [],
            "apply_url": None,
            "seniority": None,
            "apply_email": None,
        }
    ]
    # The extracted pay does not appear in the post, so it is dropped.
    assert posts[1]["fields"]["pay"] is None

    index = json.loads((tmp_path / "index.json").read_text())
    assert index["months"] == {"2026-10": {"hiring": 2}}
    assert index["rates"] == {"date": "2026-10-30", "cad_per_unit": {"USD": 1.396, "CAD": 1.0}}


def test_export_relates_posts_by_the_same_company(conn: sqlite3.Connection, tmp_path: Path) -> None:
    db.save_rates(conn, Rates("2026-10-30", {"CAD": 1.0}))
    export_site_data(conn, ["m"], tmp_path)
    first, second = sorted(
        json.loads((tmp_path / "hiring-2026-10.json").read_text()), key=lambda p: p["id"]
    )
    assert first["key"] == second["key"] == "name:acme"
    assert (first["new"], second["new"]) == (True, False)
    assert second["repost_of"] == 1
    assert second["history"] == [{"month": "2026-10", "id": 1, "roles": 0}]


def test_export_publishes_email_addresses_only_scrambled(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    db.save_rates(conn, Rates("2026-10-30", {"CAD": 1.0}))
    db.save_thread(
        conn, THREAD, [make_post(1, "<p>Acme | Engineer | Berlin | jobs [at] acme [dot] io")]
    )
    export_site_data(conn, ["m"], tmp_path)
    text = (tmp_path / "hiring-2026-10.json").read_text()
    assert "jobs@acme.io" not in text
    [post] = [post for post in json.loads(text) if post["id"] == 1]
    assert post["fields"]["contact"] is None
    assert post["fields"]["contact_email"] == scramble("jobs@acme.io")


@pytest.mark.parametrize(
    ("contact", "link", "email"),
    [
        ("mailto:jobs@acme.io", None, "jobs@acme.io"),
        ("acme.io/careers", "acme.io/careers", None),
        ("jo @ acme.io", None, None),
        ("(my HN username)@acme.io", None, None),
    ],
)
def test_contacts_become_a_link_an_email_or_nothing(
    contact: str, link: str | None, email: str | None
) -> None:
    data = {"contact": contact}
    _move_email(data, "contact", "contact_email")
    assert data == {"contact": link, "contact_email": email and scramble(email)}


def test_export_requires_rates(conn: sqlite3.Connection, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="hackerjobs fx"):
        export_site_data(conn, ["m"], tmp_path)


def test_export_skips_unknown_threads(conn: sqlite3.Connection, tmp_path: Path) -> None:
    db.save_rates(conn, Rates("2026-10-30", {"CAD": 1.0}))
    db.save_thread(conn, THREAD, [make_post(3, "<p>Stealth | Engineer")])
    export_site_data(conn, ["m"], tmp_path)
    posts = {
        post["id"]: post for post in json.loads((tmp_path / "hiring-2026-10.json").read_text())
    }
    assert posts[3]["key"] is None


def test_export_leaves_out_posts_in_the_wrong_thread(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    db.save_rates(conn, Rates("2026-10-30", {"CAD": 1.0}))
    template = "<p>Location: Oslo<p>Remote: Yes<p>Willing to relocate: Yes<p>Technologies: Rust"
    db.save_thread(conn, THREAD, [make_post(3, template)])
    export_site_data(conn, ["m"], tmp_path)
    ids = {post["id"] for post in json.loads((tmp_path / "hiring-2026-10.json").read_text())}
    assert ids == {1, 2}
