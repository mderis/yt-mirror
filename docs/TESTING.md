# yt-mirror V1: Testing

Rule: a feature is not done until its tests exist, pass, and have been reviewed. Tests are code and follow [CODING-STANDARDS.md](CODING-STANDARDS.md).

## 1. Layers

| Layer | Tool | What it covers | Speed |
|---|---|---|---|
| Unit | pytest | `core/` rules: naming, dates, status machine, quality, exclusion, matching, error classification | Milliseconds, no I/O |
| Service | pytest with fakes | Each use case in `services/` against fake ports and an in-memory or temp SQLite | Fast |
| Integration | pytest on macOS | Real adapters: SQLite repositories, real file dates and Trash on a temp folder, real ffmpeg on tiny generated media, yt-dlp gateway against recorded responses | Seconds |
| API | pytest + FastAPI test client | Every endpoint: success, validation errors, error code mapping, auth token, origin check | Fast |
| Migration | pytest | Upgrade from every released schema version with data, then verify | Fast |
| Component | Vitest + Vue Testing Library | Every shared component and every feature view with mocked API | Fast |
| End-to-end | Playwright | Real backend with the fake YouTube, real frontend, user flows through the UI, in WebKit and Chromium | Minutes |
| Live | pytest marker `live` | A few checks against the real YouTube. Opt-in, never in normal CI | Slow, flaky by nature |
| Manual | Checklist below | What cannot be automated | |

## 2. Rules

1. Every test names the requirements it covers in its docstring or title: `"""R-FN-05: a second video with the same title gets the ID suffix."""`.
2. A script (`scripts/requirements_coverage.py`) reads the IDs from [SPEC.md](SPEC.md) and from the tests and fails CI if a testable requirement has no test. Requirements that can only be tested live or by hand are listed in `tests/untestable.yml` with the reason.
3. No test touches the network except those marked `live`.
4. No test depends on the current time, time zone or locale. Use the Clock port. The suite runs in CI under at least two time zones (UTC and one with a non-hour offset such as Asia/Tehran) because of the date rules.
5. No sleeps. Wait on events or use a fake clock.
6. Tests are independent and can run in any order and in parallel.
7. A bug fix starts with a test that fails for that bug.
8. Fakes live in one place and are themselves tested against the same contract tests as the real adapters, so a fake cannot drift from reality.

## 3. Coverage thresholds (enforced in CI)

| Scope | Line coverage | Branch coverage |
|---|---|---|
| `backend/ytmirror/core` | 100% | 95% |
| `backend/ytmirror/services` | 95% | 90% |
| Backend overall | 90% | 85% |
| Frontend (stores, features, components) | 85% | 80% |

Coverage is a floor, not the goal. The review in section 7 is what establishes that the tests are good.

## 4. The fake YouTube

`e2e/fixtures/youtube/` holds a small recorded world: several channels with different shapes.

| Fixture channel | Purpose |
|---|---|
| `small` | 12 videos, the default for most tests |
| `large` | 5,000 generated videos, for performance (R-UI-07, R-QA-05) |
| `tricky-titles` | Titles with `/`, `:`, emoji, right-to-left text, very long titles, duplicates, leading dots |
| `changing` | A script of changes between checks: new video, title change, removed video, video that reappears |
| `failures` | One video per error code |
| `premieres` | Scheduled and premiered videos, for R-DT-03 |
| `no-subtitles`, `auto-subtitles-only` | Subtitle fallback (R-MD-03) |

The fake gateway produces small real MKV files (a few seconds of generated video and audio) so that file handling, ffprobe verification and dates are tested for real.

Recorded yt-dlp metadata from real videos is stored (with titles and IDs replaced) in `backend/tests/fixtures/ytdlp/` and used to test the gateway's parsing. A script refreshes these recordings on demand.

## 5. Mandatory test areas

These areas carry the most risk and need exhaustive tests, including property-based tests (hypothesis) where noted.

