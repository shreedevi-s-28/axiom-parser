import sys

sys.path.insert(
    0,
    "backend/app/extractors"
)

from math_parser import (
    is_math_block,
    text_to_latex,
    parse_math_region,
)


def test_detects_math_symbols():
    assert is_math_block("σ ≤ 10")


def test_detects_equation():
    assert is_math_block("x = 10")


def test_detects_fraction():
    assert is_math_block("A / B")


def test_converts_math_symbols():
    result = text_to_latex("σ ≤ 10")

    assert result == "$$\\sigma \\le 10$$"


def test_converts_fraction():
    result = text_to_latex("A / B")

    assert result == "$$\\frac{A}{B}$$"


def test_converts_square_root():
    result = text_to_latex("√t")

    assert result == "$$\\sqrt{t}$$"


def test_black_scholes_expression():
    result = parse_math_region(
        "d1 = (ln(S / K) + (r + σ^2 / 2)t) / (σ√t)"
    )

    assert result.startswith("$$")
    assert result.endswith("$$")
    assert "\\ln" in result
    assert "\\sigma" in result
    assert "\\sqrt" in result
    assert "\\frac" in result
