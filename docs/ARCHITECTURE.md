# yt-mirror V1: Architecture

This document says **how** the app is built. What it must do is in [SPEC.md](SPEC.md). The reasons behind the choices are in [DECISIONS.md](DECISIONS.md).

Items marked `VERIFY` are assumptions that the implementer must confirm with a small experiment before relying on them. They are collected in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md).

---

## 1. Overview

```
+--------------------------- one process on the user's Mac ---------------------------+
|                                                                                     |
|  App window (pywebview, macOS WebKit)                                               |
|     |  loads http://127.0.0.1:<port>/                                               |
|     v                                                                               |
|  Frontend (Vue 3 single-page app, static files)                                     |
|     |  REST (JSON) for commands and queries, Server-Sent Events for live updates    |
|     v                                                                               |
|  API layer (FastAPI)                                                                |
|     v                                                                               |
|  Services (channels, catalogue, queue, downloads, adoption, dates, updater, ...)    |
|     v                                   v                                           |
|  Core (pure rules and state machine)    Ports (interfaces)                          |
|                                             v                                       |
|                                         Adapters: yt-dlp, YouTube API,              |
|                                         ffmpeg, macOS filesystem, SQLite, GitHub    |
+-------------------------------------------------------------------------------------+
        |                    |                     |
   YouTube            Library folders        data/ (database, logs, cache)
```

One Python process hosts the HTTP server, the worker threads and the window. There is no separate worker process and no message broker.

## 2. Technology

| Area | Choice | Notes |
|---|---|---|
| Language (backend) | Python 3.12 or newer | Managed by `uv`, installed inside the app folder |
| Web framework | FastAPI + Uvicorn | Typed request and response models, OpenAPI schema generated |
| Validation | Pydantic v2 | API schemas and settings |
| Database | SQLite in WAL mode | One file: `data/yt-mirror.db` |
| Database access | SQLAlchemy 2 (typed ORM, explicit sessions) | No lazy loading across layer boundaries |
| Migrations | Alembic | Forward only, numbered, each with a test |
| Downloads | yt-dlp as a Python library | Never the command line |
| Media tools | ffmpeg and ffprobe (downloaded binaries) | Called by yt-dlp and by the repair service |
| JS runtime for yt-dlp | Deno (downloaded binary) | Required by yt-dlp for YouTube since 2025.11.12 |
| HTTP client | httpx2 | YouTube API, GitHub releases, tool downloads, thumbnails. The successor of httpx, also used by the test client (D-041) |
| Logging | structlog writing JSON lines | See [LOGGING.md](LOGGING.md) |
| Window | pywebview (WebKit on macOS) | `--browser` flag opens the default browser instead. What it can do is in section 7.8. The native Mac parts (app bundle, menu bar, single instance) are in section 7.10. The version is pinned exactly, because the menu bar relies on how this version behaves (D-049) |
| Notifications | macOS user notifications through a small adapter | `VERIFY` which mechanism works from an unsigned Python process (Q-07) |
| Frontend | Vue 3, TypeScript (strict), Vite | Single-page app, no server-side rendering |
| Styling | Tailwind CSS with design tokens from [DESIGN.md](DESIGN.md) | Light and dark themes through CSS variables |
| State and routing | Pinia, Vue Router | |
| API client | Types generated from the OpenAPI schema (`openapi-typescript`) | CI fails if generated types are stale |
| Lists | Virtual scrolling | Required by R-UI-07 |
| Backend tests | pytest, pytest-cov, hypothesis for naming and date rules | |
| Frontend tests | Vitest + Vue Testing Library | |
| End-to-end tests | Playwright (WebKit and Chromium) | Against the real backend with a fake YouTube |
| Lint and types | Ruff (lint, format, docstring rules), Pyright (strict), ESLint, Prettier, vue-tsc | |
| Docs site | VitePress | Built from `docs/`, deployed to GitHub Pages |
| CI | GitHub Actions, macOS runners for anything touching file dates | |

Version numbers are pinned in `uv.lock` and `package-lock.json`. The implementer picks the current stable versions at the start and records them in [DECISIONS.md](DECISIONS.md).

## 3. Repository layout

```
yt-mirror/
  start                      Launcher for clones and for the installed app
  install.sh                 Installer, also served by the website (milestone M9)
  pyproject.toml  uv.lock  .python-version
  backend/
    ytmirror/
      core/                  Pure domain code. No I/O, no framework imports.
        models.py            Dataclasses: Settings, the tools, the menu bar, the events, ...
        channels.py          Dataclasses: Channel, Video, what a lookup and a listing give
        channel_input.py     What the user pasted to add a channel (R-CH-01, R-CH-02)
        catalogue.py         What a quick and a full check change in a catalogue (R-CH-12 to R-CH-15)
        identity.py          Name and bundle identifier of an installed copy and of a clone (R-NA-01)
        icon.py              The app icon as data: colours from the tokens, the macOS icon file format
        status.py            Video and channel status machines
        naming.py            Title to file name rules (R-FN-*)
        dates.py             Date handling rules (R-DT-*)
        exact_dates.py       Rules of the exact-date fetch: date states, retries, rate, time left (R-DT-13 to R-DT-15)
        pacing.py            The budget of lookups an hour (R-DT-06, D-084)
        schedule.py          When the app checks channels by itself (R-CH-20 to R-CH-26)
        quality.py           Quality selection rules (R-QL-*)
        jobs.py              Jobs, their states and progress, what a download asks and gives, job log retention
        media.py             What a finished file contains, and whether it passes verification
        exclusion.py         Rule matching (R-EX-*)
        matching.py          Adoption matching (R-AD-*)
        errors.py            Error codes and the error taxonomy
      ports/                 typing.Protocol interfaces, one file per port
      adapters/
        ytdlp_gateway.py     Listing, metadata and downloads through yt-dlp
        fixture_youtube.py   The fake YouTube, read from files, which the app can start with (section 10)
        youtube_api.py       Optional Data API client (exact dates, D-082)
        fixture_youtube_api.py  The fake of the Data API, on the fake YouTube (section 10)
        api_key_file.py      The API key in data/youtube-api-key, 0600 (D-085)
        media_tools.py       Reads a finished file with ffprobe (the MediaTools port)
        filesystem_mac.py    File dates, Trash, reveal, free space, safe moves
        child_processes_mac.py  Stops the tools the app started: all at quit, the ffmpeg of one job at Cancel (the ChildProcesses port)
        notifier_mac.py      macOS notifications
        folder_picker_webview.py  The folder dialog of the app window (section 7.8)
        tool_box.py          Downloads, unpacks, keeps and runs the tools in tools/
        image_cache.py       The pictures of the catalogue as files in data/cache/
        native_app_mac.py    The menu bar, the app's name and the end of the app, through AppKit (section 7.10)
        image_renderer_mac.py  Draws the icon source file into pixels, through AppKit
        github_releases.py   Release lookup and download
        system_clock.py      The real clock behind the Clock port
        system_probe.py      Read-only facts about the Mac, for the environment report
        db/                  SQLAlchemy engine and tables, repositories, the Alembic migrator
      services/
        channels.py          Add, remove, pause, settings, folder moves
        catalogue.py         Checks, new and removed detection, renames
        channel_views.py     Channels as the interface shows them, and what runs on them
        youtube_access.py    Every question to YouTube, and the pause of the whole app (R-ER-05)
        thumbnails.py        The cache of thumbnails and avatars (R-CH-16)
        state.py             The snapshot of the app for the window (section 7.6)
        dates.py             The exact-date fetch, with the key or without, and the key (R-DT-05, R-DT-12)
        date_fetch_state.py  How the fetch stands, in memory, for the views
        scheduler.py         The checks the app starts by itself, and the exact-date fetch (R-CH-20 to R-CH-26)
        queue.py             Queue state, ordering, parallelism, pause, limits
        downloader.py        One job from start to synced (milestone M3: one worker, Cancel, Retry, details)
        download_state.py    The downloads that wait or run, in memory: progress, jobs, "Mirroring X of Y"
        job_logs.py          Deletes the logs of jobs that are no longer kept (R-LG-01)
        adoption.py          Match and repair existing files
        repair.py            Repair dates, rename after a new title (R-DT-09, R-FN-06); repair metadata later
        exclusions.py        Manual excludes and rule engine
        toolchain.py         Install, verify and update ffmpeg, Deno, yt-dlp
        updater.py           App updates, backup, migration, rollback
        diagnostics.py       Health, environment report, health check, debug report
        schema.py            Brings the database schema up to date at start
        settings.py          The general settings
        activity.py          User-facing activity log
        events.py            In-process event bus feeding SSE and notifications
        scheduler.py         Periodic checks while the app is open
      api/
        app.py               Builds the FastAPI app
        routers/             One router per resource
        schemas.py           Pydantic request and response models
        catalogue_schemas.py The same for channels, videos, the snapshot and their events
        pictures.py          Answers a request with a cached picture
        security.py          Host, Origin and session token checks (section 9)
        request_log.py       Request logging and the INTERNAL error boundary
        sse.py               Event stream
        errors.py            Error code to HTTP response mapping
      app/
        container.py         Composition root: builds adapters and services
        main.py              Entry point, CLI flags, lifecycle
        config.py            Paths, environment variables, options
        logging_setup.py     The debug log pipeline
        server.py            The HTTP server thread
        window.py            The app window
        signals.py           Turns Ctrl+C and a termination signal into a request to quit
        single_instance.py   The lock of the data folder, and what a second start does (section 7.10)
        doctor.py            Text of the environment report
        bundle.py            Builds the macOS app bundle (section 7.10, from milestone M1)
        menus.py             The menu bar, defined as data (section 7.10). The app menu and Edit from M1, the rest from M5
      tools/                 Developer programs: python -m ytmirror.tools.<name>
      migrations/            Alembic environment and versions
    tests/
      unit/  integration/  api/  migrations/  live/  fixtures/
      untestable.yml         Requirements that only live or manual tests can cover
  frontend/
    src/
      api/                   Generated types and a thin typed client
      router.ts              The pages and their addresses (Vue Router, hash addresses, D-063)
      stores/                Pinia stores (app, tools, channels, videos, ui, later queue and settings)
      features/              One folder per feature: shell, welcome, channel, setup, tools, later queue, adopt, settings, ...
      format/                How dates, durations, counts and sizes are written, and the clock of the interface
      components/            Shared presentational components
      design/                The theme center: tokens, Tailwind preset, fonts, brand icon, preview page
      i18n/                  All user-visible strings
    tools/                   The theme lint and the API type generator
    tests/
  e2e/                       Playwright tests, their screenshots, and the fake YouTube data set
  scripts/                   Developer and CI programs: uv wrapper, check scripts, smoke test
  docs/                      This documentation and the VitePress site
  .github/                   Workflows and issue templates
  data/                      (ignored) database, logs, backups, cache, the API key file
  tools/                     (ignored) uv, Python, ffmpeg, Deno
```

