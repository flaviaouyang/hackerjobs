from pathlib import Path

import pytest

from hackerjobs.config import ReviewConfig, load_config

CONFIG = """
since = "2026-01"
[anthropic]
concurrency = 8
[parse]
models = ["anthropic:claude-haiku-5-5", "lmstudio:google/gemma-4-e4b"]
[publish]
model = "anthropic:claude-haiku-5-5"
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "hackerjobs.toml"
    path.write_text(text)
    return path


def test_load_config_without_optional_sections(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, CONFIG))
    assert config.parse.models == ("anthropic:claude-haiku-5-5", "lmstudio:google/gemma-4-e4b")
    assert config.anthropic is not None
    assert config.lmstudio is None
    assert config.review is None


def test_load_config_with_review(tmp_path: Path) -> None:
    text = CONFIG + '[review]\nreviewer = "anthropic:a"\nof = "lmstudio:b"\n'
    assert load_config(write(tmp_path, text)).review == ReviewConfig("anthropic:a", "lmstudio:b")


@pytest.mark.parametrize(
    "bad", [CONFIG.replace("2026-01", "2026-13"), CONFIG.replace("anthropic:claude", "openai:gpt")]
)
def test_load_config_rejects_invalid_values(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError, match="Invalid config"):
        load_config(write(tmp_path, bad))


def test_load_config_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        load_config(tmp_path / "missing.toml")


def test_repository_config_is_valid() -> None:
    load_config(Path(__file__).parents[1] / "hackerjobs.toml")
