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
|                                         Adapters: yt-dlp, YouTube API, feed,        |
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
| HTTP client | httpx2 | YouTube API, channel feed, GitHub releases, tool downloads. The successor of httpx, also used by the test client (D-041) |
| Logging | structlog writing JSON lines | See [LOGGING.md](LOGGING.md) |
| Window | pywebview (WebKit on macOS) | `--browser` flag opens the default browser instead. What it can do is in section 7.8. The native Mac parts (app bundle, menu bar, single instance) are in section 7.10 and depend on Q-24 |
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
        models.py            Dataclasses: Channel, Video, Job, Settings, ...
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
        youtube_api.py       Optional Data API client (exact dates)
        channel_feed.py      Channel feed client (newest videos)
        media_tools.py       ffmpeg and ffprobe operations
        filesystem_mac.py    File dates, Trash, reveal, free space, safe moves
        notifier_mac.py      macOS notifications
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
        doctor.py            Text of the environment report
        bundle.py            Builds the macOS app bundle (section 7.10, from milestone M1)
        menus.py             The menu bar, defined as data (section 7.10, from milestone M5)
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
| avatar_url | text, null | Cached locally too |
| folder | text | Absolute path, or relative to the library when not custom |
| folder_is_custom | bool | |
| quality | text, null | null means "use default" |
| auto_mirror | bool | |
| mirror_after | int, null | Only auto-mirror videos published after this time |
| paused | bool | |
| first_listed_at | int, null | Set when the first full listing completes |
| last_check_at | int, null | Last successful check |
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
| published_at | int, null | See R-DT-* |
| published_exact | bool | false while only an approximate date is known |
| channel_position | int | Order on the channel page, used as a tie-breaker (R-DT-11) |
| status | text | See section 6 |
| excluded | bool | |
| excluded_by | text, null | `manual` or a rule ID |
| exclude_exception | bool | User chose to keep it despite rules (R-EX-07) |
| missing_checks | int | Consecutive successful checks without this video (R-CH-13) |
| gone | bool | Removed from YouTube |
| first_seen_at | int | |
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
`key`, `value`. Holds `schema_version` (also tracked by Alembic), `app_version`, `install_kind` (`clone`, `archive`), `last_update_check_at`.

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
1. Emit "checking". List the channel's Videos tab through `ytdlp_gateway.list_channel` (flat listing with approximate dates).
2. If the listing fails or returns zero entries for a channel that had videos, record the error, keep everything as it is, schedule a retry (R-CH-25). Stop.
3. In one transaction: insert unknown videos, update title, duration, views and position of known ones, reset `missing_checks` for listed videos and increment it for unlisted ones, set `gone` where it reaches 2 (R-CH-13).
4. For each title that changed on a synced video: rename the file (R-FN-06) through `filesystem_mac`, then restore its dates.
5. Verify that each synced file exists. Missing ones become `file_missing` (R-MI-06), unless the channel folder itself is unavailable (R-QU-11).
6. Run exclusion rules on new videos (R-EX-06).
7. Fetch exact dates for the newest videos from the channel feed. Queue the rest in `date_fetch_queue`.
8. If dates repair is on, compare file dates with `published_at` and fix differences (R-DT-09).
9. If auto-mirror is on, enqueue eligible videos (R-MI-02, R-MI-03).
10. Emit the new channel state, write activity entries, send a notification if there are new videos.

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

### 7.4 Exact dates (`services/dates.py`)
- With an API key: `videos.list` with `part=snippet,liveStreamingDetails`, 50 IDs per request (1 quota unit per request, default quota 10,000 units per day).
- Channel feed: `https://www.youtube.com/feeds/videos.xml?channel_id=<id>` gives exact `published` times for the newest entries.
- Without a key: one metadata extraction per video through yt-dlp, at most one every 2 seconds, paused while downloads are running or after any rate-limit signal (back off 15 minutes, doubling up to 6 hours).
- Each exact date found updates `published_at`, sets `published_exact`, and emits an update.

### 7.5 File dates on macOS (`filesystem_mac.py`)
- Modification and access time: `os.utime`.
- Creation time: `setattrlist` with `ATTR_CMN_CRTIME` through `ctypes`. `VERIFY` (Q-02). Fallback to investigate: setting the modification time earlier than the creation time moves the creation time back on APFS.
- Verification reads `st_birthtime` and `st_mtime`.
- Other operations in this adapter: move to Trash (so deletes are recoverable), reveal in Finder, open with the default app, free space of a volume, atomic rename, cross-volume move with copy, verify and delete.

### 7.6 Events and live updates
- Services publish typed events to an in-process bus (`services/events.py`): `channel.updated`, `video.updated`, `job.progress`, `queue.updated`, `activity.added`, `banner.changed`, `task.progress`.
- `GET /api/events` is one Server-Sent Events stream per window. Progress events are coalesced.
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

1. `./start` checks macOS and the processor, puts a pinned uv into `tools/` after verifying its SHA-256, and lets uv install the pinned Python and the locked packages into `tools/`.
2. In a clone it builds the interface with Node.js when `frontend/dist` is missing or older than the sources (D-037). An installed copy ships the built interface.
3. `python -m ytmirror.app.main` builds the container, brings the database up to date, starts the HTTP server in a thread on a free port of 127.0.0.1, and opens the window on the main thread with the first URL (section 9). When the window closes, the server stops and the process ends.

