import asyncio
import hashlib
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import cache
from typing import Any, Protocol

import anthropic
import httpx
from pydantic import TypeAdapter, ValidationError

from hackerjobs.config import Config

REQUEST_TIMEOUT = 600
# Anthropic structured outputs accept at most 16 nullable (union) fields per schema, so optional
# text fields are sent as plain strings, with "" meaning "not stated".
EMPTY_TEXT_NOTE = "Use an empty string for any text field the post does not state."
PROGRESS_EVERY = 25
# Real extractions stay under ~1,100 tokens; the cap stops a model stuck repeating itself.
MAX_OUTPUT_TOKENS = 2048
ANTHROPIC_RETRIES = 5


class ExtractionError(Exception):
    """A model response that cannot be used, such as a refusal or truncated output."""


class Provider(Protocol):
    """A model that returns output constrained to a JSON schema."""

    async def complete[T](self, adapter: TypeAdapter[T], system: str, user: str) -> T:
        """Run one schema-constrained completion and validate the result."""
        ...


@cache
def _schema(adapter: TypeAdapter) -> dict[str, Any]:
    return adapter.json_schema()


def _plain_strings(node: Any) -> Any:
    """Rewrite every nullable string in a JSON schema as a plain string."""
    if isinstance(node, list):
        return [_plain_strings(item) for item in node]
    if not isinstance(node, dict):
        return node
    options = node.get("anyOf")
    if (
        options
        and len(options) == 2
        and {"type": "null"} in options
        and {"type": "string"} in options
    ):
        return {key: value for key, value in node.items() if key != "anyOf"} | {"type": "string"}
    return {key: _plain_strings(value) for key, value in node.items()}


@cache
def _anthropic_schema(adapter: TypeAdapter) -> dict[str, Any]:
    return _plain_strings(_schema(adapter))


def _nullable_string_fields(node: Any) -> frozenset[str]:
    """Names of the properties a JSON schema declares as nullable strings."""
    if isinstance(node, list):
        return frozenset().union(*map(_nullable_string_fields, node))
    if not isinstance(node, dict):
        return frozenset()
    names = {
        name
        for name, schema in node.get("properties", {}).items()
        if _plain_strings(schema) != schema and schema.get("anyOf")
    }
    return frozenset(names).union(*map(_nullable_string_fields, node.values()))


@cache
def _optional_text_fields(adapter: TypeAdapter) -> frozenset[str]:
    return _nullable_string_fields(_schema(adapter))


def _empty_strings_to_none(node: Any, names: frozenset[str]) -> Any:
    """Turn "" back into None, but only in fields that were nullable (a role's title is not)."""
    if isinstance(node, dict):
        return {
            key: None if value == "" and key in names else _empty_strings_to_none(value, names)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_empty_strings_to_none(item, names) for item in node]
    return node


def prompt_version(adapters: Sequence[TypeAdapter], *prompts: str) -> str:
    """Fingerprint prompts and output schemas, so changing either triggers a re-run.

    Args:
        adapters: Output type adapters
        prompts: Prompt templates

    Returns:
        A short hex digest
    """
    payload = json.dumps([*prompts, *(_schema(adapter) for adapter in adapters)], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class LMStudio:
    """A model served by LM Studio's OpenAI-compatible API."""

    client: httpx.AsyncClient
    model: str

    async def complete[T](self, adapter: TypeAdapter[T], system: str, user: str) -> T:
        """Run one completion with a json_schema response format.

        Raises:
            httpx.HTTPStatusError: If LM Studio returns an error
            ExtractionError: If the output is truncated
            pydantic.ValidationError: If the output does not match the schema
        """
        response = await self.client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "temperature": 0,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "result", "strict": True, "schema": _schema(adapter)},
                },
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        response.raise_for_status()
        choice = response.json()["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ExtractionError(f"{self.model} hit the {MAX_OUTPUT_TOKENS}-token output limit")
        message = choice["message"]
        # Models with a thinking chat template (Qwen, GLM) can have LM Studio file the whole
        # schema-constrained answer under reasoning_content and leave content empty.
        return adapter.validate_json(
            message.get("content") or message.get("reasoning_content") or ""
        )


@dataclass(frozen=True, slots=True)
class Anthropic:
    """A Claude model called through the Anthropic API with structured outputs."""

    client: anthropic.AsyncAnthropic
    model: str

    async def complete[T](self, adapter: TypeAdapter[T], system: str, user: str) -> T:
        """Run one completion with a json_schema output format and thinking off.

        Extraction is copying, not reasoning, so thinking is disabled to keep output tokens low.
        Optional text fields come back as "" and are turned into None before validation.

        Raises:
            anthropic.APIError: If the API returns an error after retries
            ExtractionError: If the model refuses or the output is truncated
            pydantic.ValidationError: If the output does not match the schema
        """
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            thinking={"type": "disabled"},
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": _anthropic_schema(adapter)},
            },
            system=f"{system}\n\n{EMPTY_TEXT_NOTE}",
            messages=[{"role": "user", "content": user}],
        )
        if response.stop_reason != "end_turn":
            raise ExtractionError(f"{self.model} stopped with {response.stop_reason!r}")
        text = next(block.text for block in response.content if block.type == "text")
        data = _empty_strings_to_none(json.loads(text), _optional_text_fields(adapter))
        return adapter.validate_python(data)


