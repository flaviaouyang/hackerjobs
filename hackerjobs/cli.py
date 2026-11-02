import argparse
import asyncio
import logging
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from hackerjobs import db, evaluate, extract, fx, hn, review
from hackerjobs.config import Config, load_config
from hackerjobs.export import export_site_data
from hackerjobs.identity import near_matches
from hackerjobs.merge import merge
from hackerjobs.models import HiringPosting, Kind

DEFAULT_OUT_DIR = Path("web/public/data")
DEFAULT_BENCHMARK = Path("eval/benchmark.jsonl")
EVAL_CACHE_DIR = Path("eval/.cache")


def _ingest(args: argparse.Namespace, config: Config, conn: sqlite3.Connection) -> None:
    """Fetch threads since a month from Hacker News and store their posts."""
    for fetched in asyncio.run(hn.fetch(args.since or config.since)):
        db.save_thread(conn, fetched.thread, fetched.posts, fetched.removed)
        thread = fetched.thread
        logging.info(
            "%s %s: %d posts, %d removed on HN",
            thread.month,
            thread.kind,
            len(fetched.posts),
            len(fetched.removed),
        )


def _update_rates(args: argparse.Namespace, config: Config, conn: sqlite3.Connection) -> None:
    """Fetch and store the latest Bank of Canada exchange rates."""
    rates = asyncio.run(fx.fetch_rates())
    db.save_rates(conn, rates)
    logging.info("Exchange rates for %s: %d currencies", rates.date, len(rates.cad_per_unit))


def _parse(args: argparse.Namespace, config: Config, conn: sqlite3.Connection) -> None:
    """Extract fields from unparsed posts with each model."""
    for model in args.model or config.parse.models:
        failures = asyncio.run(extract.parse_posts(conn, config, model))
        if failures:
            logging.warning("parse %s: %d posts failed; rerun to retry them", model, failures)


def _review_posts(args: argparse.Namespace, config: Config, conn: sqlite3.Connection) -> None:
    """Review one model's extractions with another model."""
    reviewer = args.model or (config.review and config.review.reviewer)
    model = args.of or (config.review and config.review.of)
    if not reviewer or not model:
        logging.info("review: skipped, no reviewer configured")
        return
    failures = asyncio.run(review.review_extractions(conn, config, reviewer, model))
    if failures:
        logging.warning(
            "review %s by %s: %d failed; rerun to retry them", model, reviewer, failures
        )


def _export(args: argparse.Namespace, config: Config, conn: sqlite3.Connection) -> None:
    """Write the site's data files."""
    out_dir = args.out or DEFAULT_OUT_DIR
    export_site_data(conn, args.publish_model or config.publish.models, out_dir)
    logging.info("Exported site data to %s", out_dir)


def _sync(args: argparse.Namespace, config: Config, conn: sqlite3.Connection) -> None:
    """Run ingest, exchange rates, parse, review and export in order."""
    for step in (_ingest, _update_rates, _parse, _review_posts, _export):
        step(args, config, conn)


def _evaluate(args: argparse.Namespace, config: Config, conn: sqlite3.Connection) -> None:
    """Score extraction variants on the benchmark for each model."""
    posts = evaluate.load_benchmark(args.benchmark)
    for model in args.model or config.parse.models:
        extractions = asyncio.run(evaluate.extract_benchmark(posts, config, model, EVAL_CACHE_DIR))
        report = evaluate.score(posts, extractions)
        parsed = f"{len(extractions)}/{len(posts)} parsed"
        versions = ", ".join(
            f"{kind} {version}" for kind, version in extract.PROMPT_VERSIONS.items()
        )
        print(f"## {model} (prompts {versions}; {parsed})\n")
        print(evaluate.format_scores(report))
        if args.report:
            args.report.write_text(
                f"# {model}\n\n{evaluate.format_scores(report)}\n\n## Mismatches\n\n"
                f"{evaluate.format_mismatches(report)}\n"
            )
            logging.info("Wrote mismatches to %s", args.report)


