# yt-mirror: Status

This file is the single source of truth for where the project stands. Read it at the start of every session. It is updated only inside milestone pull requests, so `main` always shows what has really been merged.

**Version in progress:** 1.0
**Next milestone to start:** M2

| Milestone | Title | Status | Branch | Pull request | Merged |
|---|---|---|---|---|---|
| M0 | Project skeleton and tooling | Done | `m0-project-skeleton` | [#1](https://github.com/mderis/yt-mirror/pull/1) | 2026-11-13 |
| M1 | Toolchain and app identity | Done | `m1-toolchain-and-app-identity` | [#2](https://github.com/mderis/yt-mirror/pull/2) | 2026-11-14 |
| M2 | Channels and catalogue | In progress | `m2-channels-and-catalogue` | | |
| M3 | Downloading one video correctly | Not started | | | |
| M4 | Dates everywhere | Not started | | | |
| M5 | Queue | Not started | | | |
| M6 | Excluding | Not started | | | |
| M7 | Settings, feedback, activity, help | Not started | | | |
| M8 | Adopting existing files | Not started | | | |
| M9 | Installer, updater, uninstall, release pipeline | Not started | | | |
| M10 | Website and documentation | Not started | | | |
| M11 | Hardening and release | Not started | | | |

Status values: `Not started`, `In progress`, `In review` (pull request open), `Done` (merged).

## Notes carried between sessions

Short facts the next session needs and cannot get from the code or the other docs: an open question that was answered, something that was deliberately postponed, a known problem. Newest first. Remove a note when it no longer matters.

- **The native Mac app relies on the pinned pywebview (M1).** How it works: ARCHITECTURE section 7.10 and decisions D-048 to D-052. pywebview stays pinned exactly. The tests with a real window (`backend/tests/integration/app/test_window_app.py`) are the guard for an update. The menu bar of M5 is built through the same adapter (`adapters/native_app_mac.py`), with public calls of pywebview and AppKit only.
- **M5 builds the quit confirmation on the quit path of M1 (D-052).** M1 built only the shutdown work: nothing in the app listens to the `closing` event, and no quit is ever held. What exists when: the table in ARCHITECTURE section 7.10. The decision part, to be built in M5, hangs on the `closing` event of the pywebview window, which also fires for Cmd+Q, the Dock and a logout. A logout, a restart and a shutdown must never be held for a question: the quit request of macOS carries its reason. The experiment code for all of this is not in the repository: the decision record describes it.
- **M3: the gateway tests run against both ffmpeg sources (D-053).** The second source is a patched fork. Until then only the self-check of both sources runs, in the smoke test of CI.
- **M7 owes the activity entry of an installed tool (R-IN-03, D-057).** It names the source the tool came from. Until the activity log exists, the source is in the debug log, in `./start --doctor` and in `/api/tools`: the maintainer accepted this in the review of M1.
- **M9 must ship the icon source file and the token file in the release archive (D-056),** or the installer cannot build the app bundle. The installer builds the bundle with `app/bundle.py`, with the identity of an installed copy ("yt-mirror").
- **Not checked by a person yet (M1).** The manual checklist of TESTING section 8 has four new items: the name and icon in the Dock, the app switcher and Activity Monitor, a real click on the Dock icon, the Edit shortcuts typed by hand, and a real logout, restart and shutdown on the maintainer's Mac. Automated tests and the experiment of Q-24 cover the mechanisms behind each of them.
- **Two tests need an unlocked screen.** The two tests that check that the window comes to the front skip themselves while the screen of the Mac is locked. CI runs them.
- **The first ffmpeg source builds no new Intel releases from January 2027 (D-053).** Intel stays at the pinned version.
- **Do not start M7 without the About window mockup.** The maintainer supplies it before M7 (R-NA-05, DESIGN section 7.2). If `docs/design/v1/` has no About mockup when an M7 session starts, stop and ask for it.
- **Labelling tests (TESTING rule 1, D-046).** A test whose behaviour no requirement states is a spec gap: propose the requirement to the maintainer, do not mark the test `infra` and do not borrow an ID.
- **Q-09 is narrowed, not closed.** The folder picker opens, but nobody has checked by hand that it returns the chosen folder. Needed by M2.
- **Stubs that later milestones replace:** `./start --update` only says it is not available (M9). `./start --doctor` checks what exists so far, the tools included, not the network (M7). `YTM_FAKE_YOUTUBE` is not read yet (M2).
- **The requirements coverage script only reports.** CI switches to `--strict` in M11.
- **TypeScript is 5.9 on purpose** (D-039). Move to a newer one when `openapi-typescript` and `typescript-eslint` support it.
- **Playwright's own Chromium cannot be downloaded on the maintainer's Mac** (the download server refuses the location). There, local runs use the installed Chrome with `YTM_E2E_CHROME_CHANNEL=chrome`, and Playwright's own Chromium runs only in CI. WebKit runs locally and in CI. See TESTING section 6.
- **Pre-commit hooks are turned on in the maintainer's clone** (`.git/hooks/pre-commit`). Turn them off with `scripts/uv run pre-commit uninstall`.
