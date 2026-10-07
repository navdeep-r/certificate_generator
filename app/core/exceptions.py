"""Application-level exceptions and HTTP mapping.

All custom exceptions inherit from AppError.
Global handlers in main.py convert them to stable JSON responses.
"""
from __future__ import annotations


class AppError(Exception):
    """Base for all application errors."""

    http_status: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.__class__.message
        super().__init__(self.message)


class NotFoundError(AppError):
    http_status = 404
    error_code = "NOT_FOUND"
    message = "Resource not found."


class ConflictError(AppError):
    http_status = 409
    error_code = "CONFLICT"
    message = "Resource is not in the expected state."


class ValidationError(AppError):
    http_status = 422
    error_code = "VALIDATION_ERROR"
    message = "Request validation failed."


class RequestTooLargeError(AppError):
    http_status = 413
    error_code = "REQUEST_TOO_LARGE"
    message = "Request exceeds the allowed limit."


class StorageError(AppError):
    http_status = 500
    error_code = "STORAGE_ERROR"
    message = "A storage operation failed."


class DependencyUnavailableError(AppError):
    http_status = 503
    error_code = "DEPENDENCY_UNAVAILABLE"
    message = "A required dependency is unavailable."
