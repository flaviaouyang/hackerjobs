import pytest

from hackerjobs.fx import Rates, parse_rates


def test_parse_rates_keeps_only_latest_series() -> None:
    payload = {
        "observations": [
            {"d": "2019-12-31", "FXVNDCAD": {"v": "0.000056"}},
            {"d": "2026-10-30", "FXUSDCAD": {"v": "1.3960"}, "FXEURCAD": {"v": "1.5582"}},
        ]
    }
    assert parse_rates(payload) == Rates("2026-10-30", {"USD": 1.396, "EUR": 1.5582, "CAD": 1.0})


def test_parse_rates_rejects_empty_response() -> None:
    with pytest.raises(ValueError, match="no exchange rate"):
        parse_rates({"observations": []})
