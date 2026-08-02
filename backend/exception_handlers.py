"""
Centralized exception handlers for the Lyra backend.

All exceptions are caught here and returned as structured JSON
with ``success: false``, keeping the error format consistent
with the API spec documented in docs/API_SPEC.md.
"""

import traceback
from typing import Union

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.models import ErrorResponse


# ---------------------------------------------------------------------------
# Application-level exception for known error states
# ---------------------------------------------------------------------------


class LyraException(Exception):
    """Raised for known, recoverable errors within the backend layer.

    These map to HTTP 400 (client error) rather than 500 (server error).
    """

    def __init__(self, message: str, detail: str = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def lyra_exception_handler(request: Request, exc: LyraException) -> JSONResponse:
    """Known application errors → HTTP 400."""
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            module="backend",
            error=exc.message,
            detail=exc.detail,
        ).model_dump(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Pydantic validation errors → HTTP 422 with readable details."""
    errors: list[str] = []
    for error in exc.errors():
        loc = " → ".join(str(p) for p in error["loc"])
        errors.append(f"{loc}: {error['msg']}")

    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            module="backend",
            error="Request validation failed",
            detail="; ".join(errors),
        ).model_dump(),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected errors → HTTP 500.

    The traceback is logged but NOT exposed to the client.
    """
    # Log the full traceback — uses stderr, compatible with the existing
    # structured logger in src/logger.py.
    import sys

    print(
        f"[backend] ERROR Unhandled exception on {request.method} {request.url.path}",
        file=sys.stderr,
    )
    traceback.print_exc(file=sys.stderr)

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            module="backend",
            error="Internal server error",
            detail=str(exc) if __debug__ else None,
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# Register all handlers on an app instance
# ---------------------------------------------------------------------------


def register_handlers(app):
    """Attach all exception handlers to a FastAPI ``app`` instance."""
    app.add_exception_handler(LyraException, lyra_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
