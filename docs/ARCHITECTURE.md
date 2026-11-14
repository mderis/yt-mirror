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
        quality.py           Quality selection rules (R-QL-*)
        exclusion.py         Rule matching (R-EX-*)
        matching.py          Adoption matching (R-AD-*)
        errors.py            Error codes and the error taxonomy
      ports/                 typing.Protocol interfaces, one file per port
      adapters/
        ytdlp_gateway.py     Listing, metadata and downloads through yt-dlp
        fixture_youtube.py   The fake YouTube, read from files, which the app can start with (section 10)
        youtube_api.py       Optional Data API client (exact dates)
        media_tools.py       ffmpeg and ffprobe operations
        filesystem_mac.py    File dates, Trash, reveal, free space, safe moves
        notifier_mac.py      macOS notifications
        tool_box.py          Downloads, unpacks, keeps and runs the tools in tools/
        native_app_mac.py    The menu bar, the app's name and the end of the app, through AppKit (section 7.10)
        image_renderer_mac.py  Draws the icon source file into pixels, through AppKit
        github_releases.py   Release lookup and download
        system_clock.py      The real clock behind the Clock port
        system_probe.py      Read-only facts about the Mac, for the environment report
        db/                  SQLAlchemy engine and tables, repositories, the Alembic migrator
      services/
        channels.py          Add, remove, pause, settings, folder moves
        catalogue.py         Checks, new and removed detection, renames
        dates.py             Exact date fetching and date repair
        queue.py             Queue state, ordering, parallelism, pause, limits
        downloader.py        One job from start to synced
        adoption.py          Match and repair existing files
        repair.py            Repair metadata, repair dates
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
      stores/                Pinia stores (app, channels, videos, queue, settings, ui)
      features/              One folder per feature: channel, queue, adopt, settings, ...
      components/            Shared presentational components
      design/                The theme center: tokens, Tailwind preset, fonts, brand icon, preview page
      i18n/                  All user-visible strings
    tools/                   The theme lint and the API type generator
    tests/
  e2e/                       Playwright tests, their screenshots, and the fake YouTube data set
  scripts/                   Developer and CI programs: uv wrapper, check scripts, smoke test
  docs/                      This documentation and the VitePress site
  .github/                   Workflows and issue templates
  data/                      (ignored) database, logs, backups, cache
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
| quality | text, null | null means "use default" |
| auto_mirror | bool | |
| mirror_after | int, null | Only auto-mirror videos published after this time |
| paused | bool | |
| first_listed_at | int, null | Set when the first full listing completes |
| last_check_at | int, null | Last successful check, quick or full |
| last_full_check_at | int, null | Last successful full check (R-CH-26, R-CH-35) |
| last_check_error | text, null | Error code of the last failed check |
| position | int | Sidebar order |

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
| file_name | text, null | Relative to the channel folder |
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
One row per queued or running piece of work on a video.

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

### video_events
Append-only history required by R-LG-03: `id`, `video_id`, `at`, `from_status`, `to_status`, `reason`, `job_id`.

### exclude_rules
`id`, `channel_id`, `kind` (`title_contains`, `shorter_than`), `value`, `enabled`.

### activity
User-facing log (R-AC-*): `id`, `at`, `kind`, `channel_id`, `video_id`, `job_id`, `message_key`, `params` (JSON), `error_code`.

### settings
`key`, `value` (JSON). Keys are defined in one typed model in `core/models.py`.

### app_meta
`key`, `value`. Holds facts the app keeps about itself. From milestone M1: `setup_completed_at`, the moment every tool was in order for the first time (R-IN-03). Later milestones add `app_version`, `install_kind` (`clone`, `archive`) and `last_update_check_at`. The schema version is tracked by Alembic.

### date_fetch_queue
`video_id`, `attempts`, `next_try_at`. Work list for R-DT-05 and R-DT-06 so it survives restarts.

## 6. Status model

### 6.1 Video status (stored)

```
not_downloaded --enqueue--> queued --worker picks--> downloading --streams done--> processing --verified--> synced
      ^                        |                          |                            |
      |<------ cancel ---------+<------- cancel ----------+                            |
      |                                                                                |
      +<----------------------------- failure: status = failed <-----------------------+
failed --retry--> queued
synced --file not found at check--> file_missing --enqueue--> queued
synced --redownload--> queued (the old file stays until the new one is verified)
```

