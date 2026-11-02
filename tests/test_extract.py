import asyncio
import dataclasses

from conftest import make_posting

from hackerjobs import extract
from hackerjobs.models import POSTING_ADAPTERS, Kind


@dataclasses.dataclass(frozen=True, slots=True)
class FakeProvider:
    """Answers with a fixed posting, cut down to the schema it is asked for."""

    posting: object

    async def complete(self, adapter, system: str, user: str) -> object:
        """Validate the posting's fields that the requested schema has."""
        data = POSTING_ADAPTERS[Kind.HIRING].dump_python(self.posting)
        return adapter.validate_python(
            {name: data[name] for name in adapter.json_schema()["properties"]}
        )


def test_model_is_not_asked_for_fields_published_from_rules() -> None:
    asked = extract.MODEL_ADAPTERS[Kind.HIRING].json_schema()["properties"]
    assert "role_categories" not in asked
    assert "applications_closed" not in asked
    assert "post_type" in asked
    assert "website" not in extract.MODEL_ADAPTERS[Kind.SEEKING].json_schema()["properties"]


def test_extract_leaves_fields_from_rules_empty() -> None:
    posting = dataclasses.replace(
        make_posting(), role_categories=("Design",), applications_closed=True
    )
    result = asyncio.run(extract.extract(FakeProvider(posting), Kind.HIRING, "text"))
    assert result == dataclasses.replace(posting, role_categories=(), applications_closed=None)
