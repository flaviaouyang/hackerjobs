from hackerjobs.technologies import canonical_technologies, find_technologies


def test_canonical_technologies() -> None:
    assert canonical_technologies("postgres") == ["PostgreSQL"]
    assert canonical_technologies("C/C++") == ["C", "C++"]
    assert canonical_technologies("shadcn/ui") == ["shadcn/ui"]
    assert canonical_technologies("LLMs") == []
    assert canonical_technologies("agent orchestration") == []
    assert canonical_technologies("8.x") == []
    assert canonical_technologies("maud") == ["maud"]


def test_find_technologies_skips_common_words() -> None:
    text = (
        "Go to the next page. We use node.js, Postgres, C# and Rust; "
        "spring is here. Room for growth."
    )
    assert find_technologies(text) == ("Node.js", "PostgreSQL", "C#", "Rust")
