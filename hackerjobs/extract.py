import dataclasses
import sqlite3
from typing import Any

from pydantic import TypeAdapter, with_config

from hackerjobs import db, providers
from hackerjobs.config import Config
from hackerjobs.merge import FIELD_SOURCES
from hackerjobs.models import (
    EMPTY_POSTINGS,
    INDUSTRIES,
    POSTING_TYPES,
    ROLE_CATEGORIES,
    STRICT,
    Kind,
    Posting,
)

PRINCIPLES = """\
You extract structured data from a Hacker News post. Copy information exactly as the post states \
it: never summarize, infer, guess or write anything yourself. Text fields hold words copied from \
the post. Use null or an empty list for anything the post does not state."""

SHARED_RULES = """\
- post_type: "job_ad" if the post offers jobs, "job_seeker" if the author is looking for work, \
"other" for anything else (questions, comments, jokes, advertising a service). Judge the post \
itself, whichever thread it is in.
- locations: cities, countries or regions as specific as stated, e.g. "Austin, TX", \
"Berlin, Germany", "US", "EU". Never the words remote, hybrid or onsite.
- remote: "remote" if fully remote work is possible (even if restricted to a region), \
"hybrid" if partly in office, "onsite" if in office only.
- employment_types: any of full-time, part-time, contract, internship, only when stated. \
Do not assume full-time.
- pay: the stated range as plain numbers ("$150k-180k" -> min 150000, max 180000; a single \
figure goes in both), ISO 4217 currency ("$" alone is USD) and period (year, month, day or hour). \
Equity is not pay.
- technologies: named languages, frameworks, libraries, databases, cloud services and tools \
mentioned anywhere in the post, each as its own item ("C/C++" -> "C", "C++"). Never concepts or \
practices (AI, LLMs, RAG, agents, data pipelines, distributed systems, CI/CD), protocols (REST, \
MCP, WebSockets) or business areas.
- languages: spoken languages, not programming languages.
- timezone: working hours or timezone as stated ("US timezones", "UTC+1", "EU hours")."""

HIRING_RULES = f"""\
This post is a job ad from a company that is hiring.

- company: the hiring company's name.
- company_website: the company's own website, not a job board or application link.
- company_description: the sentence(s) in the post that say what the company does, copied.
- industries: the one or two industries from the list below that best describe what the company \
sells or who its customers are, based on what the post says it does. Technology it merely uses \
does not count: a company that uses AI is not AI/ML unless AI is its product. Consulting & \
agencies is only for a company that is itself a consultancy, agency, dev shop or staffing firm, \
not one that sells to such firms.
- company_stage: only if the post states it: pre-seed, seed, series-a, series-b, series-c, \
series-d+ (Series D or later), public (publicly traded), bootstrapped, subsidiary (part of another \
company), nonprofit. "Startup" or "early-stage" alone is not a stage.
- funding: total money raised as a number with ISO currency ("$5M raised" -> 5000000 USD); \
valuation the same way. investors: named investors only, not partners or customers. \
team_size (as written), founded_year.
- roles: one entry per distinct job title, short, without technologies in parentheses \
("Fullstack/Product Engineers" -> "Full-Stack Engineer", "Product Engineer"). Give a role its own \
pay, locations or apply_url only when the post states them for that role.
- pay: the overall range; when roles have different pay, from the lowest to the highest figure.
{SHARED_RULES}
- min_experience_years: minimum years of experience required.
- work_authorization ("U.S. person status required"), security_clearance, hours (required \
commitment, e.g. "at least 30h per week"), education (as required).
- equity: true if equity is offered; equity_details: only a stated amount or range ("0.5% - 1.5%").
- benefits: each benefit as written ("unlimited PTO", "401K match up to 4%").
- visa_sponsorship, relocation_support: true or false only if the post explicitly says so.
- interview_process: as written.
- contact: the email address or application URL to use.
- application_instructions: extra steps applicants are asked to take (subject line, what to \
include or mention), as written; not just where to apply."""

