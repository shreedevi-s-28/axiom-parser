# backend/app/main.py
import os
import sys

from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

# Ensure python can locate backend packages cleanly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.document import ParseResult
from app.schemas.errors import RFC7807ProblemDetails
from app.core.watchdog import enforce_timeout
from app.pipeline import UniversalIngestionPipeline

# 1. Initialize FastAPI app
app = FastAPI(
    title="AxiomParse Universal Ingestion Engine",
    version="1.0.0",
    description="Universal document parser for financial, legal, and regulated diligence."
)

# 2. CORS configuration (allows Person 4's frontend on port 5173 to talk to backend on 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Instantiate the pipeline once
pipeline = UniversalIngestionPipeline()

# 4. Health Check Endpoint
@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "engine": "AxiomParse",
        "version": "1.0.0",
        "sla_timeout_limit_seconds": 45.0
    }

# 5. Core Parsing Route protected by the Watchdog Timer
@app.post("/api/v1/parse", response_model=ParseResult)
@enforce_timeout(timeout_seconds=45.0)
async def parse_document(file: UploadFile = File(...)):
    contents = await file.read()

    # Failure Mode 1: Empty file check (0 bytes)
    if len(contents) == 0:
        problem = RFC7807ProblemDetails(
            type="https://errors.axiomparse.dev/EMPTY_FILE",
            title="Empty File Payload",
            status=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file payload contains 0 bytes.",
            instance=f"/api/v1/parse/{file.filename}",
            error_code="ERR_EMPTY_FILE",
            diagnostics={"filename": file.filename, "byte_size": 0}
        )
        raise HTTPException(status_code=400, detail=problem.model_dump())

    # Failure Mode 2: Reject plain .txt or unsupported text files
    if file.filename.lower().endswith(".txt"):
        problem = RFC7807ProblemDetails(
            type="https://errors.axiomparse.dev/UNSUPPORTED_FORMAT",
            title="Unsupported File Format",
            status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"The file '{file.filename}' is a plain text file. Please upload PDF, XLSX, PPTX, or Image formats.",
            instance=f"/api/v1/parse/{file.filename}",
            error_code="ERR_UNSUPPORTED_FORMAT",
            diagnostics={"detected_filename": file.filename}
        )
        raise HTTPException(status_code=415, detail=problem.model_dump())

    # Failure Mode 3: Corrupted PDF header check
    if file.filename.lower().endswith(".pdf") and not contents.startswith(b"%PDF"):
        problem = RFC7807ProblemDetails(
            type="https://errors.axiomparse.dev/CORRUPT_PDF_HEADER",
            title="Malformed PDF Header",
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The file header is missing valid %PDF magic identification bytes.",
            instance=f"/api/v1/parse/{file.filename}",
            error_code="ERR_MALFORMED_HEADER",
            diagnostics={
                "received_header": str(contents[:10]),
                "actionable_suggestion": "Export the document with valid PDF/A specification or check byte transmission."
            }
        )
        raise HTTPException(status_code=422, detail=problem.model_dump())

    # 4.2: Execute the 3-Stage Pipeline
    mime = file.content_type or "application/pdf"
    result = await pipeline.execute(file.filename, contents, mime)
    return result