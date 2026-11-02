import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import urlsplit

FREE_MAIL = frozenset({
    "163.com", "aol.com", "fastmail.com", "gmail.com", "gmx.com", "gmx.de", "googlemail.com",
    "hey.com", "hotmail.com", "icloud.com", "live.com", "mail.ru", "me.com", "naver.com",
    "outlook.com", "pm.me", "proton.me", "protonmail.com", "qq.com", "web.de", "yahoo.com",
    "yandex.ru", "zoho.com",
})  # fmt: skip
# Names several unrelated companies use; posts with only such a name are never grouped.
GENERIC_NAMES = frozenset({
    "anonymous", "confidential", "hiring", "mycompany", "stealth", "stealthmode",
    "stealthmodestartup", "stealthstartup", "startup", "undisclosed",
})  # fmt: skip
_LEGAL_SUFFIX = re.compile(
    r"\b(?:inc|llc|ltd|limited|gmbh|corp|corporation|co|plc|sa|sas|sarl|bv|nv|ag|ab|oy|pty|srl|spa)\b\.?$",
    re.I,
)
_PARENTHETICAL = re.compile(r"\([^)]*\)|\[[^\]]*\]")
# A name written as a domain ("AllSpice.io") is the same company as the plain name.
_DOMAIN_SUFFIX = re.compile(r"\.(?:com|io|ai|co|dev|app|xyz|fm|net|org|so|sh|tech|health)$", re.I)
_NON_ALNUM = re.compile(r"[\W_]+")
_WORDS = re.compile(r"\w+")
SHINGLE_SIZE = 3
REPOST_SIMILARITY = 0.8
NEAR_MATCH_SIMILARITY = 0.85


@dataclass(frozen=True, slots=True)
class PostSummary:
    """What identity matching needs to know about a post.

    Attributes:
        id: HN item id
        month: Thread month, formatted YYYY-MM
        posted_at: Unix timestamp
        author: HN username
        text: Plain text of the post
        company: Company name, for hiring posts
        website: Company website, for hiring posts
        email: Contact email, if any
        roles: Number of roles in the post
    """

    id: int
    month: str
    posted_at: int
    author: str
    text: str
    company: str | None
    website: str | None
    email: str | None
    roles: int


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """Another post by the same company or candidate."""

    month: str
    id: int
    roles: int


@dataclass(frozen=True, slots=True)
class Identity:
    """Who a post is from, and how it relates to their other posts.

    Attributes:
        key: Stable company or candidate key, or None if the poster cannot be identified
        new: True if this is their first post in the data
        repost_of: Id of an earlier post with nearly the same text, if any
        history: Their other posts, oldest first
    """

    key: str | None
    new: bool
    repost_of: int | None
    history: tuple[HistoryEntry, ...]


def domain(value: str | None) -> str | None:
    """Registrable host of a URL or email address, without "www.".

    Args:
        value: URL, bare domain or email address

    Returns:
        The lowercased host, or None for free email providers and unparsable values

    Example:
        >>> domain("https://www.goareo.com/jobs")
        'goareo.com'
        >>> domain("jo@gmail.com") is None
        True
    """
    if not value:
        return None
    host = (
        value.rsplit("@", 1)[1]
        if "@" in value
        else urlsplit(value if "//" in value else f"//{value}").hostname
    )
    host = (host or "").casefold().removeprefix("www.").strip(".")
    return host if "." in host and host not in FREE_MAIL else None


def name_key(company: str | None) -> str | None:
    """Comparable form of a company name.

    Args:
        company: Company name as posted

    Returns:
        Lowercased letters and digits without formatting, parentheticals or legal suffixes, or
        None for generic names

    Example:
        >>> name_key("*AREO GmbH (YC W23)")
        'areo'
        >>> name_key("AllSpice.io")
        'allspice'
        >>> name_key("Stealth") is None
        True
    """
    if not company:
        return None
    cleaned = _PARENTHETICAL.sub(" ", company).strip(" *-.,|")
    cleaned = _LEGAL_SUFFIX.sub("", _DOMAIN_SUFFIX.sub("", cleaned))
    key = _NON_ALNUM.sub("", cleaned.casefold())
    return key if key and key not in GENERIC_NAMES else None


def _tokens(post: PostSummary, by_author: bool) -> list[str]:
    if by_author:
        return [f"hn:{post.author}"]
    domains = {found for value in (post.website, post.email) if (found := domain(value))}
    tokens = [f"domain:{found}" for found in sorted(domains)]
    if name := name_key(post.company):
        tokens.append(f"name:{name}")
    return tokens


def _shingles(text: str) -> frozenset[int]:
    words = _WORDS.findall(text.casefold())
    return frozenset(
        hash(tuple(words[i : i + SHINGLE_SIZE])) for i in range(len(words) - SHINGLE_SIZE + 1)
    )


def _similarity(left: frozenset[int], right: frozenset[int]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def identify(posts: Sequence[PostSummary], by_author: bool) -> dict[int, Identity]:
    """Group posts by company (or by candidate) and relate each post to the others in its group.

    Hiring posts are grouped when they share a website or email domain, or the same cleaned
    company name; candidates are grouped by HN username. Groups are connected components, so a
    post with only a name joins posts that have both that name and a domain.

    Args:
        posts: Posts of one thread kind
        by_author: Group by HN username instead of company

    Returns:
        Identity per post id
    """
    parent: dict[str, str] = {}

    def find(token: str) -> str:
        while parent.setdefault(token, token) != token:
            parent[token] = parent[parent[token]]
            token = parent[token]
        return token

    post_tokens = {post.id: _tokens(post, by_author) for post in posts}
    for tokens in post_tokens.values():
        for token in tokens[1:]:
            parent[find(token)] = find(tokens[0])

    groups: dict[str, list[PostSummary]] = defaultdict(list)
    members: dict[str, set[str]] = defaultdict(set)
    for post in posts:
        if tokens := post_tokens[post.id]:
            root = find(tokens[0])
            groups[root].append(post)
            members[root].update(tokens)

    identities = {post.id: Identity(None, True, None, ()) for post in posts}
    for root, group in groups.items():
        # Prefer a domain as the visible key: it is the strongest identity evidence.
        key = min(members[root], key=lambda token: (not token.startswith("domain:"), token))
        group.sort(key=lambda post: post.posted_at)
        shingles = [_shingles(post.text) for post in group]
        for index, post in enumerate(group):
            earlier = [
                group[other].id
                for other in range(index)
                if _similarity(shingles[index], shingles[other]) >= REPOST_SIMILARITY
            ]
            history = tuple(
                HistoryEntry(other.month, other.id, other.roles)
                for other in group
                if other is not post
            )
            identities[post.id] = Identity(
                key, index == 0, earlier[-1] if earlier else None, history
            )
    return identities


def near_matches(companies: Iterable[str]) -> list[tuple[str, str, float]]:
    """Find company names that differ but look alike, for manual review; they are never merged.

    Args:
        companies: Company names as posted

    Returns:
        (name, name, similarity) for each similar pair with different keys, most similar first
    """
    by_key = {key: name for name in companies if (key := name_key(name))}
    blocks: dict[str, list[str]] = defaultdict(list)
    for key in by_key:
        blocks[key[0]].append(key)
    pairs = [
        (by_key[left], by_key[right], ratio)
        for keys in blocks.values()
        for index, left in enumerate(keys)
        for right in keys[index + 1 :]
        if (ratio := SequenceMatcher(None, left, right).ratio()) >= NEAR_MATCH_SIMILARITY
    ]
    return sorted(pairs, key=lambda pair: -pair[2])