Flags: `--debug` (verbose logs, developer tools in the window), `--browser` (default browser instead of the window, quit with Ctrl+C), `--doctor` (print the environment report and exit), `--update` (the updater arrives in milestone M9. Until then it says so and exits with code 2).

`--dev` runs the Vite development server next to the backend. The window shows the development server, which reloads the interface on every change and passes `/api` calls on to the backend. Its origin is accepted only in this mode. Backend code is not reloaded: restart after changing Python. The theme preview page is at `/theme-preview.html` on the development server.

### 7.10 Native Mac app (planned, not built yet)

Requirements R-NA-01 to R-NA-09. Decision D-044. **Everything here is `VERIFY` (Q-24)** until the experiment of that question has shown that pywebview can do it from a locally built, unsigned bundle. Nothing of this section exists in the code of milestone M0, where the app still appears as "Python".

**App bundle (R-NA-01, R-NA-02).**
- A small program builds `yt-mirror.app` on the user's Mac: a folder with `Contents/Info.plist` (name `yt-mirror`, the bundle identifier, the version from `pyproject.toml`), `Contents/Resources/yt-mirror.icns` generated from `frontend/src/design/brand/icon.svg` by the icon build script, and `Contents/MacOS/yt-mirror`, the program macOS starts.
- The same program is used by the installer (bundle in `~/Applications`, milestone M9) and by `./start` on a clone (bundle inside the clone, in the ignored `tools/` folder, milestone M1). `./start` then starts the app through the bundle, so a clone and an installed copy behave alike.
- The bundle contains absolute paths, so it is rebuilt when the app folder moved (R-IN-05) and when the app version or the icon source changed.
- Proposed bundle identifier: `io.github.mderis.yt-mirror`, after the website address. To be confirmed by the maintainer in M1, because it should never change afterwards.
- How the Python process takes over the identity of the bundle (so that the Dock, Cmd+Tab and Activity Monitor show "yt-mirror" and not "Python") is the first thing the Q-24 experiment has to show.

**Menu bar (R-NA-03, R-NA-04, R-NA-09).**
- The menus are defined in one module, `app/menus.py`, as data: title, shortcut, the command it sends, and the condition under which it is enabled. This is the source of truth for shortcuts.
- A menu item and the matching control in the interface trigger the same command. The menu never contains logic of its own: it tells the frontend to run a command (for example "add channel"), and the frontend does what its own button would do.
- The frontend tells the backend what is currently possible (is a channel open, is it paused, which view is shown), and the menus are enabled and titled from that.
- The standard items (Hide, Hide Others, Minimize, Zoom, the window list, and the Edit menu for text fields) are the ones macOS provides. They are not reimplemented.
- "Reload" exists only with `--debug`. It must not take Cmd+R, which belongs to "Check Now".

**Quit, Dock and single instance (R-NA-06 to R-NA-08).**
- There is one quit path in `app/main.py`. Cmd+Q, "Quit yt-mirror", Cmd+W, "Close Window" and the red window button all end in it. It is the place of the "quit while downloading" confirmation (R-QU-12, section 7.8: the window's close handler can refuse).
- A click on the Dock icon brings the window to the front (the app has one window, and closing it quits, D-020).
- A second start finds the running instance, asks it to bring its window to the front, and ends. How the instances find each other (a lock in `data/`, or what macOS offers for bundles) is decided by the Q-24 experiment.

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

Every external dependency is behind a port, and each port has a fake in `backend/tests/fixtures/fakes/`:

| Port | Fake behaviour |
|---|---|
| YouTubeGateway | Serves channels and videos from JSON fixtures, simulates progress, failures by error code, rate limits |
| ExactDateSource | Returns dates from fixtures, simulates quota errors |
| MediaTools | Creates tiny real MKV files with ffmpeg in integration tests, a pure fake in unit tests |
| FileSystem | Real temp directories on macOS runners, an in-memory fake in unit tests |
| Releases | Serves fake release archives for updater tests |
| Notifier, Clock, Random | Recorders and controllable values |

The environment variable `YTM_FAKE_YOUTUBE=<fixtures dir>` starts the real app with the fake gateway. End-to-end tests and screenshot generation use it. See [TESTING.md](TESTING.md). It arrives with the gateway in milestone M2.

Environment variables, all optional. Only `app/config.py` and `start` read them.

| Variable | Read by | Purpose |
|---|---|---|
| `YTM_HOME` | app | The folder that holds `data/` and `tools/`. Set by `./start` |
| `YTM_DATA_DIR` | app | A different data folder. For tests |
| `YTM_PORT` | app, `start`, Vite | A fixed port instead of a free one. For tests and `--dev` |
| `YTM_SESSION_TOKEN` | app | A fixed session token instead of a random one. For tests only |
| `YTM_NO_WINDOW` | app | Serve without opening a window or a browser, until a stop signal. For tests |
| `YTM_FRONTEND_URL` | app | The address of the development server. Set by `./start --dev`, ignored without `--dev` |
| `YTM_UV_BASE_URL` | `start` | Where uv is downloaded from. For tests. The checksum is checked in every case |
| `YTM_E2E_CHROME_CHANNEL` | Playwright | Use an installed Chrome where Playwright's Chromium cannot be downloaded |
