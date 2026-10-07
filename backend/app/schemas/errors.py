# backend/app/schemas/errors.py
from typing import Dict, Any
from pydantic import BaseModel, Field

class RFC7807ProblemDetails(BaseModel):
    """
    Standardized RFC 7807 Problem Details object.
    Guarantees consistent error diagnostics across the API.
    """
    type: str = Field(..., description="URI identifier for the error type")
    title: str = Field(..., description="Short summary of the problem")
    status: int = Field(..., description="HTTP status code (e.g. 400, 422, 504)")
    detail: str = Field(..., description="Human-readable explanation of what failed")
    instance: str = Field(..., description="The endpoint path that was called")
    error_code: str = Field(..., description="AxiomParse domain error code")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic data (stage, advice, byte info)")