Modules appear in the milestone that needs them. A file listed here may not exist yet.

## 4. Layer rules

These rules are enforced by an import-linter check in CI.

1. `core` imports nothing from the other packages and performs no I/O. It can be tested with plain values.
2. `ports` contains only interfaces and data types from `core`.
3. `adapters` implement ports. They contain no business rules. An adapter never imports another adapter.
4. `services` contain the use cases. They depend on `core` and `ports`, never on a concrete adapter.
5. `api` translates HTTP to service calls and back. No business logic, no database access.
6. `app/container.py` is the only place that knows which adapter implements which port. Tests build the same container with fakes.

Dependency direction: `api -> services -> core` and `services -> ports <- adapters`.

## 5. Data model

All timestamps are integers: seconds since the Unix epoch, UTC. All tables have `created_at` and `updated_at`.

### channels
| Column | Type | Notes |
|---|---|---|
| id | text, primary key | YouTube channel ID (`UC...`) |
| url | text | Canonical channel URL |
| title | text | |
| handle | text, null | `@handle` |
| avatar_url | text, null | The address at YouTube. The picture itself is in the image cache |
| folder | text | Absolute path, or relative to the library when not custom |
| folder_is_custom | bool | |
| folder_created | bool | true when the app created the folder. Only such a folder may go to the Trash when a removal leaves it empty (R-CH-32). Migration 0007 |
| quality | text, null | null means "use default" |
| auto_mirror | bool | |
| mirror_after | int, null | Only auto-mirror videos published after this time |
| paused | bool | |
| first_listed_at | int, null | Set when the first full listing completes |
| last_check_at | int, null | Last successful check, quick or full |
| last_full_check_at | int, null | Last successful full check (R-CH-26, R-CH-35) |
| last_check_error | text, null | Error code of the last failed check |
| last_check_error_at | int, null | When that check failed (R-CH-25) |
| position | int | Sidebar order |
| missing_left | int, null | How many missing files the user chose to leave missing; auto-mirror downloads none of them again until more are missing (R-MI-06, D-092). Migration 0011 |
| auto_mirror_asked | bool | false until the user answered whether auto-mirror may start the downloads of the channel (R-MI-02, D-095). Migration 0011 sets it to false for every channel stored with auto-mirror on |

### videos
| Column | Type | Notes |
|---|---|---|
| id | text, primary key | YouTube video ID |
| channel_id | text, foreign key | |
| title | text | Current title on YouTube |
| duration_s | int, null | |
| view_count | int, null | |
| published_at | int, null | See R-DT-*. For an approximate date: the point the listing gave, which is the latest possible date |
| published_exact | bool | false while only an approximate date is known |
| published_precision | text, null | `day`, `week`, `month` or `year` for an approximate date (R-DT-04). null for an exact date and for no date |
| thumbnail_url | text, null | The address at YouTube. The picture itself is in the image cache (R-CH-16) |
| channel_position | int | Order on the channel page, used as a tie-breaker (R-DT-11) |
| status | text | See section 6 |
| excluded | bool | |
| excluded_by | text, null | `manual` or a rule ID |
| exclude_exception | bool | User chose to keep it despite rules (R-EX-07) |
| missing_checks | int | Consecutive successful full checks without this video (R-CH-13) |
| gone | bool | Removed from YouTube |
| first_seen_at | int | |
| last_seen_at | int | The last successful check that listed it (R-DT-01) |
| seen_in_first_listing | bool | false means it can be "new" (R-CH-15) |
| file_name | text, null | Relative to the channel folder. Stored only when the video is recorded as synced |
| placing_file | text, null | The marker of a file being moved into the channel folder: set before the move, cleared in the same write that records the video as synced, or once the file is known to be out of the folder (R-QA-06). Migration 0007 |
| replacing | text, null | The marker of a re-download, as JSON: its job, the identity of the old file, the way the files change places (`swap` or `move`) and the step (`placing`, then `away` once the new file is stored). Set before anything moves, cleared only when the old file is in the Trash or the hidden folder. Nothing removes the temp folder of the job it names (R-QL-06, D-093). Migration 0011 |
| rename_from, rename_to | text, null | The marker of a rename after a new title (R-FN-06): set before the move, cleared in the same write that stores the new name. A rename the app's end interrupted is finished (the file is under the new name with this video's ID inside) or undone at the next check, whatever the title is by then. A check never writes these columns. Migration 0010 |
| file_size | int, null | |
| height | int, null | Downloaded height |
| vcodec, acodec | text, null | |
| has_subtitles | text, null | `manual`, `auto` or null |
| downloaded_at | int, null | |
| last_error_code | text, null | |
| last_error_at | int, null | |
| attempts | int | Automatic attempts since the last success |

Indexes: `(channel_id, channel_position)`, `(channel_id, status)`, `(status)`.

### jobs
One row per queued or running piece of work on a video. Created by migration 0006 (milestone M3). A row stays after its job ended, so that the clean-up of job logs knows when it ended (R-LG-01). Removing a channel removes the jobs of its videos.

| Column | Type | Notes |
|---|---|---|
| id | text, primary key | ULID. This is the job ID used in logs |
| video_id | text | |
| kind | text | `download`, `redownload`, `repair_metadata`, `adopt_fix` |
| state | text | `waiting`, `running`, `done`, `failed`, `cancelled` |
| priority | int | Lower runs first. Reordering rewrites priorities |
| quality | text | Resolved quality at enqueue time |
| progress | real, null | Persisted occasionally. Live progress is in memory |
| stage | text, null | `video`, `audio`, `processing` |
| error_code | text, null | |
| started_at, finished_at | int, null | |
| by_hand | bool | Whether the user started the job by hand: such a job is never held back by the lookup budget, an automatic one waits for room (R-DT-06, D-090). Migration 0011; earlier jobs count as started by hand |
| not_before | int, null | The earliest time an automatic retry may start (R-QU-07). Migration 0011 |
| formats | text, null | The formats the download chose (`399+251`), asked for again when it continues after a quit (R-QU-05, D-091). Migration 0011 |

### video_events
Append-only history required by R-LG-03: `id`, `video_id`, `at`, `from_status`, `to_status`, `reason`, `job_id`. Created by migration 0006. A status change is written in the same transaction as the job and the video (the JobRepository port). The JobRepository writes only the columns of a video that a download owns (status, file, exact date, last failure), and a check writes only the others, so that a check that runs during a download never undoes it.

### pending_side_files
A side file of a synced video that could not be written: `id`, `video_id` (removed with the video), `path` (relative to the channel folder), `data`, `created_at`, `updated_at`. Created by migration 0008. The downloader writes it again at start and after every job, and removes the row once it is written or its video is no longer synced.

