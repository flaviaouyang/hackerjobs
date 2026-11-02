import dataclasses
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from hackerjobs.identity import name_key
from hackerjobs.models import CompanyStage, Money, Pay, Posting, Role
from hackerjobs.rules import STAGE_EVIDENCE, deobfuscate, role_category
from hackerjobs.technologies import canonical_technologies

_CURRENCY_SYMBOLS = {
    "$": "USD",
    "US$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "¥": "JPY",
    "C$": "CAD",
    "A$": "AUD",
}
_ISO_CURRENCY = re.compile(r"[A-Z]{3}")
_WORK_MODE = re.compile(r"\b(?:fully\s+)?(?:remote|hybrid|on[\s-]?site|in[\s-]office)\b", re.I)
_NOT_A_PLACE = frozenset(
    {"", "anywhere", "global", "worldwide", "earth", "planet earth", "any", "flexible"}
)
_LOCATION_ALIASES = {
    "nyc": "New York City",
    "new york": "New York City",
    "new york, ny": "New York City",
    "new york city, ny": "New York City",
    "ny": "New York City",
    "sf": "San Francisco, CA",
    "san francisco": "San Francisco, CA",
    "bay area": "San Francisco Bay Area",
    "sf bay area": "San Francisco Bay Area",
}
_US_STATES = {
    name.casefold(): code
    for code, name in (
        ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"),
        ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"),
        ("DC", "District of Columbia"), ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"),
        ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"), ("KS", "Kansas"),
        ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"), ("MD", "Maryland"),
        ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"), ("MS", "Mississippi"),
        ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"), ("NV", "Nevada"),
        ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"), ("NY", "New York"),
        ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"), ("OK", "Oklahoma"),
        ("OR", "Oregon"), ("PA", "Pennsylvania"), ("RI", "Rhode Island"),
        ("SC", "South Carolina"), ("SD", "South Dakota"), ("TN", "Tennessee"), ("TX", "Texas"),
        ("UT", "Utah"), ("VT", "Vermont"), ("VA", "Virginia"), ("WA", "Washington"),
        ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming"),
    )
}  # fmt: skip
_US_STATE_CODES = frozenset(_US_STATES.values())
_US = frozenset({"us", "usa", "u.s.", "u.s.a.", "united states", "united states of america"})
_LETTERS = re.compile(r"[^\W\d_]{2,}")
_WORDS = re.compile(r"[^\W_]+")
_NON_ALNUM = re.compile(r"[\W_]+")
_URL_PREFIX = re.compile(r"^(?:https?://)?(?:www\.)?")
_LINK = re.compile(r"^(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}(?:[/?#]\S*)?$", re.I)
MAX_ROLE_LENGTH = 80
# Longer "titles" are sentences describing what someone wants, not job titles.
MAX_ROLE_WORDS = 8
# Copied text may differ from the post in punctuation or a stray word, but not in substance.
MIN_WORD_COVERAGE = 0.9
SHORT_TEXT_WORDS = 3
MAX_YEARS = 60
FIRST_FOUNDED_YEAR = 1800


@dataclass(frozen=True, slots=True)
class _Post:
    """Views of a post's text used to check that extracted values appear in it."""

    text: str
    lowered: str
    compact: str
    numbers: str
    words: frozenset[str]


def _post(text: str) -> _Post:
    lowered = text.casefold()
    return _Post(
        text,
        lowered,
        _compact(text),
        lowered.replace(",", "").replace(" ", ""),
        frozenset(_WORDS.findall(lowered)),
    )


def _compact(value: str) -> str:
    return _NON_ALNUM.sub("", value.casefold())


def _unique[T](items: Iterable[T], key: Callable[[T], str] = str.casefold) -> tuple[T, ...]:
    """Drop duplicates by key, keeping the first occurrence and the original order."""
    first: dict[str, T] = {}
    for item in items:
        first.setdefault(key(item), item)
    return tuple(first.values())


def _text(value: str | None, post: _Post) -> str | None:
    """Keep free text only if it is copied from the post."""
    if value is None or not (value := value.strip()):
        return None
    if _compact(value) in post.compact:
        return value
    words = _WORDS.findall(value.casefold())
    coverage = sum(word in post.words for word in words) / len(words) if words else 0.0
    required = 1.0 if len(words) <= SHORT_TEXT_WORDS else MIN_WORD_COVERAGE
    return value if coverage >= required else None


