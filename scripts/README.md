# scripts

Small programs for developers and CI. They are not part of the app and are not shipped in a release.

| Script | What it does |
|---|---|
| `uv` | Runs uv with the folders `./start` uses, so developer commands share the app's Python environment: `scripts/uv run pytest` |
| `requirements_coverage.py` | Reports which requirements of docs/SPEC.md no test names. `--strict` makes that an error |
| `check_coverage.py` | Checks the backend coverage thresholds per scope (docs/TESTING.md section 3) |
| `check_docstrings.py` | Checks that every backend module says where its tests live |
| `check_no_em_dash.py` | Fails when a tracked file contains an em dash (AGENTS.md rule 11) |

Tests: `backend/tests/unit/scripts/`.