def _companies(args: argparse.Namespace, config: Config, conn: sqlite3.Connection) -> None:
    """List company names that look alike but are kept apart, for manual review."""
    names = {
        fields.company
        for post in db.published_posts(conn, args.publish_model or config.publish.models)
        if post.kind is Kind.HIRING
        and isinstance(fields := merge(post.kind, post.text, post.posting), HiringPosting)
        and fields.company
    }
    lines = [f"- {left} / {right} ({ratio:.2f})" for left, right, ratio in near_matches(names)]
    report = (
        f"# Similar company names ({len(lines)} pairs, not merged)\n\n" + "\n".join(lines) + "\n"
    )
    if args.report:
        args.report.write_text(report)
        logging.info("Wrote %d similar name pairs to %s", len(lines), args.report)
    else:
        print(report)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns:
        Parser for the hackerjobs command
    """
    parser = argparse.ArgumentParser(
        prog="hackerjobs", description="Hacker News job board pipeline"
    )
    parser.add_argument(
        "--config", type=Path, default=Path("hackerjobs.toml"), help="TOML config file"
    )
    parser.add_argument(
        "--db", type=Path, default=Path("data/hackerjobs.db"), help="SQLite database file"
    )
    # Every command reads every override, so sync can pass them through to its steps.
    parser.set_defaults(since=None, model=None, of=None, publish_model=None, out=None)
    commands = parser.add_subparsers(required=True)

    since = argparse.ArgumentParser(add_help=False)
    since.add_argument("--since", help="first month to ingest, YYYY-MM (default: config since)")
    out = argparse.ArgumentParser(add_help=False)
    out.add_argument("--out", type=Path, help=f"output directory (default: {DEFAULT_OUT_DIR})")
    out.add_argument(
        "--publish-model",
        action="append",
        help="model whose results are published; repeatable, first preferred "
        "(default: config publish.models)",
    )

    commands.add_parser(
        "ingest", parents=[since], help="fetch threads from Hacker News"
    ).set_defaults(handler=_ingest)
    commands.add_parser("fx", help="fetch the latest exchange rates").set_defaults(
        handler=_update_rates
    )

    parse_parser = commands.add_parser("parse", help="extract fields from posts with a model")
    parse_parser.add_argument(
        "--model",
        action="append",
        help="model to parse with; repeatable (default: config parse.models)",
    )
    parse_parser.set_defaults(handler=_parse)

    review_parser = commands.add_parser(
        "review", help="review one model's extractions with another"
    )
    review_parser.add_argument("--model", help="reviewer model (default: config review.reviewer)")
    review_parser.add_argument(
        "--of", help="model whose extractions are reviewed (default: config review.of)"
    )
    review_parser.set_defaults(handler=_review_posts)

    eval_parser = commands.add_parser("eval", help="score extraction on the labelled benchmark")
    eval_parser.add_argument(
        "--model", action="append", help="model to score; repeatable (default: config parse.models)"
    )
    eval_parser.add_argument(
        "--benchmark", type=Path, default=DEFAULT_BENCHMARK, help="benchmark file"
    )
    eval_parser.add_argument(
        "--report", type=Path, help="write scores and mismatches to this Markdown file"
    )
    eval_parser.set_defaults(handler=_evaluate)

    companies_parser = commands.add_parser(
        "companies", help="list similar company names that are kept apart, for review"
    )
    companies_parser.add_argument(
        "--report", type=Path, help="write the list to this Markdown file"
    )
    companies_parser.add_argument(
        "--publish-model",
        action="append",
        help="model whose results are used; repeatable, first preferred "
        "(default: config publish.models)",
    )
    companies_parser.set_defaults(handler=_companies)

    commands.add_parser("export", parents=[out], help="write the site's data files").set_defaults(
        handler=_export
    )
    commands.add_parser(
        "sync", parents=[since, out], help="ingest, fx, parse, review and export"
    ).set_defaults(handler=_sync)
    return parser


def main() -> None:
    """Entry point of the hackerjobs command."""
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        config = load_config(args.config)
        with closing(db.connect(args.db)) as conn:
            args.handler(args, config, conn)
    except (ValueError, RuntimeError) as error:
        sys.exit(f"error: {error}")
