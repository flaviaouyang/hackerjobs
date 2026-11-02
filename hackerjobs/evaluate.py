import dataclasses
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any

from hackerjobs import extract, providers
from hackerjobs.config import Config
from hackerjobs.merge import FIELD_SOURCES, FIELDS, SOURCES, merge
from hackerjobs.models import EMPTY_POSTINGS, POSTING_ADAPTERS, Kind, Posting

# Variants scored against the benchmark: the raw model output, each uniform merge source, and
# the per-field sources currently configured in FIELD_SOURCES.
RAW = "llm_raw"
CONFIGURED = "configured"
VARIANTS = (RAW, *SOURCES, CONFIGURED)
SET_FIELDS = frozenset(
    {"technologies", "employment_types", "languages", "industries", "role_categories"}
)
FUZZY_SET_FIELDS = frozenset({"roles", "locations", "investors", "benefits", "interests"})
TEXT_FIELDS = frozenset({
    "company_description", "team_size",
    "work_authorization", "security_clearance", "timezone", "hours", "education",
    "equity_details", "interview_process", "application_instructions", "availability",
})  # fmt: skip
FUZZY_MATCH = 0.5
# A longer copied passage that contains the labelled text also counts as a match.
CONTAINED = 0.8
MAX_LENGTH_RATIO = 3
_NON_ALNUM = re.compile(r"[\W_]+")
_URL_PREFIX = re.compile(r"^(?:https?://)?(?:www\.)?")


@dataclass(frozen=True, slots=True)
class BenchmarkPost:
    """A hand-labelled post.

    Attributes:
        id: HN item id
        kind: Thread kind
        text: Plain text of the post when it was labelled
        expected: Correct value per field, as JSON; a list for a scalar field lists acceptable
            alternatives
    """

    id: int
    kind: Kind
    text: str = dataclasses.field(repr=False)
    expected: dict[str, Any] = dataclasses.field(repr=False)


@dataclass(frozen=True, slots=True)
class Mismatch:
    """A field where a variant disagrees with the benchmark."""

    post_id: int
    field: str
    expected: Any
    predicted: Any


@dataclass(frozen=True, slots=True)
class EvalReport:
    """Per-field scores of every variant, and the mismatches of the configured variant.

    Attributes:
        scores: Mean score in [0, 1] keyed by variant, then by "<kind>.<field>"
        mismatches: Fields the configured variant got wrong
    """

    scores: dict[str, dict[str, float]]
    mismatches: list[Mismatch]

    @property
    def best_sources(self) -> dict[str, str]:
        """Highest-scoring merge source per field, preferring the configured one on ties."""
        best = {}
        for name in self.scores[RAW]:
            kind, field = name.split(".", 1)
            configured = FIELD_SOURCES[Kind(kind)].get(field, "llm")
            best[name] = max(
                SOURCES, key=lambda source: (self.scores[source][name], source == configured)
            )
        return best


def load_benchmark(path: Path) -> list[BenchmarkPost]:
    """Read the benchmark file.

    Args:
        path: JSON Lines file with one labelled post per line

    Returns:
        The labelled posts
    """
    with path.open(encoding="utf-8") as file:
        return [
            BenchmarkPost(item["id"], Kind(item["kind"]), item["text"], item["expected"])
            for item in map(json.loads, file)
        ]


def _text(value: str) -> str:
    return _NON_ALNUM.sub(" ", _URL_PREFIX.sub("", value.casefold()).rstrip("/")).strip()


def _jaccard(left: str, right: str) -> float:
    left_words, right_words = set(_text(left).split()), set(_text(right).split())
    union = left_words | right_words
    return len(left_words & right_words) / len(union) if union else 1.0


def _fuzzy(predicted: str, expected: str) -> bool:
    if _jaccard(predicted, expected) >= FUZZY_MATCH:
        return True
    predicted_words, expected_words = _text(predicted).split(), set(_text(expected).split())
    if not expected_words or len(predicted_words) > MAX_LENGTH_RATIO * len(expected_words):
        return False
    return len(expected_words & set(predicted_words)) / len(expected_words) >= CONTAINED


def _scalar_matches(predicted: Any, expected: Any) -> bool:
    if isinstance(predicted, str) and isinstance(expected, str):
        return _text(predicted) == _text(expected)
    if isinstance(predicted, dict) and isinstance(expected, dict):
        return all(_scalar_matches(predicted[key], expected[key]) for key in expected)
    if isinstance(predicted, bool) or isinstance(expected, bool) or None in (predicted, expected):
        return predicted is expected
    return float(predicted) == float(expected)


def _set_f1(
    predicted: list[str], expected: list[str], matches: Callable[[str, str], bool]
) -> float:
    if not predicted and not expected:
        return 1.0
    unmatched = list(expected)
    hits = 0
    for item in predicted:
        found = next((candidate for candidate in unmatched if matches(item, candidate)), None)
        if found is not None:
            unmatched.remove(found)
            hits += 1
    return 2 * hits / (len(predicted) + len(expected))


def _titles(roles: list[Any]) -> list[str]:
    return [role if isinstance(role, str) else role["title"] for role in roles]


