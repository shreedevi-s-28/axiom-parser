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


# ---- Regression tests ----

from chart2data import extract_chart


def _chart(y):
    return {"chart_type": "bar", "title": "t",
            "series": [{"name": "s", "data": [{"x": "Q1", "y": y}]}]}


def test_validation_rejects_values_the_schema_cannot_load():
    assert validate_chart_data(_chart(1.5))
    assert not validate_chart_data(_chart(None))     # used to pass, then crash ChartData(**...)
    assert not validate_chart_data(_chart("12"))
    assert not validate_chart_data(_chart(True))
    assert not validate_chart_data("not a dict")


def test_extract_chart_reports_fallback_provenance(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    data, source = extract_chart(b"anything")
    assert source == "fallback"
    assert validate_chart_data(data)
