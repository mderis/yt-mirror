# live tests

Tests that need the real YouTube (docs/TESTING.md section 8). Each one carries `@pytest.mark.live`. They are skipped by default and never run in CI. Run them with `uv run pytest -m live`.

From milestone M2: a lookup, a listing, the pictures and the video count of one small public channel (`test_youtube_live.py`). The download test arrives in milestone M3.

A failure here can come from the network alone: from some networks YouTube is reachable only part of the time, and from others it refuses requests with its "not a bot" check (docs/OPEN-QUESTIONS.md, facts of M2).