Rules:
- `excluded`, `gone`, new, approximate date and "below target quality" are flags or derived values, not statuses. They combine with any status.
- Every transition goes through one function in `core/status.py` that validates it and returns the event to record. Nothing else may assign `videos.status`.
- An invalid transition raises a programming error and is logged with both statuses.

### 6.2 Channel status (derived, never stored)

Computed by `core/status.py` from the channel row, its jobs and running background tasks, using the priority in R-FB-01. Stored facts are only `paused`, `last_check_at` and `last_check_error`.

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

6. For each title that changed on a synced video: rename the file (R-FN-06) through `filesystem_mac`, then restore its dates.
7. Verify that each synced file exists. Missing ones become `file_missing` (R-MI-06), unless the channel folder itself is unavailable (R-QU-11).
8. Run exclusion rules on new videos (R-EX-06).
9. Queue the videos without an exact date in `date_fetch_queue`.
10. If dates repair is on, compare file dates with `published_at` and fix differences (R-DT-09).
11. If auto-mirror is on, enqueue eligible videos (R-MI-02, R-MI-03).
12. Emit the new channel state, write activity entries, send a notification if there are new videos.

Checks never run side by side: one worker takes them one after another (R-CH-24), so two listings never ask YouTube at the same time. A first listing that a quit interrupted has written nothing, and is started again at the next start (R-CH-11).

**Approximate dates (R-DT-04, D-060).** The listing gives a point in time, not the words YouTube showed ("2 years ago"). The point is "now minus N units", and it is the latest date the video can have: the real date lies up to one unit before it. `core/dates.py` finds the unit from the point and the time of the listing, with the same arithmetic yt-dlp uses. YouTube counts in days up to 13, in weeks from 2 to 4, in months from 1 to 11, and then in years. Where two units fit, the coarser one is stored. The first approximate date of a video is kept: a later listing never replaces it, because it can only be coarser.

### 7.2 Download one video (`services/downloader.py`)
1. Job becomes `running`. Check the disk guard and the folder (R-QU-10, R-QU-11).
2. Resolve the target file name with `core/naming.py`, including collision handling.
3. Call `ytdlp_gateway.download` with a working directory inside `.yt-mirror/tmp/<job id>/`. Progress callbacks update in-memory progress and are pushed over SSE at most 4 times per second per job.
4. yt-dlp merges to MKV and embeds metadata, chapters, subtitles, thumbnail and the info JSON.
5. Verify the result with ffprobe: it opens, has a video and an audio stream, and its duration is within 2 seconds of the expected one.
6. Take the exact published time from the full metadata. Save the info JSON and thumbnail to `.yt-mirror/`.
7. Move the file to its final name (atomic rename on the same volume). For a re-download, move the old file to the job's temp folder first and delete it only after step 8.
8. Set creation and modification dates and read them back (R-DT-07). A mismatch fails the job with `DATES_NOT_APPLIED`.
9. Update the video row, record the event, write activity, emit the update.
10. On any failure: classify the exception into an error code, clean up temp files except resumable partial downloads, set `failed` or re-queue according to the retry policy (R-QU-07).

### 7.3 yt-dlp configuration (in `ytdlp_gateway.py` only)

- Format selector for height H: `bv*[height<=H]+ba/b[height<=H]/wv*+ba/w`. For "Best available": `bv*+ba/b`.
- `merge_output_format: mkv`. No re-encoding post-processors.
- Subtitles: request English creator subtitles. Request auto-generated English only if no creator subtitles exist (two-step: inspect metadata first, then set `writeautomaticsub`). A subtitle error triggers one retry of the job without subtitles (R-MD-04).
- Post-processors, in this order: embed subtitles, metadata with chapters and attached info JSON, embed thumbnail.
- `updatetime` is not used. yt-dlp no longer sets file times by default (since 2025.07.21), and yt-mirror sets dates itself in step 8 from `release_timestamp` or `timestamp`.
- Template fields are never used for the final name. yt-dlp writes to a temp name (`<video id>.<ext>`), and yt-mirror renames. This keeps naming rules in one tested place.
- A logger object forwards all yt-dlp output to the per-job log file.
- Cancellation: progress hooks raise `DownloadCancelled` when the job is cancelled or the queue is paused.
- JavaScript runtime: the path of the bundled Deno binary is passed explicitly.