### exclude_rules
`id`, `channel_id`, `kind` (`title_contains`, `shorter_than`), `value`, `enabled`.

### activity
User-facing log (R-AC-*): `id`, `at`, `kind`, `channel_id`, `video_id`, `job_id`, `message_key`, `params` (JSON), `error_code`.

### settings
`key`, `value` (JSON). Keys are defined in one typed model in `core/models.py`.

### app_meta
`key`, `value`. Holds facts the app keeps about itself. From milestone M1: `setup_completed_at`, the moment every tool was in order for the first time (R-IN-03). From M4: `lookup_budget`, the budget of lookups as JSON (the times of the last hour's lookups and the end of a halving), read when first needed, so a restart keeps it (R-DT-06). Later milestones add `app_version`, `install_kind` (`clone`, `archive`) and `last_update_check_at`. The schema version is tracked by Alembic.

### date_fetch_queue
`video_id` (key, removed with its video), `priority` (1 when a decision waits for the date, R-MI-03), `attempts`, `next_try_at`, `last_error`, `api_left_out_at`, `created_at`, `updated_at`. Created by migration 0009. It holds what the exact-date fetch keeps across restarts (R-DT-06): failures and when a video is tried again (R-DT-13), and when the YouTube API last left a video out (D-083). It is not a list of all waiting videos: a video waits while it has no exact date, is not removed and its channel is not paused, and a video without a row simply waits its turn. The order of the fetch: `priority`, then the newest `published_at`, then the place on the channel (`adapters/db/date_repository.py`).

Migration 0009 also adds `channels.check_retries`, the count of automatic retries of a failed check since the last successful one (R-CH-25).

## 6. Status model

### 6.1 Video status (stored)

```
not_downloaded --enqueue--> queued --worker picks--> downloading --streams done--> processing --verified--> synced
      ^                        |                          |                            |
      |<------ cancel ---------+<------- cancel ----------+                            |
      |                                                                                |
      +<----------------------------- failure: status = failed <-----------------------+
failed --retry--> queued
processing --cancel, before the file is moved into its place--> not_downloaded
downloading or processing --YouTube's "not a bot" check (R-ER-05)--> queued
synced --file not found at check--> file_missing --enqueue--> queued
file_missing --the file is back, with this video's ID inside--> synced
```

Rules:
- `excluded`, `gone`, new, approximate date and "below target quality" are flags or derived values, not statuses. They combine with any status.
- A re-download (from M5, D-093) is a job of the kind `redownload` that never changes the status of its video: it stays `synced` with its old file until the new one is swapped in, and stays `synced` when the re-download fails or is cancelled. Its row shows the job's progress.
- Every transition goes through one function in `core/status.py` that validates it and returns the event to record. Nothing else may assign `videos.status`.
- An invalid transition raises a programming error and is logged with both statuses.

### 6.2 Channel status (derived, never stored)

Computed by `core/status.py` from the channel row, its jobs and running background tasks, using the priority in R-FB-01: what is running now comes first, so a check that waits or runs outranks the failure of the check before it (D-076). Stored facts are only `paused`, `last_check_at` and `last_check_error`. Whether a channel waits for YouTube is derived as well: the pause of R-ER-05 is in force and the app would otherwise work on the channel by itself. From milestone M2 that is a first listing that is still to come.

## 7. Key flows

### 7.1 Check a channel (`services/catalogue.py`)

A check is a quick check or a full check (R-CH-12, D-059). Both read the channel's Videos tab through `YouTubeGateway.list_channel`: a listing that is read video by video, newest first, with approximate dates. The reader decides when to stop. yt-dlp fetches the next page of 30 videos only when the reader asks for it, so a listing that is stopped early costs no further request.

Measured in November 2026 on four real channels: a quick check with nothing new took 3 to 5 seconds whatever the size of the channel, and one more page for every 30 new videos. A full check took 12 seconds for 149 videos, 30 seconds for 453 and 7 minutes for 6,597.

**Reading and writing the catalogue**

1. Emit "checking".
2. **Quick check:** read from the newest video and stop after 30 videos in a row that the catalogue already has. A new video in between starts the count again. A channel with fewer videos is read to its end. **Full check:** read everything, and say after every page how many videos were read (R-CH-27). A full check can be cancelled: then nothing is changed and the check counts for nothing.
3. If the listing fails, is cut off, or (full check) returns no video for a channel that had some: record the error code, keep everything as it is (R-CH-13, R-CH-25). Stop. The automatic retry with backoff is built in M4.
4. In one transaction: insert unknown videos, update title, duration and views of the videos that were read, and set their `last_seen_at`. A value the listing did not give never replaces a known one. A video that was read is no longer `gone`, and its `missing_checks` is 0.
   - **Quick check:** the videos that were read take the positions they were read in. The others keep their order behind them. `missing_checks` of a video that was not read is left alone: a quick check never marks anything as removed.
   - **Full check:** every video takes its listed position. `missing_checks` is counted up for every video that was not listed, and `gone` is set where it reaches 2 (R-CH-13). `last_full_check_at` is set. The first full check also sets `first_listed_at`: it is the first listing (R-CH-11), and the videos it finds are not "new" (R-CH-15).
5. The channel's name, handle and avatar address are taken over from the listing.

**Work that follows a check, quick or full (R-CH-28).** Each step is added by the milestone that builds what it needs.

6. Settle the renames the app's end interrupted, from their markers. Then, for each synced file the app named whose name no longer fits its video's title: rename it (R-FN-06) through `filesystem_mac`, never over another file, then set and read back its dates (`services/repair.py`). The marker (`rename_from`, `rename_to`) is stored first, then the file is moved, then the new name is stored and the marker cleared; if storing fails, the file goes back. The names taken in the folder are worked out once per check. The thumbnail next to the video moves with it only when it is the app's own copy. Never through the `placing_file` marker, whose files a start may move to the Trash.
7. Verify that each synced file exists, by name, against one listing of the folder (`services/repair.py`, also when the channel is opened). A listing that fails means the folder is unavailable and nothing is marked; a file that cannot be read is skipped. Missing ones become `file_missing`, and a `file_missing` video whose file is back with its video ID inside becomes `synced` again (R-MI-06). When the channel folder itself is gone from a connected drive, nothing is marked and the channel shows "Folder not found" (D-087); while its drive is not connected, nothing changes (R-QU-11).
8. Run exclusion rules on new videos (R-EX-06).
9. Wake the exact-date fetch: the new videos wait for their exact dates (section 7.4).
10. If dates repair is on, compare file dates with `published_at` and fix differences, then read them back (R-DT-09). "Repair dates" in the channel menu does the same on demand (`POST /channels/{id}/repair-dates`).
11. If auto-mirror is on, enqueue eligible videos (R-MI-02, R-MI-03). From M5 (`services/auto_mirror.py`, `core/auto_mirror.py`): every video that is not excluded, not synced, not removed and not waiting, as automatic downloads (D-090); a failed one only when its failure can pass and it failed at least 6 hours ago (R-QU-09). The date limit decides at once for an exact date and for an approximate one whose whole range lies on one side; any other video goes to the front of the exact-date fetch, which looks it up while downloads run too, within the budget, and auto-mirror runs again when its date arrives. At most 5 missing files are queued again; above that none is, and the channel says how many are missing until the user answers ("Mirror them again" by hand, or "Leave them missing", kept in `channels.missing_left` until more are missing, D-092). A channel whose `auto_mirror_asked` is false, after it was turned on or after migration 0011, starts more than 5 downloads only after the user answered (D-095). Auto-mirror also runs at every start, when it is turned on, and when a paused channel is resumed. A paused channel's downloads stay in line, and its running ones stop as at a quit (R-CH-31).
12. Emit the new channel state, write activity entries, send a notification if there are new videos.

Checks never run side by side: one worker takes them one after another (R-CH-24), so two listings never ask YouTube at the same time. Before every channel of "Check all channels now" but the first, the worker waits a random time of 1 to 3 seconds. The wait ends at once when the app stops or the check is dropped. A video that a check lists and that another channel already has is left out of the check and logged (R-CH-17, D-075): a video has one channel. A first listing that a quit interrupted has written nothing, and is started again at the next start (R-CH-11).

**Approximate dates (R-DT-04, D-060).** The listing gives a point in time, not the words YouTube showed ("2 years ago"). The point is "now minus N units", and it is the latest date the video can have: the real date lies up to one unit before it. `core/dates.py` finds the unit from the point and the time of the listing, with the same arithmetic yt-dlp uses. YouTube counts in days up to 13, in weeks from 2 to 4, in months from 1 to 11, and then in years. Where two units fit, the coarser one is stored. The first approximate date of a video is kept: a later listing never replaces it, because it can only be coarser.

### 7.2 Download one video (`services/downloader.py`)
1. Job becomes `running`. Check the disk guard and the folder (R-QU-10, R-QU-11).
2. Resolve the target file name with `core/naming.py`, including collision handling.
3. Call `ytdlp_gateway.download` with a working directory inside `.yt-mirror/tmp/<job id>/`. Progress callbacks update in-memory progress and are pushed over SSE at most 4 times per second per job. A report that comes sooner is kept back and pushed once the quarter second is over, unless a newer one was pushed by then, so a download that stalls never shows an older percent (R-QU-04).
4. yt-dlp merges to MKV and embeds metadata, chapters, subtitles, thumbnail and the info JSON.
5. Verify the result with ffprobe: it opens, has a video and an audio stream, and its duration is within 2 seconds of the expected one.
6. Take the exact published time from the full metadata. Save the info JSON and thumbnail to `.yt-mirror/`.
7. Move the file to its final name (atomic rename on the same volume). For a re-download, move the old file to the job's temp folder first and delete it only after step 8.
8. Set creation and modification dates and read them back (R-DT-07). A mismatch fails the job with `DATES_NOT_APPLIED`.
9. Update the video row, record the event, write activity, emit the update.
10. On any failure: classify the exception into an error code, clean up temp files except resumable partial downloads, set `failed` or re-queue according to the retry policy (R-QU-07). From M5 (`core/queue.py`): a failure of the network, of YouTube's servers or of a processing step (`RETRIED`) puts the job back in line after 1, 5 and 15 minutes (`jobs.not_before`), keeping its temp folder, as an automatic job (D-090); `videos.attempts` counts these and an action of the user sets it back to 0. After the third the video is `failed`. A permanent failure fails at once; YouTube's check, a full disk and a folder that cannot be reached pause instead (R-ER-05, R-QU-10, R-QU-11).

**The speed limit, the disk guard and a folder away (from M5).** The speed limit (R-QU-03, `services/speed_limit.py`) is one rate that every running download shares: the downloader counts the bytes of each progress report, and the progress hook waits for its share of time, in steps of a tenth of a second that end at a cancel, so yt-dlp reads its next block only then. The disk space guard (R-QU-10) reads the free space of a job's volume before it starts and every 5 seconds while it runs; below the setting (10 GB) the queue pauses, the running downloads stop as at a quit, and the summary of the queue carries the disk for the banner. A write that fails for lack of space (`DISK_FULL`) does the same. "Resume anyway" leaves that disk alone until it had room again; the pause also ends by itself when a waiting worker finds room again (it looks every minute). A channel folder that cannot be reached (R-QU-11) holds the downloads of that channel in line instead of failing them; they go on after "Try again", or when a check or the opening of the channel finds the folder (`tidy`).

**Stop and continue (D-091, from M5).** A quit, a crash, "Pause all" and YouTube's "not a bot" check stop a download instead of cancelling it: the job goes back to `waiting` with its priority, its video from downloading or processing to `queued`, and its temp folder stays with the partial and finished streams. yt-dlp keeps the files of the job's own folder (`overwrites` off) and continues a partial one with a Range request (shown with the real yt-dlp against a server on this Mac). The job keeps the formats it chose (`jobs.formats`, written only by `set_formats`); when it runs again they come first in the format selector (`399+251/<quality selector>`), so its partial files fit; when YouTube no longer offers them, the selector of the quality decides and the old files are left for the end of the job. A temp folder that holds the finished `<id>.mkv` was stopped while the file was processed: that job starts over, so no processing step runs twice on one file. At start a job left `running` goes back in line in the same way (reason `interrupted`); waiting jobs keep their order (R-QU-06). Cancel by the user and a removal of the channel still delete the temp folder. The sweep of temp folders leaves those of waiting and running jobs, and runs for a channel whenever its folder can be reached: at start, after a check and when the channel is opened (`DownloaderService.tidy`), so a drive that was not connected at start is cleaned up as soon as it is back.

What milestone M3 builds of this flow (`services/downloader.py`): workers take jobs in the order of their priority under a lock and keep everything about a job by its ID; from M5 as many run as the setting allows (section 7.7). Step 1 checks only that the folder is available; the disk guard (R-QU-10) and the retry policy of step 10 (R-QU-07) arrive with M5. Cancel is asked by the hooks of yt-dlp and before the move of step 7, which is the point of no return (R-QU-02). The gateway calls `start_writing` after the metadata lookup, which only reads, and before yt-dlp writes anything; it also creates the job's temp folder. A cancel before that call ends the job at once and abandons the lookup: `start_writing` then refuses it, and its late answer or error is ignored. A removal does not wait for such a job. After a cancel or a failure, the temp folder of the job is deleted. From M5 a quit or a crash keeps it, and the job continues (R-QU-05, R-QU-06, D-091, below). YouTube's "not a bot" check (R-ER-05) puts a running job back in line, and the worker takes no job while the app pauses. A subtitle failure is tried once more without subtitles (R-MD-04). Every file the app puts in a channel folder is known to it at once (R-QA-06):
- Before the move of step 7 the video gets the marker `placing_file`. The name goes into `file_name` only in the write of step 9, which clears the marker. The same write keeps its side files in `pending_side_files`. That write is the point of no return: nothing after it moves, trashes or deletes the file, and the interface is told only after it, where a failure is logged and changes nothing.
- Everything that can fail on its own (reading the side files, the settings) is done before the move. Between the move and that write every line is inside the one `try` whose failure moves the file out of the channel folder again, so it never looks finished. If that move back fails too, the marker stays.
- No path clears a marker without a cleanup. Only the synced write, or the end of a job whose file is known to be out of the folder, clears it. A new job of a video that has a marker first moves the marked file to the Trash (when the video ID inside it matches); while its folder cannot be reached, the job fails with `FOLDER_UNAVAILABLE` and the marker waits for the folder.
- The side files (the info JSON, the thumbnail in the hidden folder, the thumbnail next to the video) are written after step 9. One that fails is logged, the video stays synced, and the file waits in `pending_side_files`.
- A start ends the jobs a quit or a crash left, one at a time. A marked file goes to the Trash only when the video ID inside it is the one of the job; a Trash that refuses is logged and the start goes on.

### 7.3 yt-dlp configuration (in `ytdlp_gateway.py` only)

Verified in milestone M3 against yt-dlp 2026.10.26 with a real download (Q-04, D-078):

- Format selector for height H (`format`): `bv*[height<=H]+ba/b[height<=H]/wv*+ba/w`. For "Best available": `bv*+ba/b` (`core/quality.py`).
- `merge_output_format: mkv`. No re-encoding post-processors: the merger copies the streams (for example AV1 and Opus).
- `outtmpl` writes `<video id>.<ext>` into the temp folder of the job. Template fields are never used for the final name: yt-mirror renames, so the naming rules stay in one tested place.
- `ffmpeg_location` is the folder of the ffmpeg tool, and `js_runtimes` is `{"deno": {"path": <the Deno program of the app folder>}}`. Deno runs with `DENO_DIR` inside the app folder, because Deno otherwise keeps its cache in `~/Library/Caches/deno` (R-PL-15).
- The JavaScript challenge solver is the Python package `yt-dlp-ejs`, locked in the version that yt-dlp pins. `remote_components` is never set, so no solver is fetched from GitHub or npm (D-078). Without the package, yt-dlp warns that solving the challenge failed and offers fewer formats.
- Subtitles: `writesubtitles` with `subtitleslangs: ["en"]` when the metadata has creator subtitles in English, else `writeautomaticsub` when it has auto-generated English ones (two steps: the metadata is read first). A subtitle error triggers one retry of the job without subtitles (R-MD-04).
- `writethumbnail: true`. Post-processors, in this order: `FFmpegEmbedSubtitle`, `FFmpegMetadata` with `add_chapters`, `add_metadata` and `add_infojson`, `EmbedThumbnail`. The thumbnail of YouTube is WebP: it is converted to JPEG for the hidden folder (R-MD-05). `FFmpegMetadata` writes the title, the channel as `ARTIST`, the description, the day (not the time) as `DATE`, and the address as `PURL` and `COMMENT`; the gateway adds the exact published time and the video ID as tags of their own (R-MD-01, R-DT-08).
- `overwrites` is off: the temp folder belongs to one job, so a file in it is this job's own, and a stream that a stopped run left complete is kept (D-091). yt-dlp continues a partial `.part` file by itself.
- `updatetime` is not used. yt-dlp no longer sets file times by default (since 2025.07.21), and yt-mirror sets dates itself in step 8 from `release_timestamp` or `timestamp`.
- A logger object forwards all yt-dlp output to the per-job log file.
- Cancellation: an exception raised in a `progress_hooks` function (while bytes arrive) or a `postprocessor_hooks` function (between post-processing steps; the step names in the hook are `Merger`, `EmbedSubtitle`, `Metadata`, `EmbedThumbnail`, `MoveFiles`) ends the download at once and reaches the caller unchanged. A running ffmpeg step is not interrupted: the next hook ends the job. Everything left behind is inside the temp folder of the job, which is then deleted (R-FI-03).
- yt-dlp warns that no impersonation target is available (it would need `curl_cffi`). Downloads work without it, so it is not installed.

**Listing and channel lookup (verified in milestone M2 against yt-dlp 2026.10.26, D-059, D-061).**

- The address is always the channel's Videos tab (`.../videos`). Without the tab a channel can come back as a list of its tabs, and Shorts and streams must not be listed (R-CH-07). An entry that yt-dlp marks as a live stream or a past live stream is left out.
- `extract_flat: in_playlist`, and `extract_info(..., process=False)`: the entries then are a generator that fetches one page when asked.
- Extractor arguments: `youtubetab: approximate_date`, without which a listing has no dates at all, and `youtube: raise_incomplete_data`, without which yt-dlp ends a cut-off listing as if it were complete. A cut-off listing would count videos as missing.
- A listing gives per video: ID, title, duration, a rounded view count, one or two thumbnail addresses and the approximate date. Duration and view count are missing on a few. It never gives a description or an exact date.
- A channel without a Videos tab ("This channel does not have a videos tab") has an empty catalogue. It is not an error.
- Timeouts and retries are set by the app. With yt-dlp's defaults a stalled connection is reported only after about 160 seconds.
- yt-dlp writes no cache outside the app folder.
- A lookup reads the channel's facts without reading its videos: channel ID, name, handle, address, avatar. There is no video count in them. The count of the preview (R-CH-03) comes from the playlist `UULF<channel id without UC>`, which holds the channel's long videos. This is a convention of YouTube that is documented nowhere, so the count is optional in every respect (D-061).
- Every error text of yt-dlp is turned into an error code in this adapter. A text it does not know is logged in full and becomes `YOUTUBE_CHANGED`.

### 7.4 Exact dates (`services/dates.py`)
- With an API key: `videos.list` with `part=snippet,liveStreamingDetails`, 50 IDs per request (1 quota unit per request, default quota 10,000 units per day), for the videos without an exact date, after every check. No pass over the uploads playlist (D-082). The exact time is `liveStreamingDetails.actualStartTime` when it is there, else `snippet.publishedAt` when there are no `liveStreamingDetails`; with `liveStreamingDetails` and no actual start the video has not been released and gets none (R-DT-03). A video missing from the answer keeps its date and its status (D-083). The key is sent in the `X-Goog-Api-Key` header, never in an address, so it cannot appear in an error text. The API is asked during the pause of R-ER-05 too.
- Without a key: one metadata lookup at a time through yt-dlp, within the lookup budget it shares with the metadata lookups of downloads (D-084, R-DT-06), held while downloads are running or after any rate-limit signal (back off 15 minutes, doubling up to 6 hours), and under the pause of the whole app after a "not a bot" check (R-ER-05).
- What one lookup costs was measured in milestone M2 on 32 videos from the maintainer's network (D-072). With yt-dlp's default options: 10.3 seconds. With the lightest options that still return the exact time (the `web` client, `player_skip: configs, js`, `skip: hls, dash, translated_subs`, `process=False`): 3.5 seconds. Lookups in parallel with these options: 2.0 seconds per video with two at a time, 1.4 with three, 0.9 with four, without an error in 96 lookups. No longer run was made, so how many lookups YouTube accepts in a row is still open (Q-08). The rate the app uses and the time it tells the user come from what it measures while it runs, never from a fixed number.
- The lookup takes the release time before the upload time (`core/dates.published_time(release_timestamp, timestamp)`), as a download does. A video yt-dlp marks `is_upcoming` gets no exact date: its `release_timestamp` is only the scheduled time.
- Measured in M4 on a channel of 1,103 videos (OPEN-QUESTIONS, facts of M4): two in parallel, 996 lookups in 25 minutes at 1.4 to 1.7 seconds per video, then YouTube's "not a bot" check, with no `RATE_LIMITED` before it. The pace without a key follows from it (D-084).
- There is no other source without a key. The channel feed (`feeds/videos.xml`) answered "not found" for every channel from three networks during M2 and is not used. A listing, of the channel or of its uploads playlist, has approximate dates only.
- Each exact date found updates `published_at`, sets `published_exact`, clears the precision and the fetch state, and emits `video.updated`. A synced file whose video got an exact time has its dates repaired (R-DT-10).
- The fetch is run by the scheduler (`services/scheduler.py`): one piece of work per step, one API request or one lookup, and the step says how long to wait. It yields to downloads (it runs only while none waits or runs), and while it is held by the pause of R-ER-05 or by its own back-off its channels show "Waiting for YouTube" (R-FB-01). The time left of a channel comes from the measured time per video, waits included, over the last 20 lookups, shown after 5 (R-DT-14); above 10 minutes with no key the channel offers the key (R-DT-15).
- The key (D-085) is read from `data/youtube-api-key` the first time the fetch needs it. A key that is refused is done without until a new key is saved or tested; a used-up quota until the next midnight Pacific time; an unreadable key until it is saved again, with one warning in the log. The key setting and a notice by the progress say so (R-DT-12).
- A download asks YouTube once: it is made from the metadata of the lookup before it (`process_ie_result`, as yt-dlp's `--load-info-json` does), so it counts as one lookup and fetches exactly the streams its progress was planned with (D-088). Metadata whose stream links YouTube refuses (HTTP 403) is read again, once; as a safety net, so is metadata older than 5 minutes as the download starts, which today only a very slow lookup makes. Each such lookup is counted (D-089).
- The lookup budget (D-084, `core/pacing.py`): `YouTubeAccess` counts the metadata lookup of every download and every lookup of the fetch in the hour before; the fetch waits for room and keeps its lookups an equal share of the hour apart (12 seconds at 300). From M5 (D-090) a job records whether it was started by hand (`jobs.by_hand`): the first 20 jobs of one action of the user are, and they are never held by the budget. An automatic job (auto-mirror, an automatic retry, a job beyond the first 20 of one action) starts only while the budget has room (`LookupBudget.room`); a worker then takes the next job started by hand behind it instead. `LookupBudget.free_times` estimates when each paced job may start, counting the room each of them uses in turn; the downloader keeps those times in `DownloadState`, the rows show them ("Waiting · paced to protect your access to YouTube · may start at 14:05"), and a worker looks again when the first of them comes. Mirror or "Mirror first" on a paced job makes it a job started by hand. After a "not a bot" check the budget is halved until midnight in the Mac's time zone. The counts of each hour are logged (`youtube.lookups.hour`).

### 7.5 File dates on macOS (`filesystem_mac.py`)
- Modification and access time: `os.utime`.
- Creation time: `setattrlist` with `ATTR_CMN_CRTIME` through `ctypes` (D-077). It works on APFS and on exFAT. There is no fallback: setting the modification time earlier than the creation time moves the creation time back on APFS only.
- Verification reads `st_birthtime` and `st_mtime`.
- Other operations in this adapter: move to Trash (so deletes are recoverable, `NSFileManager.trashItemAtURL`), reveal in Finder (`open -R`), open with the default app (`open`), free space of a volume, a rename that never overwrites (`renamex_np` with `RENAME_EXCL`), whole-file writes through a hidden temp file, the size of a folder, whether a path leaves a folder through a symlink, the delete of the temp folder of one job, and the delete of one job log. Nothing else is ever deleted for good. A cross-volume move (copy, verify, delete) arrives with the milestone that moves folders.

### 7.6 Events and live updates
- Services publish typed events to an in-process bus (`services/events.py`): `tool.updated` (from milestone M1: the state of a tool and the progress of its download), `channel.updated` (from milestone M2: one channel as the interface shows it, with its derived status and its totals. Published for every change of a channel and exactly once at the end of a check, never once per video), `task.progress` (from M2: how far a first listing or a full check has come), `video.updated`, `job.progress`, `queue.updated`, `activity.added`, `banner.changed`, and from M4 `apikey.changed` (how the key stands, never the key) and `checks.progress` ("Checking channels: 3 of 5", R-CH-20). From M5, `queue.updated` carries how the queue stands (running, waiting and failed counts, the pause of all downloads, the number of places) after every change; the downloads panel loads `GET /queue` again when it hears it. Also from M5, `menu.command` carries a command chosen in the menu bar, which the interface runs as its own control does (D-094), and `quit.asked` says that a quit waits for the question of R-QU-12. An open event stream counts as an interface that can be asked: without one, no quit is held.
- `GET /api/events` is one Server-Sent Events stream per window. Progress events are coalesced. When the app stops, the bus is closed first: every stream ends, so an open window never holds up the shutdown.
- On connect and after a reconnect the frontend refetches snapshots (`/api/state`, the open channel's videos), so a missed event can never leave the UI stale.
- One store of the interface owns the stream (`stores/app.ts`) and passes every event on to the store it belongs to. What the events tell is newer than the answer of a call: the answer to "Check now" is not taken over, and the answer to adding a channel only when no event told about the channel yet (D-073).
- A channel carries three numbers that only grow, so that the interface knows what to load again without comparing times, which are whole seconds (D-073): `catalogue_version` grows with every stored check, and the list of the open channel is loaded again when it changes. `avatar_version` grows when the avatar was cached anew, and is part of the avatar's address. `pictures` grows with every batch of cached pictures. Only a thumbnail that was asked for and was missing is asked for again, once per batch: the pictures of a channel with thousands of videos arrive in hundreds of batches, and a batch must not draw the whole list again.
- `channel.updated` says "checking" before the worker can take the check, so a check that ends at once is never told as checking after it has ended.

### 7.7 Concurrency
- One asyncio event loop for HTTP and SSE.
- Blocking work (yt-dlp, ffmpeg, file operations, database writes from workers) runs in threads. Download workers are a pool as large as the setting "Parallel downloads" (R-QU-01), read each time a job is taken: a higher value adds workers at the next Mirror, and idle workers that are too many end. A worker takes a job only while fewer jobs run than the setting allows. A job cancelled while it only asks YouTube takes no place: its worker is replaced at once and ends when YouTube answers (R-QU-02). Side files that waited are written by one worker at a time.
- One writer at a time per database connection. Each unit of work is a short transaction on its own connection: connections are opened when needed and closed afterwards, not pooled (D-040).
- One lock per channel serialises check, adoption and folder moves for that channel.
- One scheduler thread (`services/scheduler.py`, from M4) starts the checks the app makes by itself (on open, on selection, on the interval, retries, full checks) and runs the exact-date fetch. It waits on a condition until its next work is due or it is woken: by the end of the pause of R-ER-05, by the end of the last download, after a check, or when a key is saved. Nothing is put in line while the pause is in force.

### 7.8 The window (`app/window.py`)

Checked with a probe against pywebview 6.2 on macOS in milestone M0 (open question Q-09):

- **Minimum size:** the window is created with `min_size=(1100, 700)` (R-PL-03). macOS applies it when the user drags the window edge. Code can still resize below it, so the app never resizes the window itself.
- **Closing:** a handler on the window's `closing` event can refuse the close by returning false. The quit confirmation of R-QU-12 uses this.
- **External links:** a link with `target="_blank"` opens in the default browser. A plain link would load inside the app window, and `window.open` does nothing. So every link that leaves the app is written as an anchor with `target="_blank"`, and the frontend never calls `window.open`.
- **Folder picker:** the native folder dialog opens and returns to Python. That it returns the chosen folder still has to be checked by hand once (Q-09).
- **Developer tools:** `./start --debug` enables the WebKit inspector in the window.

### 7.9 Starting the app (`start`, `app/main.py`)

1. `./start` checks macOS and the processor, puts a pinned uv into `tools/` after verifying its SHA-256, and lets uv install the pinned Python and the locked packages into `tools/`. The Python environment holds absolute paths: when it belongs to another place, because the folder was moved or copied, it is removed first and built again (R-IN-05).
2. In a clone it builds the interface with Node.js when `frontend/dist` is missing or older than the sources (D-037). An installed copy ships the built interface.
3. For a run with a window, `python -m ytmirror.app.bundle` makes sure the app bundle in `tools/` is current (section 7.10) and prints the path of the script in it that starts the app. `./start` runs that script. With `--browser`, with `--doctor` and without a window there is nothing for the Dock, and `./start` runs Python directly.
4. `python -m ytmirror.app.main` builds the container, brings the database up to date, starts the HTTP server in a thread on a free port of 127.0.0.1, and opens the window on the main thread with the first URL (section 9). When the window closes, the server stops and the process ends.

Flags: `--debug` (verbose logs, developer tools in the window), `--browser` (default browser instead of the window, quit with Ctrl+C), `--doctor` (print the environment report and exit), `--update` (the updater arrives in milestone M9. Until then it says so and exits with code 2).

`--dev` runs the Vite development server next to the backend. The window shows the development server, which reloads the interface on every change and passes `/api` calls on to the backend. Its origin is accepted only in this mode. Backend code is not reloaded: restart after changing Python. The theme preview page is at `/theme-preview.html` on the development server.

### 7.10 Native Mac app

Requirements R-NA-01 to R-NA-09. Decisions D-044 and D-048 to D-052. The experiment of open question Q-24 showed in milestone M1 that all of this works from a locally built, unsigned bundle: on macOS 15 (Apple Silicon and Intel) and on macOS 27. The parts are built in M1 (bundle, identity, one instance, the app menu and the Edit menu, the shutdown work of the quit path), M5 (the full menu bar, the decision part of the quit path with the quit confirmation), M7 (About window) and M9 (installer).

**App bundle (R-NA-01, R-NA-02).**
- A small program builds the app bundle on the user's Mac: a folder with `Contents/Info.plist` (the name, the bundle identifier, the version from `pyproject.toml`), `Contents/Resources/` with the icon (`.icns`) generated from `frontend/src/design/brand/icon.svg` by the icon build script, and `Contents/MacOS/` with the program macOS starts.
- The same program is used by the installer (bundle in `~/Applications`, milestone M9) and by `./start` on a clone (bundle inside the clone, in the ignored `tools/` folder, milestone M1). `./start` then starts the app through the bundle, so a clone and an installed copy behave alike.
- **How the process gets the identity of the bundle (D-048).** macOS decides which app a process belongs to from the place of its program file. So the program macOS starts is a small shell script (`Contents/MacOS/launch`), and it starts the app's Python through a symbolic link that lies inside `Contents/MacOS` and is named after the app. A copy of the environment's `pyvenv.cfg` in `Contents/` and a link `Contents/lib` to the environment's `lib` folder make that link a full stand-in for the environment's own Python: it finds the same packages. The process then runs inside the bundle, and the Dock, the app switcher, the menu bar and Activity Monitor show the app's name and icon, whether the app was started from Finder or from a terminal. A launcher that starts Python at its own place outside the bundle does not work: started from a terminal, the app shows up as "python".
- The Python must be the one uv manages. A framework build of Python (Homebrew, python.org) restarts itself as its own `Python.app` and appears as "Python". `./start` allows only the managed Python (`UV_PYTHON_PREFERENCE=only-managed`).
- The bundle contains absolute paths, so it is rebuilt when the app folder moved (R-IN-05) and when the app version, the icon source, the token file or the Python environment changed. A file inside the bundle records what it was built from. The bundle is built next to its place and swapped in, so an interrupted start leaves no half-built bundle.
- The icon (`.icns`) is drawn on the user's Mac by AppKit, which reads SVG by itself, so no Node.js is needed. Tests draw the real source file and compare the result with it: the colours of the tokens, the area the source gives the rounded square, transparency outside of it.
- The bundle identifier of an installed copy is `io.github.mderis.yt-mirror` (D-047). It must never change: macOS ties an app's identity, its saved state and its permissions to it. A clone started with `./start` is a different app to macOS: its identifier is `io.github.mderis.yt-mirror.dev` and its name is "yt-mirror (dev)", so a clone and an installed copy can run on one Mac and be told apart (D-051).

**Menu bar (R-NA-03, R-NA-04, R-NA-09).**
- The menus are defined in one module, `app/menus.py`, as data: title, shortcut, the command it sends, and the condition under which it is enabled. This is the source of truth for shortcuts.
- The menu bar is built with AppKit, not with pywebview's menu API (D-049). pywebview's API knows neither shortcuts nor enabling and disabling, and it always adds menus of its own (About, Services, a View menu). One adapter builds the whole menu bar from the data and puts it in place of pywebview's menus when the window is shown. It uses only public calls of pywebview and AppKit.
- This relies on one behaviour of pywebview: it sets its own menus once, when the first window is shown, and not again. So the pywebview version is pinned exactly, and a test asserts the structure of the menu bar, so that an update which breaks it fails CI.
- An item is enabled or disabled while the app runs through the standard AppKit validation: macOS asks before it shows or triggers an item.
- macOS adds items of its own to menus called File, Edit and Window, as it does in every Mac app: Close All, AutoFill, Start Dictation, Emoji & Symbols, Writing Tools and the window arrangement items, depending on the macOS version. They are not ours and are left alone.
- A menu item and the matching control in the interface trigger the same command. The menu never contains logic of its own: it tells the frontend to run a command (for example "add channel"), and the frontend does what its own button would do.
- The frontend tells the backend what is currently possible (is a channel open, is it paused, which view is shown), and the menus are enabled and titled from that.
- The standard items (Hide, Hide Others, Minimize, Zoom, the window list, and the Edit menu for text fields) send the standard AppKit actions. They are not reimplemented. Undo, Redo, Cut, Copy, Paste and Select All work in the text fields of the web view this way.
- "Reload" exists only with `--debug`. It must not take Cmd+R, which belongs to "Check Now". The web view does not reload on Cmd+R by itself.

**Quit, Dock and single instance (R-NA-06 to R-NA-08).**
- There is one quit path (D-052). It has two parts: a decision (may the app quit now?) and the shutdown work (stop the workers and the server, close the database, write the last log line), which runs exactly once, whoever asks.
- **What exists when.** The two parts are built in different milestones:

  | Part | Built in | State after M5 |
  |---|---|---|
  | The shutdown work, for every way of quitting (R-PL-13) | M1 | Exists, with tests that use a real window |
  | Ctrl+C and a termination signal become a quit request | M1 | Exists |
  | The decision: a handler of the `closing` event that can hold a quit | M5 | Exists (`services/ui_bridge.py`, wired in `app/window.py`), with tests that use a real window |
  | The "quit while downloading" confirmation (R-NA-06, R-QU-12) | M5 | Exists (`QuitConfirmDialog.vue`) |
  | Reading the reason of a quit request, so that a logout, a restart and a shutdown are never held for a question | M5 | Exists (`NativeApp.ending_session`). A real logout, restart and shutdown are on the manual checklist |

*The shutdown work (built in M1):*
- It is reached from two ends. Closing the window (the red window button, Cmd+W) ends the window loop, and the code after it runs. Quit ends the process inside AppKit, and the code after the window loop never runs: there the work hangs on AppKit's "will terminate" notification. This covers Cmd+Q, "Quit yt-mirror", Quit in the Dock icon's menu, logout, restart and shutdown.
- Ctrl+C and a termination signal are turned into the same AppKit quit request: Python's `signal` module with a wake-up pipe, because a Python signal handler does not run while AppKit's loop waits.
- At a logout, a restart or a shutdown the app does its shutdown work at once, which holds macOS for that moment, and then lets it go on. This work must stay short: macOS does not wait for an app without limit.
- A handler of an AppKit notification must return nothing. A returned value makes pyobjc raise inside AppKit, and AppKit then drops the event it was handling. In the experiment a logout hung on exactly this.

*The decision (built in M5):*
- Every way of quitting reaches the decision through one public hook, the `closing` event of the pywebview window. The red window button, Cmd+W and "Close Window" reach it directly. Cmd+Q, "Quit yt-mirror", Quit in the Dock icon's menu, logout, restart and shutdown reach it because pywebview asks the same event when AppKit asks whether the app may terminate. The handler runs on the main thread while macOS waits, so it decides from memory only: never from the database.
- The decision holds the quit while at least one download runs and an interface is connected to the event stream: the event answers no, the app and its workers keep running, and the interface asks (`quit.asked`, R-NA-06, R-QU-12). Without a connected interface nothing is held, so the app can never be stuck with nobody to ask. A second quit while the question is open asks again.
- "Quit" in the question (`POST /api/ui/quit`) lets the next quit through and asks the app to quit, which reaches the decision again and passes. "Keep running" closes the question and changes nothing.
- Logout, restart and shutdown are never held for a question. The quit request of macOS is an Apple event whose parameter `kAEQuitReason` (`why?`) says why: `kAEQuitAll`, `kAEReallyLogOut`, `kAERestart` or `kAEShutDown` let the quit through to the shutdown work. Cmd+Q and the menu send no Apple event, and Quit in the Dock sends one without a reason: these may be held.
- Ctrl+C and a termination signal are never held either: the app lets the next quit through before it turns the signal into the quit request.

*Dock and single instance:*
- A click on the Dock icon brings the window to the front (the app has one window, and closing it quits, D-020). This is what AppKit does by itself, also for a minimized window and for a hidden app.
- One instance per data folder, in every mode (D-050). A running app holds a lock on the file `data/instance.lock` and writes its process ID and its bundle into `data/instance.json`. A second start that finds the lock held never loads the window library, so no second Dock icon appears. Started for a window, it asks macOS to open the app bundle again and ends: macOS then brings the running app's window to the front, exactly as a click on the Dock icon does. Started with `--browser` or without a window, it ends with a plain message. When the bundle is opened from Finder or the Dock while the app runs, macOS itself starts no second copy and brings the running app to the front.

**`--browser` and tests.** With `--browser` and in automated tests there is no app window and no menu bar. Everything a menu item does must therefore also be reachable inside the interface (R-UI-13), which the menu design above guarantees.

## 8. HTTP API

All paths are under `/api`. Responses are JSON. Errors use one shape: `{ "error": { "code", "message", "details" } }`. `message` is a short technical sentence. The text the user reads is written per code in the frontend (R-ER-02). `code` is one of the codes of [LOGGING.md](LOGGING.md) section 4, and the generated frontend types know them all. One code is never sent by the server: `LOCAL_SERVER_UNREACHABLE` is raised by the window itself when the server does not answer (R-ER-04).

| Method and path | Purpose |
|---|---|
| GET `/health` | The server runs: app version and database schema version |
| GET `/state` | App snapshot: channels with derived status, queue summary, banners, settings, versions. From M2: the channels, the channel that was open last, the library and its disk, whether a folder can be chosen, and the pause of YouTube |
| PUT `/state/open-channel` | Remember which channel is open, for the next start (R-UI-02) |
| POST `/youtube/try-now` | End the pause after a "not a bot" check and take up the work that waited (R-ER-05) |
| GET `/events` | Server-Sent Events stream |
| POST `/channels/lookup` | Resolve a URL or handle to a channel preview (R-CH-03). The video count is not in it |
| GET `/channels/lookup/{id}/video-count`, `/channels/lookup/{id}/avatar` | The optional video count of a preview, which waits at most 8 seconds (D-061), and its avatar |
| POST `/folders/choose` | Show the folder dialog of macOS and return the chosen folder (R-CH-05) |
| POST `/channels` | Add a channel |
| GET, PATCH, DELETE `/channels/{id}` | Read, change settings (from M2: pause and resume), remove (`keep_files` flag from M3) |
| POST `/channels/{id}/check` | Check now (`kind`: `quick` or `full`; `trigger`: what the user pressed, `button`, `menu` or `retry`, logged with the check; `api` when it names none) |
| POST `/channels/{id}/check/cancel` | Cancel a full check (R-CH-27) |
| POST `/channels/check-all` | Check all channels |
| POST `/channels/{id}/mirror-missing` | Queue everything eligible once, by hand (R-MI-04). From M5 |
| PUT `/channels/{id}/auto-mirror`, POST `/channels/{id}/auto-mirror/answer`, POST `/channels/{id}/missing/leave` | Turn auto-mirror on or off; answer the question before a large start (`mirror_all`, `only_new`, `turn_off`, D-095); leave the missing files missing (D-092). From M5 |
| POST `/channels/{id}/open-folder` | Open in Finder |
| GET `/channels/{id}/videos` | The catalogue (all rows, compact fields) |
| GET `/channels/{id}/avatar`, `/videos/{id}/thumbnail` | A cached picture, or `NOT_FOUND` at once when it is not cached (R-CH-16, D-067) |
| GET `/videos/{id}` | Full details for the panel (from M3: the facts of the file, read with ffprobe, and the description and chapters of the saved metadata) |
| POST `/videos/mirror` | Queue videos (`ids`, optional `first` from M5). From M3 |
| POST `/videos/{id}/retry` | Put a failed video in line again (R-QU-08). From M3 |
| GET `/channels/{id}/files-to-trash` | How many files and how much room "Delete the files" moves to the Trash (R-CH-32). From M3 |
| POST `/videos/exclude` , `/videos/restore` | Exclude and restore (`ids`, `file_action`) |
| POST `/videos/redownload` | Download synced videos again in the quality of their channel; each file is swapped for the new one once that is verified (R-QL-06, D-093). From M5 |
| POST `/videos/repair-metadata` | From M8 |
| POST `/videos/{id}/play`, `/videos/{id}/reveal` | By video ID, never a path (R-UI-10). From M3 |
| GET `/queue` | Full queue: the downloads that run and wait, in their order, and the failed videos (R-QU-02, R-QU-08). From M5 |
| POST `/queue/pause`, `/queue/resume`, `/queue/reorder`, `/queue/clear-waiting` | Pause and resume all downloads (stored, so a restart keeps it), put the waiting ones in a new order, remove every waiting one (R-QU-02). From M5 |
| POST `/queue/speed-limit`, `/queue/resume-anyway`, `/queue/folders/{channel_id}/try-again` | The limit of all downloads together (`mbps`: 0, 5, 2 or 1, R-QU-03); go on although the disk guard paused (R-QU-10); look again whether a channel folder can be reached (R-QU-11). From M5 |
| POST `/jobs/{id}/cancel` | Cancel a job that waits or runs (R-QU-02). From M3 |
| PUT `/ui/state` | What the interface tells the app about itself, for the menu bar: whether a channel is open, paused, checking, has videos to mirror and a folder that can be reached, the view, and whether any channel is not paused (R-NA-04, D-094). From M5 |
| POST `/ui/quit` | Quit although downloads run: "Quit" in the question of R-QU-12. From M5 |
| GET, PUT `/channels/{id}/exclude-rules` | Rules, with `POST .../preview` (R-EX-06) |
| POST `/channels/{id}/adopt/scan`, GET `.../adopt`, POST `.../adopt/apply` | Adoption (R-AD-*) |
| POST `/channels/{id}/repair-dates` | Repair the dates of a channel's synced files now (R-DT-09). From M4 |
| GET, PATCH `/settings` | From M7 |
| GET, PUT, DELETE `/settings/api-key` | How the API key stands (never the key), save a key, remove it (R-DT-12). From M4 |
| POST `/settings/api-key/test` | Ask the YouTube API once with a pasted key or the saved one (R-DT-12). From M4 |
| GET `/activity` | Paged, filterable |
| GET `/errors/{code}` and GET `/jobs/{id}/log` | Error text and technical details |
| GET `/tools`, POST `/tools/{name}/install`, POST `/tools/ytdlp/update` | Toolchain |
| GET `/update`, POST `/update/apply`, POST `/update/skip` | App update |
| POST `/diagnostics/health-check`, POST `/diagnostics/debug-report` | |
| POST `/app/uninstall`, POST `/app/quit` | |
| POST `/client-log` | Frontend errors forwarded to the log |

The OpenAPI schema generated by FastAPI is the contract. Frontend types are generated from it.

Outside `/api`, and without the session token: the built interface, and the app icon as `/favicon.svg` and `/favicon.png`, made from the icon source file (D-064).

## 9. Security

- Bind to 127.0.0.1 on a random free port. Reject requests whose `Host` or `Origin` header is not that address (protects against DNS rebinding and other websites calling the local API).
- A random session token is created at start and given to the window in the initial URL (`/?token=...`). The server answers that URL by setting the token as a cookie (`ytm_session`, HttpOnly, SameSite=Strict) and redirecting to `/`, so the token leaves the address bar and scripts cannot read it (D-038). Every `/api` call must carry the cookie. Tests and tools may send the same token as an `Authorization: Bearer` header instead. A wrong or missing token is answered with `UNAUTHORIZED`, a foreign Host or Origin with `ORIGIN_REJECTED`.
- The interface files themselves need no token: they contain no secrets.
- The OpenAPI schema and the interactive API docs are not served by the running app.
- No remote content is rendered as HTML. Descriptions are shown as text.
- File operations accept video and channel IDs, never paths from the client, except folder choices that come from the native folder picker.
- Downloaded tools and releases are verified against SHA-256 checksums before use.
- The API key is never stored in the database, a settings file, a log or an error text; the debug report says only whether one is set (R-SE-03). It is kept in `data/youtube-api-key`, a file only the user can read (0600), written atomically, and read only when the exact-date fetch first needs it (D-085). Its value is registered with the redactor of the logs (R-LG-07) whenever the app holds it.

## 10. Testing seams

Every external dependency is behind a port, and each port has a fake in `backend/tests/fixtures/fakes/`. The one exception is the fake YouTube: the real app must be able to start with it, and the app is installed without its tests, so it is an adapter of the app (D-062).

| Port | Fake behaviour |
|---|---|
| YouTubeGateway | Serves channels and videos from JSON fixtures, simulates progress, failures by error code, rate limits. This one fake is part of the app: `adapters/fixture_youtube.py` (D-062) |
| ExactDateSource | The fake of the YouTube API, `adapters/fixture_youtube_api.py`, answers from the videos of the fake YouTube and fails by its key: one that starts with `fixture-invalid` is refused, one with `fixture-quota` is out of quota. Part of the app like the fake YouTube, so the app started with `YTM_FAKE_YOUTUBE` takes a key without the network. The real adapter is tested against a local server that answers like the API |
| ApiKeyStore | Keeps the key in memory and can be made unreadable. The file of the app is tested on a temp folder |
| DateRepository | None: the services are tested on a migrated database in a temp folder |
| MediaTools | Creates tiny real MKV files with ffmpeg in integration tests, a pure fake in unit tests |
| FileSystem | Real temp directories on macOS runners, an in-memory fake in unit tests |
| ChildProcesses | No fake: the downloader is given a function to call at quit, which unit tests replace. The adapter is tested with processes the test starts itself. Cancel finds the ffmpeg of a job by the job's temp folder in its arguments; a media test runs real yt-dlp through every ffmpeg step the app uses (merge, thumbnail, subtitles, metadata, cover) and checks that each call names that folder (yt-dlp passes it as `file:<path>`) |
| Releases | Serves fake release archives for updater tests |
| Notifier, Clock, Random | Recorders and controllable values |

The environment variable `YTM_FAKE_YOUTUBE=<fixtures dir>` starts the real app with the fake gateway. End-to-end tests and screenshot generation use it. See [TESTING.md](TESTING.md).

Environment variables, all optional. Only `app/config.py` and `start` read them.

| Variable | Read by | Purpose |
|---|---|---|
| `YTM_HOME` | app | The folder that holds `data/` and `tools/`. Set by `./start` |
| `YTM_DATA_DIR` | app | A different data folder. For tests |
| `YTM_PORT` | app, `start`, Vite | A fixed port instead of a free one. For tests and `--dev` |
| `YTM_SESSION_TOKEN` | app | A fixed session token instead of a random one. For tests only |
| `YTM_NO_WINDOW` | app | Serve without opening a window or a browser, until a stop signal. For tests |
| `YTM_FRONTEND_URL` | app | The address of the development server. Set by `./start --dev`, ignored without `--dev` |
| `YTM_FAKE_YOUTUBE` | app | A folder with a recorded world of channels (`e2e/fixtures/youtube/`). The app then never talks to the real YouTube. For tests and for reproducing a problem |
| `YTM_LIBRARY_DIR` | app | The default of the library folder instead of `~/Movies/YouTube`. For tests, so that no test creates a folder in the user's own library |
| `YTM_TRASH_DIR` | app | A folder that stands for the Trash of macOS: files that "Delete the files" moves to the Trash go there. For tests, so that no test fills the Trash of the person who runs it. It counts only together with `YTM_FAKE_YOUTUBE`: an app on the real YouTube always uses the Trash of macOS |
| `YTM_FAKE_FREE_SPACE_FILE` | app | A file whose number, in bytes, stands for the free space of every disk, read each time the disk space guard looks (R-QU-10). For tests, so that the guard never depends on the Mac that runs them. It counts only together with `YTM_FAKE_YOUTUBE` |
| `YTM_FAKE_LOOKUPS_PER_HOUR` | app | The budget of exact-date lookups an hour instead of 300 (D-084), or 0 for no lookups without a key. For the end-to-end tests: their apps use 0, so the dates of M2 and M3 stay as recorded, and the tests of exact dates use a fast pace. It counts only together with `YTM_FAKE_YOUTUBE`: an app on the real YouTube always keeps to 300 |
| `YTM_FAKE_HOLD_DOWNLOADS` | app | `1` makes the fake YouTube hold the downloads of the videos that name a hold (`hold_after_report`, `hold_ms`), so the end-to-end tests can record a row in the middle of a download. Off otherwise, so a hand run never waits. It counts only together with `YTM_FAKE_YOUTUBE` |
| `YTM_YOUTUBE_API_KEY` | live tests, probes | A YouTube API key for measurements and, from M4, live tests. The app does not use it: its key is saved through the key guide into `data/youtube-api-key` (R-DT-12, D-085). Its value is a secret of the logs, so the app removes it from every line (R-LG-07). Never written to a file, a fixture or a commit |
| `YTM_TOOL_DIR` | app | Another folder for the downloaded tools than `tools/`. The end-to-end tests use it, so that their stand-in tools never replace real ones |
| `YTM_TOOL_MANIFEST` | app | Another tool manifest than the one of the app. The end-to-end tests point it at small stand-ins for the tools, served from this Mac |
| `YTM_TOOL_SOURCE` | app | Use only the tool source of this name. The automated checks install from each source on its own (D-053) |
| `YTM_WINDOW_REPORT` | app | A file to which the app writes what macOS shows of it, once the window is up: its name, its bundle identifier and its menu bar. For tests |
| `YTM_UV_BASE_URL` | `start` | Where uv is downloaded from. For tests. The checksum is checked in every case |
| `YTM_E2E_CHROME_CHANNEL` | Playwright | Use an installed Chrome where Playwright's Chromium cannot be downloaded |
