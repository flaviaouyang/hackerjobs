import pytest

from hackerjobs.technologies import canonical_technologies, find_technologies


def test_canonical_technologies() -> None:
    assert canonical_technologies("postgres") == ["PostgreSQL"]
    assert canonical_technologies("C/C++") == ["C", "C++"]
    assert canonical_technologies("shadcn/ui") == ["shadcn/ui"]
    assert canonical_technologies("LLMs") == []
    assert canonical_technologies("agent orchestration") == []
    assert canonical_technologies("8.x") == []
    assert canonical_technologies("maud") == ["maud"]


@pytest.mark.parametrize(
    ("name", "canonical"),
    [
        (".NET", ".NET"),
        (".NET 8", ".NET"),
        ("NET", ".NET"),
        ("ROS 2", "ROS"),
        ("ROS1", "ROS"),
        ("Qt5", "Qt"),
        ("Qt 6.9", "Qt"),
        ("Next.js 15", "Next.js"),
        ("YOLOv8", "YOLO"),
        ("OAuth 2.0", "OAuth"),
        ("Unreal Engine 5", "Unreal Engine"),
        ("S3", "S3"),
        ("R2", "R2"),
        ("V8", "V8"),
        ("ISO 27001", "ISO 27001"),
    ],
)
def test_versions_belong_to_the_named_technology(name: str, canonical: str) -> None:
    assert canonical_technologies(name) == [canonical]


def test_find_technologies_skips_common_words() -> None:
    text = (
        "Go to the next page. We use node.js, Postgres, C# and Rust; "
        "spring is here. Room for growth. Cast a wide net."
    )
    assert find_technologies(text) == ("Node.js", "PostgreSQL", "C#", "Rust")
