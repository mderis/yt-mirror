# live tests

Tests that need the real YouTube (docs/TESTING.md section 8). Each one carries `@pytest.mark.live`. They are skipped by default and never run in CI. Run them with `uv run pytest -m live`.

From milestone M2: a lookup, a listing, the pictures and the video count of one small public channel (`test_youtube_live.py`). From milestone M3: one real download of that channel's video at 480p through the whole app, verified for its file, metadata and dates (`test_download_live.py`). It reads the ffmpeg and Deno of the app folder. From milestone M4: the light exact-date lookup of the first video of YouTube and of a premiere, and, only when `YTM_YOUTUBE_API_KEY` is set in the environment, one request of the YouTube API with that key (`test_exact_dates_live.py`). The key is never written anywhere.

A failure here can come from the network alone: from some networks YouTube is reachable only part of the time, and from others it refuses requests with its "not a bot" check (docs/OPEN-QUESTIONS.md, facts of M2).
