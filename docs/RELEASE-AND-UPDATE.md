# yt-mirror V1: Distribution, Installation and Updates

Requirements: R-IN-*, R-UP-*, R-UN-*, R-WS-* in [SPEC.md](SPEC.md).

## 1. Principles

1. **GitHub Releases are the single source.** The repository is https://github.com/mderis/yt-mirror and the website is https://mderis.github.io/yt-mirror/. Every way of installing ends up with the contents of one release archive.
2. **One folder.** App code, tools and data are in one folder. Nothing is installed system-wide and no admin password is needed.
3. **Code and data are separate.** Updates replace code and never touch `data/` or the user's videos.
4. **Every update can be undone automatically** if it fails.

## 2. Folder layout of an installed app

```
~/Applications/yt-mirror/          (default, the installer asks nothing)
  app/                             Code from the release archive (replaced on update)
    start  backend/  frontend/dist/  pyproject.toml  uv.lock  VERSION
  tools/                           uv, Python, ffmpeg, ffprobe, Deno (survive updates)
  data/                            Database, logs, backups, cache, settings (never replaced)
  previous/                        The previous app/ kept until the next successful start
~/Applications/yt-mirror.app       The app bundle, built locally by the installer (R-NA-02)
~/.local/bin/yt-mirror             Command line launcher (only if that folder is on PATH)
```

A clone has the same `tools/` and `data/` folders in the repository root (both ignored by git), and the repository itself plays the role of `app/`. `./start` on a clone builds the same app bundle inside `tools/` and starts the app through it, so the app has its own name and icon there too (R-NA-01, R-NA-02, from milestone M1).

## 3. Versions and releases

- Semantic versioning: `MAJOR.MINOR.PATCH`. The version lives in `pyproject.toml` and is copied to `VERSION` in the archive.
- A release is created by pushing a tag `vX.Y.Z`. A GitHub Actions workflow then:
  1. Runs the full test suite.
  2. Builds the frontend.
  3. Produces `yt-mirror-X.Y.Z.tar.gz` containing `app/` as above (backend source, built frontend, lock files, `start`, `VERSION`). No tools and no Python packages are inside.
  4. Writes `SHA256SUMS`.
  5. Publishes the GitHub Release with the changelog section for that version as release notes.
  6. Rebuilds the website so the installer serves the new version.
- `CHANGELOG.md` follows "Keep a Changelog". Every pull request adds to "Unreleased".

## 4. Installer (`install.sh`)

Served at `https://mderis.github.io/yt-mirror/install.sh` and run with `curl -fsSL <url> | sh`. It must be short, readable and POSIX `sh`. Steps:

1. Check macOS and the CPU architecture. Stop with a clear message on anything else.
2. Refuse to overwrite an existing installation: offer to open it instead.
3. Ask GitHub for the latest release, download the archive and `SHA256SUMS`, verify the checksum.
4. Unpack into `~/Applications/yt-mirror/app`.
5. Download `uv` into `tools/` (pinned version and checksum), then let `uv` install Python and the locked dependencies into `tools/`.
6. Build the app bundle (a real macOS app bundle with `Info.plist`, bundle identifier and icon, [ARCHITECTURE.md](ARCHITECTURE.md) section 7.10) and, if possible, the command line launcher.
7. Write everything it did to `data/logs/install.log`.
8. Start the app.

The installer installs nothing else. ffmpeg and Deno are installed by the app's first-run screen (R-IN-03) where progress and errors can be shown properly.

`VERIFY` (Q-03): files fetched by `curl` and an app bundle created locally are not quarantined by Gatekeeper, so the launcher opens without a security prompt.

Environment overrides for advanced users and tests: `YTM_INSTALL_DIR`, `YTM_VERSION`.

## 5. Tools

