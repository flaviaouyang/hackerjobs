import base64
import json
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import groupby
from pathlib import Path
from typing import Any

from hackerjobs import db
from hackerjobs.identity import PostSummary, identify
from hackerjobs.merge import in_right_thread, merge
from hackerjobs.models import POSTING_ADAPTERS, HiringPosting, Kind, Posting
from hackerjobs.rules import EMAIL, role_category, seniority

# A web address, with or without a scheme: no spaces or @, and a dotted host.
_LINK = re.compile(r"(?:https?://)?[^\s@/]+\.[^\s@/]+(?:/\S*)?", re.IGNORECASE)


def _write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))


def _summary(post: db.PublishedPost, fields: Posting) -> PostSummary:
    hiring = isinstance(fields, HiringPosting)
    contact = fields.contact if fields.contact and "@" in fields.contact else None
    return PostSummary(
        post.id,
        post.month,
        post.posted_at,
        post.author,
        post.text,
        fields.company if hiring else None,
        fields.company_website if hiring else None,
        contact,
        len(fields.roles),
    )


def scramble(email: str) -> str:
    """Hide an email address from address harvesters; the site reverses this on demand.

    Args:
        email: Email address

    Returns:
        The address reversed and Base64-encoded

    Example:
        >>> scramble("jo@example.com")
        'bW9jLmVscG1heGVAb2o='
    """
    return base64.b64encode(email[::-1].encode()).decode()


def _move_email(data: dict[str, Any], key: str, email_key: str) -> None:
    """Split a contact into a web link under `key` and a scrambled email under `email_key`.

    Anything else ("jo @ acme.io", "(my HN username)@acme.io", "ssh apply@host") is neither a
    link nor an address the site can use, so it is dropped; the post still shows it as written.
    """
    value = (data[key] or "").strip().removeprefix("mailto:")
    is_email = EMAIL.fullmatch(value) is not None
    is_link = bool(value) and not is_email and _LINK.fullmatch(value) is not None
    data[key] = value if is_link else None
    data[email_key] = scramble(value) if is_email else None


def _fields_json(kind: Kind, fields: Posting) -> dict[str, Any]:
    """Serialize fields, adding role details read from job titles and scrambling email addresses.

    Many candidates disguise their address ("jo [at] example [dot] com"); the site must not undo
    that in plain text, so every address is published scrambled.
    """
    data = POSTING_ADAPTERS[kind].dump_python(fields, mode="json")
    _move_email(data, "contact", "contact_email")
    if kind is Kind.HIRING:
        for role in data["roles"]:
            role["seniority"] = seniority(role["title"])
            role["category"] = role_category(role["title"]) or "Other"
            _move_email(role, "apply_url", "apply_email")
        titles = [role["title"] for role in data["roles"]]
    else:
        titles = data["roles"]
    data["seniority"] = sorted({level for title in titles if (level := seniority(title))})
    return data


def export_site_data(conn: sqlite3.Connection, models: Sequence[str], out_dir: Path) -> None:
    """Write the site's data files: one per thread kind and month, plus an index.

    Each post's fields are the model's extraction merged with rule-based fields and cleaned up.
    Posts in the wrong thread (a candidate in a hiring thread, or neither a job ad nor a
    candidate) are left out. Each post also carries who it is from (company or candidate key),
    whether it is their first post, the earlier post it repeats if any, and links to their other
    posts.

    Args:
        conn: Database connection
        models: Models whose extractions are published, in order of preference
        out_dir: Directory to write into; created if missing

    Raises:
        ValueError: If no exchange rates have been fetched
    """
    rates = db.load_rates(conn)
    if rates is None:
        raise ValueError("No exchange rates stored; run `hackerjobs fx` first")
    out_dir.mkdir(parents=True, exist_ok=True)

    merged = (
        (post, merge(post.kind, post.text, post.posting))
        for post in db.published_posts(conn, models)
    )
    posts = [
        (post, fields) for post, fields in merged if in_right_thread(post.kind, post.text, fields)
    ]
    identities = {}
    for kind in Kind:
        summaries = [_summary(post, fields) for post, fields in posts if post.kind is kind]
        identities |= identify(summaries, by_author=kind is Kind.SEEKING)

    counts: dict[str, dict[str, int]] = {}
    for (kind, month), group in groupby(posts, key=lambda item: (item[0].kind, item[0].month)):
        payload = [
            {
                "id": post.id,
                "author": post.author,
                "posted_at": post.posted_at,
                "html": post.html,
                "fields": _fields_json(kind, fields),
                **asdict(identities[post.id]),
            }
            for post, fields in group
        ]
        _write_json(out_dir / f"{kind}-{month}.json", payload)
        counts.setdefault(month, {})[kind] = len(payload)

    _write_json(
        out_dir / "index.json",
        {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "months": dict(sorted(counts.items(), reverse=True)),
            "rates": asdict(rates),
        },
    )
