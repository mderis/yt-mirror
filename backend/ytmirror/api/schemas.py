"""Request and response models of the HTTP API.

The OpenAPI schema generated from these models is the contract with the
frontend (docs/ARCHITECTURE.md section 8). After a change here, run
``npm --prefix frontend run gen:api``. This module must not contain logic.

Tests: backend/tests/api/
"""

from typing import Literal

from pydantic import BaseModel


class ErrorBody(BaseModel):
    """The content of every error response.

    Attributes:
        code: The stable error code (docs/LOGGING.md section 4).
        message: A short technical sentence. User text is written per code in the frontend.
        details: Extra facts for the technical details.
    """

    code: str
    message: str
    details: dict[str, str]


class ErrorResponse(BaseModel):
    """The one shape of every error response."""

    error: ErrorBody


class HealthResponse(BaseModel):
    """The answer of ``GET /api/health``.

    Attributes:
        status: Always ``ok`` when the server answers.
        version: The app version.
        schema_version: The database schema version.
    """

    status: Literal["ok"]
    version: str
    schema_version: str | None
