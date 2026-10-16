"""End-to-end tests of Person 3's Stage 2 against the real demo PDFs."""
import asyncio
import collections
import os
import sys
import tempfile

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "backend", "app", "extractors"))

import app.core.cache as cache_module
from app.pipeline import UniversalIngestionPipeline
from app.schemas.document import BlockType

DEMO = os.path.join(ROOT, "demo_assets")


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    """Never read or write the repo's real provenance cache from these tests."""
    monkeypatch.setattr(cache_module, "CACHE_DIR", tempfile.mkdtemp())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def parse(name):
    with open(os.path.join(DEMO, name), "rb") as f:
        data = f.read()
    return asyncio.run(UniversalIngestionPipeline().execute(name, data, "application/pdf"))


def figures(result):
    return [b for b in result.blocks if b.type == BlockType.FIGURE]


def test_bar_chart_values_are_read_exactly_from_the_pdf():
    result = parse("merger_filing_q3.pdf")
    (fig,) = figures(result)
    points = [(p.x, p.y) for p in fig.chart_data.series[0].data]
    assert points == [("Q1", 12.4), ("Q2", 15.1), ("Q3", 18.2), ("Q4", 21.0)]
    assert fig.chart_data.chart_type == "bar_chart"
    assert "| Q3 | 18.2 |" in result.markdown
    assert not fig.flagged_for_review


def test_each_chart_gets_its_own_title_and_data():
    result = parse("chart_heavy_report.pdf")
    titles = {f.chart_data.title for f in figures(result) if f.chart_data}
    assert titles == {"Revenue ($M)", "Free Cash Flow ($M)"}


def test_unrecoverable_chart_is_flagged_not_fabricated():
    result = parse("chart_heavy_report.pdf")
    unreadable = [f for f in figures(result) if f.chart_data is None]
    assert len(unreadable) == 1
    assert unreadable[0].flagged_for_review and unreadable[0].review_reason
    # The canned golden chart must never leak into real extraction.
    assert not any(b.chart_data and b.chart_data.series[0].name == "EBITDA 2025" for b in result.blocks)


def test_ruled_table_becomes_table_block():
    result = parse("mixed_financial_report.pdf")
    (table,) = [b for b in result.blocks if b.type == BlockType.TABLE]
    assert table.table_data.headers == ["Metric", "2025", "2026"]
    assert ["EBITDA", "$120M", "$155M"] in table.table_data.rows
    assert "| EBITDA | $120M | $155M |" in result.markdown


def test_black_scholes_becomes_single_equation_block_and_prose_is_untouched():
    result = parse("options_pricing.pdf")
    eqs = [b for b in result.blocks if b.type == BlockType.EQUATION]
    assert len(eqs) == 1
    assert r"\frac{\sigma^{2}}{2}" in eqs[0].latex
    assert not eqs[0].latex.startswith("$$")
    assert "$$\n$$" not in result.markdown          # no double wrapping
    prose = [b for b in result.blocks if b.type == BlockType.PARAGRAPH]
    assert any("risk-free rate" in b.text for b in prose)


def test_math_symbols_page_converts_every_formula():
    result = parse("math_symbols.pdf")
    eqs = [b for b in result.blocks if b.type == BlockType.EQUATION]
    assert len(eqs) == 6
    assert not any(b.flagged_for_review for b in eqs)


def test_plain_documents_are_unchanged_by_stage2():
    result = parse("edge_case_document.pdf")
    kinds = collections.Counter(b.type for b in result.blocks)
    assert kinds.keys() <= {BlockType.HEADING, BlockType.PARAGRAPH}


def test_reading_order_is_sequential_per_page():
    for name in ("chart_heavy_report.pdf", "multi_series_chart.pdf", "mixed_financial_report.pdf"):
        result = parse(name)
        for page in {b.page for b in result.blocks}:
            orders = [b.reading_order for b in result.blocks if b.page == page]
            assert orders == list(range(1, len(orders) + 1)), (name, page)


def test_fixture_blocks_pass_through_untouched():
    from app.extractors.stage2_adapter import enrich_blocks
    pipe = UniversalIngestionPipeline()
    baseline = pipe._generate_baseline_blocks()
    assert enrich_blocks(baseline, b"%PDF-1.4 irrelevant") is baseline


def test_stage2_failure_falls_back_to_stage1_blocks(monkeypatch):
    import app.extractors.stage2_adapter as adapter

    def boom(*_a, **_k):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(adapter, "_enrich_page", boom)
    result = parse("merger_filing_q3.pdf")           # must still return 200-equivalent output
    assert len(result.blocks) > 0
    assert not figures(result)
