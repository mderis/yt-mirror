# yt-mirror: Status

This file is the single source of truth for where the project stands. Read it at the start of every session. It is updated only inside milestone pull requests, so `main` always shows what has really been merged.

**Version in progress:** 1.0
**Next milestone to start:** M1

| Milestone | Title | Status | Branch | Pull request | Merged |
|---|---|---|---|---|---|
| M0 | Project skeleton and tooling | Done | `m0-project-skeleton` | [#1](https://github.com/mderis/yt-mirror/pull/1) | 2026-11-13 |
| M1 | Toolchain and app identity | In progress | `m1-toolchain-and-app-identity` | | |
| M2 | Channels and catalogue | Not started | | | |
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

- **Q-24 is answered (M1).** pywebview with AppKit can do the native Mac app from an unsigned bundle. How: ARCHITECTURE section 7.10 and decisions D-048 to D-052. The menu bar of M5 must be built through the same adapter, with public calls only, and the pywebview version stays pinned exactly.
- **Do not start M7 without the About window mockup.** The maintainer supplies it before M7 (R-NA-05, DESIGN section 7.2). If `docs/design/v1/` has no About mockup when an M7 session starts, stop and ask for it.
- **Labelling tests (TESTING rule 1, D-046).** A test whose behaviour no requirement states is a spec gap: propose the requirement to the maintainer, do not mark the test `infra` and do not borrow an ID.
- **`httpx2` is the app's HTTP client (D-041).** It is still a development package. The milestone that makes the first HTTP call (M1) moves it to the app's own packages.
- **Minimum macOS (D-035) is provisional.** M1 must confirm that the ffmpeg build it chooses (Q-05) and Deno run on macOS 15, then remove this note.
- **Q-09 is narrowed, not closed.** The folder picker opens, but nobody has checked by hand that it returns the chosen folder. Needed by M2.
- **Stubs that later milestones replace:** `./start --update` only says it is not available (M9). `./start --doctor` checks what exists so far, not the tools (M1) or the network (M7). `YTM_FAKE_YOUTUBE` is not read yet (M2).
- **The requirements coverage script only reports.** CI switches to `--strict` in M11.
- **TypeScript is 5.9 on purpose** (D-039). Move to a newer one when `openapi-typescript` and `typescript-eslint` support it.
- **Playwright's own Chromium cannot be downloaded on the maintainer's Mac** (the download server refuses the location). There, local runs use the installed Chrome with `YTM_E2E_CHROME_CHANNEL=chrome`, and Playwright's own Chromium runs only in CI. WebKit runs locally and in CI. See TESTING section 6.
- **Pre-commit hooks are turned on in the maintainer's clone** (`.git/hooks/pre-commit`). Turn them off with `scripts/uv run pre-commit uninstall`.
