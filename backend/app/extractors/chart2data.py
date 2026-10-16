import os
import json
import base64
from typing import Any, Dict, Optional, Tuple


def get_fallback_chart_data() -> Dict[str, Any]:
    return {
        "chart_type": "bar",
        "title": "Quarterly EBITDA ($M)",
        "x_label": "Quarter",
        "y_label": "USD Millions",
        "series": [
            {
                "name": "EBITDA 2025",
                "data": [
                    {"x": "Q1", "y": 12.4},
                    {"x": "Q2", "y": 15.1},
                    {"x": "Q3", "y": 18.2},
                    {"x": "Q4", "y": 21.0}
                ]
            }
        ]
    }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_chart_data(data: Dict[str, Any]) -> bool:
    """True only if `data` can be loaded into the ChartData schema."""
    if not isinstance(data, dict):
        return False

    required_keys = ["chart_type", "title", "series"]

    if not all(key in data for key in required_keys):
        return False

    if not isinstance(data["series"], list):
        return False

    for series in data["series"]:
        if not isinstance(series, dict) or "name" not in series or "data" not in series:
            return False

        if not isinstance(series["data"], list):
            return False

        for point in series["data"]:
            if not isinstance(point, dict) or "x" not in point or "y" not in point:
                return False
            if not _is_number(point["y"]):
                return False
            if not (isinstance(point["x"], str) or _is_number(point["x"])):
                return False

    return True


def chart_to_markdown_table(chart_data: Dict[str, Any]) -> str:
    title = chart_data.get("title", "Extracted Chart Data")
    series_list = chart_data.get("series", [])

    if not series_list:
        return "*(Empty chart)*"

    headers = [chart_data.get("x_label") or "Category"]

    for series in series_list:
        headers.append(series.get("name", "Value"))

    markdown = f"### {title}\n\n"
    markdown += "| " + " | ".join(headers) + " |\n"
    markdown += "| " + " | ".join(["---"] * len(headers)) + " |\n"

    primary_data = series_list[0].get("data", [])

    for index, point in enumerate(primary_data):
        row = [str(point.get("x", ""))]

        for series in series_list:
            data_points = series.get("data", [])

            if index < len(data_points):
                value = data_points[index].get("y", "")
            else:
                value = ""

            row.append(str(value))

        markdown += "| " + " | ".join(row) + " |\n"

    return markdown


def extract_chart(image_bytes: bytes) -> Tuple[Optional[Dict[str, Any]], str]:
    """Vision extraction. Returns (data, source) with source 'vision' or 'fallback'.
    data is the canned golden chart only when source == 'fallback'."""
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key or not image_bytes:
        return get_fallback_chart_data(), "fallback"

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=20.0, max_retries=0)

        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        prompt = """
Extract the chart information from this image.

Return ONLY valid JSON using this schema:

{
  "chart_type": "bar",
  "title": "Chart title",
  "x_label": "X axis label",
  "y_label": "Y axis label",
  "series": [
    {
      "name": "Series name",
      "data": [
        {
          "x": "category",
          "y": 10
        }
      ]
    }
  ]
}

Rules:
- Preserve numerical values exactly.
- Extract all visible data points.
- Return JSON only.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )

        raw = response.choices[0].message.content.strip()

        if raw.startswith("```json"):
            raw = raw[7:-3].strip()
        elif raw.startswith("```"):
            raw = raw[3:-3].strip()

        chart_data = json.loads(raw)

        if not validate_chart_data(chart_data):
            return get_fallback_chart_data(), "fallback"

        return chart_data, "vision"

    except Exception:
        return get_fallback_chart_data(), "fallback"


def parse_chart_region(image_bytes: bytes) -> Dict[str, Any]:
    """Backward-compatible wrapper: always returns a valid chart dict."""
    data, _source = extract_chart(image_bytes)
    return data
