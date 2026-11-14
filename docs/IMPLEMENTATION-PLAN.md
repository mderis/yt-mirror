# yt-mirror V1: Implementation Plan

This plan is written so that a developer or an AI agent can build the app milestone by milestone. Each milestone ends in a working, tested, committed state.

## How to work

1. Read [AGENTS.md](../AGENTS.md), then [SPEC.md](SPEC.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [CODING-STANDARDS.md](CODING-STANDARDS.md).
2. Take the next milestone. Resolve its open questions first ([OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)).
3. For each requirement: write the tests, write the code, run all checks, commit.
4. At the end of the milestone: open a pull request and wait for the maintainer, exactly as described in [WORKFLOW.md](WORKFLOW.md). The two reviews in [TESTING.md](TESTING.md) section 7 happen on that pull request.
5. Do not start work that belongs to a later milestone. Do not add features that are not in the spec. If the spec is wrong or incomplete, stop and raise it: the spec is changed first, then the code.

A milestone is done when its acceptance list passes and the definition of done in the coding standards holds for every change in it.

---

## M0. Project skeleton and tooling
Requirements: R-PL-01 to R-PL-06 (as far as they apply to a skeleton), R-PL-10 to R-PL-13, R-IN-02, R-IN-06, R-IN-07, R-SE-03, R-SE-04, R-ER-02, R-ER-04, R-LG-01, R-LG-06 to R-LG-08, R-QA-03, R-QA-04, R-QA-07, R-TH-01 to R-TH-06, R-TH-08, R-TH-09. `./start --doctor` is the first part of R-LG-05, and telling a clone from an archive install is the first part of R-UP-04. Resolve: Q-01, Q-09.

- Repository structure from [ARCHITECTURE.md](ARCHITECTURE.md) section 3, with a README in each package.
- `pyproject.toml` with uv, Ruff, Pyright, pytest, coverage thresholds, import-linter rules. `frontend/` with Vite, Vue, TypeScript strict, Tailwind with the design tokens, ESLint, Prettier, Vitest. `e2e/` with Playwright.
- `./start` for a clone: bootstraps uv into `tools/`, installs Python and dependencies, builds or fetches the frontend, starts the app. Flags: `--dev`, `--debug`, `--browser`, `--doctor`, `--update`.
- Backend starts, serves a health endpoint and the built frontend. The window opens and shows a placeholder page.
- Security basics: localhost binding, session token, origin check (with tests).
- Logging pipeline from [LOGGING.md](LOGGING.md) with `app.started` and `app.config`.
- Database setup with Alembic and the first empty migration. Settings table and typed settings model.
- CI workflow `.github/workflows/ci.yml` as specified in [WORKFLOW.md](WORKFLOW.md) section 6: runs on every pull request, on every new commit pushed to a pull request, and on pushes to `main`. Pre-commit hooks.
- The requirements coverage script (may report everything as uncovered for now).
- The theme center ([DESIGN.md](DESIGN.md) section 2): tokens, Tailwind preset, bundled fonts, brand icon source, the token lint, the theme preview page, and visual regression screenshots in both themes.

Acceptance: a fresh clone on a Mac runs with `./start` and opens a window. CI is green. `./start --doctor` reports the environment.

## M1. Toolchain and app identity
Requirements: R-IN-03, R-IN-04, R-IN-05, R-NA-01, R-NA-02, R-NA-07, R-NA-08. Resolve: Q-24 first, then Q-05.

- Tool manifest, download with progress, checksum verification, per-tool self-check. A second source per tool (D-053). yt-dlp becomes a locked package (D-057).
- First-run screen (`Setup.html`). Banner and "Install now" for a missing tool. When which of the two is shown: D-055.
- The event bus and `GET /api/events`, with the one event this milestone needs (D-057). The first shared components: button, progress bar, banner, icons.
- Rebuild of the Python environment after the folder moved.
- The quit path, first part (D-052): the shutdown work runs however the app is asked to quit (R-PL-13). Nothing can hold a quit yet. The decision part and the "quit while downloading" confirmation are built in M5.
- Native Mac app, first part ([ARCHITECTURE.md](ARCHITECTURE.md) section 7.10). **Q-24 is resolved before any of it is built. If the window library cannot do it, stop and ask.**
  - Brand icon ([DESIGN.md](DESIGN.md) section 5): the build script that generates assets from `frontend/src/design/brand/icon.svg`, the test that every generated asset is newer than the source, and the macOS icon (`.icns`).
  - The app bundle: `./start` on a clone builds `yt-mirror.app` locally and starts the app through it. It is rebuilt after the folder moved.
  - App identity: "yt-mirror" and its icon in the Dock, the app switcher, the menu bar and Activity Monitor. Until the full menu bar of M5, the app has the standard macOS menus (the app menu with Quit, and Edit so that text fields work).
  - One instance only: a second start focuses the existing window. A click on the Dock icon brings the window to the front.

Acceptance: deleting any tool and restarting leads to a guided repair, never a crash. Moving the folder and starting works. The running app is called "yt-mirror" everywhere macOS names it, with its icon, and a second `./start` focuses the first window.

## M2. Channels and catalogue
Requirements: R-CH-01 to R-CH-16, R-CH-23, R-CH-24, R-CH-27, R-CH-30 to R-CH-35 (without folder move), R-UI-01, R-UI-02, R-PL-08, R-QA-08. Partly: R-CH-25 (the banner, "Try again", and that the catalogue is kept), R-CH-28 (the rule: no such work exists yet), R-DT-01 ("last seen"), R-DT-02 and R-DT-04 (how a date is stored and shown), R-DT-13 (the waiting state), R-FB-01 and R-FB-03 (the channel statuses that can occur: checking, up to date, new videos, paused, could not check), R-FI-01 (the library default and the channel folder), R-QA-02 (the first live test), R-UI-14 (the screens of this milestone), R-ER-05 and R-FB-04 (the "not a bot" check for what this milestone asks of YouTube: lookups, listings and pictures, with its banner). Resolve: Q-12, Q-09.

- Core models and the status machine. Repositories. The YouTube gateway port, its fake, and the real listing through yt-dlp.
- Channel lookup with the optional video count (D-061), add, remove (the folder stays: no file can exist yet), pause.
- First listing in the background with progress. Quick check and full check as manual actions, with new, updated and removed detection (D-059). A full check shows progress and can be cancelled.
- Thumbnail cache.
- The pause of the whole app and the one banner when YouTube answers with its "not a bot" check (R-ER-05, D-071). Later milestones put their own work under the same pause: downloads (M3, M5), the exact date fetch and the scheduler (M4).
- Frontend: shell, sidebar, welcome, add channel dialogs, list view with read-only rows, the channel menu, loading, error and empty states. The events of this milestone on the event stream of M1, with snapshot refetch.
- Approximate dates with their precision, and the waiting state of a date (D-060).
- Brand icon: the favicon, made from the icon source by the backend (D-064). The logo in the sidebar is drawn from the same source file.
- An element of a mockup whose target a later milestone builds is added by that milestone (D-066). Each one is listed under its milestone below as "Postponed from M2".

Acceptance: with the fake YouTube, channels can be added and browsed, and the `changing` fixture shows new, renamed and removed videos correctly across quick and full checks: a quick check never marks a video as removed, a full check that is cancelled changes nothing, and a failed check keeps the catalogue.

## M3. Downloading one video correctly
Requirements: R-MI-01, R-QL-01 to R-QL-04, R-FI-*, R-FN-01 to R-FN-05, R-FN-07, R-MD-01 to R-MD-05, R-DT-01 to R-DT-03, R-DT-07, R-DT-08, R-DT-10, R-LG-02, R-LG-03. Partly: R-UI-08 to R-UI-10 (the details panel, Play, Show in Finder), R-DT-13 (the highlight when an exact date replaces an approximate one, and the date in the details panel), R-QA-02 (the live download test), R-UI-14. Resolve: Q-02, Q-04.

- `core/naming.py`, `core/dates.py`, `core/quality.py` with property-based tests.
- macOS filesystem adapter: dates with verification, atomic moves, Trash, reveal, open.
- Downloader service: the full flow of [ARCHITECTURE.md](ARCHITECTURE.md) section 7.2 with a single worker.
- Error classification into codes.
- Frontend: Mirror action, progress on rows, synced state, details panel, Play, Show in Finder.
- The job ID in every log line of a download (R-LG-02) and the status history table `video_events` (R-LG-03), with the first status changes.
- Postponed from M2 (D-066), in the remove channel dialog (`RemoveChannel.html`): the choice "Keep the files" or "Delete the files" (to the Trash), and the number and size of the downloaded videos. Until this milestone the dialog only says that the folder stays.

Acceptance: a video mirrored from the fake YouTube is a valid MKV with the right name, embedded metadata, cover, subtitles, and creation and modification dates equal to the published time, verified by integration tests on macOS. The live test downloads one real video. The requirement coverage and the end-to-end tests include the element postponed from M2.

## M4. Exact dates and automatic checks
Requirements: R-DT-04 to R-DT-06, R-DT-09, R-DT-11 to R-DT-13, R-FN-06, R-CH-20 to R-CH-22, R-CH-25 (the automatic retry with backoff), R-CH-26, R-CH-28 (date repair with every check), R-PL-07. Resolve: Q-06, Q-08, Q-11.

- Channel feed source. Background fetch with backoff and persistence: newest videos first, and an entry at the front of the queue for videos a decision waits for (R-DT-05). Optional API key with guide dialog and test button.
- The updating and unavailable states of an approximate date (R-DT-13), driven by the fetch queue, in the list, the details panel and on the theme preview page.
- Date repair at check and on demand. Rename on title change.
- One scheduler (`services/scheduler.py`) for all background work that runs by itself while the app is open: the exact date fetch, the quick checks when the app opens (R-CH-20), when a channel is selected (R-CH-21) and on the interval (R-CH-22), the automatic retry of a failed check with backoff (R-CH-25), and the automatic full check (R-CH-26) with its setting "Full check at least every" (default 7 days). The setting gets its control on the settings screen in M7.
- Postponed from M2 (D-066), in the sidebar (`Main.html`, `States.html`): the global indicator "Checking channels: 3 of 5", and the channel status "Could not check · retrying in 5 min".

Acceptance: the mandatory date tests in [TESTING.md](TESTING.md) section 5 pass under two time zones. With a fake clock, channels are checked when the app opens, when one is selected after more than 5 minutes, and on the interval. A failed check is retried after 5, 15 and 60 minutes. A full check starts by itself after the set time, one channel at a time. The app works with no API key (R-PL-07). The requirement coverage and the end-to-end tests include the elements postponed from M2.

## M5. Queue
Requirements: R-QU-01 to R-QU-12, R-MI-02 to R-MI-07, R-UI-03 to R-UI-13 (remaining), R-QL-05 to R-QL-07, R-NA-03, R-NA-04, R-NA-06, R-NA-09. Partly: R-CH-26 (no full check while the channel downloads), R-CH-28 (verifying that synced files exist with every check), R-DT-13 (the grid), R-UI-14.

- Worker pool, ordering, reorder, pause and resume, speed limit, retry policy, resume of partial downloads, restart recovery, disk guard, unavailable folder handling.
- Auto-mirror with the date limit. A video whose approximate date cannot decide the limit gets its exact date first, through the front of the fetch queue of M4 (R-MI-03). Mirror everything missing. File missing status.
- Sorting by date follows the position on the channel while any date of the channel is approximate (R-UI-06).
- Quality change with re-download.
- Frontend: queue bar and downloads panel, selection and bulk bar, grid view, tabs, search, sort, context menus, virtual scrolling, keyboard shortcuts, quit confirmation. The video menus use the Menu component of M2 and its pattern: a right-click, and the visible "More actions" button on every row and card ([DESIGN.md](DESIGN.md) section 8).
- Postponed from M2 (D-066): "Mirror everything missing" in the channel menu (`Menus.html`), the Auto-mirror toggle in the channel header (`Main.html`), and the channel statuses "Mirroring X of Y" and "Paused · X of Y" in the sidebar (`States.html`).
- The quit path, second part (D-052, [ARCHITECTURE.md](ARCHITECTURE.md) section 7.10). M1 built only the shutdown work, and nothing in the app listens to the window's `closing` event. This milestone builds the decision part: the handler of the `closing` event that can hold a quit, the "quit while downloading" confirmation (R-NA-06, R-QU-12), and the reading of the reason of a quit request, so that a logout, a restart and a shutdown are never held for a question. Tests with a real window cover every way of quitting, held and confirmed.
- Native Mac app, second part: the menu bar ([DESIGN.md](DESIGN.md) section 7.1), now that the actions exist. File, Edit, View (List, Grid, Show Downloads), Channel and Window menus, items enabled only when they apply. One quit path for Cmd+Q, Close Window and the window button, with the quit confirmation. The in-app shortcut list follows the menu bar ([DESIGN.md](DESIGN.md) section 7.3). A menu item whose target does not exist yet is added by the milestone that builds the target, never shown disabled without one.

Acceptance: end-to-end flows 2, 3, 6, 7, 10 and 13 pass. The `large` fixture scrolls smoothly. Every menu item of this milestone does the same as its control in the interface, and Cmd+Q during a download asks for confirmation. The requirement coverage and the end-to-end tests include the elements postponed from M2.

## M6. Excluding
Requirements: R-EX-01 to R-EX-09. Partly: R-UI-14.

- Manual exclude and restore with undo. File behaviour setting and dialog. Rules, preview, exceptions.

Acceptance: end-to-end flows 4 and 5 pass. A property test shows that no path queues an excluded video.

## M7. Settings, feedback, activity, help
Requirements: section 10 of the spec, R-SE-*, R-FB-*, R-ER-*, R-AC-*, R-HE-*, R-LG-04, R-LG-05, R-CH-33, R-NA-05. Partly: R-CH-30 (channel settings), R-UI-14. Resolve: Q-07, Q-26.

- Settings and channel settings screens with every control wired. Folder move for a channel.
- The activity log must record every installed tool with the source it came from (R-IN-03, D-057), with a test. Since M1 the source is only in the debug log (`tool.install.finished`), in `./start --doctor` and in the answer of `/api/tools`: the maintainer accepted that for the time before the activity log exists.
- Banners, toasts, notifications. Error details dialog for every error code, with texts.
- Activity log. Help page. Report a problem. Debug report. Health check. The `explain` tool.
- Native Mac app, third part: the About window, and the menu items whose targets are built here: About yt-mirror, Settings..., Show Activity, yt-mirror Help, Keyboard Shortcuts, Report a Problem....
- Postponed from M2 (D-066):
  - Sidebar (`Main.html`, `Welcome.html`): the entries Activity, Settings, Help and Report a problem.
  - Welcome screen (`Welcome.html`): the link "Change in Settings" after "Videos will be saved in ...".
  - Channel page, banner of a failed check (`StateError.html`): "Show details".
  - Channel header (`Main.html`) and channel menu (`Menus.html`): the Channel settings button and the item "Channel settings".
  - Whole app (`States.html`): the toasts "<channel> added: N videos" and "<channel> removed". Whether the second one can offer Undo is open question Q-26.

Acceptance: end-to-end flow 11 passes. Every error code has user text and a test that renders it. The requirement coverage and the end-to-end tests include every element postponed from M2.

## M8. Adopting existing files
Requirements: R-AD-01 to R-AD-08, R-MD-06. Partly: R-CH-06 (the offer), R-UI-14.

- Scan, match, differences, three actions, resumable apply. Repair metadata.
- Postponed from M2 (D-066), in step 2 of the add channel dialog (`AddChannel2.html`): the sentence "After adding, you can match them to the channel instead of downloading again." after the number of video files, and the offer to match them once the channel is added (R-CH-06). Until this milestone the dialog only says how many video files the folder contains.

Acceptance: end-to-end flow 8 passes. Fix in place is shown by test never to re-encode or download video data. The requirement coverage and the end-to-end tests include the element postponed from M2.

## M9. Installer, updater, uninstall, release pipeline
Requirements: R-IN-01, R-IN-02, R-UP-01 to R-UP-07, R-UN-01, R-QA-04, R-PL-09. Resolve: Q-03.

- The installer installs nothing that runs by itself: no login item, no background service (R-PL-09), with a test.
- Release workflow, archive and checksums. `install.sh`. The archive ships the icon source file and the token file, which the bundle is built from (D-056).
- Native Mac app, fourth part: the installer builds the same app bundle as `./start` does on a clone (M1), in `~/Applications` (R-NA-02). The menu item Check for Updates... arrives with the updater.
- Updater for archive and clone installs, with backup, migration, rollback. yt-dlp overlay update with self-check.
- Uninstall.
- Migration test harness with a fixture database of this version.
- `./start --update` becomes real. Until now it is a stub whose tests are infrastructure tests (`infra:`). The tests of the real updater get their R-UP IDs here, and the stub tests are removed.

Acceptance: end-to-end flow 12 passes. A manual install on a clean Mac works. An update from a test release to another test release works and rolls back when a migration is made to fail.

## M10. Website and documentation
Requirements: R-WS-01 to R-WS-05, R-TH-07.

- VitePress site with the home page and documentation structure, styled from the app's token file (R-TH-07). User guide written for non-technical users. Developer docs moved into the site structure.
- Screenshot generation. Pages deployment workflow. Contributor files and issue templates checked.
- Brand icon, third part: the social preview image and the logo on the website, generated by the same icon build script.

Acceptance: the site builds and deploys from `main`, the install line on the home page works, screenshots are generated from the app.

## M11. Hardening and release
Requirements: R-QA-01, R-QA-02 (the manual checklist), R-QA-05, R-QA-06, R-UI-14 (the final pass).

- Full manual checklist ([TESTING.md](TESTING.md) section 8). Accessibility pass. Performance check (R-QA-05, R-UI-07). Crash safety tests (R-QA-06).
- Final code review and test review of the whole code base. Mutation testing on `core/`.
- Requirements coverage script reports no gaps.
- Tag `v1.0.0`.

---

## Progress

Progress is tracked in [STATUS.md](STATUS.md), and nowhere else.