- **Dates (R-DT-*)**: every path that creates, renames, moves, repairs or re-downloads a file ends with creation and modification dates equal to the published time. Time zone independence. Premieres. Approximate dates never reach a file. Finder order equals app order.
- **Naming (R-FN-*)**: property-based: for any title, the result is a valid macOS file name, is at most 255 bytes, is NFC, is stable (same input, same output), and maps back to the same video. Collisions. Renames on title change.
- **Status machine**: every allowed transition, and every forbidden one is rejected.
- **Never lose data**: property-based sequences of operations (check, exclude, restore, rename, crash, restart) never delete or overwrite a user file except by an explicit delete choice.
- **Crash safety (R-QA-06)**: kill the process at each step of a download, a folder move, an adoption fix and an update, restart, and verify a consistent state.
- **Catalogue checks (R-CH-12 to R-CH-15)**: an empty or failed listing changes nothing. Removal needs two misses.
- **Queue (R-QU-*)**: parallelism limit, ordering, pause and resume, retry policy by error kind, disk guard, unavailable folder.
- **Exclusion (R-EX-*)**: excluded videos are never queued by any path. Rules, preview, exceptions.
- **Adoption (R-AD-*)**: certain, proposed and ambiguous matches. Fix in place never re-encodes.
- **Updater (R-UP-*)**: success, failure at each step with rollback, refusing a newer database.
- **API security**: token required, foreign origins rejected.
- **Theme (R-TH-*)**: every theme defines the same tokens, every token used in code is defined, code outside the theme center uses only tokens.

## 6. End-to-end flows (Playwright)

1. First run: tools install screen, then welcome.
2. Add a channel, pick two videos, mirror, watch progress, see them synced, open details.
3. Auto-mirror with "only after a date", then a check that brings a new video.
4. Exclude a downloaded video with each of the three file behaviours. Undo. Restore.
5. Auto-exclude rules with preview and an exception.
6. Queue: reorder, pause all, cancel, retry a failed download, error details.
7. Quality change with re-download.
8. Adopt existing files with a certain, a proposed and an ambiguous match.
9. Title change on YouTube renames the file. Removed video keeps its file.
10. Disk guard pauses the queue. Missing folder banner.
11. Settings: every control changes the stored value and the behaviour it controls.
12. App update: success and rollback.
13. Light and dark theme, list and grid, keyboard-only use of the main flow.
14. Accessibility scan (axe) on every screen: no serious violations.

Visual regression: Playwright screenshots of every screen and of the theme preview page, in both themes, are compared with stored baselines (R-TH-09). The same run produces the website screenshots (R-WS-05).

## 7. Reviews

After the implementation of each milestone:

1. **Code review** by a reviewer (human or a separate agent that did not write the code) against [CODING-STANDARDS.md](CODING-STANDARDS.md) and the spec.
2. **Test review**: for each requirement in the milestone, read its tests and ask: would this test fail if the requirement were broken? Mutation testing (`mutmut` on `core/`) is run to find tests that cannot fail.
3. Findings are fixed before the next milestone starts.

## 8. Live tests and the manual checklist

Run before every release, on a real Mac with a real connection.

Automated (`uv run pytest -m live`): list one known public channel, fetch metadata for one video, download one short video at 480p and verify the file, its metadata and its dates.

Manual:
- [ ] Fresh install with the one-line installer on a Mac that never had yt-mirror. No security warning blocks the launcher (Q-03).
- [ ] First run installs the tools and reaches the welcome screen.
- [ ] Add a real channel. The catalogue matches the channel's Videos tab.
- [ ] Mirror three videos at different qualities. They play in a media player with chapters, subtitles and cover.
- [ ] In Finder, sort the channel folder by Date Created and by Date Modified. The order matches YouTube.
- [ ] Get Info on a file shows the published time as created and modified.
- [ ] Exact dates fill in without an API key, and quickly with one.
- [ ] Quit during a download and reopen. The download continues.
- [ ] Unplug the library drive during a download. The app pauses and recovers.
- [ ] Update from the previous release. Data is intact.
- [ ] Uninstall. Videos remain.
- [ ] macOS notifications appear.
