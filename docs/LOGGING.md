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
4. Never log secrets. The API key and the session token are redacted by a processor that runs on every line. So is the value of `YTM_YOUTUBE_API_KEY` when it is set.
5. `error` means a requirement was not met and someone should look. Expected failures (a members-only video) are `warning`.
6. Exceptions are logged once, where they are handled, with `exc_info` and the mapped `error_code`.
7. The console shows the same events in a readable one-line form.

Levels by setting: "Normal" writes `info` and above. "Verbose" writes `debug` and above. `./start --debug` forces Verbose for one run. Lines from libraries (`app.external_log`) are written from `warning` at Normal and from `info` at Verbose.

## 2. Per-job logs

Each job writes the complete output of yt-dlp and ffmpeg to `data/logs/jobs/<job_id>.log`. Kept: the log of the latest failed attempt of a video for as long as that video is failed, however old; any other failed job's log for 14 days after its video stopped being failed; and the logs of the 50 newest other jobs. The clean-up runs at every start and deletes only files of that folder whose names are a ULID and `.log`, never anything else (R-LG-01). The error details dialog and `GET /api/jobs/{id}/log` read this file.

## 3. Event catalogue (initial)

| Area | Events |
|---|---|
| app | `app.started`, `app.stopping`, `app.child_stopped` (at quit, a tool the app started, such as ffmpeg, was stopped, with `pid` and whether it had to be `killed`), `app.crashed`, `app.config` (paths, versions, install kind), `app.external_log` (a line written by a library such as uvicorn or Alembic. Its text is in `msg`, its logger name in `component`) |
| toolchain | `tool.check`, `tool.install.started`, `tool.install.finished`, `tool.install.failed`, `ytdlp.update.finished` |
| channel | `channel.added`, `channel.removed` (with `files_trashed` and `files_left`, the files macOS refused to move to the Trash, R-CH-32), `channel.file_written` (the channel file of a folder was written, R-FI-05), `channel.file_failed` (it could not be written, with `error_code`; a channel file that could not go to the Trash is a `file.trash_failed`), `channel.file_unreadable` (a channel file that cannot be read, cannot be understood or comes from a newer version; it is left as it is), `channel.paused`, `channel.resumed`, `channel.folder_moved`, `channel.count_unavailable` (the preview of a channel has no video count, with the reason, R-CH-03), `channel.count_differs` (the first listing found another number of videos than the preview showed) |
| check | `check.started`, `check.finished` (counts: new, updated, gone, returned, read, renamed, missing), `check.failed`, `check.cancelled`, `check.retry_scheduled`, `check.video_of_other_channel` (a listed video belongs to another channel and stays there, with `video_id` and `owner_channel_id`, R-CH-17). Each carries `kind`: `quick` or `full` (R-CH-12). `check.started` also carries `first_listing` and `trigger`, what started the check: `button` ("Check now" on the channel page), `menu` ("Check now" or "Full check" in the channel menu), `check_all`, `retry` ("Try again", or work taken up when YouTube is asked again), `add` (the first listing of a new channel), `app_start` (a first listing taken up at start), `resume` (a paused channel that was never listed was resumed), `schedule` (automatic checks, from M4) or `api` (a request that names none). A full check that takes the place of a waiting quick one keeps its own trigger (R-CH-24) |
| youtube | `youtube.paused` (YouTube answered with its "not a bot" check, with `request`: the kind of request that was refused, and the length of the pause, R-ER-05), `youtube.resumed` |
| image | `image.cache.finished` (pictures of a channel were cached: stored, failed, left, R-CH-16) |
| dates | `dates.fetch.batch`, `dates.fetch.backoff`, `dates.applied`, `dates.repaired`, `dates.verify_failed` |
| queue | `queue.enqueued`, `queue.paused`, `queue.resumed`, `queue.reordered`, `queue.disk_guard` |
| download | `download.started`, `download.stage`, `download.retry` (the subtitles failed and the video is downloaded again without them, R-MD-04, or YouTube's "not a bot" check holds the download back, R-ER-05), `download.finished`, `download.failed`, `download.cancelled` (a cancel before a file was written ends the job at once and says so; with `reason` "removed from YouTube" when a waiting download did not start because a check found its video removed, R-CH-14), `download.side_file_failed` (a side file of a synced video, its info JSON or a thumbnail, could not be written; the video stays synced and the file is written later, with `file`), `download.side_file_written` (a side file that waited was written), `download.tell_failed` (the interface could not be told about a video that was just stored as synced; the file stays, R-QA-06), `download.temp_left` (the temp folder of a download that ended could not be removed, with `error_code`; the job ends as it would, and the next start sweeps the folder, R-FI-03), `download.temp_swept` (at start, the temp folder of a job that is no longer active was removed, R-QA-06), `download.side_file_skipped` (a file of that name is next to the video, so the thumbnail is not put there). Every line of a download carries its `job_id` (R-LG-02), and the whole output of yt-dlp and ffmpeg goes into the log of the job |
| ffprobe | `ffprobe.ran` (debug: ffprobe read a file, with its exit code) |
| log | `log.jobs_deleted` (the clean-up at start deleted logs of jobs, with their count) |
| file | `file.renamed`, `file.moved`, `file.trashed`, `file.missing`, `file.unreachable` (the folder of a file an interrupted download placed is not there, for example on a drive that is not connected; its marker stays and a later start cleans up), `file.kept` (a file of a removed channel leads out of its folder through a symlink and is not moved to the Trash, R-CH-32, or a file has the name of an interrupted download, or of a video of a removed channel, but another video ID inside, R-QA-06, R-CH-32, or the video ID inside a file of a removed channel could not be read; with `reason` for a removed channel: `another_video` or `not_checked`), `file.move_back_failed` (a file of a download that failed after its move into the channel folder could not be moved back to the temp folder; its marker stays, and the next job of the video or the next start cleans it up, R-QA-06), `file.trash_failed` (a file of a removed channel, or of a download that a quit interrupted, could not be moved to the Trash, with `error_code`; the app goes on) |
| exclude | `exclude.manual`, `exclude.rule`, `exclude.restored` |
| adopt | `adopt.scan`, `adopt.matched`, `adopt.ambiguous`, `adopt.fixed`, `adopt.failed` |
| update | `update.available`, `update.started`, `update.backup`, `update.migrated`, `update.finished`, `update.rolled_back` |
| db | `db.backup` (the database was copied before its migrations, with `file` and `version`, R-QA-07), `db.migration.started`, `db.migration.finished`, `db.unreadable` (the database file cannot be read at start), `db.migration.failed` (with the `step` that failed, `backup`, `migration` or `restore`, its `error_code`, the `backup`, and `restored` when the copy had to be put back; the app does not start) |
| api | `api.request` (debug), `api.error` |
| ui | `ui.error` (forwarded from the frontend) |

## 4. Error codes

Defined once in `backend/ytmirror/core/errors.py`. Each code has: a name, whether it is permanent or transient, and a key for its user-facing text (what happened, what the app does, what the user can do).

| Code | Kind | Meaning |
|---|---|---|
| `NETWORK_UNREACHABLE` | transient | No connection to YouTube |
| `RATE_LIMITED` | transient | YouTube asked us to slow down |
| `BOT_CHECK` | transient | YouTube refused the request with its check "Sign in to confirm you're not a bot". It depends on the network address the request comes from. The whole app pauses what it asks of YouTube by itself (R-ER-05). Never shown once per video |
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
| `CHANNEL_BUSY` | transient | A removal found a download or a check of the channel still running after its wait. The channel and its files stay; its waiting checks were dropped and, once no check ran, its downloads were cancelled (R-CH-32) |
| `DB_UNREADABLE` | permanent | At start the database file cannot be read, or a copy could not be put back after a failed update: the file itself may be damaged. The app does not start and names the backup if there is one (R-QA-07) |
| `DB_UPGRADE_FAILED` | permanent | A migration failed at start. The database is left as it was, a backup was made before, and the app does not start (R-QA-07) |
| `TOOL_MISSING` | transient | ffmpeg, Deno or yt-dlp is not usable |
| `CHANNEL_NOT_FOUND` | permanent | |
| `INVALID_CHANNEL_INPUT` | permanent | What the user pasted is not a channel |
| `UNAUTHORIZED` | permanent | A request to the local API came without the session token, or with a wrong one |
| `ORIGIN_REJECTED` | permanent | A request to the local server came from another website or was addressed to another host (R-PL-04) |
| `NOT_FOUND` | permanent | There is nothing at the requested address of the local server |
| `INVALID_REQUEST` | permanent | A request to the local API is malformed |
| `LOCAL_SERVER_UNREACHABLE` | transient | The window cannot reach the app's own local server (R-ER-04). This code is raised by the window, never sent by the server |
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
