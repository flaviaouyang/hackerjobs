import dataclasses

from conftest import make_posting

from hackerjobs.merge import FIELDS, in_right_thread, merge
from hackerjobs.models import EMPTY_POSTINGS, Kind

TEXT = (
    "Globex | Engineer | REMOTE (US) | Full-time\n\n"
    "Stack: Kubernetes, Postgres. Email jobs@globex.example"
)
HIRING_FIELDS = FIELDS[Kind.HIRING]


def test_unparsed_post_gets_rule_fields() -> None:
    merged = merge(Kind.HIRING, TEXT, None)
    assert merged.company == "Globex"
    assert merged.remote == "remote"
    assert merged.technologies == ("Kubernetes", "PostgreSQL")
    assert merged.contact == "jobs@globex.example"


def test_sources() -> None:
    llm = dataclasses.replace(
        EMPTY_POSTINGS[Kind.HIRING],
        company="Globex Corp",
        remote="onsite",
        technologies=("Python",),
    )
    rules_first = merge(Kind.HIRING, TEXT, llm, dict.fromkeys(HIRING_FIELDS, "rules_then_llm"))
    assert (rules_first.company, rules_first.remote) == ("Globex", "remote")

    llm_only = merge(Kind.HIRING, TEXT, llm, dict.fromkeys(HIRING_FIELDS, "llm"))
    assert (llm_only.remote, llm_only.contact) == ("onsite", None)

    union = merge(Kind.HIRING, TEXT, llm, dict.fromkeys(HIRING_FIELDS, "union"))
    assert union.technologies == ("Python", "Kubernetes", "PostgreSQL")
    assert union.remote == "onsite"


def test_unlisted_fields_come_from_the_model() -> None:
    llm = dataclasses.replace(make_posting(), visa_sponsorship=True, industries=("Fintech",))
    merged = merge(Kind.HIRING, TEXT, llm, {"visa_sponsorship": "rules"})
    assert merged.visa_sponsorship is None
    assert merged.industries == ("Fintech",)


def test_posts_in_the_wrong_thread() -> None:
    template = (
        "Location: Oslo\nRemote: Yes\nWilling to relocate: Yes\nTechnologies: Rust\nEmail: a@b.co"
    )
    job = make_posting()
    assert in_right_thread(Kind.HIRING, TEXT, job)
    assert not in_right_thread(Kind.HIRING, template, job)
    assert not in_right_thread(Kind.HIRING, TEXT, dataclasses.replace(job, post_type="other"))
    candidate = dataclasses.replace(EMPTY_POSTINGS[Kind.SEEKING], post_type="job_ad")
    assert not in_right_thread(Kind.SEEKING, template, candidate)
    # Unparsed posts have no type yet and stay unless the template gives them away.
    assert in_right_thread(Kind.SEEKING, template, EMPTY_POSTINGS[Kind.SEEKING])
