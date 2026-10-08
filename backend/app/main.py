# backend/app/main.py
import os
import sys

from fastapi import FastAPI, UploadFile, File, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

# Ensure python can locate backend packages cleanly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.document import ParseResult
from app.schemas.errors import RFC7807ProblemDetails
from app.core.errors import PipelineError
from app.core.store import document_store
from app.core.watchdog import enforce_timeout
from app.extractors.render import render_page_png
from app.pipeline import UniversalIngestionPipeline

# Upload ceiling (bytes). Override with AXIOMPARSE_MAX_UPLOAD_MB.
MAX_UPLOAD_BYTES = int(float(os.getenv("AXIOMPARSE_MAX_UPLOAD_MB", "50")) * 1024 * 1024)

# Origins allowed to call the API from a browser. Override with a comma-separated
# AXIOMPARSE_CORS_ORIGINS (e.g. the deployed frontend URL).
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("AXIOMPARSE_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

# 1. Initialize FastAPI app
app = FastAPI(
    title="AxiomParse Universal Ingestion Engine",
    version="1.0.0",
    description="Universal document parser for financial, legal, and regulated diligence."
)

# 2. CORS: only the configured frontend origins, only the methods the API uses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 3. Instantiate the pipeline once
pipeline = UniversalIngestionPipeline()


def _problem(http_status: int, title: str, detail: str, instance: str, code: str, diagnostics: dict) -> HTTPException:
    problem = RFC7807ProblemDetails(
        type=f"https://errors.axiomparse.dev/{code.removeprefix('ERR_')}",
        title=title,
        status=http_status,
        detail=detail,
        instance=instance,
        error_code=code,
        diagnostics=diagnostics,
    )
    return HTTPException(status_code=http_status, detail=problem.model_dump())


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
    filename = file.filename or ""
    instance = f"/api/v1/parse/{filename}"
    contents = await file.read()

    # Failure Mode 0: No usable filename
    if not filename:
        raise _problem(
            400, "Missing Filename", "The upload has no filename, so its type cannot be determined.",
            instance, "ERR_MISSING_FILENAME", {},
        )

    # Failure Mode 1: Empty file check (0 bytes)
    if len(contents) == 0:
        problem = RFC7807ProblemDetails(
            type="https://errors.axiomparse.dev/EMPTY_FILE",
            title="Empty File Payload",
            status=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file payload contains 0 bytes.",
            instance=instance,
            error_code="ERR_EMPTY_FILE",
            diagnostics={"filename": filename, "byte_size": 0}
        )
        raise HTTPException(status_code=400, detail=problem.model_dump())

    # Failure Mode 1b: Oversized upload
    if len(contents) > MAX_UPLOAD_BYTES:
        raise _problem(
            413, "File Too Large",
            f"The file is {len(contents) / 1024 / 1024:.1f} MB; the limit is {MAX_UPLOAD_BYTES / 1024 / 1024:.0f} MB.",
            instance, "ERR_FILE_TOO_LARGE",
            {"filename": filename, "byte_size": len(contents), "max_bytes": MAX_UPLOAD_BYTES},
        )

    # Failure Mode 2: Corrupted PDF header check
    if filename.lower().endswith(".pdf") and not contents.startswith(b"%PDF"):
        problem = RFC7807ProblemDetails(
            type="https://errors.axiomparse.dev/CORRUPT_PDF_HEADER",
            title="Malformed PDF Header",
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The file header is missing valid %PDF magic identification bytes.",
            instance=instance,
            error_code="ERR_MALFORMED_HEADER",
            diagnostics={
                "received_header": str(contents[:10]),
                "actionable_suggestion": "Export the document with valid PDF/A specification or check byte transmission."
            }
        )
        raise HTTPException(status_code=422, detail=problem.model_dump())


    # 4.2: Execute the 3-Stage Pipeline
    mime = file.content_type or "application/pdf"
    try:
        return await pipeline.execute(filename, contents, mime)
    except PipelineError as exc:
        raise _problem(
            exc.status_code, exc.title, exc.detail, instance, exc.error_code, exc.diagnostics
        )


# 6. Page preview: renders a page of a previously analysed PDF to PNG.
@app.get("/api/v1/documents/{document_id}/pages/{page}/image")
def get_page_image(document_id: str, page: int):
    instance = f"/api/v1/documents/{document_id}/pages/{page}/image"
    pdf_path = document_store.path_for(document_id)
    if pdf_path is None:
        raise _problem(
            404, "Document Not Found",
            "No stored PDF exists for this document id. It may have expired; upload the file again.",
            instance, "ERR_DOCUMENT_NOT_FOUND", {"document_id": document_id},
        )
    try:
        png = render_page_png(pdf_path, page)
    except IndexError as exc:
        raise _problem(
            404, "Page Not Found", str(exc), instance, "ERR_PAGE_NOT_FOUND",
            {"document_id": document_id, "page": page},
        )
    except Exception as exc:
        raise _problem(
            500, "Page Render Failed", f"The page could not be rendered: {exc}", instance,
            "ERR_RENDER_FAILED", {"document_id": document_id, "page": page},
        )
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})
