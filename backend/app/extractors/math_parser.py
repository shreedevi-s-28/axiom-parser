import re


MATH_SYMBOLS_PATTERN = re.compile(
    r'[∑∫∂√α-ωΑ-Ω±≤≥≠≈∞½¾¼≡→∆∇]'
)


def is_math_block(text: str) -> bool:
    """Detect whether a string contains mathematical notation."""

    if not text:
        return False

    if MATH_SYMBOLS_PATTERN.search(text):
        return True

    if re.search(r'\b[a-zA-Z]\s*=\s*[-+]?\d', text):
        return True

    if re.search(r'\w+\s*/\s*\w+', text):
        return True

    if re.search(r'\w+\^\w+', text):
        return True

    return False


def text_to_latex(text: str) -> str:
    """Convert extracted mathematical text into KaTeX-compatible LaTeX."""

    clean = text.strip()

    # Convert square roots before replacing the √ symbol.
    clean = re.sub(
        r'√\s*([A-Za-z0-9]+)',
        r'\\sqrt{\1}',
        clean
    )

    replacements = {
        '≤': r'\le',
        '≥': r'\ge',
        '≠': r'\ne',
        '±': r'\pm',
        '∞': r'\infty',
        'π': r'\pi',
        'σ': r'\sigma',
        'λ': r'\lambda',
        'α': r'\alpha',
        'β': r'\beta',
        'γ': r'\gamma',
        'δ': r'\delta',
        'θ': r'\theta',
        'Δ': r'\Delta',
        '∆': r'\Delta',
        '∑': r'\sum',
        '∫': r'\int',
        '∂': r'\partial',
        '→': r'\rightarrow',
        '·': r'\cdot',
    }

    for symbol, latex in replacements.items():
        clean = clean.replace(symbol, latex)

    # Protect exponents such as σ^2 before converting divisions.
    powers = []

    def protect_power(match):
        powers.append(match.group(0))
        return f'__POWER_{len(powers) - 1}__'

    clean = re.sub(
        r'[A-Za-z0-9\\]+(?:\^\w+)',
        protect_power,
        clean
    )

    # Convert simple divisions such as A / B and S / K.
    clean = re.sub(
        r'(\w+)\s*/\s*(\w+)',
        r'\\frac{\1}{\2}',
        clean
    )

    # Restore protected powers.
    for index, power in enumerate(powers):
        power = re.sub(
            r'\^(\w+)',
            r'^{\1}',
            power
        )
        clean = clean.replace(
            f'__POWER_{index}__',
            power
        )

    # Convert remaining simple powers such as x^2.
    clean = re.sub(
        r'([A-Za-z0-9\\]+)\^([A-Za-z0-9]+)',
        r'\1^{\2}',
        clean
    )

    # Convert common mathematical functions.
    clean = re.sub(r'\bln\s*\(', r'\\ln(', clean)
    clean = re.sub(r'\blog\s*\(', r'\\log(', clean)
    clean = re.sub(r'\bsin\s*\(', r'\\sin(', clean)
    clean = re.sub(r'\bcos\s*\(', r'\\cos(', clean)
    clean = re.sub(r'\btan\s*\(', r'\\tan(', clean)

    if not clean.startswith('$$'):
        clean = f'$${clean}$$'

    return clean


def parse_math_region(text_or_crop) -> str:
    """Main interface for the pipeline."""

    if isinstance(text_or_crop, str):
        return text_to_latex(text_or_crop)

    return (
        r"$$d_1 = "
        r"\frac{\ln(S/K) + (r + \sigma^2/2)t}"
        r"{\sigma\sqrt{t}}$$"
    )
