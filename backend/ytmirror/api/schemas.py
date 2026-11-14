"""Request and response models of the HTTP API.

The OpenAPI schema generated from these models is the contract with the
frontend (docs/ARCHITECTURE.md section 8). After a change here, run
``npm --prefix frontend run gen:api``. This module must not contain logic.

Tests: backend/tests/api/
"""

from typing import Literal

from pydantic import BaseModel

from ytmirror.core.errors import ErrorCode
from ytmirror.core.models import ToolName, ToolReport, ToolStatus


class ErrorBody(BaseModel):
    """The content of every error response.

    Attributes:
        code: The stable error code (docs/LOGGING.md section 4). Typed, so that the
            generated frontend types know every code.
        message: A short technical sentence. User text is written per code in the frontend.
        details: Extra facts for the technical details.
    """

    code: ErrorCode
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


class Tool(BaseModel):
    """The state of one tool the app needs (R-IN-03, R-IN-04).

    Attributes:
        name: The tool.
        status: What is known about it right now.
        version: Its version, when it is installed.
        source: The source it was downloaded from, for a downloaded tool.
        progress: How much of its download is done, from 0 to 1, while it installs.
        error_code: Why the last installation failed, when it did.
        installable: Whether the app can install it by itself.
    """

    name: ToolName
    status: ToolStatus
    version: str | None
    source: str | None
    progress: float | None
    error_code: ErrorCode | None
    installable: bool

    @classmethod
    def of(cls, report: ToolReport) -> Tool:
        """Return the API form of a tool report."""
        return cls(
            name=report.name,
            status=report.status,
            version=report.version,
            source=report.source,
            progress=report.progress,
            error_code=report.error_code,
            installable=report.installable,
        )


class ToolsResponse(BaseModel):
    """The answer of ``GET /api/tools``.

    Attributes:
        tools: Every tool, in the order of the first-run screen.
        setup_required: Whether the interface must show the first-run screen.
    """

    tools: list[Tool]
    setup_required: bool


class ToolUpdatedEvent(BaseModel):
    """The data of the ``tool.updated`` event of ``GET /api/events``.

    Attributes:
        tool: The new state of the tool.
        setup_required: Whether the first-run screen is still needed.
    """

    tool: Tool
    setup_required: bool
