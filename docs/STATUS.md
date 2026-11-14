# yt-mirror: Status

This file is the single source of truth for where the project stands. Read it at the start of every session. It is updated only inside milestone pull requests, so `main` always shows what has really been merged.

**Version in progress:** 1.0
**Next milestone to start:** M3

| Milestone | Title | Status | Branch | Pull request | Merged |
|---|---|---|---|---|---|
| M0 | Project skeleton and tooling | Done | `m0-project-skeleton` | [#1](https://github.com/mderis/yt-mirror/pull/1) | 2026-11-13 |
| M1 | Toolchain and app identity | Done | `m1-toolchain-and-app-identity` | [#2](https://github.com/mderis/yt-mirror/pull/2) | 2026-11-14 |
| M2 | Channels and catalogue | In review | `m2-channels-and-catalogue` | | |
| M3 | Downloading one video correctly | Not started | | | |
| M4 | Exact dates and automatic checks | Not started | | | |
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

- **Open with the maintainer when the pull request of M2 was opened.** (1) About 70 tests of M2 name a requirement that does not state what they check, or are `infra` although they check product code. The list and a proposal for each are in the pull request. No label and no requirement text was changed for them: the maintainer decides. (2) R-CH-24 asks for "a short random delay between channels". The checks run one after another, but without a delay: the spec gives no length. (3) The design of the exact date fetch for M4 was proposed in the session of M2 and is not in the spec. What was measured for it is in OPEN-QUESTIONS (Q-08).
- **yt-dlp warns that its JavaScript challenge solver is missing (seen in M2, matters in M3, Q-04).** With the Deno path given, a metadata lookup still said "Some formats may be missing". Listings are not affected. M3 must settle it before the first download.
- **A metadata lookup of one video takes 3.5 to 10 seconds from the maintainer's network (M2, for M4).** The numbers and what follows from them are in OPEN-QUESTIONS (Q-08). From the CI runners of GitHub every such lookup was refused with the "not a bot" check, so nothing that looks up a video can be tested live in CI.
- **YouTube is reachable from the maintainer's Mac only on and off.** Requests sometimes stall completely for a while. The gateway has its own time limits. Live tests can fail for this reason alone: run them again before believing a failure.
- **The video list is not virtual before M5.** A channel of 5,000 videos takes about two seconds to draw in WebKit, once per load of its catalogue. The list is built so that nothing else draws it again (D-073).
- **The quality and "what to mirror" of a channel are only stored (M2).** They take effect in M3 (quality) and M5 (auto-mirror). The date of "only videos uploaded after" is stored as the start of that day in the time zone of the Mac.
- **The Chromium screenshots come from CI.** After an intended visual change, run WebKit locally, push, and take the new Chromium images from the `e2e-results` artifact of the failed run.
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
- **Q-09 is still not checked by a person.** The folder dialog is built on what the window library documents, and tested with a stand-in window. Nobody has clicked a folder in the real dialog yet. It is on the manual checklist (TESTING section 8).
- **Stubs that later milestones replace:** `./start --update` only says it is not available (M9). `./start --doctor` checks what exists so far, the tools included, not the network (M7). The fake YouTube has the channels of M2 only: `failures`, `premieres` and the subtitle channels arrive with M3.
- **The requirements coverage script only reports.** CI switches to `--strict` in M11.
- **TypeScript is 5.9 on purpose** (D-039). Move to a newer one when `openapi-typescript` and `typescript-eslint` support it.
- **Playwright's own Chromium cannot be downloaded on the maintainer's Mac** (the download server refuses the location). There, local runs use the installed Chrome with `YTM_E2E_CHROME_CHANNEL=chrome`, and Playwright's own Chromium runs only in CI. WebKit runs locally and in CI. See TESTING section 6.
- **Pre-commit hooks are turned on in the maintainer's clone** (`.git/hooks/pre-commit`). Turn them off with `scripts/uv run pre-commit uninstall`.
