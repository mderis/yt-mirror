"""Tests of ``ytmirror.core.errors``."""

import pytest

from ytmirror.core.errors import AppError, ErrorCode, ErrorKind


@pytest.mark.parametrize("code", list(ErrorCode))
def test_every_error_code_has_a_kind_and_a_text_key(code: ErrorCode) -> None:
    """R-ER-02: every code is stable, classified, and has a key for its user text."""
    kind = code.kind

    assert kind in (ErrorKind.PERMANENT, ErrorKind.TRANSIENT)
    assert code.text_key == f"errors.{code.value.lower()}"


def test_only_the_internal_error_is_transient_so_far() -> None:
    """R-ER-02: the kinds match the table in docs/LOGGING.md section 4."""
    transient = {code for code in ErrorCode if code.kind is ErrorKind.TRANSIENT}

    assert transient == {ErrorCode.INTERNAL}


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
