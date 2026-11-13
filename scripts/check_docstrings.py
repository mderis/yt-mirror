"""Checks that every backend module says where its tests live.

Every module starts with a docstring that says what it is for, what it must
not do, and where its counterpart tests live (docs/CODING-STANDARDS.md
section 2). Ruff checks that the docstring exists. This program checks the
part Ruff cannot: a line that starts with "Tests:".

Run: python scripts/check_docstrings.py

Tests: backend/tests/unit/scripts/test_check_docstrings.py
"""

import ast
import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKED_DIRS = ("backend/ytmirror", "scripts")
TESTS_MARKER = "Tests:"


def names_its_tests(source: str) -> bool:
    """Return whether the module docstring of a source text has a "Tests:" line.

    Args:
        source: The content of a Python file.
    """
    docstring = ast.get_docstring(ast.parse(source))
    if docstring is None:
        return False
    return any(line.strip().startswith(TESTS_MARKER) for line in docstring.splitlines())


def modules_to_check(repo_root: Path) -> list[Path]:
    """Return every module that must name its tests.

    Package markers (``__init__.py``) are exempt: they hold no code to test.

    Args:
        repo_root: The repository root.
    """
    modules: list[Path] = []
    for folder in CHECKED_DIRS:
        modules += [
            path
            for path in sorted((repo_root / folder).rglob("*.py"))
            if path.name != "__init__.py"
        ]
    return modules


def main(argv: Sequence[str]) -> int:
    """Check every module of the repository.

    Args:
        argv: Not used.

    Returns:
        The process exit code: 1 when a module does not name its tests.
    """
    del argv
    missing = [
        path.relative_to(REPO_ROOT)
        for path in modules_to_check(REPO_ROOT)
        if not names_its_tests(path.read_text(encoding="utf-8"))
    ]
    if missing:
        print('These modules need a "Tests:" line in their module docstring:')
        for path in missing:
            print(f"  {path}")
        return 1
    print("Every module names its tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
