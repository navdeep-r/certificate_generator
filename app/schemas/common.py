"""Shared schema primitives."""
from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error_code: str
    message: str
