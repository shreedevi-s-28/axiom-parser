import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
)
from reportlab.graphics.shapes import Drawing, Rect, String


ASSET_DIR = "demo_assets"

os.makedirs(ASSET_DIR, exist_ok=True)

styles = getSampleStyleSheet()


def make_bar_chart(title, values, labels):
    drawing = Drawing(450, 220)

    drawing.add(
        String(
            150,
            200,
            title,
            fontSize=14,
        )
    )

    max_value = max(values)

    for i, value in enumerate(values):
        x = 40 + i * 90
        height = (value / max_value) * 130

        drawing.add(
            Rect(
                x,
                40,
                45,
                height,
                fillColor=colors.blue,
                strokeColor=colors.black,
            )
        )

        drawing.add(
            String(
                x + 10,
                25,
                labels[i],
                fontSize=9,
            )
        )

        drawing.add(
            String(
                x + 8,
                45 + height,
                str(value),
                fontSize=8,
            )
        )

    return drawing


def make_line_chart(title, values, labels):
    drawing = Drawing(450, 220)

    drawing.add(
        String(
            150,
            200,
            title,
            fontSize=14,
        )
    )

    max_value = max(values)

    previous_x = None
    previous_y = None

    for i, value in enumerate(values):
        x = 50 + i * 80
        y = 50 + (value / max_value) * 120

        drawing.add(
            Rect(
                x - 3,
                y - 3,
                6,
                6,
                fillColor=colors.red,
            )
        )

        drawing.add(
            String(
                x - 8,
                30,
                labels[i],
                fontSize=9,
            )
        )

        if previous_x is not None:
            from reportlab.graphics.shapes import Line

            drawing.add(
                Line(
                    previous_x,
                    previous_y,
                    x,
                    y,
                    strokeColor=colors.black,
                    strokeWidth=2,
                )
            )

        previous_x = x
        previous_y = y

    return drawing


# ---------------------------------------------------------
# 1. merger_filing_q3.pdf
# ---------------------------------------------------------

doc = SimpleDocTemplate(
    f"{ASSET_DIR}/merger_filing_q3.pdf",
    pagesize=letter,
)

story = []

story.append(
    Paragraph(
        "<b>Q3 Merger Filing & Debt Analysis</b>",
        styles["Title"],
    )
)

story.append(Spacer(1, 20))

story.append(
    Paragraph(
        "<b>Section 1: Narrative Overview</b>",
        styles["Heading2"],
    )
)

story.append(
    Paragraph(
        "Company A has agreed to acquire Company B. "
        "Senior credit facilities are detailed below across "
        "multiple pages.",
        styles["Normal"],
    )
)

story.append(Spacer(1, 20))

story.append(
    Paragraph(
        "<b>Debt Maturity Schedule - Part 1</b>",
        styles["Heading3"],
    )
)

story.append(
    Paragraph(
        "Facility A: $150M | Interest: 5.5% | Due: 2027<br/>"
        "Facility B: $300M | Interest: 6.2% | Due: 2029",
        styles["Normal"],
    )
)

story.append(PageBreak())

story.append(
    Paragraph(
        "<b>Debt Maturity Schedule - Part 2</b>",
        styles["Heading3"],
    )
)

story.append(
    Paragraph(
        "Facility C: $450M | Interest: 7.0% | Due: 2031<br/>"
        "Facility D: $200M | Interest: 8.1% | Due: 2033",
        styles["Normal"],
    )
)

story.append(Spacer(1, 30))

story.append(
    make_bar_chart(
        "Quarterly EBITDA ($M)",
        [12.4, 15.1, 18.2, 21.0],
        ["Q1", "Q2", "Q3", "Q4"],
    )
)

doc.build(story)


# ---------------------------------------------------------
# 2. options_pricing.pdf
# ---------------------------------------------------------

doc = SimpleDocTemplate(
    f"{ASSET_DIR}/options_pricing.pdf",
    pagesize=letter,
)

story = [
    Paragraph(
        "<b>Quantitative Valuation Model</b>",
        styles["Title"],
    ),
    Spacer(1, 20),
    Paragraph(
        "The standard Black-Scholes formula for European "
        "options is defined as:",
        styles["Normal"],
    ),
    Spacer(1, 15),
    Paragraph(
        "<b>d1 = (ln(S / K) + (r + σ² / 2)t) / (σ√t)</b>",
        styles["Normal"],
    ),
    Spacer(1, 15),
    Paragraph(
        "Where S is spot price, K is strike price, "
        "r is the risk-free rate, and σ is volatility.",
        styles["Normal"],
    ),
]

doc.build(story)


# ---------------------------------------------------------
# 3. smudged_contract.pdf
# ---------------------------------------------------------

doc = SimpleDocTemplate(
    f"{ASSET_DIR}/smudged_contract.pdf",
    pagesize=letter,
)

story = [
    Paragraph(
        "<b>Commercial Supply Agreement</b>",
        styles["Title"],
    ),
    Spacer(1, 20),
    Paragraph(
        "1. Term: This agreement shall remain in effect "
        "for 36 months.",
        styles["Normal"],
    ),
    Spacer(1, 80),
    Paragraph(
        "2. Payment Terms: Payment shall be made within "
        "thirty days of invoice receipt.",
        styles["Normal"],
    ),
    Spacer(1, 80),
    Paragraph(
        '<font color="gray">'
        "3. Confidentiality: All commercial information "
        "shall remain confidential."
        "</font>",
        styles["Normal"],
    ),
    Spacer(1, 80),
    Paragraph(
        '<font color="gray">'
        "SMUDGED / LOW-CONTRAST VERIFICATION AREA"
        "</font>",
        styles["Normal"],
    ),
]

