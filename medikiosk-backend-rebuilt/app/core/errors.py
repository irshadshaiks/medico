"""
Application errors.

Every failure the client can see is one of these. Handlers in `main.py` turn
them into a consistent JSON body, so the frontend never has to guess a shape.
"""

from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class ProviderUnavailable(AppError):
    """An external provider timed out or errored after retries."""

    status_code = 503
    code = "provider_unavailable"
