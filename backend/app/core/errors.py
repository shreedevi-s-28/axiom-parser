# backend/app/core/errors.py
from typing import Any, Dict, Optional


class PipelineError(Exception):
    """
    Domain error raised by the ingestion pipeline.

    The API layer converts it into an RFC 7807 problem-details response, so the
    frontend always receives a structured, human-readable failure instead of a
    fabricated result.
    """

    def __init__(
        self,
        status_code: int,
        error_code: str,
        title: str,
        detail: str,
        diagnostics: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(detail)
        self.status_code = status_code
        self.error_code = error_code
        self.title = title
        self.detail = detail
        self.diagnostics = diagnostics or {}
