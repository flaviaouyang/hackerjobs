import dataclasses
import typing
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from pydantic import ConfigDict, TypeAdapter, with_config

Remote = Literal["remote", "hybrid", "onsite"]
EmploymentType = Literal["full-time", "part-time", "contract", "internship"]
PayPeriod = Literal["year", "month", "day", "hour"]
Verdict = Literal["correct", "corrected"]
Seniority = Literal[
    "intern",
    "junior",
    "mid",
    "senior",
    "staff",
    "principal",
    "lead",
    "manager",
    "director",
    "executive",
]
CompanyStage = Literal[
    "pre-seed", "seed", "series-a", "series-b", "series-c", "series-d+", "public", "bootstrapped",
    "subsidiary", "nonprofit",
]  # fmt: skip
INDUSTRIES = (
    "AI/ML", "Fintech", "Banking & trading", "Insurance", "Healthcare", "Biotech & pharma",
    "Education", "Developer tools", "Security", "Cloud & infrastructure", "Data & analytics",
    "Enterprise software", "E-commerce & retail", "Consumer apps", "Gaming",
    "Media & entertainment", "Marketing & ads", "Legal", "HR & recruiting", "Real estate",
    "Logistics & supply chain",
    "Energy & climate", "Hardware & robotics", "Manufacturing", "Aerospace & defense",
    "Automotive & mobility", "Travel & hospitality", "Food & agriculture", "Crypto & web3",
    "Government & public sector", "Nonprofit", "Scientific research", "Consulting & agencies",
)  # fmt: skip
Industry = Literal[INDUSTRIES]
ROLE_CATEGORIES = (
    "Engineering", "Data & ML", "Design", "Product", "Sales & marketing", "Operations & support",
    "People & finance", "Other",
)  # fmt: skip
RoleCategory = Literal[ROLE_CATEGORIES]
# What a post is, whichever thread it was posted in; posts in the wrong thread are hidden.
PostType = Literal["job_ad", "job_seeker", "other"]

# Every object in the output schema forbids extra keys, so schema-constrained decoding
# (LM Studio grammars, Anthropic structured outputs) cannot add fields of its own.
STRICT = ConfigDict(extra="forbid")


class Kind(StrEnum):
    """Which monthly thread a post belongs to."""

    HIRING = "hiring"
    SEEKING = "seeking"


@with_config(STRICT)
@dataclass(frozen=True, slots=True)
class Pay:
    """A stated pay range: amounts in `currency` per `period`."""

    min: float | None
    max: float | None
    currency: str | None
    period: PayPeriod | None


@with_config(STRICT)
@dataclass(frozen=True, slots=True)
class Money:
    """A stated amount of money, such as funding raised or a valuation."""

    amount: float
    currency: str | None


@with_config(STRICT)
@dataclass(frozen=True, slots=True)
class Role:
    """A job title in a hiring post, with details the post gives for that role only."""

    title: str
    pay: Pay | None
    locations: tuple[str, ...]
    apply_url: str | None


@with_config(STRICT)
@dataclass(frozen=True, slots=True)
class HiringPosting:
    """Fields extracted from a "Who is hiring?" post. Free text is copied from the post."""

    post_type: PostType
    role_categories: tuple[RoleCategory, ...]
    company: str | None
    company_website: str | None
    company_description: str | None
    industries: tuple[Industry, ...]
    company_stage: CompanyStage | None
    funding: Money | None
    valuation: Money | None
    investors: tuple[str, ...]
    team_size: str | None
    founded_year: int | None
    roles: tuple[Role, ...]
    locations: tuple[str, ...]
    remote: Remote | None
    employment_types: tuple[EmploymentType, ...]
    pay: Pay | None
    technologies: tuple[str, ...]
    min_experience_years: int | None
    languages: tuple[str, ...]
    work_authorization: str | None
    security_clearance: str | None
    timezone: str | None
    hours: str | None
    education: str | None
    equity: bool | None
    equity_details: str | None
    benefits: tuple[str, ...]
    visa_sponsorship: bool | None
    relocation_support: bool | None
    interview_process: str | None
    contact: str | None
    application_instructions: str | None
    applications_closed: bool | None


@with_config(STRICT)
@dataclass(frozen=True, slots=True)
class SeekingPosting:
    """Fields extracted from a "Who wants to be hired?" post. Free text is copied from the post.

    The candidate's name is not extracted: the board shows their HN username.
    """

    post_type: PostType
    roles: tuple[str, ...]
    role_categories: tuple[RoleCategory, ...]
    locations: tuple[str, ...]
    remote: Remote | None
    willing_to_relocate: bool | None
    timezone: str | None
    employment_types: tuple[EmploymentType, ...]
    pay: Pay | None
    experience_years: int | None
    work_authorization: str | None
    availability: str | None
    languages: tuple[str, ...]
    education: str | None
    interests: tuple[str, ...]
    technologies: tuple[str, ...]
    contact: str | None
    website: str | None
    linkedin: str | None
    github: str | None
    resume_url: str | None
    # Every arrangement they are open to ("Remote: Yes, or on-site" is remote and onsite), read
    # from the template by rules. Defaults to empty so extractions stored before it still load.
    arrangements: tuple[Remote, ...] = ()


Posting = HiringPosting | SeekingPosting


@with_config(STRICT)
@dataclass(frozen=True, slots=True)
class Review[P]:
    """A reviewer model's assessment of another model's extraction.

    Attributes:
        verdict: "correct" if the extraction needs no change, otherwise "corrected"
        issues: One short note per corrected field
        posting: The extraction with all corrections applied
    """

    verdict: Verdict
    issues: tuple[str, ...]
    posting: P


POSTING_TYPES: dict[Kind, type[HiringPosting] | type[SeekingPosting]] = {
    Kind.HIRING: HiringPosting,
    Kind.SEEKING: SeekingPosting,
}
POSTING_ADAPTERS: dict[Kind, TypeAdapter[Any]] = {
    kind: TypeAdapter(posting_type) for kind, posting_type in POSTING_TYPES.items()
}
REVIEW_ADAPTERS: dict[Kind, TypeAdapter[Any]] = {
    kind: TypeAdapter(Review[posting_type]) for kind, posting_type in POSTING_TYPES.items()
}


def _empty_value(field: dataclasses.Field) -> tuple[()] | None:
    return () if typing.get_origin(field.type) is tuple else None


EMPTY_POSTINGS: dict[Kind, Posting] = {
    kind: posting_type(
        **{field.name: _empty_value(field) for field in dataclasses.fields(posting_type)}
    )
    for kind, posting_type in POSTING_TYPES.items()
}
