"""Tests of ``ytmirror.api.security``: the checks of ARCHITECTURE section 9."""

from pathlib import Path

import pytest
from structlog.testing import capture_logs

from tests.api.conftest import BASE_URL, PORT, TOKEN, Api, make_diagnostics
from tests.fixtures.fakes.clock import FakeClock
from ytmirror.api.app import ApiConfig, create_app
from ytmirror.api.security import SESSION_COOKIE, SecurityPolicy, rejection_for
from ytmirror.core.errors import ErrorCode

POLICY = SecurityPolicy.for_local_server(TOKEN, PORT)
HOST = f"127.0.0.1:{PORT}"


def decide(
    *,
    path: str = "/api/health",
    host: str | None = HOST,
    origin: str | None = None,
    cookie: str | None = TOKEN,
    bearer: str | None = None,
) -> ErrorCode | None:
    """Ask the rule about one request. The defaults describe an accepted API call."""
    return rejection_for(
        POLICY, path=path, host=host, origin=origin, cookie_token=cookie, bearer_token=bearer
    )


def test_an_api_call_from_the_app_window_is_accepted() -> None:
    """R-PL-04: the app's own requests pass."""
    assert decide() is None
    assert decide(origin=BASE_URL) is None


@pytest.mark.parametrize(
    "host",
    [None, "", "localhost:8000", "127.0.0.1", "127.0.0.1:9999", "evil.example", "0.0.0.0:8000"],
)
def test_a_request_for_any_other_host_is_rejected(host: str | None) -> None:
    """R-PL-04: only the server's own address is accepted, which stops DNS rebinding."""
    assert decide(host=host) is ErrorCode.ORIGIN_REJECTED


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://localhost:8000",
        "http://127.0.0.1:9999",
        "https://127.0.0.1:8000",
        "null",
        "",
    ],
)
def test_a_request_from_another_origin_is_rejected(origin: str) -> None:
    """R-PL-04: the server must reject requests from other origins."""
    assert decide(origin=origin) is ErrorCode.ORIGIN_REJECTED


def test_another_origin_is_rejected_even_with_a_valid_token() -> None:
    """R-PL-04: a website that somehow knows the token is still refused."""
    assert decide(origin="https://evil.example", cookie=TOKEN) is ErrorCode.ORIGIN_REJECTED


def test_another_origin_is_rejected_for_pages_too_not_only_for_the_api() -> None:
    """R-PL-04: the checks cover every path."""
    assert decide(path="/", origin="https://evil.example") is ErrorCode.ORIGIN_REJECTED
    assert decide(path="/assets/app.js", host="evil.example") is ErrorCode.ORIGIN_REJECTED


def test_host_and_origin_are_compared_without_regard_to_case() -> None:
    """R-PL-04: header values are not case sensitive."""
    assert decide(origin="HTTP://127.0.0.1:8000") is None


@pytest.mark.parametrize("path", ["/api", "/api/", "/api/health", "/api/anything/else"])
def test_every_api_path_needs_the_session_token(path: str) -> None:
    """R-PL-04: the token is required on every API call."""
    assert decide(path=path, cookie=None) is ErrorCode.UNAUTHORIZED
    assert decide(path=path, cookie=TOKEN) is None


@pytest.mark.parametrize("wrong", ["", "wrong", TOKEN + "x", TOKEN[:-1], TOKEN.upper()])
def test_a_wrong_token_is_rejected(wrong: str) -> None:
    """R-PL-04: only the exact token of this run is accepted."""
    assert decide(cookie=wrong) is ErrorCode.UNAUTHORIZED
    assert decide(cookie=None, bearer=wrong) is ErrorCode.UNAUTHORIZED


def test_the_token_is_also_accepted_as_a_bearer_header() -> None:
    """R-PL-04: tests and tools may send the token in a header (docs/DECISIONS.md D-038)."""
    assert decide(cookie=None, bearer=TOKEN) is None


def test_pages_and_assets_need_no_token() -> None:
    """R-PL-04: the interface files hold no secrets and load before the session exists."""
    assert decide(path="/", cookie=None) is None
    assert decide(path="/assets/app.js", cookie=None) is None
    assert decide(path="/apiary", cookie=None) is None


