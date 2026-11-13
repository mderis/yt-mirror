"""The security checks of the local server (docs/ARCHITECTURE.md section 9).

Implements R-PL-04. Every request must be addressed to the local server
(Host header), must not come from another website (Origin header), and
every ``/api`` call must carry the session token. The token arrives once in
the first URL, is exchanged for a cookie, and never appears in a URL again
(docs/DECISIONS.md D-038).

This module must not know any route other than the ``/api`` prefix.

Tests: backend/tests/api/test_security.py
"""

import secrets
from dataclasses import dataclass

import structlog
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send
from structlog.typing import FilteringBoundLogger

from ytmirror.api.errors import error_response
from ytmirror.core.errors import ErrorCode

_log: FilteringBoundLogger = structlog.get_logger(__name__)

API_PREFIX = "/api"
SESSION_COOKIE = "ytm_session"
LOCAL_ADDRESS = "127.0.0.1"
_BEARER = "bearer "


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    """What a request must show to be accepted.

    Attributes:
        token: The session token of this run.
        allowed_hosts: Accepted values of the Host header, in lower case.
        allowed_origins: Accepted values of the Origin header, in lower case.
    """

    token: str
    allowed_hosts: frozenset[str]
    allowed_origins: frozenset[str]

    @classmethod
    def for_local_server(
        cls, token: str, port: int, extra_origin: str | None = None
    ) -> SecurityPolicy:
        """Return the policy for a server on 127.0.0.1.

        Args:
            token: The session token of this run.
            port: The port the server listens on.
            extra_origin: The origin of the development server in ``--dev`` mode, otherwise None.

        Returns:
            A policy that accepts only the server's own address, plus the extra origin.
        """
        host = f"{LOCAL_ADDRESS}:{port}"
        origins = {f"http://{host}"}
        if extra_origin is not None:
            origins.add(extra_origin.rstrip("/").lower())
        return cls(token=token, allowed_hosts=frozenset({host}), allowed_origins=frozenset(origins))

    def token_matches(self, candidate: str | None) -> bool:
        """Return whether a presented token is the session token.

        Args:
            candidate: The token a request presented, or None.
        """
        if candidate is None:
            return False
        return secrets.compare_digest(candidate.encode(), self.token.encode())


def rejection_for(
    policy: SecurityPolicy,
    *,
    path: str,
    host: str | None,
    origin: str | None,
    cookie_token: str | None,
    bearer_token: str | None,
) -> ErrorCode | None:
    """Decide whether a request must be rejected.

    Implements R-PL-04.

    Args:
        policy: The policy of this run.
        path: The request path.
        host: The Host header, or None.
        origin: The Origin header, or None when the browser sent none.
        cookie_token: The value of the session cookie, or None.
        bearer_token: The token of an ``Authorization: Bearer`` header, or None.

    Returns:
        The error code to answer with, or None when the request is accepted.
    """
    if host is None or host.lower() not in policy.allowed_hosts:
        return ErrorCode.ORIGIN_REJECTED
    if origin is not None and origin.lower() not in policy.allowed_origins:
        return ErrorCode.ORIGIN_REJECTED
    is_api_call = path == API_PREFIX or path.startswith(API_PREFIX + "/")
    if is_api_call and not (
        policy.token_matches(cookie_token) or policy.token_matches(bearer_token)
    ):
        return ErrorCode.UNAUTHORIZED
    return None


class SecurityMiddleware:
    """Rejects requests that fail the security checks before they reach a route."""

    def __init__(self, app: ASGIApp, policy: SecurityPolicy) -> None:
        """Create the middleware.

        Args:
            app: The next ASGI app.
            policy: The policy of this run.
        """
        self._app = app
        self._policy = policy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Check one request and pass it on or answer with an error."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        request = Request(scope)
        code = rejection_for(
            self._policy,
            path=request.url.path,
            host=request.headers.get("host"),
            origin=request.headers.get("origin"),
            cookie_token=request.cookies.get(SESSION_COOKIE),
            bearer_token=_bearer_token(request.headers.get("authorization")),
        )
        if code is None:
            await self._app(scope, receive, send)
            return
        _log.warning(
            "api.error",
            msg="Request rejected by the security checks",
            error_code=code.value,
            method=request.method,
            path=request.url.path,
            host=request.headers.get("host"),
            origin=request.headers.get("origin"),
        )
        await error_response(code)(scope, receive, send)


def _bearer_token(authorization: str | None) -> str | None:
    """Return the token of an ``Authorization: Bearer`` header, or None."""
    if authorization is None or not authorization.lower().startswith(_BEARER):
        return None
    return authorization[len(_BEARER) :].strip()
