# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- A native Mac app (milestone M1): `./start` builds a real app bundle on your Mac and starts the app through it. The running app is "yt-mirror" with its own icon in the Dock, the app switcher, the menu bar and Activity Monitor, and no longer "Python". A clone is "yt-mirror (dev)", so it can run next to an installed copy.
- The app's own menu bar, so far with the app menu and Edit: Undo, Redo, Cut, Copy, Paste and Select All work in text fields.
- Only one yt-mirror runs per data folder. Starting it again brings the open window to the front.
- The first-run screen: it shows the tools yt-mirror needs (Python, yt-dlp, ffmpeg, Deno), downloads the missing ones into the app folder with a progress bar, checks every download against its checksum, and offers "Try again" for a step that failed.
- ffmpeg has a second download source that is used when the first one fails. `./start --doctor` says which source a tool came from.
- The tools are checked at every start. A tool that is missing or stopped working gets a banner with an "Install now" button.
- Live updates in the window: the interface follows a download as it happens.
- The app folder can be moved or copied: the Python environment and the app bundle are rebuilt at the next start.

### Fixed
- Quitting with Cmd+Q, from the Dock, with Ctrl+C or with a termination signal now shuts the app down cleanly. Before, only closing the window did: the other ways ended the app without stopping its server and without the last log line.

### Added in milestone M0
- The project skeleton (milestone M0): `./start` prepares its own Python environment inside the app folder, builds the interface, and opens the app window with a placeholder page. Flags `--dev`, `--debug`, `--browser`, `--doctor`.
- The local server with its security checks: it listens on 127.0.0.1 only, rejects other origins, and requires a session token on every API call.
- Structured debug logs in `data/logs/`, one file per day, kept 14 days, with secrets removed.
- The database with migrations, and the settings table.
- The theme center: every colour, font, size, radius, shadow and animation duration is a named token in one folder, with a light and a dark theme, a lint check that allows only tokens, and a theme preview page for development.
- A convention for tests: each one names the requirement whose behaviour it verifies, or is marked `infra` when it verifies no product behaviour at all. Behaviour without a requirement is added to the specification first.
- An error code and user text for the case that the window cannot reach the app's own server.
- Automated checks on every pull request: lint, types, layer rules, tests with coverage thresholds, end-to-end tests in WebKit and Chromium with screenshots in both themes, and a smoke test that starts a fresh clone on macOS 15 and 26.
- Complete planning package for version 1: product specification, architecture, designs for every screen, test strategy, logging specification, release and update design, coding standards, glossary, decision records, implementation plan and open questions.