def score_field(field: str, predicted: Any, expected: Any) -> float:
    """Score one extracted field (as JSON) against the benchmark.

    Args:
        field: Posting field name
        predicted: Extracted value as JSON
        expected: Correct value as JSON; for scalar fields, a list means any listed value is
            correct

    Returns:
        Set F1 for list fields (job titles, places and other free-text items match on word
        overlap; names match exactly); 1.0 or 0.0 for single values (copied text matches on word
        overlap)

    Example:
        >>> score_field("technologies", ["Python", "Rust"], ["python"])
        0.6666666666666666
        >>> score_field("company_description", "Acme builds rockets.", "Acme builds rockets")
        1.0
    """
    if field == "roles":
        return _set_f1(_titles(predicted), _titles(expected), _fuzzy)
    if field in SET_FIELDS:
        return _set_f1(predicted, expected, lambda left, right: _text(left) == _text(right))
    if field in FUZZY_SET_FIELDS:
        return _set_f1(predicted, expected, _fuzzy)
    alternatives = expected if isinstance(expected, list) else [expected]
    if field in TEXT_FIELDS:
        return float(
            any(
                (predicted is None and alternative is None)
                or (None not in (predicted, alternative) and _fuzzy(predicted, alternative))
                for alternative in alternatives
            )
        )
    return float(any(_scalar_matches(predicted, alternative) for alternative in alternatives))


def variants(post: BenchmarkPost, llm: Posting | None) -> dict[str, Posting]:
    """Produce every scored variant of a post's fields.

    Args:
        post: Benchmark post
        llm: The model's extraction, or None if it failed

    Returns:
        Fields per variant name
    """
    raw = EMPTY_POSTINGS[post.kind] if llm is None else llm
    fields = FIELDS[post.kind]
    return {
        RAW: raw,
        **{
            source: merge(post.kind, post.text, raw, dict.fromkeys(fields, source))
            for source in SOURCES
        },
        CONFIGURED: merge(post.kind, post.text, raw),
    }


def score(posts: list[BenchmarkPost], extractions: Mapping[int, Posting]) -> EvalReport:
    """Score all variants on the benchmark.

    Args:
        posts: Benchmark posts
        extractions: Model extraction per post id; missing posts count as empty extractions

    Returns:
        Per-field scores and the configured variant's mismatches
    """
    field_scores: dict[str, dict[str, list[float]]] = {name: {} for name in VARIANTS}
    mismatches = []
    for post in posts:
        adapter = POSTING_ADAPTERS[post.kind]
        for name, posting in variants(post, extractions.get(post.id)).items():
            predicted = adapter.dump_python(posting, mode="json")
            expected = post.expected
            for field in FIELDS[post.kind]:
                value = score_field(field, predicted[field], expected[field])
                field_scores[name].setdefault(f"{post.kind}.{field}", []).append(value)
                if name == CONFIGURED and value < 1:
                    mismatches.append(Mismatch(post.id, field, expected[field], predicted[field]))
    scores = {
        name: {field: fmean(values) for field, values in fields.items()}
        for name, fields in field_scores.items()
    }
    return EvalReport(scores, mismatches)


def _cache_path(cache_dir: Path, model_ref: str) -> Path:
    versions = "-".join(extract.PROMPT_VERSIONS[kind] for kind in Kind)
    return cache_dir / f"{re.sub(r'[^\w.-]', '_', model_ref)}-{versions}.json"


async def extract_benchmark(
    posts: list[BenchmarkPost], config: Config, model_ref: str, cache_dir: Path
) -> dict[int, Posting]:
    """Run a model on the benchmark posts, reusing cached results for the current prompt version.

    Args:
        posts: Benchmark posts
        config: Loaded configuration
        model_ref: Model reference such as "anthropic:claude-haiku-5-5"
        cache_dir: Directory for cached extractions

    Returns:
        Extraction per post id; posts that failed are absent

    Raises:
        RuntimeError: If the provider is not configured, unreachable or lacks the model
    """
    kinds = {post.id: post.kind for post in posts}
    path = _cache_path(cache_dir, model_ref)
    cached = json.loads(path.read_text()) if path.exists() else {}
    results = {
        int(post_id): POSTING_ADAPTERS[kinds[int(post_id)]].validate_python(data)
        for post_id, data in cached.items()
        if int(post_id) in kinds
    }
    pending = [post for post in posts if post.id not in results]
    if pending:
        async with providers.open_provider(config, model_ref) as provider:
            await providers.run_jobs(
                pending,
                lambda post: extract.extract(provider, post.kind, post.text),
                lambda post, posting: results.__setitem__(post.id, posting),
                providers.concurrency(config, model_ref),
                f"eval {model_ref}",
            )
        cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    post_id: POSTING_ADAPTERS[kinds[post_id]].dump_python(value, mode="json")
                    for post_id, value in results.items()
                }
            )
        )
    return results


def format_scores(report: EvalReport) -> str:
    """Render per-field scores as a Markdown table, marking each field's best merge source.

    Args:
        report: Evaluation report

    Returns:
        The table, followed by each variant's mean score
    """
    best = report.best_sources
    lines = [f"| field | {' | '.join(VARIANTS)} |", f"|---|{'---|' * len(VARIANTS)}"]
    for field in report.scores[RAW]:
        cells = [
            f"**{report.scores[name][field]:.2f}**"
            if name == best[field]
            else f"{report.scores[name][field]:.2f}"
            for name in VARIANTS
        ]
        lines.append(f"| {field} | {' | '.join(cells)} |")
    means = (f"{fmean(report.scores[name].values()):.3f}" for name in VARIANTS)
    lines.append(f"| **mean** | {' | '.join(means)} |")
    return "\n".join(lines)


def format_mismatches(report: EvalReport) -> str:
    """Render the configured variant's mismatches as Markdown.

    Args:
        report: Evaluation report

    Returns:
        One bullet per mismatched field, in benchmark order
    """
    return "\n".join(
        f"- {mismatch.post_id} `{mismatch.field}`: "
        f"expected {mismatch.expected!r}, got {mismatch.predicted!r}"
        for mismatch in report.mismatches
    )