doc.build(story)


# ---------------------------------------------------------
# 4. corrupt_sample.pdf
# ---------------------------------------------------------

with open(
    f"{ASSET_DIR}/corrupt_sample.pdf",
    "wb",
) as file:
    file.write(
        b"NOT_A_VALID_PDF_HEADER_CORRUPTED_DATA_123456789"
    )


# ---------------------------------------------------------
# 5. chart_heavy_report.pdf
# ---------------------------------------------------------

doc = SimpleDocTemplate(
    f"{ASSET_DIR}/chart_heavy_report.pdf",
    pagesize=letter,
)

story = [
    Paragraph(
        "<b>Financial Performance Dashboard</b>",
        styles["Title"],
    ),
    Spacer(1, 15),
    Paragraph(
        "Revenue Growth",
        styles["Heading2"],
    ),
    make_bar_chart(
        "Revenue ($M)",
        [100, 125, 140, 175],
        ["2023", "2024", "2025", "2026"],
    ),
    Spacer(1, 20),
    Paragraph(
        "Operating Margin",
        styles["Heading2"],
    ),
    make_line_chart(
        "Operating Margin (%)",
        [12, 15, 18, 21],
        ["Q1", "Q2", "Q3", "Q4"],
    ),
    PageBreak(),
    Paragraph(
        "<b>Additional Metrics</b>",
        styles["Heading2"],
    ),
    make_bar_chart(
        "Free Cash Flow ($M)",
        [40, 55, 62, 78],
        ["Q1", "Q2", "Q3", "Q4"],
    ),
]

doc.build(story)


# ---------------------------------------------------------
# 6. multi_series_chart.pdf
# ---------------------------------------------------------

doc = SimpleDocTemplate(
    f"{ASSET_DIR}/multi_series_chart.pdf",
    pagesize=letter,
)

table = Table(
    [
        ["Quarter", "Revenue", "EBITDA"],
        ["Q1", "120", "30"],
        ["Q2", "145", "38"],
        ["Q3", "160", "44"],
        ["Q4", "185", "52"],
    ]
)

table.setStyle(
    TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ]
    )
)

story = [
    Paragraph(
        "<b>Multi-Series Financial Data</b>",
        styles["Title"],
    ),
    Spacer(1, 20),
    table,
    Spacer(1, 30),
    make_line_chart(
        "Revenue Trend",
        [120, 145, 160, 185],
        ["Q1", "Q2", "Q3", "Q4"],
    ),
]

doc.build(story)


# ---------------------------------------------------------
# 7. math_symbols.pdf
# ---------------------------------------------------------

doc = SimpleDocTemplate(
    f"{ASSET_DIR}/math_symbols.pdf",
    pagesize=letter,
)

story = [
    Paragraph(
        "<b>Mathematical Symbols Stress Test</b>",
        styles["Title"],
    ),
    Spacer(1, 20),
    Paragraph(
        "σ ≤ 10",
        styles["Normal"],
    ),
    Spacer(1, 15),
    Paragraph(
        "x² + y² = z²",
        styles["Normal"],
    ),
    Spacer(1, 15),
    Paragraph(
        "∑ xᵢ = nμ",
        styles["Normal"],
    ),
    Spacer(1, 15),
    Paragraph(
        "∫ f(x) dx",
        styles["Normal"],
    ),
    Spacer(1, 15),
    Paragraph(
        "√(x² + y²)",
        styles["Normal"],
    ),
    Spacer(1, 15),
    Paragraph(
        "α + β ≠ γ",
        styles["Normal"],
    ),
]

doc.build(story)


# ---------------------------------------------------------
# 8. mixed_financial_report.pdf
# ---------------------------------------------------------

doc = SimpleDocTemplate(
    f"{ASSET_DIR}/mixed_financial_report.pdf",
    pagesize=letter,
)

table = Table(
    [
        ["Metric", "2025", "2026"],
        ["Revenue", "$500M", "$620M"],
        ["EBITDA", "$120M", "$155M"],
        ["Margin", "24%", "25%"],
    ]
)

table.setStyle(
    TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ]
    )
)

story = [
    Paragraph(
        "<b>Mixed Financial Analysis</b>",
        styles["Title"],
    ),
    Spacer(1, 15),
    Paragraph(
        "The company reported strong financial performance "
        "during the fiscal year.",
        styles["Normal"],
    ),
    Spacer(1, 15),
    table,
    Spacer(1, 25),
    Paragraph(
        "<b>Valuation Formula:</b> "
        "EV = Equity Value + Debt - Cash",
        styles["Normal"],
    ),
    Spacer(1, 20),
    make_bar_chart(
        "EBITDA ($M)",
        [100, 120, 135, 155],
        ["2023", "2024", "2025", "2026"],
    ),
]

doc.build(story)


# ---------------------------------------------------------
# 9. edge_case_document.pdf
# ---------------------------------------------------------

doc = SimpleDocTemplate(
    f"{ASSET_DIR}/edge_case_document.pdf",
    pagesize=letter,
)

story = [
    Paragraph(
        "<b>Edge Case Document</b>",
        styles["Title"],
    ),
    Spacer(1, 20),
    Paragraph(
        "Short text.",
        styles["Normal"],
    ),
    Spacer(1, 300),
    Paragraph(
        "End of document.",
        styles["Normal"],
    ),
    PageBreak(),
    Paragraph(
        "Second page with unusual spacing.",
        styles["Normal"],
    ),
]

doc.build(story)


print("Successfully generated 9 golden test fixtures:")
for filename in sorted(os.listdir(ASSET_DIR)):
    print(f"  - {filename}")
