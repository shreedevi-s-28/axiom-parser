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


# ---- Regression tests: strings exactly as PyMuPDF extracts them from the demo PDFs ----

from math_parser import to_bare_latex, is_equation_line, has_unconverted_symbols


def test_unicode_superscript_black_scholes():
    # Real extracted text uses σ², not σ^2. Previously produced "\\frac{sigma²}{2}".
    latex = to_bare_latex("d1 = (ln(S / K) + (r + σ² / 2)t) / (σ√t)")
    assert r"\frac{\sigma^{2}}{2}" in latex
    assert "sigma²" not in latex
    assert "\\\\" not in latex


def test_unicode_and_caret_inputs_agree():
    assert to_bare_latex("σ² / 2") == to_bare_latex("σ^2 / 2")


def test_symbols_are_not_glued_to_following_letters():
    assert to_bare_latex("2πr") == r"2\pi r"
    assert to_bare_latex("ΔS") == r"\Delta S"


def test_sqrt_of_parenthesised_expression():
    assert to_bare_latex("√(x² + y²)") == r"\sqrt{x^{2} + y^{2}}"


def test_micro_sign_and_superscript_equation():
    assert is_math_block("x² + y² = z²")
    assert to_bare_latex("∑ xI = nµ") == r"\sum xI = n\mu"


def test_no_false_positives_on_prose_fragments():
    for text in ("and/or", "12/31/2025", "N/A", "Q1 = 12.4", "Term Loan B 620.0"):
        assert not is_math_block(text), text


def test_sentence_mentioning_a_symbol_is_not_an_equation_line():
    prose = "Where S is spot price, K is strike price, r is the risk-free rate, and σ is volatility."
    assert is_math_block(prose)          # contains σ ...
    assert not is_equation_line(prose)   # ... but it is a sentence


def test_bare_latex_has_no_delimiters_and_wrapper_adds_them():
    assert not to_bare_latex("σ ≤ 10").startswith("$$")
    assert text_to_latex("σ ≤ 10") == "$$" + to_bare_latex("σ ≤ 10") + "$$"


def test_unconverted_symbol_detection():
    assert has_unconverted_symbols("a ⊕ b")
    assert not has_unconverted_symbols(r"\sigma \le 10")