`VERIFY` each option name against the pinned yt-dlp version when implementing (Q-04).

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
- With an API key: `videos.list` with `part=snippet,liveStreamingDetails`, 50 IDs per request (1 quota unit per request, default quota 10,000 units per day).
- Without a key: one metadata lookup per video through yt-dlp, paused while downloads are running or after any rate-limit signal (back off 15 minutes, doubling up to 6 hours), and under the pause of the whole app after a "not a bot" check (R-ER-05).
- What one lookup costs was measured in milestone M2 on 32 videos from the maintainer's network (D-072). With yt-dlp's default options: 10.3 seconds. With the lightest options that still return the exact time (the `web` client, `player_skip: configs, js`, `skip: hls, dash, translated_subs`, `process=False`): 3.5 seconds. Lookups in parallel with these options: 2.0 seconds per video with two at a time, 1.4 with three, 0.9 with four, without an error in 96 lookups. No longer run was made, so how many lookups YouTube accepts in a row is still open (Q-08). The rate the app uses and the time it tells the user come from what it measures while it runs, never from a fixed number.
- There is no other source without a key. The channel feed (`feeds/videos.xml`) answered "not found" for every channel from three networks during M2 and is not used. A listing, of the channel or of its uploads playlist, has approximate dates only.
- Each exact date found updates `published_at`, sets `published_exact`, and emits an update.

### 7.5 File dates on macOS (`filesystem_mac.py`)
- Modification and access time: `os.utime`.
- Creation time: `setattrlist` with `ATTR_CMN_CRTIME` through `ctypes`. `VERIFY` (Q-02). Fallback to investigate: setting the modification time earlier than the creation time moves the creation time back on APFS.
- Verification reads `st_birthtime` and `st_mtime`.
- Other operations in this adapter: move to Trash (so deletes are recoverable), reveal in Finder, open with the default app, free space of a volume, atomic rename, cross-volume move with copy, verify and delete.

