# yt-mirror V1: Implementation Plan

This plan is written so that a developer or an AI agent can build the app milestone by milestone. Each milestone ends in a working, tested, committed state.

## How to work

1. Read [AGENTS.md](../AGENTS.md), then [SPEC.md](SPEC.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [CODING-STANDARDS.md](CODING-STANDARDS.md).
2. Take the next milestone. Resolve its open questions first ([OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)).
3. For each requirement: write the tests, write the code, run all checks, commit.
4. At the end of the milestone: run the two reviews in [TESTING.md](TESTING.md) section 7, fix the findings, update the changelog, tick the milestone here.
5. Do not start work that belongs to a later milestone. Do not add features that are not in the spec. If the spec is wrong or incomplete, stop and raise it: the spec is changed first, then the code.

A milestone is done when its acceptance list passes and the definition of done in the coding standards holds for every change in it.

---

## M0. Project skeleton and tooling
Resolve: Q-01, Q-09.

- Repository structure from [ARCHITECTURE.md](ARCHITECTURE.md) section 3, with a README in each package.
- `pyproject.toml` with uv, Ruff, Pyright, pytest, coverage thresholds, import-linter rules. `frontend/` with Vite, Vue, TypeScript strict, Tailwind with the design tokens, ESLint, Prettier, Vitest. `e2e/` with Playwright.
- `./start` for a clone: bootstraps uv into `tools/`, installs Python and dependencies, builds or fetches the frontend, starts the app. Flags: `--dev`, `--debug`, `--browser`, `--doctor`, `--update`.
- Backend starts, serves a health endpoint and the built frontend. The window opens and shows a placeholder page.
- Security basics: localhost binding, session token, origin check (with tests).
- Logging pipeline from [LOGGING.md](LOGGING.md) with `app.started` and `app.config`.
- Database setup with Alembic and the first empty migration. Settings table and typed settings model.
- CI workflow: lint, types, unit tests, frontend tests, build, on macOS. Pre-commit hooks.
- The requirements coverage script (may report everything as uncovered for now).

Acceptance: a fresh clone on a Mac runs with `./start` and opens a window. CI is green. `./start --doctor` reports the environment.

## M1. Toolchain
Requirements: R-IN-03, R-IN-04, R-IN-05. Resolve: Q-05.

- Tool manifest, download with progress, checksum verification, per-tool self-check.
- First-run screen (`Setup.html`). Banner and "Install now" for a missing tool.
- Rebuild of the Python environment after the folder moved.

Acceptance: deleting any tool and restarting leads to a guided repair, never a crash. Moving the folder and starting works.

## M2. Channels and catalogue
Requirements: R-CH-01 to R-CH-16, R-CH-30 to R-CH-35 (without folder move), R-UI-01, R-UI-02. Resolve: Q-12.

- Core models and the status machine. Repositories. The YouTube gateway port, its fake, and the real listing through yt-dlp.
- Channel lookup, add, remove (keep files only for now), pause.
- First listing in the background with progress. Check with new, updated and removed detection.
- Thumbnail cache.
- Frontend: shell, sidebar, welcome, add channel dialogs, list view with read-only rows, loading, error and empty states. SSE connection with snapshot refetch.

Acceptance: with the fake YouTube, channels can be added and browsed, and the `changing` fixture shows new, renamed and removed videos correctly across checks.

## M3. Downloading one video correctly
Requirements: R-MI-01, R-QL-01 to R-QL-04, R-FI-*, R-FN-01 to R-FN-05, R-FN-07, R-MD-01 to R-MD-05, R-DT-01 to R-DT-03, R-DT-07, R-DT-08, R-DT-10. Resolve: Q-02, Q-04.

- `core/naming.py`, `core/dates.py`, `core/quality.py` with property-based tests.
- macOS filesystem adapter: dates with verification, atomic moves, Trash, reveal, open.
- Downloader service: the full flow of [ARCHITECTURE.md](ARCHITECTURE.md) section 7.2 with a single worker.
- Error classification into codes.
- Frontend: Mirror action, progress on rows, synced state, details panel, Play, Show in Finder.

Acceptance: a video mirrored from the fake YouTube is a valid MKV with the right name, embedded metadata, cover, subtitles, and creation and modification dates equal to the published time, verified by integration tests on macOS. The live test downloads one real video.

## M4. Dates everywhere
Requirements: R-DT-04 to R-DT-06, R-DT-09, R-DT-11, R-DT-12, R-FN-06. Resolve: Q-06, Q-08, Q-11.

- Approximate date flag and display. Channel feed source. Background fetch with backoff and persistence. Optional API key with guide dialog and test button.
- Date repair at check and on demand. Rename on title change.

Acceptance: the mandatory date tests in [TESTING.md](TESTING.md) section 5 pass under two time zones.

## M5. Queue
Requirements: R-QU-01 to R-QU-12, R-MI-02 to R-MI-07, R-UI-03 to R-UI-13 (remaining), R-QL-05 to R-QL-07. Resolve: Q-10 first.

- Worker pool, ordering, reorder, pause and resume, speed limit, retry policy, resume of partial downloads, restart recovery, disk guard, unavailable folder handling.
- Auto-mirror with the date limit. Mirror everything missing. File missing status.
- Quality change with re-download.
- Frontend: queue bar and downloads panel, selection and bulk bar, grid view, tabs, search, sort, context menus, virtual scrolling, keyboard shortcuts, quit confirmation.

Acceptance: end-to-end flows 2, 3, 6, 7, 10 and 13 pass. The `large` fixture scrolls smoothly.

## M6. Excluding
Requirements: R-EX-01 to R-EX-09.

- Manual exclude and restore with undo. File behaviour setting and dialog. Rules, preview, exceptions.

Acceptance: end-to-end flows 4 and 5 pass. A property test shows that no path queues an excluded video.

## M7. Settings, feedback, activity, help
Requirements: section 10 of the spec, R-SE-*, R-FB-*, R-ER-*, R-AC-*, R-HE-*, R-LG-04, R-LG-05, R-CH-33. Resolve: Q-07.

- Settings and channel settings screens with every control wired. Folder move for a channel.
- Banners, toasts, notifications. Error details dialog for every error code, with texts.
- Activity log. Help page. Report a problem. Debug report. Health check. The `explain` tool.

Acceptance: end-to-end flow 11 passes. Every error code has user text and a test that renders it.

## M8. Adopting existing files
Requirements: R-AD-01 to R-AD-08, R-MD-06.

- Scan, match, differences, three actions, resumable apply. Repair metadata.

Acceptance: end-to-end flow 8 passes. Fix in place is shown by test never to re-encode or download video data.

## M9. Installer, updater, uninstall, release pipeline
Requirements: R-IN-01, R-IN-02, R-UP-01 to R-UP-07, R-UN-01, R-QA-04. Resolve: Q-03.

- Release workflow, archive and checksums. `install.sh`. Launcher bundle.
- Updater for archive and clone installs, with backup, migration, rollback. yt-dlp overlay update with self-check.
- Uninstall.
- Migration test harness with a fixture database of this version.

Acceptance: end-to-end flow 12 passes. A manual install on a clean Mac works. An update from a test release to another test release works and rolls back when a migration is made to fail.

## M10. Website and documentation
Requirements: R-WS-01 to R-WS-05.

- VitePress site with the home page and documentation structure. User guide written for non-technical users. Developer docs moved into the site structure.
- Screenshot generation. Pages deployment workflow. Contributor files and issue templates checked.

Acceptance: the site builds and deploys from `main`, the install line on the home page works, screenshots are generated from the app.

## M11. Hardening and release
- Full manual checklist ([TESTING.md](TESTING.md) section 8). Accessibility pass. Performance check (R-QA-05, R-UI-07). Crash safety tests (R-QA-06).
- Final code review and test review of the whole code base. Mutation testing on `core/`.
- Requirements coverage script reports no gaps.
- Tag `v1.0.0`.

---

## Progress

- [ ] M0 Skeleton and tooling
- [ ] M1 Toolchain
- [ ] M2 Channels and catalogue
- [ ] M3 Downloading one video correctly
- [ ] M4 Dates everywhere
- [ ] M5 Queue
- [ ] M6 Excluding
- [ ] M7 Settings, feedback, activity, help
- [ ] M8 Adopting existing files
- [ ] M9 Installer, updater, uninstall, release pipeline
- [ ] M10 Website and documentation
- [ ] M11 Hardening and release
