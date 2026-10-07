# backend/app/core/watchdog.py
import asyncio
from functools import wraps
from fastapi import HTTPException
from app.schemas.errors import RFC7807ProblemDetails

# Set safety ceiling to 45s (well within Cenizas Labs 60s SLA)
TIMEOUT_HARD_CEILING = 45.0

def enforce_timeout(timeout_seconds: float = TIMEOUT_HARD_CEILING):
    """
    Decorator that wraps an async endpoint or function in a strict watchdog timer.
    If execution exceeds timeout_seconds, it raises an RFC 7807 compliant HTTP 504 error.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                problem = RFC7807ProblemDetails(
                    type="https://errors.axiomparse.dev/PROCESSING_TIMEOUT",
                    title="Document Processing Timeout Exceeded",
                    status=504,
                    detail=f"The engine could not complete parsing within the guaranteed {timeout_seconds}s SLA window.",
                    instance="/api/v1/parse",
                    error_code="ERR_PARSE_TIMEOUT_SLA",
                    diagnostics={
                        "timeout_seconds": timeout_seconds,
                        "remedy": "File may contain extreme page complexity. Split into smaller page batches."
                    }
                )
                raise HTTPException(status_code=504, detail=problem.model_dump())
        return wrapper
    return decorator