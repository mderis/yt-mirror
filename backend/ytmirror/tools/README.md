# tools

Small command line programs for developers, run with `python -m ytmirror.tools.<name>`.

**Belongs here:** programs that build the same container as the app and print something, such as the OpenAPI schema export, and programs that prepare test data from the real world, such as `record_ytdlp`, which records answers of yt-dlp for the tests of the gateway.

**Does not belong here:** anything the running app needs.

Tests: `backend/tests/integration/tools/`.
