import dataclasses

from conftest import make_posting

from hackerjobs.models import EMPTY_POSTINGS, Kind, Money, Pay, Role
from hackerjobs.normalize import normalize

TEXT = (
    "Acme | Engineer | Boston | $100k-150k | jobs@acme.example\n"
    "Acme builds rockets for small satellites. Benefits: unlimited PTO, 401K match.\n"
    "We raised $12.5M in our Series A at a $1.2B valuation."
)


def test_hiring_fields_are_cleaned() -> None:
    posting = dataclasses.replace(
        make_posting(),
        locations=("Boston, Massachusetts, USA", "Remote (US)", "Remote"),
        roles=(
            Role("Engineer", Pay(100, 150, "$", "year"), ("Remote (US)",), None),
            Role(".*", None, (), None),
        ),
        technologies=("postgres", "LLMs", "C/C++", "Python"),
        pay=Pay(150000, 100000, "$", "year"),
        applications_closed=False,
    )
    cleaned = normalize(TEXT, posting)
    assert cleaned.locations == ("Boston, MA", "US")
    assert cleaned.roles == (Role("Engineer", Pay(100, 150, "USD", "year"), ("US",), None),)
    assert cleaned.technologies == ("PostgreSQL", "C", "C++", "Python")
    assert cleaned.pay == Pay(100000, 150000, "USD", "year")
    assert cleaned.applications_closed is None


def test_only_copied_text_is_kept() -> None:
    posting = dataclasses.replace(
        make_posting("Globex"),
        company_description="Acme builds rockets for small satellites.",
        company_stage="seed",
        funding=Money(12_500_000, "$"),
        valuation=Money(3_000_000_000, "USD"),
        benefits=("unlimited PTO.", "free lunch", "401K match", "- Unlimited PTO"),
        contact="hr@acme.example",
        pay=Pay(90000, None, "USD", "year"),
    )
    cleaned = normalize(TEXT, posting)
    assert cleaned.company is None
    assert cleaned.company_description == "Acme builds rockets for small satellites."
    assert cleaned.company_stage is None
    assert cleaned.funding == Money(12_500_000, "USD")
    assert cleaned.valuation is None
    assert cleaned.benefits == ("Unlimited PTO", "401K match")
    assert (
        normalize(TEXT, dataclasses.replace(posting, company_stage="series-a")).company_stage
        == "series-a"
    )
    assert cleaned.contact is None
    assert cleaned.pay is None


def test_candidate_fields() -> None:
    text = (
        "Location: Lille\nEmail: jo@example.com\nGitHub: https://github.com/jo\n"
        "5 years of experience"
    )
    posting = dataclasses.replace(
        EMPTY_POSTINGS[Kind.SEEKING],
        roles=("Backend Engineer", "I want something interesting and well paid at a large company"),
        contact="jo@example.com",
        github="https://github.com/jo",
        linkedin="https://linkedin.com/in/made-up",
        experience_years=500,
    )
    cleaned = normalize(text, posting)
    assert cleaned.roles == ("Backend Engineer",)
    assert cleaned.contact == "jo@example.com"
    assert cleaned.github == "https://github.com/jo"
    assert cleaned.linkedin is None
    assert cleaned.experience_years is None


def test_links_must_be_urls_in_the_post() -> None:
    text = (
        "Email: taylor@taylorgood.com | GitHub: MaxHass12 | LinkedIn: linkedin.com/in/jo\n"
        "Résumé: available upon request. I'm Jo Smith."
    )
    posting = dataclasses.replace(
        EMPTY_POSTINGS[Kind.SEEKING],
        github="MaxHass12",
        linkedin="linkedin.com/in/jo",
        resume_url="available upon request",
    )
    cleaned = normalize(text, posting)
    assert cleaned.github is None
    assert cleaned.linkedin == "linkedin.com/in/jo"
    assert cleaned.resume_url is None


def test_candidate_interests_are_tidied_phrases() -> None:
    posting = dataclasses.replace(
        EMPTY_POSTINGS[Kind.SEEKING],
        interests=("game development", "Developer tools.", "game Development"),
    )
    assert normalize("I want to work in the games industry", posting).interests == (
        "Game development",
        "Developer tools",
    )


def test_generic_company_names_are_no_name() -> None:
    posting = dataclasses.replace(make_posting("Confidential"))
    assert normalize("Confidential | Senior Engineer | Khobar", posting).company is None
