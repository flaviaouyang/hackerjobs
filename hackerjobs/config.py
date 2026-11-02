import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import Field, PositiveInt, TypeAdapter, ValidationError

Month = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
# "<provider>:<model id>", e.g. "anthropic:claude-haiku-5-5" or "lmstudio:google/gemma-4-e4b".
ModelRef = Annotated[str, Field(pattern=r"^(lmstudio|anthropic):.+$")]


@dataclass(frozen=True, slots=True)
class LMStudioConfig:
    """LM Studio server settings.

    Attributes:
        url: Base URL of the OpenAI-compatible API, e.g. http://localhost:1234/v1
        concurrency: Maximum number of simultaneous requests
    """

    url: str
    concurrency: PositiveInt


@dataclass(frozen=True, slots=True)
class AnthropicConfig:
    """Anthropic API settings; the API key comes from ANTHROPIC_API_KEY.

    Attributes:
        concurrency: Maximum number of simultaneous requests
    """

    concurrency: PositiveInt


@dataclass(frozen=True, slots=True)
class ParseConfig:
    """Models that extract fields from posts."""

    models: tuple[ModelRef, ...]


@dataclass(frozen=True, slots=True)
class ReviewConfig:
    """A reviewer model and the model whose extractions it checks."""

    reviewer: ModelRef
    of: ModelRef


@dataclass(frozen=True, slots=True)
class PublishConfig:
    """Model whose extractions, with review corrections, are published."""

    model: ModelRef


@dataclass(frozen=True, slots=True)
class Config:
    """Settings loaded from hackerjobs.toml.

    Attributes:
        since: First month to ingest, formatted YYYY-MM
        parse: Models that extract fields
        publish: Model whose results are exported
        lmstudio: LM Studio settings, required for "lmstudio:" models
        anthropic: Anthropic settings, required for "anthropic:" models
        review: Optional reviewer setup; reviews are skipped when absent
    """

    since: Month
    parse: ParseConfig
    publish: PublishConfig
    lmstudio: LMStudioConfig | None = None
    anthropic: AnthropicConfig | None = None
    review: ReviewConfig | None = None


CONFIG_ADAPTER = TypeAdapter(Config)


def load_config(path: Path) -> Config:
    """Load and validate the configuration file.

    Args:
        path: TOML configuration file

    Returns:
        The validated configuration

    Raises:
        ValueError: If the file is missing, is not valid TOML or does not match the schema
    """
    try:
        with path.open("rb") as file:
            return CONFIG_ADAPTER.validate_python(tomllib.load(file))
    except FileNotFoundError as error:
        raise ValueError(f"Config file {path} not found") from error
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        raise ValueError(f"Invalid config file {path}: {error}") from error
