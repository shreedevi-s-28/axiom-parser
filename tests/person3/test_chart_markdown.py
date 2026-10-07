import sys

sys.path.insert(
    0,
    "backend/app/extractors"
)

from chart2data import chart_to_markdown_table


def test_chart_to_markdown_table():
    chart_data = {
        "chart_type": "bar",
        "title": "Revenue",
        "x_label": "Quarter",
        "y_label": "USD",
        "series": [
            {
                "name": "Revenue",
                "data": [
                    {"x": "Q1", "y": 100},
                    {"x": "Q2", "y": 120},
                    {"x": "Q3", "y": 140},
                ],
            }
        ],
    }

    result = chart_to_markdown_table(chart_data)

    assert "### Revenue" in result
    assert "| Quarter | Revenue |" in result
    assert "| Q1 | 100 |" in result
    assert "| Q2 | 120 |" in result
    assert "| Q3 | 140 |" in result


def test_empty_chart():
    chart_data = {
        "title": "Empty",
        "series": [],
    }

    result = chart_to_markdown_table(chart_data)

    assert result == "*(Empty chart)*"
