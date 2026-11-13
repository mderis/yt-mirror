# yt-mirror: Status

This file is the single source of truth for where the project stands. Read it at the start of every session. It is updated only inside milestone pull requests, so `main` always shows what has really been merged.

**Version in progress:** 1.0
**Next milestone to start:** M1

| Milestone | Title | Status | Branch | Pull request | Merged |
|---|---|---|---|---|---|
| M0 | Project skeleton and tooling | In review | `m0-project-skeleton` | [#1](https://github.com/mderis/yt-mirror/pull/1) | |
| M1 | Toolchain and app identity | Not started | | | |
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

- **M1 starts with Q-24.** The native Mac app requirements (R-NA-01 to R-NA-09, D-044) were added to the docs during the M0 review and are not built. M1 gets the app bundle and the app identity, but only after the Q-24 experiment has shown that pywebview can do it. If it cannot, stop and ask the maintainer. The bundle identifier proposed in ARCHITECTURE section 7.10 needs the maintainer's confirmation.
- **The About window has no mockup yet.** It is needed before M7 (DESIGN section 7.2).
- **`httpx2` is the app's HTTP client (D-041).** It is still a development package. The milestone that makes the first HTTP call (M1) moves it to the app's own packages.
- **Minimum macOS (D-035) is provisional.** M1 must confirm that the ffmpeg build it chooses (Q-05) and Deno run on macOS 15, then remove this note.
- **Q-09 is narrowed, not closed.** The folder picker opens, but nobody has checked by hand that it returns the chosen folder. Needed by M2.
- **Stubs that later milestones replace:** `./start --update` only says it is not available (M9). `./start --doctor` checks what exists so far, not the tools (M1) or the network (M7). `YTM_FAKE_YOUTUBE` is not read yet (M2).
- **The requirements coverage script only reports.** CI switches to `--strict` in M11.
- **TypeScript is 5.9 on purpose** (D-039). Move to a newer one when `openapi-typescript` and `typescript-eslint` support it.
- **Playwright's own Chromium cannot be downloaded on the maintainer's Mac** (the download server refuses the location). There, local runs use the installed Chrome with `YTM_E2E_CHROME_CHANNEL=chrome`, and Playwright's own Chromium runs only in CI. WebKit runs locally and in CI. See TESTING section 6.
- **Pre-commit hooks are turned on in the maintainer's clone** (`.git/hooks/pre-commit`). Turn them off with `scripts/uv run pre-commit uninstall`.
