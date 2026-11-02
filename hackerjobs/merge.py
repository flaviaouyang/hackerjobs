import dataclasses
from collections.abc import Mapping
from typing import Any, Literal

from hackerjobs.models import EMPTY_POSTINGS, POSTING_TYPES, Kind, Posting
from hackerjobs.normalize import normalize
from hackerjobs.rules import extract_rules

# "union" combines both lists for list fields and acts like "llm_then_rules" for single values.
Source = Literal["llm", "rules", "rules_then_llm", "llm_then_rules", "union"]
SOURCES: tuple[Source, ...] = ("llm", "rules", "rules_then_llm", "llm_then_rules", "union")
FIELDS: dict[Kind, tuple[str, ...]] = {
    kind: tuple(field.name for field in dataclasses.fields(posting_type))
    for kind, posting_type in POSTING_TYPES.items()
}

# Where each published field comes from, chosen per field from `hackerjobs eval` scores.
# Fields not listed use the model's value only.
FIELD_SOURCES: dict[Kind, dict[str, Source]] = {
    Kind.HIRING: {
        "company": "rules_then_llm",
        "company_website": "rules_then_llm",
        "company_stage": "llm_then_rules",
        "locations": "rules_then_llm",
        "remote": "rules_then_llm",
        "employment_types": "llm_then_rules",
        "pay": "llm_then_rules",
        "technologies": "union",
        "min_experience_years": "llm_then_rules",
        "equity": "llm_then_rules",
        "visa_sponsorship": "rules",
        "relocation_support": "rules_then_llm",
        "contact": "rules_then_llm",
        "applications_closed": "rules_then_llm",
    },
    Kind.SEEKING: {
        "locations": "rules_then_llm",
        "remote": "rules_then_llm",
        "willing_to_relocate": "rules",
        "timezone": "rules_then_llm",
        "experience_years": "llm_then_rules",
        "contact": "rules_then_llm",
        "website": "rules",
        "linkedin": "rules_then_llm",
        "github": "rules_then_llm",
        "resume_url": "rules_then_llm",
    },
}


def _is_empty(value: Any) -> bool:
    return value is None or value == ()


def _pick(source: Source, llm_value: Any, rule_value: Any, empty: Any) -> Any:
    match source:
        case "llm":
            return llm_value
        case "rules":
            return empty if rule_value is None else rule_value
        case "rules_then_llm":
            return llm_value if rule_value is None else rule_value
        case "llm_then_rules":
            return rule_value if _is_empty(llm_value) and rule_value is not None else llm_value
        case "union" if isinstance(llm_value, tuple):
            return tuple(dict.fromkeys((*llm_value, *(rule_value or ()))))
        case "union":
            return _pick("llm_then_rules", llm_value, rule_value, empty)


def merge(
    kind: Kind, text: str, llm: Posting | None, sources: Mapping[str, Source] | None = None
) -> Posting:
    """Combine rule-based and model-extracted fields, then clean them up.

    Posts without a model extraction get their rule-based fields only.

    Args:
        kind: Thread kind of the post
        text: Plain text of the post
        llm: The model's extraction, or None if the post has not been parsed
        sources: Source per field; defaults to FIELD_SOURCES for the kind, "llm" for unlisted fields

    Returns:
        The published fields
    """
    sources = FIELD_SOURCES[kind] if sources is None else sources
    rules = extract_rules(kind, text)
    empty = EMPTY_POSTINGS[kind]
    base = empty if llm is None else llm
    values = {
        name: _pick(
            "rules_then_llm" if llm is None else sources.get(name, "llm"),
            getattr(base, name),
            rules.get(name),
            getattr(empty, name),
        )
        for name in FIELDS[kind]
    }
    return normalize(text, type(empty)(**values))
