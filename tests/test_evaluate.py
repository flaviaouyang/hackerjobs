import pytest
from conftest import make_posting

from hackerjobs.evaluate import RAW, BenchmarkPost, score, score_field
from hackerjobs.models import POSTING_ADAPTERS, Kind


@pytest.mark.parametrize(
    ("field", "predicted", "expected", "value"),
    [
        ("technologies", ["Python", "Rust"], ["python"], 2 / 3),
        ("technologies", [], [], 1.0),
        ("roles", [{"title": "Senior Backend Engineer"}], [{"title": "Backend Engineer"}], 1.0),
        ("roles", ["Designer"], ["Designer", "Builder"], 2 / 3),
        ("locations", ["NYC"], ["New York City"], 0.0),
        ("contact", "https://www.acme.example/jobs/", "acme.example/jobs", 1.0),
        ("contact", "b@acme.example", ["a@acme.example", "b@acme.example"], 1.0),
        ("visa_sponsorship", None, [False, None], 1.0),
        ("visa_sponsorship", False, None, 0.0),
        ("pay", {"min": 1, "max": 2, "currency": "USD", "period": "year"},
         {"min": 1, "max": 2, "currency": "USD", "period": "year"}, 1.0),
        ("pay", None, {"min": 1, "max": 2, "currency": "USD", "period": "year"}, 0.0),
        ("company_description", "Acme builds rockets.", "Acme builds rockets", 1.0),
        ("company_description", None, ["Acme builds rockets", None], 1.0),
        ("company_description", "We sell shoes.", "Acme builds rockets", 0.0),
    ],
)  # fmt: skip
def test_score_field(field: str, predicted: object, expected: object, value: float) -> None:
    assert score_field(field, predicted, expected) == pytest.approx(value)


def test_score_reports_mismatches() -> None:
    posting = make_posting()
    expected = POSTING_ADAPTERS[Kind.HIRING].dump_python(posting, mode="json") | {
        "company": "Acme Inc"
    }
    post = BenchmarkPost(1, Kind.HIRING, "Acme | Engineer | Berlin", expected)
    report = score([post], {1: posting})
    assert report.scores[RAW]["hiring.company"] == 0.0
    assert report.scores[RAW]["hiring.roles"] == 1.0
    assert any(mismatch.field == "company" for mismatch in report.mismatches)
