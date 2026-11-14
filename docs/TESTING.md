# yt-mirror V1: Testing

Rule: a feature is not done until its tests exist, pass, and have been reviewed. Tests are code and follow [CODING-STANDARDS.md](CODING-STANDARDS.md).

## 1. Layers

| Layer | Tool | What it covers | Speed |
|---|---|---|---|
| Unit | pytest | `core/` rules: naming, dates, status machine, quality, exclusion, matching, error classification | Milliseconds, no I/O |
| Service | pytest with fakes | Each use case in `services/` against fake ports and an in-memory or temp SQLite | Fast |
| Integration | pytest on macOS | Real adapters: SQLite repositories, real file dates and Trash on a temp folder, real ffmpeg on tiny generated media, yt-dlp gateway against recorded responses, AppKit for the menu bar | Seconds |
| Window | pytest on macOS, marker `window` | The real app in a child process with its real window: the menu bar, the app's name, every way of quitting. These tests guard what relies on the pinned window library (D-049, D-052). A window appears for a few seconds. Leave them out with `uv run pytest -m "not window"` | Seconds |
| API | pytest + FastAPI test client | Every endpoint: success, validation errors, error code mapping, auth token, origin check | Fast |
| Migration | pytest | Upgrade from every released schema version with data, then verify | Fast |
| Component | Vitest + Vue Testing Library | Every shared component and every feature view with mocked API | Fast |
| End-to-end | Playwright | Real backend with the fake YouTube, real frontend, user flows through the UI, in WebKit and Chromium | Minutes |
| Live | pytest marker `live` | A few checks against the real YouTube. Opt-in, never in normal CI | Slow, flaky by nature |
| Manual | Checklist below | What cannot be automated | |

## 2. Rules

1. Every test says what it covers at the start of its docstring (Python) or its title (TypeScript). Which label a test gets is decided by this rule, in this order:
   1. **The test verifies behaviour that a requirement states, even partly.** It starts with that requirement's ID: `"""R-FN-05: a second video with the same title gets the ID suffix."""`. The requirement must really state the behaviour. An ID that is merely the closest fit is not allowed.
   2. **The test verifies real behaviour that a user or the maintainer relies on, but no requirement states it.** That is a gap in the spec, not an infrastructure test. Stop, propose a requirement to the maintainer, and label the test once the requirement is in [SPEC.md](SPEC.md). Such a test is never labelled `infra` and never borrows an ID.
   3. **The test verifies no product behaviour at all.** Only this is an infrastructure test. It starts with `infra:` and names no requirement: `"""infra: the fake clock moves only when told."""`. This covers the clock and other test doubles, test builders and fixtures, the check scripts, the test harness itself including variables that exist only for tests, and temporary scaffolding that a later milestone replaces (the placeholder page, the `--update` stub).

   A lint or check that a requirement itself demands is not infrastructure: the theme lint is tested under R-TH-06 and R-TH-09. In pytest, infrastructure tests also carry the marker `infra` (`uv run pytest -m infra`, or `-m "not infra"`).
2. A script (`scripts/requirements_coverage.py`) reads the IDs from [SPEC.md](SPEC.md) and from the tests and fails CI if a testable requirement has no test. It ignores infrastructure tests: they never count as coverage. It fails when a test starts with neither a requirement ID nor `infra:`. Requirements that can only be tested live or by hand are listed in `backend/tests/untestable.yml` with the reason. Until milestone M11 the script only reports. From then on CI runs it with `--strict`. A test that names an ID the spec does not contain fails the script from the start.
3. No test touches the network except those marked `live`.
4. No test depends on the current time, time zone or locale. Use the Clock port. The suite runs in CI under at least two time zones (UTC and one with a non-hour offset such as Asia/Tehran) because of the date rules.
5. No sleeps. Wait on events or use a fake clock.
6. Tests are independent and can run in any order and in parallel.
7. A bug fix starts with a test that fails for that bug.
8. Fakes live in one place and are themselves tested against the same contract tests as the real adapters, so a fake cannot drift from reality. The one fake that is not in that place is the fake YouTube, which is an adapter of the app because the app itself can start with it (D-062). It passes the same contract test.

## 3. Coverage thresholds (enforced in CI)

| Scope | Line coverage | Branch coverage |
|---|---|---|
| `backend/ytmirror/core` | 100% | 95% |
| `backend/ytmirror/services` | 95% | 90% |
| Backend overall | 90% | 85% |
| Frontend (stores, features, components) | 85% | 80% |

Coverage is a floor, not the goal. The review in section 7 is what establishes that the tests are good.

## 4. The fake YouTube

`e2e/fixtures/youtube/` holds a small recorded world: several channels with different shapes, one JSON file each. The gateway that reads it is `backend/ytmirror/adapters/fixture_youtube.py`. Channels arrive with the milestone that needs them: `small`, `large`, `tricky-titles`, `changing` and `empty` in M2, the others in M3.

| Fixture channel | Purpose |
|---|---|
| `small` | 12 videos, the default for most tests. Its preview has a video count. Other channels cover a count request that fails and a count that disagrees with the listing (R-CH-03) |
| `large` | 5,000 generated videos, for performance (R-UI-07, R-QA-05) |
| `tricky-titles` | Titles with `/`, `:`, emoji, right-to-left text, very long titles, duplicates, leading dots |
| `changing` | A script of changes between checks: every listing of this channel serves the next step. New video on top, new video between two older known ones, title change, removed video, video that reappears, a check that fails. It covers both kinds of check: a quick check never marks a video as removed |
| `empty` | A channel without any regular video |
| `failures` | One video per error code |
| `premieres` | Scheduled and premiered videos, for R-DT-03 |
| `no-subtitles`, `auto-subtitles-only` | Subtitle fallback (R-MD-03) |

