"""Tests of ``ytmirror.core.errors``."""

from pathlib import Path

import pytest

from ytmirror.core.errors import AppError, ErrorCode, ErrorKind


@pytest.mark.parametrize("code", list(ErrorCode))
def test_every_error_code_has_a_kind_and_a_text_key(code: ErrorCode) -> None:
    """R-ER-02: every code is stable, classified, and has a key for its user text."""
    kind = code.kind

    assert kind in (ErrorKind.PERMANENT, ErrorKind.TRANSIENT)
    assert code.text_key == f"errors.{code.value.lower()}"


def test_the_kinds_of_the_codes_match_the_logging_document() -> None:
    """R-ER-02: the kinds match the table in docs/LOGGING.md section 4."""
    transient = {code for code in ErrorCode if code.kind is ErrorKind.TRANSIENT}

    assert transient == {
        ErrorCode.INTERNAL,
        ErrorCode.LOCAL_SERVER_UNREACHABLE,
        ErrorCode.NETWORK_UNREACHABLE,
        ErrorCode.CHECKSUM_MISMATCH,
        ErrorCode.DISK_FULL,
        ErrorCode.TOOL_MISSING,
    }


def test_app_error_carries_its_code_and_a_copy_of_the_details() -> None:
    """R-ER-02: an expected failure travels with its code, not with free text."""
    details = {"field": "port"}

    error = AppError(ErrorCode.INVALID_REQUEST, details)
    details["field"] = "changed afterwards"

    assert error.code is ErrorCode.INVALID_REQUEST
    assert error.details == {"field": "port"}
    assert str(error) == "INVALID_REQUEST"


def test_app_error_without_details_has_empty_details() -> None:
    """R-ER-02: details are optional."""
    error = AppError(ErrorCode.NOT_FOUND)

    assert error.details == {}


def test_the_window_has_a_code_of_its_own_for_an_unreachable_server() -> None:
    """R-ER-04: "the window cannot reach its own server" is a transient error with its own code."""
    code = ErrorCode.LOCAL_SERVER_UNREACHABLE

    assert code.value == "LOCAL_SERVER_UNREACHABLE"
    assert code.kind is ErrorKind.TRANSIENT
    assert code.text_key == "errors.local_server_unreachable"


def test_every_code_is_listed_in_the_logging_document() -> None:
    """R-ER-02: codes are defined once and documented in docs/LOGGING.md section 4."""
    document = (Path(__file__).resolve().parents[4] / "docs" / "LOGGING.md").read_text(
        encoding="utf-8"
    )

    for code in ErrorCode:
        assert f"`{code.value}`" in document, code
        assert f"| {code.kind.value} |" in next(
            line for line in document.splitlines() if f"`{code.value}`" in line
        ), code
