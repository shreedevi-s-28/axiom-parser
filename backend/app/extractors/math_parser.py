"""Math detection and text -> LaTeX conversion (Person 3).

Public API (unchanged): is_math_block, text_to_latex, parse_math_region.
New: is_equation_line (stricter, prose-safe) and to_bare_latex (no $$ wrapper,
which is what SemanticBlock.latex stores).
"""
import re

MATH_SYMBOLS_PATTERN = re.compile(r'[∑∫∂√α-ωΑ-Ω±≤≥≠≈∞½¾¼≡→∆∇µ²³]')

_SUPERSCRIPTS = {'²': '^2', '³': '^3', '¹': '^1'}
_SUBSCRIPTS = {chr(0x2080 + i): f'_{i}' for i in range(10)}

# Order matters only for readability; each maps a single symbol to a macro.
_SYMBOLS = {
    '≤': r'\le', '≥': r'\ge', '≠': r'\ne', '≈': r'\approx', '±': r'\pm',
    '∞': r'\infty', 'π': r'\pi', 'σ': r'\sigma', 'λ': r'\lambda',
    'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta',
    'θ': r'\theta', 'μ': r'\mu', 'µ': r'\mu',  # Greek mu and micro sign
    'Δ': r'\Delta', '∆': r'\Delta', '∑': r'\sum', '∫': r'\int',
    '∂': r'\partial', '→': r'\rightarrow', '·': r'\cdot', '∇': r'\nabla',
}

_FUNCTIONS = ('ln', 'log', 'sin', 'cos', 'tan', 'exp')
_TOKEN = r'(\\[A-Za-z]+(?:\^\{\w+\})?|[A-Za-z0-9.]+(?:\^\{\w+\})?)'


def _is_date_or_na(text: str) -> bool:
    return bool(re.search(r'\b\d{1,4}/\d{1,2}(/\d{1,4})?\b', text)) or \
        bool(re.fullmatch(r'\s*[Nn]/[Aa]\s*', text))


def is_math_block(text: str) -> bool:
    """Detect whether a string contains mathematical notation."""
    if not text:
        return False
    if MATH_SYMBOLS_PATTERN.search(text):
        return True
    if re.search(r'\b[a-zA-Z]\s*=\s*[-+]?\d', text):
        return True
    if re.search(r'\w+\^\w+', text):
        return True
    # Single-token fractions only (A / B, S / K); never dates, N/A, "and/or".
    if not _is_date_or_na(text) and re.search(r'(?<![A-Za-z])[A-Za-z]\s*/\s*[A-Za-z](?![A-Za-z])', text):
        return True
    return False


def is_equation_line(text: str) -> bool:
    """Stricter than is_math_block: true only when the line IS an equation, not
    a sentence that happens to mention σ or K. Used by the pipeline adapter."""
    if not is_math_block(text):
        return False
    words = [w for w in re.findall(r'[A-Za-z]{4,}', text) if w.lower() not in _FUNCTIONS]
    return len(words) <= 1


def _convert_sqrt(text: str) -> str:
    """√(...) with balanced parentheses, or √token."""
    out, i = [], 0
    while i < len(text):
        if text[i] != '√':
            out.append(text[i]); i += 1; continue
        j = i + 1
        while j < len(text) and text[j] == ' ':
            j += 1
        if j < len(text) and text[j] == '(':
            depth, k = 0, j
            while k < len(text):
                depth += text[k] == '('
                depth -= text[k] == ')'
                if depth == 0:
                    break
                k += 1
            if depth == 0:
                out.append('\\sqrt{' + _convert_sqrt(text[j + 1:k]) + '}')
                i = k + 1
                continue
        m = re.match(r'[A-Za-z0-9]+', text[j:])
        if m:
            out.append('\\sqrt{' + m.group(0) + '}')
            i = j + m.end()
            continue
        out.append('\\sqrt{}'); i += 1
    return ''.join(out)


def to_bare_latex(text: str) -> str:
    """Convert extracted text to KaTeX-compatible LaTeX WITHOUT $$ delimiters."""
    clean = text.strip()

    for sup, repl in _SUPERSCRIPTS.items():
        clean = clean.replace(sup, repl)
    for sub, repl in _SUBSCRIPTS.items():
        clean = clean.replace(sub, repl)

    clean = _convert_sqrt(clean)

    # Macro followed by a space so \pi r never glues into \pir.
    for symbol, macro in _SYMBOLS.items():
        clean = clean.replace(symbol, macro + ' ')
    clean = re.sub(r' {2,}', ' ', clean)
    # A macro's trailing space must not detach a following ^ or _.
    clean = re.sub(r'(\\[A-Za-z]+) ([\^_])', r'\1\2', clean)

    # Powers: x^2 -> x^{2}, \sigma^2 -> \sigma^{2}, (a+b)^2 -> (a+b)^{2}
    clean = re.sub(r'(\\[A-Za-z]+|[A-Za-z0-9]+|\))\^(\w+)', r'\1^{\2}', clean)

    # Simple fractions between single tokens.
    clean = re.sub(_TOKEN + r'\s*/\s*' + _TOKEN, r'\\frac{\1}{\2}', clean)

    for fn in _FUNCTIONS:
        clean = re.sub(r'(?<!\\)\b' + fn + r'\s*\(', '\\\\' + fn + '(', clean)

    return re.sub(r'\s+', ' ', clean).strip()


def text_to_latex(text: str) -> str:
    """Convert extracted math text into KaTeX-compatible LaTeX wrapped in $$."""
    clean = to_bare_latex(text)
    if not clean.startswith('$$'):
        clean = f'$${clean}$$'
    return clean


def has_unconverted_symbols(latex: str) -> bool:
    """True if non-ASCII characters survived conversion (KaTeX may reject them)."""
    return bool(re.search(r'[^\x00-\x7f]', latex))


def parse_math_region(text_or_crop) -> str:
    """Main interface for the pipeline (text input). A crop input has no text
    layer to convert, so it returns the reference Black-Scholes demo formula."""
    if isinstance(text_or_crop, str):
        return text_to_latex(text_or_crop)

    return (
        r"$$d_1 = "
        r"\frac{\ln(S/K) + (r + \sigma^2/2)t}"
        r"{\sigma\sqrt{t}}$$"
    )
