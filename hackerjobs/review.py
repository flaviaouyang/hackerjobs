import sqlite3

from hackerjobs import db, providers
from hackerjobs.config import Config
from hackerjobs.extract import HIRING_RULES, PRINCIPLES, SEEKING_RULES
from hackerjobs.models import POSTING_ADAPTERS, REVIEW_ADAPTERS, Kind

INSTRUCTIONS = """\
You review structured data that another model extracted from a Hacker News post. Check every \
field against the post and the rules below. If every field is right, answer verdict "correct", \
no issues, and the fields unchanged. Otherwise answer verdict "corrected", one short note per \
wrong field in issues, and the full set of fields with every correction applied."""

SYSTEM_PROMPTS = {
    kind: f"{INSTRUCTIONS}\n\nExtraction rules:\n{PRINCIPLES}\n\n{rules}"
    for kind, rules in ((Kind.HIRING, HIRING_RULES), (Kind.SEEKING, SEEKING_RULES))
}
REVIEW_TEMPLATE = "Post:\n{post}\n\nExtracted fields:\n{fields}"

PROMPT_VERSION = providers.prompt_version(
    [REVIEW_ADAPTERS[Kind.HIRING], REVIEW_ADAPTERS[Kind.SEEKING]],
    *SYSTEM_PROMPTS.values(),
    REVIEW_TEMPLATE,
)


async def review_extractions(
    conn: sqlite3.Connection, config: Config, reviewer: str, model: str
) -> int:
    """Review each post's latest extraction by a model that the reviewer has not yet reviewed.

    Args:
        conn: Database connection
        config: Loaded configuration
        reviewer: Reviewer model reference
        model: Reference of the model whose extractions are reviewed

    Returns:
        Number of reviews that failed

    Raises:
        RuntimeError: If the reviewer's provider is not configured, unreachable or lacks the model
    """
    pending = db.extractions_to_review(conn, reviewer, model, PROMPT_VERSION)
    async with providers.open_provider(config, reviewer) as provider:
        return await providers.run_jobs(
            pending,
            lambda item: provider.complete(
                REVIEW_ADAPTERS[item.kind],
                SYSTEM_PROMPTS[item.kind],
                REVIEW_TEMPLATE.format(
                    post=item.text,
                    fields=POSTING_ADAPTERS[item.kind].dump_json(item.posting, indent=2).decode(),
                ),
            ),
            lambda item, result: db.save_review(conn, item, reviewer, PROMPT_VERSION, result),
            providers.concurrency(config, reviewer),
            f"review {model} by {reviewer}",
        )
