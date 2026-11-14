"""Prints the OpenAPI schema of the HTTP API as JSON.

Used by ``npm --prefix frontend run gen:api`` to generate the frontend types
(docs/ARCHITECTURE.md section 2). It builds the same app as a real run and
must not start a server or touch the database.

Run: python -m ytmirror.tools.export_openapi [output file]

Tests: backend/tests/integration/tools/test_export_openapi.py
"""

import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from ytmirror.api.app import ApiConfig, create_app
from ytmirror.api.security import SecurityPolicy
from ytmirror.app.config import resolve_paths
from ytmirror.app.container import build_container
from ytmirror.app.main import api_services

_SCHEMA_ONLY_TOKEN = "schema-export"
_SCHEMA_ONLY_PORT = 0


def openapi_json() -> str:
    """Return the OpenAPI schema as stable, sorted JSON text."""
    paths = resolve_paths(os.environ)
    container = build_container(paths)
    config = ApiConfig(
        security=SecurityPolicy.for_local_server(_SCHEMA_ONLY_TOKEN, _SCHEMA_ONLY_PORT),
        frontend_dir=paths.frontend_dir,
    )
    app = create_app(config, api_services(container), container.clock)
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str]) -> int:
    """Write the schema to a file, or to standard output without an argument.

    Args:
        argv: The command line arguments without the program name.

    Returns:
        The process exit code.
    """
    text = openapi_json()
    if argv:
        Path(argv[0]).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
