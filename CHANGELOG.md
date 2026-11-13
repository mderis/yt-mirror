# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- The project skeleton (milestone M0): `./start` prepares its own Python environment inside the app folder, builds the interface, and opens the app window with a placeholder page. Flags `--dev`, `--debug`, `--browser`, `--doctor`.
- The local server with its security checks: it listens on 127.0.0.1 only, rejects other origins, and requires a session token on every API call.
- Structured debug logs in `data/logs/`, one file per day, kept 14 days, with secrets removed.
- The database with migrations, and the settings table.
- The theme center: every colour, font, size, radius, shadow and animation duration is a named token in one folder, with a light and a dark theme, a lint check that allows only tokens, and a theme preview page for development.
- A convention for tests: each one names the requirement whose behaviour it verifies, or is marked `infra` when it verifies no product behaviour at all. Behaviour without a requirement is added to the specification first.
- An error code and user text for the case that the window cannot reach the app's own server.
- Automated checks on every pull request: lint, types, layer rules, tests with coverage thresholds, end-to-end tests in WebKit and Chromium with screenshots in both themes, and a smoke test that starts a fresh clone on macOS 15 and 26.
- Complete planning package for version 1: product specification, architecture, designs for every screen, test strategy, logging specification, release and update design, coding standards, glossary, decision records, implementation plan and open questions.