SEEKING_RULES = f"""\
This post is a candidate looking for work.

- roles: the job titles they are looking for, one per title; if they name none, the title they \
describe themselves as ("Full-Stack AI Engineer with 10 years..."). Never a sentence.
- role_categories: the kinds of work those roles are, from the role categories below.
- willing_to_relocate: true or false only if stated.
{SHARED_RULES}
- pay: their expected pay, if stated.
- experience_years: total years of professional experience, if stated.
- work_authorization ("US citizen", "F-1 OPT", "EU citizen"), availability ("available \
immediately", "from December 2026"), education (as written).
- interests: only what they explicitly say they want to work on next ("looking for", "interested \
in", "would love to", "best fit"), as short phrases naming an industry ("games industry" -> \
"game development") or a kind of work ("distributed systems", "developer tools"). Empty if they \
only describe their background; never their skills, past work or hobbies.
- contact: their email address. linkedin, github, resume_url: their links."""

INDUSTRY_LIST = f"Industries: {', '.join(INDUSTRIES)}."
ROLE_CATEGORY_LIST = (
    f"Role categories: {', '.join(ROLE_CATEGORIES)}. Engineering covers software, infrastructure, "
    "hardware and security engineering; Data & ML covers data science, data engineering and "
    "machine learning; Product covers product and program management."
)

SYSTEM_PROMPTS = {
    Kind.HIRING: f"{PRINCIPLES}\n\n{HIRING_RULES}\n\n{INDUSTRY_LIST}",
    Kind.SEEKING: f"{PRINCIPLES}\n\n{SEEKING_RULES}\n\n{ROLE_CATEGORY_LIST}",
}


def _model_type(kind: Kind) -> type:
    """The kind's posting without the fields published from rules alone.

    Every field makes the constrained-output grammar bigger, and the hiring schema is close to the
    API's limit, so the model is not asked for fields it would not be used for.
    """
    posting_type = POSTING_TYPES[kind]
    asked = [
        (field.name, field.type)
        for field in dataclasses.fields(posting_type)
        if FIELD_SOURCES[kind].get(field.name) != "rules"
    ]
    model_type = dataclasses.make_dataclass(
        posting_type.__name__,
        asked,
        namespace={"__doc__": posting_type.__doc__},
        frozen=True,
        slots=True,
    )
    return with_config(STRICT)(model_type)


MODEL_ADAPTERS: dict[Kind, TypeAdapter[Any]] = {
    kind: TypeAdapter(_model_type(kind)) for kind in Kind
}

# One version per post kind, so changing the hiring prompt does not re-parse candidates.
PROMPT_VERSIONS = {
    kind: providers.prompt_version([MODEL_ADAPTERS[kind]], prompt)
    for kind, prompt in SYSTEM_PROMPTS.items()
}


async def extract(provider: providers.Provider, kind: Kind, text: str) -> Posting:
    """Extract a post's fields with schema-constrained output.

    Args:
        provider: Connected model provider
        kind: Thread kind of the post
        text: Plain text of the post

    Returns:
        The kind's posting, with fields published from rules alone left empty
    """
    output = await provider.complete(MODEL_ADAPTERS[kind], SYSTEM_PROMPTS[kind], text)
    asked = {field.name: getattr(output, field.name) for field in dataclasses.fields(output)}
    return dataclasses.replace(EMPTY_POSTINGS[kind], **asked)


async def parse_posts(conn: sqlite3.Connection, config: Config, model_ref: str) -> int:
    """Extract fields with a model for every post it has not parsed at its kind's prompt version.

    Args:
        conn: Database connection
        config: Loaded configuration
        model_ref: Model reference such as "anthropic:claude-haiku-5-5"

    Returns:
        Number of posts that failed

    Raises:
        RuntimeError: If the provider is not configured, unreachable or lacks the model
    """
    pending = [
        post
        for kind, version in PROMPT_VERSIONS.items()
        for post in db.posts_to_parse(conn, model_ref, kind, version)
    ]
    async with providers.open_provider(config, model_ref) as provider:
        return await providers.run_jobs(
            pending,
            lambda post: extract(provider, post.kind, post.text),
            lambda post, posting: db.save_extraction(
                conn, post, model_ref, PROMPT_VERSIONS[post.kind], posting
            ),
            providers.concurrency(config, model_ref),
            f"parse {model_ref}",
        )
