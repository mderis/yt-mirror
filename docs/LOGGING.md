# yt-mirror V1: Logging and Debugging

Goal: a person or an AI agent who was not there must be able to answer "what happened to this video and why" from the logs and the database alone.

There are three records, each for a different reader:

| Record | Reader | Where |
|---|---|---|
| Activity log | The user | Database table `activity`, shown in the app |
| Debug log | Developers and agents | `data/logs/*.jsonl` |
| Status history | Developers and agents | Database table `video_events` |

They are linked by `job_id`, `video_id` and `channel_id`.

## 1. Debug log format

One JSON object per line, UTF-8, in `data/logs/yt-mirror-YYYY-MM-DD.jsonl`. A new file starts each day (UTC). Files older than 14 days are deleted at start.

Required fields on every line:

| Field | Example | Notes |
|---|---|---|
| `ts` | `2026-11-13T09:28:04.512Z` | UTC, millisecond precision |
| `level` | `info` | `debug`, `info`, `warning`, `error` |
| `event` | `download.finished` | Stable name from the catalogue below |
| `component` | `services.downloader` | Python module path below `ytmirror` |
| `msg` | `Download finished` | Short human sentence |
| `run_id` | `01JCD...` | New ULID at every app start |

Context fields, present when they apply: `channel_id`, `video_id`, `job_id`, `error_code`, `duration_ms`, `attempt`.
Any other data goes in named fields, never inside `msg`. Example:

```json
{"ts":"2026-11-13T09:28:04.512Z","level":"info","event":"download.finished","component":"services.downloader","msg":"Download finished","run_id":"01JCD0","channel_id":"UCabc","video_id":"a1B2c3D4e5F","job_id":"01JCD1","height":1080,"file_size":431821004,"duration_ms":74210}
```

Rules:
1. Event names are `area.action` in lower case and never change once released. New events are added to the catalogue in this file in the same commit.
2. Log at the boundary of every use case: one line when it starts, one when it ends (with `duration_ms`), one for every decision that changes what happens next (retry, skip, fallback).
3. Log every external call (YouTube, API, GitHub, ffmpeg) at `debug` with its duration and outcome.
4. Never log secrets. The API key and the session token are redacted by a processor that runs on every line.
5. `error` means a requirement was not met and someone should look. Expected failures (a members-only video) are `warning`.
6. Exceptions are logged once, where they are handled, with `exc_info` and the mapped `error_code`.
7. The console shows the same events in a readable one-line form.

Levels by setting: "Normal" writes `info` and above. "Verbose" writes `debug` and above. `./start --debug` forces Verbose for one run. Lines from libraries (`app.external_log`) are written from `warning` at Normal and from `info` at Verbose.

## 2. Per-job logs

Each job writes the complete output of yt-dlp and ffmpeg to `data/logs/jobs/<job_id>.log`. Kept: every failed job for 14 days, and the 50 most recent successful jobs. The error details dialog and `GET /api/jobs/{id}/log` read this file.

## 3. Event catalogue (initial)

| Area | Events |
|---|---|
| app | `app.started`, `app.stopping`, `app.crashed`, `app.config` (paths, versions, install kind), `app.external_log` (a line written by a library such as uvicorn or Alembic. Its text is in `msg`, its logger name in `component`) |
| toolchain | `tool.check`, `tool.install.started`, `tool.install.finished`, `tool.install.failed`, `ytdlp.update.finished` |
| channel | `channel.added`, `channel.removed`, `channel.paused`, `channel.resumed`, `channel.folder_moved` |
| check | `check.started`, `check.finished` (counts: new, updated, gone, renamed, missing), `check.failed`, `check.retry_scheduled` |
| dates | `dates.fetch.batch`, `dates.fetch.backoff`, `dates.applied`, `dates.repaired`, `dates.verify_failed` |
| queue | `queue.enqueued`, `queue.paused`, `queue.resumed`, `queue.reordered`, `queue.disk_guard` |
| download | `download.started`, `download.stage`, `download.retry`, `download.finished`, `download.failed`, `download.cancelled` |
| file | `file.renamed`, `file.moved`, `file.trashed`, `file.missing` |
| exclude | `exclude.manual`, `exclude.rule`, `exclude.restored` |
| adopt | `adopt.scan`, `adopt.matched`, `adopt.ambiguous`, `adopt.fixed`, `adopt.failed` |
| update | `update.available`, `update.started`, `update.backup`, `update.migrated`, `update.finished`, `update.rolled_back` |
| db | `db.migration.started`, `db.migration.finished`, `db.backup` |
| api | `api.request` (debug), `api.error` |
| ui | `ui.error` (forwarded from the frontend) |