The fake gateway produces small real MKV files (a few seconds of generated video and audio) so that file handling, ffprobe verification and dates are tested for real.

Recorded answers of yt-dlp for real channels and videos are stored (with titles, names and IDs replaced) in `backend/tests/fixtures/ytdlp/` and used to test the gateway's parsing. `python -m ytmirror.tools.record_ytdlp` refreshes these recordings on demand.

## 5. Mandatory test areas

These areas carry the most risk and need exhaustive tests, including property-based tests (hypothesis) where noted.

- **Dates (R-DT-*)**: every path that creates, renames, moves, repairs or re-downloads a file ends with creation and modification dates equal to the published time. Time zone independence. Premieres. Approximate dates never reach a file. Finder order equals app order.
- **Naming (R-FN-*)**: property-based: for any title, the result is a valid macOS file name, is at most 255 bytes, is NFC, is stable (same input, same output), and maps back to the same video. Collisions. Renames on title change.
- **Status machine**: every allowed transition, and every forbidden one is rejected.
- **Never lose data**: property-based sequences of operations (check, exclude, restore, rename, crash, restart) never delete or overwrite a user file except by an explicit delete choice.
- **Crash safety (R-QA-06)**: kill the process at each step of a download, a folder move, an adoption fix and an update, restart, and verify a consistent state.
- **Catalogue checks (R-CH-12 to R-CH-15)**: an empty, failed or cancelled listing changes nothing. Removal needs two misses in full checks. A quick check never marks a video as removed, whatever it reads.
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

What exists so far: flow 1 (milestone M1), and of flows 2, 9, 13 and 14 what milestone M2 builds (`e2e/tests/channels.spec.ts`): adding a channel from the welcome screen, the `changing` channel across quick and full checks, a failed check and "Try again", pausing, resuming and removing a channel, the menu and the dialogs by keyboard, and a channel of 5,000 videos. That a cancelled full check changes nothing is tested in the services and in the component tests, not end to end: the fake YouTube answers at once, so there is no moment to cancel in.

Every app these tests start runs against the fake YouTube (`YTM_FAKE_YOUTUBE`) with a library folder of its own (`YTM_LIBRARY_DIR`), and the browsers run in a fixed time zone, because dates are shown in the time zone of the machine (R-DT-02). A test that adds or changes channels starts an app of its own.

Visual regression: Playwright screenshots of every screen and of the theme preview page, in both themes, are compared with stored baselines (R-TH-09). The baselines are in `e2e/tests/__screenshots__/`, one per browser. After an intended visual change, update them with `npm --prefix e2e run test:update-screenshots`, look at the new images, and commit them.

The end-to-end tests start the real app themselves with `./start`, without a window, using the test variables of [ARCHITECTURE.md](ARCHITECTURE.md) section 10.

The tools the app downloads are stand-ins in these tests: tiny shell scripts, packed like the real downloads and served from the same Mac (`e2e/fixtures/tools/`), installed into a folder of the tests. The tests of the first run (flow 1) each start an app of their own on empty folders, and can make a download fail to see the retry and the second source. That the real tools download and run is checked by the smoke test of a fresh clone, on every supported macOS, from both sources (D-053).

Where the browsers come from:

| Browser | In CI | On a developer's Mac |
|---|---|---|
| WebKit | Playwright's own build | Playwright's own build. Its download works everywhere we know of, including the maintainer's Mac |
| Chromium | Playwright's own build | Playwright's own build where it can be downloaded. Otherwise an installed Google Chrome: `YTM_E2E_CHROME_CHANNEL=chrome npm --prefix e2e test` |

Playwright takes its Chromium from Google's "Chrome for Testing" download server, and that server refuses some locations with "not available in your location" (HTTP 403). This is the case on the maintainer's Mac. So there, Playwright's own Chromium runs only in CI, and local runs use the installed Chrome, which is a different version. The WebKit tests, the engine the app window uses, run locally and in CI alike. CI is the reference for the Chromium screenshots. The same run produces the website screenshots (R-WS-05).

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
- [ ] In the add channel dialog, "Choose..." opens the folder dialog of macOS, and the folder that was chosen is the one the channel is saved in (Q-09).
- [ ] Add a real channel with several thousand videos. The window stays usable while it is listed and while its pictures arrive.
- [ ] Quit during the first listing of a channel and start again. The listing starts again by itself.
- [ ] Mirror three videos at different qualities. They play in a media player with chapters, subtitles and cover.
- [ ] In Finder, sort the channel folder by Date Created and by Date Modified. The order matches YouTube.
- [ ] Get Info on a file shows the published time as created and modified.
- [ ] Exact dates fill in without an API key, and quickly with one.
- [ ] Quit during a download and reopen. The download continues.
- [ ] Unplug the library drive during a download. The app pauses and recovers.
- [ ] Update from the previous release. Data is intact.
- [ ] Uninstall. Videos remain.
- [ ] macOS notifications appear.
- [ ] The app is "yt-mirror" with its icon in the Dock, in the app switcher (Cmd+Tab), in the menu bar and in Activity Monitor. Nothing is called "Python".
- [ ] With another app in front, a click on the Dock icon brings the yt-mirror window forward. The same with the window minimized.
- [ ] Undo, Redo, Cut, Copy, Paste and Select All work with their shortcuts in a text field of the app.
- [ ] Log out of macOS, restart and shut down while the app runs. Each one goes through without the app holding it up, and the last line of the debug log is `app.stopping`.