def _company(value: str | None, post: _Post) -> str | None:
    """A copied company name; generic stand-ins such as "Confidential" or "Stealth" are no name."""
    name = _text(value, post)
    return name if name and name_key(name) else None


def _texts(values: tuple[str, ...], post: _Post) -> tuple[str, ...]:
    return _unique(text for value in values if (text := _text(value, post)))


def _tidy(value: str) -> str:
    """One style for list items: single spaces, no list markers or trailing punctuation, and a
    capital first letter (the rest is kept, so "401K" and "PTO" survive)."""
    value = re.sub(r"\s+", " ", value).strip(" -*\u2022").rstrip(".,;:")
    return value[:1].upper() + value[1:]


def _tidy_texts(values: tuple[str, ...], post: _Post) -> tuple[str, ...]:
    return _unique(_tidy(text) for text in _texts(values, post) if _tidy(text))


def _phrases(values: tuple[str, ...], post: _Post) -> tuple[str, ...]:
    """Short phrases that may be normalized wording ("game development"), so only tidied."""
    return _unique(phrase for value in values if (phrase := _tidy(value)))


def _url(value: str | None, post: _Post) -> str | None:
    """Keep a URL or email address only if it appears in the post."""
    if value is None or not (value := value.strip()):
        return None
    needle = _URL_PREFIX.sub("", value).rstrip("/").casefold()
    if needle in post.lowered or ("@" in needle and needle in deobfuscate(post.text).casefold()):
        return value
    return None


def _link(value: str | None, post: _Post, host: str = "") -> str | None:
    """Keep a link only if it looks like a URL (on `host`, when given) and appears in the post."""
    if (
        value is None
        or not _LINK.match(value.strip())
        or host not in value.casefold()
        or "<" in value
    ):
        return None
    return _url(value, post)


def _us_city(location: str) -> str:
    """Write "City, State[, USA]" as "City, ST"."""
    parts = [part.strip() for part in location.split(",")]
    if len(parts) > 2 and parts[-1].casefold() in _US:
        parts.pop()
    if len(parts) == 2:
        parts[1] = _US_STATES.get(parts[1].casefold(), parts[1])
    return ", ".join(parts) if len(parts) == 2 and parts[1] in _US_STATE_CODES else location