### 7.6 Events and live updates
- Services publish typed events to an in-process bus (`services/events.py`): `tool.updated` (from milestone M1: the state of a tool and the progress of its download), `channel.updated` (from milestone M2: one channel as the interface shows it, with its derived status and its totals. Published for every change of a channel and exactly once at the end of a check, never once per video), `task.progress` (from M2: how far a first listing or a full check has come), `video.updated`, `job.progress`, `queue.updated`, `activity.added`, `banner.changed`.
- `GET /api/events` is one Server-Sent Events stream per window. Progress events are coalesced. When the app stops, the bus is closed first: every stream ends, so an open window never holds up the shutdown.
- On connect and after a reconnect the frontend refetches snapshots (`/api/state`, the open channel's videos), so a missed event can never leave the UI stale.

### 7.7 Concurrency
- One asyncio event loop for HTTP and SSE.
- Blocking work (yt-dlp, ffmpeg, file operations, database writes from workers) runs in threads. Download workers are a fixed-size pool equal to the parallel downloads setting.
- One writer at a time per database connection. Each unit of work is a short transaction on its own connection: connections are opened when needed and closed afterwards, not pooled (D-040).
- One lock per channel serialises check, adoption and folder moves for that channel.

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

  | Part | Built in | State after M1 |
  |---|---|---|
  | The shutdown work, for every way of quitting (R-PL-13) | M1 | Exists, with tests that use a real window |
  | Ctrl+C and a termination signal become a quit request | M1 | Exists |
  | The decision: a handler of the `closing` event that can hold a quit | M5 | Does not exist. Nothing in the app listens to the `closing` event |
  | The "quit while downloading" confirmation (R-NA-06, R-QU-12) | M5 | Does not exist. No quit is ever held, and the app never asks |
  | Reading the reason of a quit request, so that a logout, a restart and a shutdown are never held for a question | M5 | Does not exist, and is not needed before a quit can be held: every quit gets the same shutdown work |

  The M5 rows were shown to work in the experiment of Q-24 with throwaway code that is not in the repository. They are a design, not code.

*The shutdown work (built in M1):*
- It is reached from two ends. Closing the window (the red window button, Cmd+W) ends the window loop, and the code after it runs. Quit ends the process inside AppKit, and the code after the window loop never runs: there the work hangs on AppKit's "will terminate" notification. This covers Cmd+Q, "Quit yt-mirror", Quit in the Dock icon's menu, logout, restart and shutdown.
- Ctrl+C and a termination signal are turned into the same AppKit quit request: Python's `signal` module with a wake-up pipe, because a Python signal handler does not run while AppKit's loop waits.
- At a logout, a restart or a shutdown the app does its shutdown work at once, which holds macOS for that moment, and then lets it go on. This work must stay short: macOS does not wait for an app without limit.
- A handler of an AppKit notification must return nothing. A returned value makes pyobjc raise inside AppKit, and AppKit then drops the event it was handling. In the experiment a logout hung on exactly this.

*The decision (built in M5, not in the code yet):*
- Every way of quitting will reach the decision through one public hook, the `closing` event of the pywebview window. The red window button, Cmd+W and "Close Window" reach it directly. Cmd+Q, "Quit yt-mirror", Quit in the Dock icon's menu, logout, restart and shutdown reach it because pywebview asks the same event when AppKit asks whether the app may terminate. Ctrl+C and a termination signal reach it as the quit request they were turned into.
- The decision can hold the quit: the event answers no, the app and its workers keep running, and the interface asks. This is the place of the "quit while downloading" confirmation (R-NA-06, R-QU-12). When the user confirms, the app closes its window itself.
- Logout, restart and shutdown must never be held for a question. The quit request of macOS carries its reason, and the decision lets these through to the shutdown work.

*Dock and single instance:*
- A click on the Dock icon brings the window to the front (the app has one window, and closing it quits, D-020). This is what AppKit does by itself, also for a minimized window and for a hidden app.
- One instance per data folder, in every mode (D-050). A running app holds a lock on the file `data/instance.lock` and writes its process ID and its bundle into `data/instance.json`. A second start that finds the lock held never loads the window library, so no second Dock icon appears. Started for a window, it asks macOS to open the app bundle again and ends: macOS then brings the running app's window to the front, exactly as a click on the Dock icon does. Started with `--browser` or without a window, it ends with a plain message. When the bundle is opened from Finder or the Dock while the app runs, macOS itself starts no second copy and brings the running app to the front.

**`--browser` and tests.** With `--browser` and in automated tests there is no app window and no menu bar. Everything a menu item does must therefore also be reachable inside the interface (R-UI-13), which the menu design above guarantees.

## 8. HTTP API

All paths are under `/api`. Responses are JSON. Errors use one shape: `{ "error": { "code", "message", "details" } }`. `message` is a short technical sentence. The text the user reads is written per code in the frontend (R-ER-02). `code` is one of the codes of [LOGGING.md](LOGGING.md) section 4, and the generated frontend types know them all. One code is never sent by the server: `LOCAL_SERVER_UNREACHABLE` is raised by the window itself when the server does not answer (R-ER-04).

| Method and path | Purpose |
|---|---|
| GET `/health` | The server runs: app version and database schema version |
| GET `/state` | App snapshot: channels with derived status, queue summary, banners, settings, versions |
| GET `/events` | Server-Sent Events stream |
| POST `/channels/lookup` | Resolve a URL or handle to a channel preview (R-CH-03) |
| POST `/channels` | Add a channel |
| GET, PATCH, DELETE `/channels/{id}` | Read, change settings, remove (`keep_files` flag) |
| POST `/channels/{id}/check` | Check now |
| POST `/channels/check-all` | Check all channels |
| POST `/channels/{id}/mirror-missing` | Queue everything eligible once |
| POST `/channels/{id}/open-folder` | Open in Finder |
| GET `/channels/{id}/videos` | The catalogue (all rows, compact fields) |
| GET `/videos/{id}` | Full details for the panel |
| POST `/videos/mirror` | Queue videos (`ids`, optional `first`) |
| POST `/videos/exclude` , `/videos/restore` | Exclude and restore (`ids`, `file_action`) |
| POST `/videos/redownload`, `/videos/repair-metadata` | |
| POST `/videos/{id}/play`, `/videos/{id}/reveal` | |
| GET `/queue` | Full queue |
| POST `/queue/pause`, `/queue/resume`, `/queue/reorder`, `/queue/clear-waiting` | |
| POST `/jobs/{id}/cancel`, `/jobs/{id}/retry` | |
| GET, PUT `/channels/{id}/exclude-rules` | Rules, with `POST .../preview` (R-EX-06) |
| POST `/channels/{id}/adopt/scan`, GET `.../adopt`, POST `.../adopt/apply` | Adoption (R-AD-*) |
| POST `/channels/{id}/repair-dates` | |
| GET, PATCH `/settings` | |
| POST `/settings/api-key/test` | |
| GET `/activity` | Paged, filterable |
| GET `/errors/{code}` and GET `/jobs/{id}/log` | Error text and technical details |
| GET `/tools`, POST `/tools/{name}/install`, POST `/tools/ytdlp/update` | Toolchain |
| GET `/update`, POST `/update/apply`, POST `/update/skip` | App update |
| POST `/diagnostics/health-check`, POST `/diagnostics/debug-report` | |
| POST `/app/uninstall`, POST `/app/quit` | |
| POST `/client-log` | Frontend errors forwarded to the log |

The OpenAPI schema generated by FastAPI is the contract. Frontend types are generated from it.

## 9. Security

- Bind to 127.0.0.1 on a random free port. Reject requests whose `Host` or `Origin` header is not that address (protects against DNS rebinding and other websites calling the local API).
- A random session token is created at start and given to the window in the initial URL (`/?token=...`). The server answers that URL by setting the token as a cookie (`ytm_session`, HttpOnly, SameSite=Strict) and redirecting to `/`, so the token leaves the address bar and scripts cannot read it (D-038). Every `/api` call must carry the cookie. Tests and tools may send the same token as an `Authorization: Bearer` header instead. A wrong or missing token is answered with `UNAUTHORIZED`, a foreign Host or Origin with `ORIGIN_REJECTED`.
- The interface files themselves need no token: they contain no secrets.
- The OpenAPI schema and the interactive API docs are not served by the running app.
- No remote content is rendered as HTML. Descriptions are shown as text.
- File operations accept video and channel IDs, never paths from the client, except folder choices that come from the native folder picker.
- Downloaded tools and releases are verified against SHA-256 checksums before use.
- The API key is stored in the database, redacted in logs and debug reports.

## 10. Testing seams

Every external dependency is behind a port, and each port has a fake in `backend/tests/fixtures/fakes/`. The one exception is the fake YouTube: the real app must be able to start with it, and the app is installed without its tests, so it is an adapter of the app (D-062).

| Port | Fake behaviour |
|---|---|
| YouTubeGateway | Serves channels and videos from JSON fixtures, simulates progress, failures by error code, rate limits. This one fake is part of the app: `adapters/fixture_youtube.py` (D-062) |
| ExactDateSource | Returns dates from fixtures, simulates quota errors |
| MediaTools | Creates tiny real MKV files with ffmpeg in integration tests, a pure fake in unit tests |
| FileSystem | Real temp directories on macOS runners, an in-memory fake in unit tests |
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
| `YTM_TOOL_DIR` | app | Another folder for the downloaded tools than `tools/`. The end-to-end tests use it, so that their stand-in tools never replace real ones |
| `YTM_TOOL_MANIFEST` | app | Another tool manifest than the one of the app. The end-to-end tests point it at small stand-ins for the tools, served from this Mac |
| `YTM_TOOL_SOURCE` | app | Use only the tool source of this name. The automated checks install from each source on its own (D-053) |
| `YTM_WINDOW_REPORT` | app | A file to which the app writes what macOS shows of it, once the window is up: its name, its bundle identifier and its menu bar. For tests |
| `YTM_UV_BASE_URL` | `start` | Where uv is downloaded from. For tests. The checksum is checked in every case |
| `YTM_E2E_CHROME_CHANNEL` | Playwright | Use an installed Chrome where Playwright's Chromium cannot be downloaded |
