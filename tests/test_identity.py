from hackerjobs.identity import HistoryEntry, PostSummary, domain, identify, name_key, near_matches


def summary(
    post_id: int, month: str, company: str | None, website: str | None = None, text: str = ""
) -> PostSummary:
    return PostSummary(
        post_id,
        month,
        post_id,
        f"user{post_id}",
        text or f"post {post_id}",
        company,
        website,
        None,
        1,
    )


def test_domain_and_name_keys() -> None:
    assert domain("https://www.goareo.com/jobs") == "goareo.com"
    assert domain("jobs@acme.io") == "acme.io"
    assert domain("jo@gmail.com") is None
    assert name_key("*AREO GmbH (YC W23)") == "areo"
    assert name_key("AllSpice.io") == name_key("AllSpice") == "allspice"
    assert name_key("Stealth Startup") is None


def test_posts_join_through_shared_name_or_domain() -> None:
    posts = [
        summary(1, "2026-05", "ABC", "abc.com"),
        summary(2, "2026-06", "ABC Inc."),
        summary(3, "2026-07", "ABC Labs", "https://www.abc.com/careers"),
        summary(4, "2026-06", "Stealth"),
        summary(5, "2026-06", "Abcd"),
    ]
    identities = identify(posts, by_author=False)
    assert {identities[post_id].key for post_id in (1, 2, 3)} == {"domain:abc.com"}
    assert identities[1].new and not identities[2].new
    assert identities[3].history == (HistoryEntry("2026-05", 1, 1), HistoryEntry("2026-06", 2, 1))
    assert identities[4].key is None
    assert identities[5].key == "name:abcd"


def test_reposts_are_nearly_identical_texts() -> None:
    text = (
        "Acme is hiring backend engineers to build payment systems in Berlin with Go and Postgres."
    )
    posts = [
        summary(1, "2026-05", "Acme", text=text),
        summary(2, "2026-06", "Acme", text=text + " Updated."),
        summary(
            3,
            "2026-07",
            "Acme",
            text="Acme is hiring designers for a brand new mobile app in Lisbon.",
        ),
    ]
    identities = identify(posts, by_author=False)
    assert identities[2].repost_of == 1
    assert identities[3].repost_of is None


def test_candidates_are_grouped_by_username() -> None:
    posts = [summary(1, "2026-05", None), summary(2, "2026-06", None)]
    posts[1] = PostSummary(2, "2026-06", 2, "user1", "other", None, None, None, 0)
    identities = identify(posts, by_author=True)
    assert identities[1].key == identities[2].key == "hn:user1"


def test_near_matches_are_reported_not_merged() -> None:
    pairs = near_matches(["Modal", "Modall", "Acme", "Globex"])
    assert [(left, right) for left, right, _ in pairs] == [("Modal", "Modall")]
