"""Maps error codes to HTTP responses in the one error shape.

Every error response of the API is ``{"error": {"code", "message",
"details"}}`` (docs/ARCHITECTURE.md section 8). This module must not log
unhandled exceptions: ``request_log.py`` does that, once.

Tests: backend/tests/api/test_errors.py
"""

from collections.abc import Mapping

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from structlog.typing import FilteringBoundLogger

from ytmirror.api.schemas import ErrorBody, ErrorResponse
from ytmirror.core.errors import AppError, ErrorCode

_log: FilteringBoundLogger = structlog.get_logger(__name__)

_STATUS: dict[ErrorCode, int] = {
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.ORIGIN_REJECTED: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.INVALID_REQUEST: 422,
    ErrorCode.LOCAL_SERVER_UNREACHABLE: 503,
    ErrorCode.INTERNAL: 500,
}

_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.UNAUTHORIZED: "The session token is missing or wrong.",
    ErrorCode.ORIGIN_REJECTED: "The request did not come from the yt-mirror window.",
    ErrorCode.NOT_FOUND: "There is nothing at this address.",
    ErrorCode.INVALID_REQUEST: "The request is not valid.",
    ErrorCode.LOCAL_SERVER_UNREACHABLE: "The window cannot reach the local server.",
    ErrorCode.INTERNAL: "yt-mirror hit an unexpected problem.",
}

_NOT_FOUND = 404
_FIRST_SERVER_ERROR = 500


def error_response(
    code: ErrorCode,
    details: Mapping[str, str] | None = None,
    status: int | None = None,
) -> JSONResponse:
    """Return the HTTP response for an error code.

    Args:
        code: The error code.
        details: Extra facts for the technical details. Never secrets.
        status: The HTTP status, when it must differ from the usual one for the code.

    Returns:
        A JSON response in the one error shape.
    """
    body = ErrorResponse(
        error=ErrorBody(code=code, message=_MESSAGES[code], details=dict(details or {}))
    )
    return JSONResponse(body.model_dump(mode="json"), status_code=status or _STATUS[code])


def install_error_handlers(app: FastAPI) -> None:
    """Make every error the app raises use the one error shape.

    Args:
        app: The FastAPI app.
    """
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(HTTPException, _handle_http_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    _log_handled(request, exc.code)
    return error_response(exc.code, exc.details)


async def _handle_http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    if exc.status_code == _NOT_FOUND:
        code = ErrorCode.NOT_FOUND
    elif exc.status_code >= _FIRST_SERVER_ERROR:
        code = ErrorCode.INTERNAL
    else:
        code = ErrorCode.INVALID_REQUEST
    _log_handled(request, code)
    return error_response(code, status=exc.status_code)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    _log_handled(request, ErrorCode.INVALID_REQUEST)
    fields = ", ".join(".".join(str(part) for part in error["loc"]) for error in exc.errors())
    return error_response(ErrorCode.INVALID_REQUEST, {"fields": fields})


def _log_handled(request: Request, code: ErrorCode) -> None:
    _log.warning(
        "api.error",
        msg="Request answered with an error",
        error_code=code.value,
        method=request.method,
        path=request.url.path,
    )
