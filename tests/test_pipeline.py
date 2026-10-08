# tests/test_pipeline.py
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

# Ensure Python can resolve the backend package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REAL_PDFS = [
    "mixed_financial_report.pdf",
    "merger_filing_q3.pdf",
    "edge_case_document.pdf",
    "smudged_contract.pdf",
    "chart_heavy_report.pdf",
    "math_symbols.pdf",
]

# Text that only ever appeared in the old built-in fixture.
FIXTURE_MARKERS = ["ITEM 7", "Consolidated Debt Schedule", "Leverage Ratio", "deferred financing costs"]


def read_demo(name: str) -> bytes:
    with open(os.path.join(ROOT, "demo_assets", name), "rb") as handle:
        return handle.read()


def upload(name: str, content: bytes, mime: str = "application/pdf", test_client: TestClient = client):
    return test_client.post("/api/v1/parse", files={"file": (name, content, mime)})


def words_of(text: str):
    return sorted(re.findall(r"\S+", text))


# ---------------------------------------------------------------- basics
def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "AxiomParse" in data["engine"]


def test_empty_file_rejection():
    # Empty file should return RFC 7807 400 error
    response = upload("empty.pdf", b"")
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "ERR_EMPTY_FILE"


def test_corrupt_pdf_rejection():
    # Non-%PDF header should return 422
    response = upload("corrupt.pdf", b"NOT_A_VALID_PDF_HEADER")
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "ERR_MALFORMED_HEADER"


def test_missing_file_field_is_a_validation_error():
    response = client.post("/api/v1/parse")
    assert response.status_code == 422


# ------------------------------------------------- real extraction (no fixtures)
@pytest.mark.parametrize("name", REAL_PDFS)
def test_blocks_come_from_the_uploaded_pdf(name):
    content = read_demo(name)
    response = upload(name, content)
    assert response.status_code == 200
    data = response.json()

    # Independent ground truth straight from PyMuPDF.
    with fitz.open(stream=content, filetype="pdf") as doc:
        expected_pages = len(doc)
        expected_sizes = [(round(p.rect.width, 2), round(p.rect.height, 2)) for p in doc]
        expected_words = {i + 1: words_of(p.get_text("text")) for i, p in enumerate(doc)}

    assert data["filename"] == name
    assert data["page_count"] == expected_pages
    assert data["metrics"]["total_pages"] == expected_pages
    assert [(p["width"], p["height"]) for p in data["pages"]] == expected_sizes
    assert data["metrics"]["total_blocks"] == len(data["blocks"]) > 0

    for page_number, words in expected_words.items():
        got = words_of(" ".join(b["text"] for b in data["blocks"] if b["page"] == page_number))
        assert got == words, f"text on page {page_number} differs from the PDF"

    # Nothing from the old fixture, and nothing invented.
    full_text = " ".join(b["text"] for b in data["blocks"])
    for marker in FIXTURE_MARKERS:
        assert marker not in full_text
    for block in data["blocks"]:
        assert block["confidence"] is None
        assert 0.0 <= block["bbox"]["x0"] <= block["bbox"]["x1"] <= 1000.0
        assert 0.0 <= block["bbox"]["y0"] <= block["bbox"]["y1"] <= 1000.0
        assert block["font_size"] is not None and block["font_size"] > 0
    assert data["metrics"]["confidence_average"] is None

    # One continuous reading order.
    assert [b["reading_order"] for b in data["blocks"]] == list(range(1, len(data["blocks"]) + 1))


def test_different_pdfs_give_different_results():
    a = upload("a.pdf", read_demo("mixed_financial_report.pdf")).json()
    b = upload("b.pdf", read_demo("math_symbols.pdf")).json()
    assert [x["text"] for x in a["blocks"]] != [x["text"] for x in b["blocks"]]
    assert a["document_id"] != b["document_id"]


def test_generated_pdf_text_and_geometry_are_reported_exactly():
    doc = fitz.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((50, 100), "Zebra quartz 4711", fontsize=20)
    content = doc.tobytes()
    doc.close()

    data = upload("generated.pdf", content).json()
    assert data["pages"] == [{"page": 1, "width": 400.0, "height": 600.0}]
    assert len(data["blocks"]) == 1
    block = data["blocks"][0]
    assert block["text"] == "Zebra quartz 4711"
    assert block["font_size"] == 20.0
    # x starts at 50/400 -> 125 in the 0-1000 space.
    assert block["bbox"]["x0"] == pytest.approx(125.0, abs=1.0)


def test_concurrent_uploads_do_not_mix_results():
    names = ["mixed_financial_report.pdf", "math_symbols.pdf", "smudged_contract.pdf", "chart_heavy_report.pdf"] * 3

    def run(name):
        # Separate client per thread: TestClient is not shared across threads.
        return name, upload(name, read_demo(name), test_client=TestClient(app)).json()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(run, names))

    for name, data in results:
        with fitz.open(stream=read_demo(name), filetype="pdf") as doc:
            expected = words_of(" ".join(p.get_text("text") for p in doc))
        assert words_of(" ".join(b["text"] for b in data["blocks"])) == expected


# -------------------------------------------------------------- failure modes
def test_pdf_header_with_garbage_body_is_rejected_not_faked():
    response = upload("garbage.pdf", b"%PDF-1.4 test document stream")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "ERR_CORRUPT_PDF"
    assert "blocks" not in response.json()


