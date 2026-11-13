"""Fails when a file of the repository contains an em dash.

No em dash may appear in any text written for this project: code comments,
docs, UI text, commit messages (AGENTS.md rule 11). This program checks every
tracked text file. Commit messages are not checked here.

Run: python scripts/check_no_em_dash.py

Tests: backend/tests/unit/scripts/test_check_no_em_dash.py
"""

import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Written as a code point so that this file passes its own check.
EM_DASH = chr(0x2014)


def find_em_dashes(path: Path, text: str) -> list[str]:
    """Return one "file:line" entry for every line of a text that contains an em dash.

    Args:
        path: The path to show.
        text: The content of the file.
    """
    return [
        f"{path}:{number}"
        for number, line in enumerate(text.splitlines(), start=1)
        if EM_DASH in line
    ]


def check_files(repo_root: Path, files: Iterable[str]) -> list[str]:
    """Check files and return every place an em dash was found.

    Files that are not UTF-8 text (images, fonts) are skipped.

    Args:
        repo_root: The repository root.
        files: Paths relative to the repository root.
    """
    found: list[str] = []
    for name in files:
        path = repo_root / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        found += find_em_dashes(Path(name), text)
    return found


def tracked_files(repo_root: Path) -> list[str]:
    """Return every file git tracks or would track: committed, staged or new and not ignored.

    Args:
        repo_root: The repository root.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [name for name in result.stdout.split("\0") if name]


def main(argv: Sequence[str]) -> int:
    """Check the repository, or only the files given as arguments.

    Args:
        argv: Optional paths relative to the repository root.

    Returns:
        The process exit code: 1 when an em dash was found.
    """
    found = check_files(REPO_ROOT, argv or tracked_files(REPO_ROOT))
    if found:
        print("Em dashes are not allowed in this project (AGENTS.md rule 11). Found in:")
        for place in found:
            print(f"  {place}")
        return 1
    print("No em dashes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
