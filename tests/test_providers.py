import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from conftest import CONFIG, make_posting

from hackerjobs import providers
from hackerjobs.models import POSTING_ADAPTERS, Kind

ADAPTER = POSTING_ADAPTERS[Kind.HIRING]


def lmstudio_handler(content: str, field: str = "content"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "m"}]})
        body = json.loads(request.content)
        if "response_format" in body:
            schema = body["response_format"]["json_schema"]["schema"]
            assert schema["additionalProperties"] is False
        message = {"content": "", field: content}
        return httpx.Response(200, json={"choices": [{"message": message}]})

    return handler


async def complete_once(model_ref: str = "lmstudio:m") -> object:
    async with providers.open_provider(CONFIG, model_ref) as provider:
        return await provider.complete(ADAPTER, "system", "user")


def test_lmstudio_returns_validated_output(mock_http) -> None:
    mock_http(lmstudio_handler(ADAPTER.dump_json(make_posting()).decode()))
    assert asyncio.run(complete_once()) == make_posting()


def test_lmstudio_reads_answers_filed_as_reasoning(mock_http) -> None:
    answer = ADAPTER.dump_json(make_posting()).decode()
    mock_http(lmstudio_handler(answer, field="reasoning_content"))
    assert asyncio.run(complete_once()) == make_posting()


def test_lmstudio_rejects_unknown_model(mock_http) -> None:
    mock_http(lmstudio_handler(""))
    with pytest.raises(RuntimeError, match=r"no model 'missing'\. Available: m"):
        asyncio.run(complete_once("lmstudio:missing"))


def test_lmstudio_reports_load_failure(mock_http) -> None:
    def fail_load(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "m"}]})
        return httpx.Response(500, text="out of memory")

    mock_http(fail_load)
    with pytest.raises(RuntimeError, match="could not load 'm': out of memory"):
        asyncio.run(complete_once())


def test_lmstudio_reports_unreachable_server(mock_http) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    mock_http(refuse)
    with pytest.raises(RuntimeError, match="lms server start"):
        asyncio.run(complete_once())


class FakeMessages:
    """Stands in for AsyncAnthropic().messages, recording the request."""

    def __init__(self, stop_reason: str, text: str) -> None:
        self.stop_reason, self.text, self.request = stop_reason, text, {}

    async def create(self, **request: object) -> SimpleNamespace:
        self.request = request
        blocks = [SimpleNamespace(type="text", text=self.text)]
        return SimpleNamespace(stop_reason=self.stop_reason, content=blocks)


def test_anthropic_requests_structured_output_without_thinking() -> None:
    messages = FakeMessages("end_turn", ADAPTER.dump_json(make_posting()).decode())
    provider = providers.Anthropic(SimpleNamespace(messages=messages), "claude-haiku-5-5")
    assert asyncio.run(provider.complete(ADAPTER, "system", "user")) == make_posting()
    assert messages.request["thinking"] == {"type": "disabled"}
    assert messages.request["output_config"]["format"]["type"] == "json_schema"
    assert "temperature" not in messages.request


def test_anthropic_sends_optional_text_as_plain_strings() -> None:
    data = ADAPTER.dump_python(make_posting(), mode="json") | {"company_description": ""}
    data["roles"] = [{"title": "", "pay": None, "locations": [], "apply_url": ""}]
    messages = FakeMessages("end_turn", json.dumps(data))
    provider = providers.Anthropic(SimpleNamespace(messages=messages), "m")
    result = asyncio.run(provider.complete(ADAPTER, "system", "user"))
    assert result.company_description is None
    # A role's title is required, so "" stays "" (clean-up drops the role); its link is optional.
    assert (result.roles[0].title, result.roles[0].apply_url) == ("", None)
    assert result.contact == "jobs@acme.example"
    properties = messages.request["output_config"]["format"]["schema"]["properties"]
    assert properties["company_description"]["type"] == "string"
    assert "anyOf" in properties["remote"]  # nullable enums keep their union
    assert "empty string" in messages.request["system"]


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_anthropic_rejects_unusable_responses(stop_reason: str) -> None:
    provider = providers.Anthropic(SimpleNamespace(messages=FakeMessages(stop_reason, "{")), "m")
    with pytest.raises(providers.ExtractionError, match=stop_reason):
        asyncio.run(provider.complete(ADAPTER, "system", "user"))


def test_concurrency_per_provider() -> None:
    assert providers.concurrency(CONFIG, "lmstudio:m") == 2
    assert providers.concurrency(CONFIG, "anthropic:claude-haiku-5-5") == 4


def test_run_jobs_saves_successes_and_counts_failures() -> None:
    saved: dict[int, int] = {}

    async def work(job: int) -> int:
        if job == 2:
            raise httpx.ReadTimeout("slow")
        return job * 10

    failures = asyncio.run(providers.run_jobs([1, 2, 3], work, saved.__setitem__, 2, "test"))
    assert failures == 1
    assert saved == {1: 10, 3: 30}


def test_prompt_version_changes_with_prompt() -> None:
    assert providers.prompt_version([ADAPTER], "a") != providers.prompt_version([ADAPTER], "b")
