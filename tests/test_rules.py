import pytest

from hackerjobs.models import Kind, Pay
from hackerjobs.rules import deobfuscate, extract_rules, looks_like_seeker, role_category, seniority


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mail jo [at] acme [dot] com now", "mail jo@acme.com now"),
        ("kev ( at ) yuzu ( dot ) health", "kev@yuzu.health"),
        ("9u[dot]harsh [at] gmail[dot]com", "9u.harsh@gmail.com"),
        ("lordfoom<at/>gmail<dot/>com", "lordfoom@gmail.com"),
        (
            "email me at julian.berman at quantumrise.com",
            "email me at julian.berman@quantumrise.com",
        ),
        ("contact at ddahon dot com", "contact@ddahon.com"),
        ("tg @ taylorgood.com", "tg@taylorgood.com"),
        ("we meet at the office at 5", "we meet at the office at 5"),
    ],
)
def test_deobfuscate(text: str, expected: str) -> None:
    assert deobfuscate(text) == expected


@pytest.mark.parametrize(
    ("title", "level"),
    [
        ("Senior Android Developer", "senior"),
        ("Staff Software Engineer", "staff"),
        ("Engineering Manager", "manager"),
        ("Lead Product Engineer", "lead"),
        ("Programming Intern", "intern"),
        ("Head of Data", "director"),
        ("Backend Engineer", None),
    ],
)
def test_seniority(title: str, level: str | None) -> None:
    assert seniority(title) == level


def test_seeker_template() -> None:
    text = (
        "Location: Limerick, Ireland (UTC)\nRemote: Yes\nWilling to relocate: No\n"
        "Technologies: Postgres, C/C++, Legal, Kubernetes\nRésumé/CV: https://cv.example/me.pdf\n"
        "LinkedIn: https://www.linkedin.com/in/jo/\nGitHub: https://github.com/jo\n"
        "Email: jo [at] example [dot] com\n\nEngineer with 7+ years of experience."
    )
    assert extract_rules(Kind.SEEKING, text) == {
        "locations": ("Limerick, Ireland",),
        "timezone": "UTC",
        "remote": "remote",
        "willing_to_relocate": False,
        "technologies": ("PostgreSQL", "C", "C++", "Kubernetes"),
        "experience_years": 7,
        "contact": "jo@example.com",
        "linkedin": "https://www.linkedin.com/in/jo",
        "github": "https://github.com/jo",
        "resume_url": "https://cv.example/me.pdf",
    }


def test_seeker_template_on_one_line() -> None:
    fields = extract_rules(Kind.SEEKING, "Location: Nepal | Remote: Yes\nwilling to relocate: Yes")
    assert fields["locations"] == ("Nepal",)
    assert fields["remote"] == "remote"
    assert fields["willing_to_relocate"] is True


def test_hiring_header() -> None:
    text = (
        "Bookarang | DevOps developer | Amsterdam | € 55-72k | Fulltime, Onsite | bookarang.com\n\n"
        "We use Docker and MongoDB. No visa sponsorship. Minimum of 3 years of experience.\n"
        "Equity and relocation support.\nApply: https://acme.example/careers/1"
    )
    assert extract_rules(Kind.HIRING, text) == {
        "company": "Bookarang",
        "company_website": "bookarang.com",
        "remote": "onsite",
        "employment_types": ("full-time",),
        "pay": Pay(55000, 72000, "EUR", "year"),
        "min_experience_years": 3,
        "equity": True,
        "relocation_support": True,
        "visa_sponsorship": False,
        "technologies": ("Docker", "MongoDB"),
        "contact": "https://acme.example/careers/1",
    }


def test_hiring_header_variants() -> None:
    header = "Post Up | Senior Engineer | ONSITE (2 days/week) | $120-$130k CAD"
    fields = extract_rules(Kind.HIRING, header)
    assert fields["remote"] == "hybrid"
    assert fields["pay"] == Pay(120000, 130000, "CAD", "year")


def test_hiring_role_first_header_has_no_company_and_hourly_pay_on_next_line() -> None:
    text = (
        "Senior Python Engineer | REMOTE (EMEA)\n\nSalary on a B2B contract:\n- 45-70 USD per hour"
    )
    fields = extract_rules(Kind.HIRING, text)
    assert "company" not in fields
    assert fields["pay"] == Pay(45, 70, "USD", "hour")


def test_hiring_closed_and_visa_offered() -> None:
    text = (
        "Edit: APPLICATIONS CLOSED\nAcme | NYC | https://jobs.lever.co/acme\nWill sponsor any visa"
    )
    fields = extract_rules(Kind.HIRING, text)
    assert fields["applications_closed"] is True
    assert fields["visa_sponsorship"] is True
    assert "company_website" not in fields


def test_combined_experience_is_not_a_requirement() -> None:
    text = "Acme | Remote\nFounded by a team with 20+ years of combined experience."
    assert "min_experience_years" not in extract_rules(Kind.HIRING, text)


@pytest.mark.parametrize(
    ("text", "stage"),
    [
        ("Acme | Remote\nWe raised our pre-seed round.", "pre-seed"),
        ("Acme | Remote\nWe just closed our Series-C led by IVP.", "series-c"),
        ("Bookarang (part of NBD Biblion) | Amsterdam", "subsidiary"),
        ("Acme | Remote\nA publicly traded fintech company.", "public"),
        ("Acme | Remote\nYou will be part of our team.", None),
        ("Acme | Remote\nWe went from seed to Series B in a year.", None),
    ],
)
def test_company_stage_needs_one_clear_stage(text: str, stage: str | None) -> None:
    assert extract_rules(Kind.HIRING, text).get("company_stage") == stage


def test_sentence_header_is_not_a_company_name() -> None:
    text = "Backed by Sequoia Capital, Peregrine is the operational AI platform | In-office 4 days"
    assert "company" not in extract_rules(Kind.HIRING, text)


@pytest.mark.parametrize(
    ("title", "category"),
    [
        ("Senior Backend Engineer", "Engineering"),
        ("Product Engineer", "Engineering"),
        ("Data Engineer", "Data & ML"),
        ("Machine Learning Engineer", "Data & ML"),
        ("Product Designer", "Design"),
        ("Technical Program Manager II", "Product"),
        ("Account Executive", "Sales & marketing"),
        ("Technical Recruiter", "People & finance"),
        ("Customer Support Specialist", "Operations & support"),
        ("Founder's Office", None),
    ],
)
def test_role_category(title: str, category: str | None) -> None:
    assert role_category(title) == category


def test_candidate_template_is_recognised() -> None:
    text = (
        "Location: Oslo\nRemote: Yes\nWilling to relocate: Yes\nTechnologies: Rust\nEmail: a@b.co"
    )
    assert looks_like_seeker(text)
    assert not looks_like_seeker("Acme | Engineer | Oslo\nLocation: Oslo\nRemote: yes")
