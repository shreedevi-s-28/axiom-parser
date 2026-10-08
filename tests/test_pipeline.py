# tests/test_pipeline.py
import os
import sys

# Ensure Python can resolve the backend package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "AxiomParse" in data["engine"]

def test_empty_file_rejection():
    # Empty file should return RFC 7807 400 error
    response = client.post(
        "/api/v1/parse",
        files={"file": ("empty.pdf", b"", "application/pdf")}
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_code"] == "ERR_EMPTY_FILE"

def test_corrupt_pdf_rejection():
    # Non-%PDF header should return 422
    response = client.post(
        "/api/v1/parse",
        files={"file": ("corrupt.pdf", b"NOT_A_VALID_PDF_HEADER", "application/pdf")}
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "ERR_MALFORMED_HEADER"

def test_valid_pdf_pipeline_execution():
    # Valid %PDF header should pass through pipeline and return 200 with metrics
    response = client.post(
        "/api/v1/parse",
        files={"file": ("filing.pdf", b"%PDF-1.4 test document stream", "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert data["metrics"]["total_blocks"] > 0
    assert data["metrics"]["estimated_cost_usd"] > 0.0
    assert len(data["blocks"]) > 0