def test_the_development_server_origin_is_accepted_only_when_given() -> None:
    """R-PL-04: ``--dev`` adds exactly one origin, and normal runs add none."""
    dev_policy = SecurityPolicy.for_local_server(TOKEN, PORT, "http://127.0.0.1:5173/")

    assert dev_policy.allowed_origins == {BASE_URL, "http://127.0.0.1:5173"}
    assert dev_policy.allowed_hosts == {HOST}
    assert POLICY.allowed_origins == {BASE_URL}


def test_the_api_answers_401_without_a_session(api: Api) -> None:
    """R-PL-04: an API call without the token gets the UNAUTHORIZED error."""
    response = api.client().get("/api/health")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_the_api_answers_403_to_a_foreign_origin(api: Api) -> None:
    """R-PL-04: a request from another website gets the ORIGIN_REJECTED error."""
    client = api.signed_in_client()

    response = client.get("/api/health", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_REJECTED"


def test_the_api_answers_403_to_a_foreign_host(api: Api) -> None:
    """R-PL-04: a request addressed to another host name is refused."""
    client = api.signed_in_client()

    response = client.get("/api/health", headers={"Host": "attacker.example"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_REJECTED"


def test_a_bearer_header_opens_the_api(api: Api) -> None:
    """R-PL-04: the bearer form of the token works end to end."""
    response = api.client().get("/api/health", headers={"Authorization": f"Bearer {TOKEN}"})

    assert response.status_code == 200


@pytest.mark.parametrize("header", ["Basic abc", f"Token {TOKEN}", TOKEN, "Bearer"])
def test_other_authorization_headers_do_not_open_the_api(api: Api, header: str) -> None:
    """R-PL-04: only a well-formed bearer header counts."""
    response = api.client().get("/api/health", headers={"Authorization": header})

    assert response.status_code == 401


def test_the_first_url_trades_the_token_for_a_cookie_and_leaves_the_url(api: Api) -> None:
    """R-PL-04: the token is exchanged once and then never appears in a URL (D-038)."""
    client = api.client()

    response = client.get("/", params={"token": TOKEN})

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}={TOKEN};")
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert client.get("/api/health").status_code == 200


def test_a_wrong_token_in_the_first_url_gives_no_cookie(api: Api) -> None:
    """R-PL-04: guessing the token does not start a session."""
    client = api.client()

    response = client.get("/", params={"token": "guess"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert "set-cookie" not in response.headers
    assert client.get("/api/health").status_code == 401


def test_a_rejected_request_is_logged_without_the_token(api: Api) -> None:
    """R-PL-04, R-LG-01: a rejection leaves an ``api.error`` line with its code."""
    with capture_logs() as logs:
        api.client().get("/api/health", headers={"Origin": "https://evil.example"})

    rejected = [line for line in logs if line["event"] == "api.error"]
    assert len(rejected) == 1
    assert rejected[0]["error_code"] == "ORIGIN_REJECTED"
    assert rejected[0]["origin"] == "https://evil.example"
    assert rejected[0]["log_level"] == "warning"
    assert TOKEN not in str(rejected[0])


def test_in_dev_mode_the_first_url_leads_to_the_development_server(
    tmp_path: Path, frontend_dir: Path, clock: FakeClock
) -> None:
    """R-PL-04: with ``--dev`` the cookie is set and the window moves to the dev server."""
    dev_url = "http://127.0.0.1:5173/"
    config = ApiConfig(
        security=SecurityPolicy.for_local_server(TOKEN, PORT, dev_url),
        frontend_dir=frontend_dir,
        frontend_url=dev_url,
    )
    dev = Api(create_app(config, make_diagnostics(tmp_path), clock), frontend_dir)
    client = dev.client()

    with_token = client.get("/", params={"token": TOKEN})
    without_token = client.get("/")
    from_dev_server = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})

    assert with_token.status_code == 303
    assert with_token.headers["location"] == dev_url
    assert SESSION_COOKIE in with_token.headers["set-cookie"]
    assert without_token.status_code == 303
    assert without_token.headers["location"] == dev_url
    assert from_dev_server.status_code == 200
