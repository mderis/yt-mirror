# yt-mirror: Status

This file is the single source of truth for where the project stands. Read it at the start of every session. It is updated only inside milestone pull requests, so `main` always shows what has really been merged.

**Version in progress:** 1.0
**Next milestone to start:** M1

| Milestone | Title | Status | Branch | Pull request | Merged |
|---|---|---|---|---|---|
| M0 | Project skeleton and tooling | In review | `m0-project-skeleton` | [#1](https://github.com/mderis/yt-mirror/pull/1) | |
| M1 | Toolchain | Not started | | | |
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

- **Minimum macOS (D-035) is provisional.** M1 must confirm that the ffmpeg build it chooses (Q-05) and Deno run on macOS 15, then remove this note.
- **Q-09 is narrowed, not closed.** The folder picker opens, but nobody has checked by hand that it returns the chosen folder. Needed by M2.
- **`httpx` or `httpx2`.** ARCHITECTURE section 2 names `httpx` as the app's HTTP client. The test client of FastAPI has moved to its successor `httpx2`, which is what the tests use. M1 adds the first HTTP client to the app itself and must choose, then update ARCHITECTURE (D-039).
- **Shadows are a first proposal.** The maintainer asked for real shadows. The values in DESIGN section 2.7 wait for the maintainer's judgement on the theme preview page.
- **The generated icons have no milestone.** `frontend/src/design/brand/icon.svg` exists and the app draws its logo from it. The build script for the `.icns`, favicon and social image, and its freshness test (DESIGN section 5), are assigned to no milestone yet. Suggested: favicon in M2, `.icns` in M9.
- **Stubs that later milestones replace:** `./start --update` only says it is not available (M9). `./start --doctor` checks what exists so far, not the tools (M1) or the network (M7). `YTM_FAKE_YOUTUBE` is not read yet (M2).
- **The requirements coverage script only reports.** CI switches to `--strict` in M11.
- **TypeScript is 5.9 on purpose** (D-039). Move to a newer one when `openapi-typescript` and `typescript-eslint` support it.
- **Chromium for Playwright cannot be downloaded on the maintainer's Mac** (the download server refuses the location). Local runs use `YTM_E2E_CHROME_CHANNEL=chrome`. CI uses Playwright's own Chromium.
- **Pre-commit hooks are turned on in the maintainer's clone** (`.git/hooks/pre-commit`). Turn them off with `scripts/uv run pre-commit uninstall`.