def test_repo_stub_valid_sample_is_not_a_real_pdf():
    # backend/demo_assets/valid_sample.pdf is only a header stub; it must not yield made-up blocks.
    path = os.path.join(ROOT, "backend", "demo_assets", "valid_sample.pdf")
    with open(path, "rb") as handle:
        response = upload("valid_sample.pdf", handle.read())
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "ERR_CORRUPT_PDF"


def test_backend_demo_empty_and_corrupt_assets():
    for name, code in [("empty_sample.pdf", "ERR_EMPTY_FILE"), ("corrupt_sample.pdf", "ERR_MALFORMED_HEADER")]:
        with open(os.path.join(ROOT, "backend", "demo_assets", name), "rb") as handle:
            response = upload(name, handle.read())
        assert response.json()["detail"]["error_code"] == code


def test_image_only_pdf_reports_no_text_layer():
    doc = fitz.open()
    doc.new_page()  # a blank page: valid PDF, nothing to extract
    content = doc.tobytes()
    doc.close()

    response = upload("blank.pdf", content)
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "ERR_NO_TEXT_LAYER"


def test_encrypted_pdf_is_reported(tmp_path):
    doc = fitz.open()
    doc.new_page().insert_text((50, 50), "secret")
    path = tmp_path / "locked.pdf"
    doc.save(str(path), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
    doc.close()

    response = upload("locked.pdf", path.read_bytes())
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "ERR_ENCRYPTED_PDF"


def test_unsupported_extension_is_rejected_not_faked():
    response = upload("notes.docx", b"PK\x03\x04 not really", "application/octet-stream")
    assert response.status_code == 415
    assert response.json()["detail"]["error_code"] == "ERR_UNSUPPORTED_FORMAT"


def test_txt_is_rejected():
    response = upload("notes.txt", b"hello", "text/plain")
    assert response.status_code == 415


def test_oversized_upload_rejected(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "MAX_UPLOAD_BYTES", 10)
    response = upload("big.pdf", b"%PDF-1.4 " + b"x" * 100)
    assert response.status_code == 413
    assert response.json()["detail"]["error_code"] == "ERR_FILE_TOO_LARGE"


# ------------------------------------------------------------- non-PDF routes
def test_csv_route_still_extracts_real_content():
    response = upload("table.csv", b"name,score\nada,10\ngrace,20\n", "text/csv")
    assert response.status_code == 200
    data = response.json()
    table = data["blocks"][0]["table_data"]
    assert table["headers"] == ["name", "score"]
    assert table["rows"] == [["ada", "10"], ["grace", "20"]]
    assert data["pages"] == []


# --------------------------------------------------------------------- cache
def test_cache_is_off_by_default_and_never_serves_by_filename(tmp_path, monkeypatch):
    import app.core.cache as cache_module

    monkeypatch.setattr(cache_module, "CACHE_DIR", str(tmp_path))
    poisoned = {"document_id": "x", "filename": "x", "file_type": "application/pdf", "page_count": 1,
                "metrics": {"processing_time_ms": 1, "estimated_cost_usd": 0, "confidence_average": 0.5,
                            "total_pages": 1, "total_blocks": 1},
                "blocks": [{"id": "fake", "page": 1, "type": "paragraph", "text": "POISONED",
                            "bbox": {"x0": 0, "y0": 0, "x1": 1, "y1": 1}, "confidence": 0.5, "reading_order": 1}],
                "markdown": "POISONED"}
    (tmp_path / "mixed_financial_report.pdf.json").write_text(json.dumps(poisoned))

    data = upload("mixed_financial_report.pdf", read_demo("mixed_financial_report.pdf")).json()
    assert "POISONED" not in json.dumps(data)
    assert list(tmp_path.glob("*.json")) == [tmp_path / "mixed_financial_report.pdf.json"]  # nothing written


# ---------------------------------------------------------------- page images
def test_page_image_endpoint_renders_the_uploaded_pdf():
    data = upload("merger.pdf", read_demo("merger_filing_q3.pdf")).json()
    document_id = data["document_id"]

    for page in range(1, data["page_count"] + 1):
        response = client.get(f"/api/v1/documents/{document_id}/pages/{page}/image")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")

    # PNG aspect ratio follows the real page size.
    png = fitz.Pixmap(client.get(f"/api/v1/documents/{document_id}/pages/1/image").content)
    size = data["pages"][0]
    assert png.width / png.height == pytest.approx(size["width"] / size["height"], rel=0.01)

    assert client.get(f"/api/v1/documents/{document_id}/pages/99/image").status_code == 404
    assert client.get("/api/v1/documents/doc_00000000/pages/1/image").status_code == 404
    assert client.get("/api/v1/documents/not-an-id/pages/1/image").status_code == 404


def test_failed_analysis_leaves_no_stored_document():
    from app.core.store import document_store

    before = set(os.listdir(document_store.directory))
    upload("garbage.pdf", b"%PDF-1.4 test document stream")
    assert set(os.listdir(document_store.directory)) == before


# ----------------------------------------------------------------------- CORS
def test_cors_allows_only_configured_origins():
    allowed = client.options(
        "/api/v1/parse",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    denied = client.options(
        "/api/v1/parse",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in denied.headers