| Tool | Installed by | Updated by | Source |
|---|---|---|---|
| uv | Installer or `./start` | App update (pinned per release) | Official uv release binaries |
| Python | uv | uv, pinned by `.python-version` | uv managed builds |
| Python packages except yt-dlp | uv from `uv.lock` | App update | PyPI |
| yt-dlp | uv | Independently, one click (R-UP-06) | PyPI |
| ffmpeg and ffprobe | First-run screen | App update (pinned per release) | Martin Riedl's build server. Second source: jellyfin-ffmpeg portable builds on GitHub (D-053) |
| Deno | First-run screen | App update (pinned per release) | Official Deno release binaries |

- Each downloadable tool has, in `backend/ytmirror/services/toolchain_manifest.json`: one or two sources, each with its version, its URL per architecture and its SHA-256, and the command that proves the tool works. The second source is tried when the first fails or its file does not match its checksum. The project mirrors no binaries itself.
- yt-dlp is the exception to locked versions, because it must be updatable within hours when YouTube changes. The app installs the newest yt-dlp into an overlay directory in `tools/` that takes precedence over the locked one, and records the version in the debug report. An app update resets the overlay if the locked version is newer.
- Before using a new yt-dlp, the app runs a self-check (list one fixture, import the library). If it fails, the previous version stays active.

## 6. App update flow

Trigger: banner, Settings, or `./start --update`.

1. **Check**: read the latest release from the GitHub API. Compare with the installed version. Respect "skip this version".
2. **Show**: version, release notes, what will happen.
3. **Preflight**: free space, no jobs in `processing` (wait for them or ask), queue paused.
4. **Download**: archive and checksums into `data/cache/update/`. Verify.
5. **Backup**: copy the database with SQLite's backup API to `data/backups/yt-mirror-<old version>-<timestamp>.db`. Keep the 5 most recent backups.
6. **Swap code**: `archive` installs move `app/` to `previous/` and unpack the new one. `clone` installs run `git fetch --tags` and check out the release tag, after confirming the working tree is clean (if not, explain and stop).
7. **Dependencies**: `uv sync --frozen`.
8. **Restart** into the new version in "migrating" mode.
9. **Migrate**: run pending Alembic migrations inside the new version. Run the post-migration self-check (open the database, load state, check tools).
10. **Finish**: mark the update as successful, delete `previous/` on the next successful start.

Rollback, at any failure in steps 6 to 9: restore `previous/` (or check out the previous tag), restore the database backup, start the old version, show what failed with the error code and a "Report a problem" button. Log `update.rolled_back`.

## 7. Database migrations

- Alembic, forward only. One migration per schema change, named `NNNN_short_description`.
- Each migration is written to be safe on a database of any size the app can produce and must not lose data.
- The app refuses to start on a database whose schema version is higher than it knows (R-UP-05).
- Tests: for every released version there is a fixture database in `backend/tests/migrations/fixtures/`. A test upgrades each one to the current schema and checks the data (R-QA-04).

## 8. Uninstall

"Uninstall yt-mirror" (R-UN-01) removes `app/`, `tools/`, `previous/`, the app bundle and the command line launcher. If the user chooses, `data/` is moved to the Trash. The library and channel folders are never touched. The last step is done by a small script that runs after the app has quit.

## 9. Website

- VitePress site in `docs/`, with a custom home page (`SiteHome.html` design) and the documentation pages (`SiteDocs.html` design).
- Sections: User guide (written for non-technical users, with screenshots) and For developers (architecture, running from source, testing, logging, contributing, releases, guide for AI agents, decisions, changelog).
- Deployed to GitHub Pages by a workflow on every push to `main` and on every release.
- `install.sh` is copied into the site's public folder at build time, so there is one copy in the repository.
- Screenshots are produced by the Playwright screenshot run (R-WS-05) and committed by the release workflow.

## 10. Later channels (not in V1)

- **Homebrew tap**: a formula that installs the same release archive. Cheap to add, but the app must then keep its own yt-dlp overlay and disable the in-app app updater in favour of `brew upgrade`.
- **Signed and notarized Mac app in a DMG**: drag-and-drop install, the best experience for non-technical users. Needs an Apple Developer Program membership. The options and their consequences are in [ROADMAP.md](ROADMAP.md).