## 4. Error codes

Defined once in `backend/ytmirror/core/errors.py`. Each code has: a name, whether it is permanent or transient, and a key for its user-facing text (what happened, what the app does, what the user can do).

| Code | Kind | Meaning |
|---|---|---|
| `NETWORK_UNREACHABLE` | transient | No connection to YouTube |
| `RATE_LIMITED` | transient | YouTube asked us to slow down |
| `YOUTUBE_CHANGED` | transient | Extraction failed in a way that suggests yt-dlp is outdated. Triggers the yt-dlp update offer (R-UP-06) |
| `VIDEO_PRIVATE` | permanent | |
| `VIDEO_REMOVED` | permanent | |
| `MEMBERS_ONLY` | permanent | |
| `AGE_RESTRICTED` | permanent | Needs sign-in, not supported in V1 |
| `GEO_BLOCKED` | permanent | |
| `NOT_YET_AVAILABLE` | transient | Premiere or scheduled video not public yet. Retried after its start time |
| `NO_FORMATS` | permanent | Nothing downloadable was offered |
| `DISK_FULL` | transient | Write failed for lack of space |
| `DISK_GUARD` | transient | Paused by the free space threshold |
| `FOLDER_UNAVAILABLE` | transient | Library or channel folder not reachable |
| `PERMISSION_DENIED` | permanent | macOS denied access to the folder |
| `FFMPEG_FAILED` | transient | Merge or embed step failed |
| `VERIFY_FAILED` | transient | The finished file did not pass verification |
| `DATES_NOT_APPLIED` | transient | File dates could not be set or verified |
| `TOOL_MISSING` | transient | ffmpeg, Deno or yt-dlp is not usable |
| `CHANNEL_NOT_FOUND` | permanent | |
| `INVALID_CHANNEL_INPUT` | permanent | What the user pasted is not a channel |
| `UNAUTHORIZED` | permanent | A request to the local API came without the session token, or with a wrong one |
| `ORIGIN_REJECTED` | permanent | A request to the local server came from another website or was addressed to another host (R-PL-04) |
| `NOT_FOUND` | permanent | There is nothing at the requested address of the local server |
| `INVALID_REQUEST` | permanent | A request to the local API is malformed |
| `API_KEY_INVALID`, `API_QUOTA_EXCEEDED` | transient | Never shown as an error dialog (R-DT-12) |
| `UPDATE_FAILED`, `MIGRATION_FAILED`, `CHECKSUM_MISMATCH` | transient | |
| `INTERNAL` | transient | Anything unclassified. Always logged at `error` with a stack trace |

An unclassified yt-dlp error must be logged with its full original text so the classification can be extended.

## 5. Tools for debugging

| Tool | What it does |
|---|---|
| Settings, "Export debug report" | A zip with the last 3 days of logs, failed job logs, settings (redacted), `app.config`, tool versions, schema version, macOS version, and counts of channels and videos by status |
| Settings, "Run health check" and `./start --doctor` | Checks tools, folders, permissions, free space, database integrity, network reachability. Prints pass or fail per item with the fix |
| `./start --debug` | Verbose logging and the browser developer tools enabled in the window |
| `YTM_FAKE_YOUTUBE=<dir> ./start` | Runs the app against recorded data, to reproduce a problem without the network |
| `uv run python -m ytmirror.tools.explain <video id>` | Prints the video's row, its status history, its jobs and the matching log lines in time order |

## 6. How to investigate a problem (for agents)

1. Get the `video_id` or `job_id` from the user, the activity log, or the debug report.
2. Run the `explain` tool, or query `video_events` and `jobs` for that ID.
3. Search the debug log for the `job_id`. The lines between `download.started` and `download.failed` tell the story. The `error_code` field gives the classification.
4. Read `data/logs/jobs/<job_id>.log` for the raw yt-dlp and ffmpeg output.
5. Reproduce with the fake YouTube: add a fixture that returns the same failure, write a failing test, then fix.
6. If the code was `INTERNAL`, the fix includes adding a proper error code.