def _location(item: str) -> str | None:
    cleaned = _WORK_MODE.sub("", item).replace("(", " ").replace(")", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,/-\u2013:")
    if cleaned.casefold() in _NOT_A_PLACE:
        return None
    return _LOCATION_ALIASES.get(cleaned.casefold(), _us_city(cleaned))


def _locations(values: tuple[str, ...], post: _Post) -> tuple[str, ...]:
    return _unique(location for item in values if (location := _location(item)))


def _currency(value: str | None) -> str | None:
    if value is None:
        return None
    code = _CURRENCY_SYMBOLS.get(value.strip(), value.strip().upper())
    return code if _ISO_CURRENCY.fullmatch(code) else None


def _number_grounded(value: float, post: _Post, currency: str | None) -> bool:
    divisors = (1, 1000, 100000) if currency == "INR" else (1, 1000)
    forms = {f"{value / divisor:g}" for divisor in divisors}
    return any(re.search(rf"(?<![\d.]){re.escape(form)}(?![\d])", post.numbers) for form in forms)


def _pay(pay: Pay | None, post: _Post) -> Pay | None:
    """Fill single figures, order the range, and keep it only if a figure appears in the post."""
    if pay is None or (pay.min is None and pay.max is None):
        return None
    if pay.min is None or pay.max is None:
        low = high = pay.min if pay.max is None else pay.max
    else:
        low, high = sorted((pay.min, pay.max))
    currency = _currency(pay.currency)
    if not any(_number_grounded(value, post, currency) for value in (low, high)):
        return None
    return Pay(low, high, currency, pay.period)


def _money(money: Money | None, post: _Post) -> Money | None:
    """Keep an amount only if it appears in the post, possibly written in thousands, millions or
    billions ("$5M", "$1.2B")."""
    if money is None:
        return None
    currency = _currency(money.currency)
    forms = {f"{money.amount / divisor:g}" for divisor in (1, 1e3, 1e6, 1e9)}
    if not any(re.search(rf"(?<![\d.]){re.escape(form)}(?![\d])", post.numbers) for form in forms):
        return None
    return Money(money.amount, currency)


def _stage(stage: CompanyStage | None, post: _Post) -> CompanyStage | None:
    """Keep a company stage only if the post contains words for it."""
    return stage if stage is not None and STAGE_EVIDENCE[stage].search(post.text) else None


def _technologies(values: tuple[str, ...], post: _Post) -> tuple[str, ...]:
    return _unique(name for item in values for name in canonical_technologies(item))


def _title(value: str) -> str | None:
    title = value.strip()
    if (
        not _LETTERS.search(title)
        or len(title) > MAX_ROLE_LENGTH
        or len(title.split()) > MAX_ROLE_WORDS
    ):
        return None
    return title


def _role_title(role: Role | str) -> str:
    return (role if isinstance(role, str) else role.title).casefold()


def _roles(values: tuple[Role | str, ...], post: _Post) -> tuple[Role | str, ...]:
    """Clean job titles; hiring roles also get their own pay, locations and link checked."""
    roles: list[Role | str] = []
    for role in values:
        if isinstance(role, str):
            if title := _title(role):
                roles.append(title)
        elif title := _title(role.title):
            locations = _locations(role.locations, post)
            roles.append(Role(title, _pay(role.pay, post), locations, _url(role.apply_url, post)))
    return _unique(roles, key=_role_title)


def _years(value: int | None, post: _Post) -> int | None:
    return value if value is not None and 0 <= value <= MAX_YEARS else None


def _founded(value: int | None, post: _Post) -> int | None:
    current = datetime.now(UTC).year
    return value if value is not None and FIRST_FOUNDED_YEAR <= value <= current else None


def _deduplicated(values: tuple[str, ...], post: _Post) -> tuple[str, ...]:
    return _unique(values)


def _true_only(value: bool | None, post: _Post) -> bool | None:
    """A post never states that applications are open, so only "closed" is kept."""
    return True if value else None


def _role_categories(posting: Posting) -> tuple[str, ...]:
    """Categories read from role titles.

    The model's reading covers titles the rules can't read; without one they count as Other.
    """
    titles = [role if isinstance(role, str) else role.title for role in posting.roles]
    from_titles = [role_category(title) for title in titles]
    known = [category for category in from_titles if category]
    if None not in from_titles and titles:
        return _unique(known)
    unread = posting.role_categories or (("Other",) if titles else ())
    return _unique([*known, *unread])


def _same(value: Any, post: _Post) -> Any:
    return value


_CLEANERS: dict[str, Callable[[Any, _Post], Any]] = {
    **dict.fromkeys(
        (
            "company_description", "team_size",
            "work_authorization", "security_clearance", "timezone", "hours", "education",
            "equity_details", "interview_process", "application_instructions", "availability",
        ),
        _text,
    ),
    "investors": _texts,
    **dict.fromkeys(("languages", "benefits"), _tidy_texts),
    "interests": _phrases,
    "industries": _deduplicated,
    "role_categories": _deduplicated,
    "company_stage": _stage,
    **dict.fromkeys(("funding", "valuation"), _money),
    **dict.fromkeys(("company_website", "website", "resume_url"), _link),
    "linkedin": lambda value, post: _link(value, post, "linkedin.com"),
    "github": lambda value, post: _link(value, post, "github.com"),
    "contact": _url,
    "company": _company,
    "employment_types": _deduplicated,
    "locations": _locations,
    "pay": _pay,
    "technologies": _technologies,
    "roles": _roles,
    "min_experience_years": _years,
    "experience_years": _years,
    "founded_year": _founded,
    "applications_closed": _true_only,
}  # fmt: skip


def normalize[P: Posting](text: str, posting: P) -> P:
    """Clean up extracted fields and drop values the post does not support.

    - Free text, names, links and pay must appear in the post; anything else is dropped, so a
      model can only copy, never write.
    - Technologies are mapped to canonical names; generic concepts are dropped.
    - Work-mode words are removed from locations; US states and common city aliases are
      normalized; currencies become ISO 4217 codes; garbage job titles are dropped.

    Args:
        text: Plain text of the post
        posting: Extracted fields of either kind

    Returns:
        The cleaned fields
    """
    post = _post(text)
    values = {
        field.name: _CLEANERS.get(field.name, _same)(getattr(posting, field.name), post)
        for field in dataclasses.fields(posting)
    }
    cleaned = dataclasses.replace(posting, **values)
    return dataclasses.replace(cleaned, role_categories=_role_categories(cleaned))