@asynccontextmanager
async def _lmstudio(config: Config, model: str) -> AsyncIterator[LMStudio]:
    if config.lmstudio is None:
        raise RuntimeError("Model uses LM Studio but hackerjobs.toml has no [lmstudio] section")
    url = config.lmstudio.url
    async with httpx.AsyncClient(base_url=url, timeout=REQUEST_TIMEOUT) as client:
        try:
            response = await client.get("/models")
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError(
                f"Cannot reach LM Studio at {url} ({error!r}). Start it with `lms server start`."
            ) from error
        available = sorted(entry["id"] for entry in response.json()["data"])
        if model not in available:
            raise RuntimeError(
                f"LM Studio has no model {model!r}. Available: {', '.join(available)}"
            )
        # LM Studio loads a model on its first request, and requests arriving during the load
        # fail, so load it with a single tiny request before any concurrent work.
        response = await client.post(
            "/chat/completions",
            json={"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
        )
        if response.is_error:
            raise RuntimeError(f"LM Studio could not load {model!r}: {response.text}")
        yield LMStudio(client, model)


@asynccontextmanager
async def _anthropic(model: str) -> AsyncIterator[Anthropic]:
    async with anthropic.AsyncAnthropic(max_retries=ANTHROPIC_RETRIES) as client:
        try:
            await client.models.retrieve(model)
        # The SDK raises TypeError when it finds no credentials at all.
        except (anthropic.AuthenticationError, TypeError) as error:
            raise RuntimeError(
                "Anthropic API credentials are missing or invalid; set ANTHROPIC_API_KEY"
            ) from error
        except anthropic.NotFoundError as error:
            raise RuntimeError(f"Anthropic has no model {model!r}") from error
        yield Anthropic(client, model)


def concurrency(config: Config, model_ref: str) -> int:
    """Maximum simultaneous requests for a model's provider.

    Args:
        config: Loaded configuration
        model_ref: Model reference such as "anthropic:claude-haiku-5-5"

    Returns:
        The configured concurrency
    """
    provider, _ = model_ref.split(":", 1)
    section = config.anthropic if provider == "anthropic" else config.lmstudio
    if section is None:
        raise RuntimeError(f"hackerjobs.toml has no [{provider}] section for {model_ref!r}")
    return section.concurrency


@asynccontextmanager
async def open_provider(config: Config, model_ref: str) -> AsyncIterator[Provider]:
    """Connect to the provider of a model and check that the model is available.

    Args:
        config: Loaded configuration
        model_ref: "lmstudio:<model id>" or "anthropic:<model id>"

    Yields:
        A ready provider

    Raises:
        RuntimeError: If the provider is not configured, unreachable or lacks the model
    """
    provider, model = model_ref.split(":", 1)
    opener = _anthropic(model) if provider == "anthropic" else _lmstudio(config, model)
    async with opener as connected:
        yield connected


async def run_jobs[J, R](
    jobs: Sequence[J],
    work: Callable[[J], Awaitable[R]],
    save: Callable[[J, R], None],
    concurrency: int,
    label: str,
) -> int:
    """Run model jobs concurrently, saving each result as soon as it completes.

    Failed jobs are logged and skipped, so a later run retries them.

    Args:
        jobs: Inputs to process
        work: Coroutine function producing a result for one job
        save: Stores a job's result
        concurrency: Maximum number of jobs in flight
        label: Name used in progress logs

    Returns:
        Number of failed jobs
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def run(job: J) -> tuple[J, R | None]:
        async with semaphore:
            try:
                return job, await work(job)
            except (httpx.HTTPError, anthropic.APIError, ValidationError, ExtractionError) as error:
                logging.warning("%s: %r failed: %r", label, job, error)
                return job, None

    failures = 0
    for done, future in enumerate(asyncio.as_completed([run(job) for job in jobs]), 1):
        job, result = await future
        if result is None:
            failures += 1
        else:
            save(job, result)
        if done % PROGRESS_EVERY == 0 or done == len(jobs):
            logging.info("%s: %d/%d done, %d failed", label, done, len(jobs), failures)
    return failures
