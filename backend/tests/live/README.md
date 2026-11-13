# live tests

Tests that need the real YouTube (docs/TESTING.md section 8). Each one carries `@pytest.mark.live`. They are skipped by default and never run in CI. Run them with `uv run pytest -m live`.

The first live tests arrive in milestone M3.
