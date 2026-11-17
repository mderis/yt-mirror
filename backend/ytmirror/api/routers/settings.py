"""The settings endpoints of milestone M4: the optional YouTube API key.

Implements the HTTP side of R-DT-12: save a key, remove it, test it. The key
travels only in request bodies, which the request log never writes
(R-LG-07); no answer contains it, only how it stands. The rest of the
settings arrive with the settings screen of milestone M7. No logic here.

Tests: backend/tests/api/test_settings.py
"""

from fastapi import APIRouter

from ytmirror.api.catalogue_schemas import (
    ApiKey,
    SaveApiKeyRequest,
    TestApiKeyRequest,
    TestApiKeyResponse,
)
from ytmirror.services.dates import DatesService


def build_router(dates: DatesService) -> APIRouter:
    """Return the router for the key setting.

    Args:
        dates: The exact-date fetch, which keeps and uses the key.

    Returns:
        The router, to be mounted under ``/api``.
    """
    router = APIRouter(tags=["settings"])

    def get_api_key() -> ApiKey:
        """Return how the API key stands. Never the key itself."""
        return ApiKey.of(dates.key_state())

    def save_api_key(body: SaveApiKeyRequest) -> ApiKey:
        """Save an API key in place of the saved one, and use it from now on (R-DT-12)."""
        return ApiKey.of(dates.save_key(body.key))

    def remove_api_key() -> ApiKey:
        """Remove the API key: exact dates are looked up without it (R-DT-12)."""
        return ApiKey.of(dates.remove_key())

    def test_api_key(body: TestApiKeyRequest) -> TestApiKeyResponse:
        """Ask the YouTube API once with a key, or with the saved one (R-DT-12)."""
        result = dates.test_key(body.key)
        return TestApiKeyResponse(
            works=result.works, error_code=result.code, api_key=ApiKey.of(dates.key_state())
        )

    router.add_api_route(
        "/settings/api-key",
        get_api_key,
        methods=["GET"],
        response_model=ApiKey,
        operation_id="getApiKey",
    )
    router.add_api_route(
        "/settings/api-key",
        save_api_key,
        methods=["PUT"],
        response_model=ApiKey,
        operation_id="saveApiKey",
    )
    router.add_api_route(
        "/settings/api-key",
        remove_api_key,
        methods=["DELETE"],
        response_model=ApiKey,
        operation_id="removeApiKey",
    )
    router.add_api_route(
        "/settings/api-key/test",
        test_api_key,
        methods=["POST"],
        response_model=TestApiKeyResponse,
        operation_id="testApiKey",
    )
    return router
