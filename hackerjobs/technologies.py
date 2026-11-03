import re
import tomllib
from functools import cache
from importlib.resources import files

with files("hackerjobs").joinpath("technologies.toml").open("rb") as _file:
    _TABLE = tomllib.load(_file)

CONCEPTS = frozenset(_TABLE["concepts"])
CANONICAL = {
    alias.casefold(): canonical
    for canonical, aliases in _TABLE["aliases"].items()
    for alias in (canonical, *aliases)
}
_AMBIGUOUS = frozenset(_TABLE["ambiguous"])
_UNSCANNABLE = frozenset(_TABLE["unscannable"])
_SPACES = re.compile(r"\s+")
_VERSION = re.compile(r"[\d.x+]+")
# A name followed by a version: "Qt5", "ROS 2", "Next.js 15", "YOLOv8", "OAuth 2.0".
_VERSIONED = re.compile(r"(?P<base>.+?)[\s-]?v?\d+(?:\.\d+)*(?:\.x)?")
# Unknown multi-word, all-lowercase items ("agent orchestration") are descriptions, not names.
_LOWERCASE_PHRASE = re.compile(r"[a-z]+(?: [a-z]+)+")


def canonical_technologies(name: str) -> list[str]:
    """Map a technology name to canonical spellings, splitting combined items like "C/C++".

    Args:
        name: Technology name as written in a post or extracted by a model

    Returns:
        Canonical names; unknown names are kept as written, generic concepts are dropped

    Example:
        >>> canonical_technologies("postgres")
        ['PostgreSQL']
        >>> canonical_technologies("C/C++")
        ['C', 'C++']
        >>> canonical_technologies("LLMs")
        []
        >>> [canonical_technologies(name) for name in (".NET 8", "Qt5", "S3")]
        [['.NET'], ['Qt'], ['S3']]
    """
    # A leading dot belongs to names like ".NET"; trailing ones end sentences.
    cleaned = _SPACES.sub(" ", name).strip(" -*").rstrip(".").removeprefix(". ")
    key = cleaned.casefold()
    if key in CANONICAL:
        return [CANONICAL[key]]
    # A known name with a version is that name. One-letter bases are left alone: in "S3",
    # "R2" or "V8" the number is part of the name.
    if (
        (match := _VERSIONED.fullmatch(key))
        and len(match["base"]) > 1
        and match["base"] in CANONICAL
    ):
        return [CANONICAL[match["base"]]]
    if (
        not key
        or key in CONCEPTS
        or _VERSION.fullmatch(key)
        or _LOWERCASE_PHRASE.fullmatch(cleaned)
    ):
        return []
    if "/" in cleaned:
        return [
            canonical for part in cleaned.split("/") for canonical in canonical_technologies(part)
        ]
    return [cleaned]


def is_known_technology(name: str) -> bool:
    """Tell whether a name is in the canonical technology table.

    Args:
        name: Technology name

    Returns:
        True if the name or one of its aliases is known
    """
    return name.strip().casefold() in CANONICAL


_TOKEN = re.compile(r"[\w.+#/-]+")


@cache
def _scannable() -> tuple[dict[str, str], dict[str, int]]:
    """Scannable aliases, and the longest alias length in words for each first word."""
    names = {
        alias: canonical
        for alias, canonical in CANONICAL.items()
        if canonical not in _AMBIGUOUS
        and alias not in _UNSCANNABLE
        and (len(alias) > 2 or not alias.isalpha())
    }
    longest: dict[str, int] = {}
    for alias in names:
        first, *rest = alias.split()
        longest[first] = max(longest.get(first, 1), len(rest) + 1)
    return names, longest


def _tokens(text: str, names: dict[str, str]) -> list[str]:
    tokens = []
    for raw in _TOKEN.findall(text):
        token = raw.rstrip(".,;:/-").lstrip("/-").casefold()
        if token in names or "/" not in token:
            tokens.append(token)
        elif "." not in token:  # "C/C++" splits; URL-like tokens ("github.com/x") are skipped
            tokens.extend(part for part in token.split("/") if part)
    return tokens


def find_technologies(text: str) -> tuple[str, ...]:
    """Find known, unambiguous technology names anywhere in a text.

    Matches whole words and multi-word names (e.g. "React Native"), longest first, in linear time.

    Args:
        text: Post text

    Returns:
        Canonical names in order of first mention
    """
    names, longest = _scannable()
    tokens = _tokens(text, names)
    found: dict[str, None] = {}
    index = 0
    while index < len(tokens):
        for size in range(min(longest.get(tokens[index], 1), len(tokens) - index), 0, -1):
            if (canonical := names.get(" ".join(tokens[index : index + size]))) is not None:
                found[canonical] = None
                index += size
                break
        else:
            index += 1
    return tuple(found)
