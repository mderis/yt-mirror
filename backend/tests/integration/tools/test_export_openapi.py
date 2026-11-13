"""Tests of ``ytmirror.tools.export_openapi``."""

import json
from pathlib import Path

import pytest

from ytmirror.tools.export_openapi import main, openapi_json


def test_the_schema_describes_the_api_and_is_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    """infra: the generated frontend types come from this schema, so it must not jitter."""
    monkeypatch.setenv("YTM_HOME", "/nonexistent/yt-mirror-home")

    first = openapi_json()
    second = openapi_json()

    schema = json.loads(first)
    assert first == second
    assert first.endswith("\n")
    assert "/api/health" in schema["paths"]
    assert list(schema) == sorted(schema)


def test_the_schema_goes_to_standard_output_or_to_a_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """infra: ``gen:api`` writes the schema to a file, developers can also print it."""
    target = tmp_path / "openapi.json"

    printed_exit = main([])
    printed = capsys.readouterr().out
    written_exit = main([str(target)])

    assert printed_exit == written_exit == 0
    assert target.read_text(encoding="utf-8") == printed == openapi_json()
