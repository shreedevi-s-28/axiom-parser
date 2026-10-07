import sys

sys.path.insert(
    0,
    "backend/app/extractors"
)

from chart2data import (
    get_fallback_chart_data,
    validate_chart_data,
    parse_chart_region,
)


def test_fallback_chart_data_is_valid():
    data = get_fallback_chart_data()

    assert validate_chart_data(data)
    assert data["chart_type"] == "bar"
    assert len(data["series"]) == 1


def test_fallback_chart_has_four_quarters():
    data = get_fallback_chart_data()

    points = data["series"][0]["data"]

    assert len(points) == 4
    assert points[0]["x"] == "Q1"
    assert points[-1]["x"] == "Q4"


def test_parse_without_api_key_uses_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    data = parse_chart_region(b"fake image data")

    assert validate_chart_data(data)
    assert data["title"] == "Quarterly EBITDA ($M)"
