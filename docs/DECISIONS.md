# yt-mirror: Decision Records

One entry per decision. Newest at the bottom. An entry is never edited after it is accepted: a change of mind is a new entry that says which one it replaces.

Format: **Decision**, **Why**, **Consequences**.

---

### D-001 Local app with a web UI, not a terminal app
**Decision:** The app is a local server with a graphical web UI.
**Why:** The core workflow is visual: thumbnails, selecting from hundreds of videos, several progress bars. A terminal cannot show thumbnails and makes long lists slow.
**Consequences:** A frontend build is needed. A command line interface is not part of V1.

### D-002 yt-dlp is the download engine, used as a Python library
**Decision:** Use yt-dlp through its Python API.
**Why:** It is the maintained standard for YouTube. The library gives structured progress, typed errors and control over post-processing that parsing command output cannot.
**Consequences:** The backend is Python. yt-dlp needs a JavaScript runtime (Deno) and ffmpeg. yt-dlp must be updatable independently of the app (D-017).

### D-003 Build our own app instead of using an existing one
**Decision:** Do not adopt Pinchflat, Tube Archivist, TubeSync or ytdl-sub.
**Why:** The requirements they do not centre on: picking individual videos with checkboxes, a permanent exclude list, file names equal to titles, exact file dates, adopting existing files, a native-feeling single-user Mac app.
**Consequences:** We own all the behaviour and all the maintenance.

### D-004 Python backend with FastAPI, Vue 3 frontend with TypeScript and Tailwind
**Decision:** As stated. Not Next.js or Nuxt, not Laravel.
**Why:** Meta-frameworks solve server rendering and deployment, which a local app does not need, and they suit long-running background work poorly. Python gives direct yt-dlp access. Vue with TypeScript is typed, component-based and easy for agents to read.
**Consequences:** Two languages. The OpenAPI schema is the contract and frontend types are generated from it.

### D-005 SQLite for all app state
**Why:** One file inside the app folder, no server, portable, enough for tens of thousands of videos.
**Consequences:** One writer at a time. WAL mode. Short transactions.

### D-006 MKV is the only container
**Why:** The user chose it. It holds any codec at any resolution, full subtitles, chapters, a cover and attachments (the raw metadata).
**Consequences:** Files do not play in QuickTime or on iOS without a third-party player. No container setting.

### D-007 Regular videos only
**Decision:** Shorts and live streams are not listed in V1.

### D-008 No proxy setting, no background running in V1
**Decision:** The app works only while open and has no proxy setting.
**Consequences:** Standard proxy environment variables are still honoured.

### D-009 File names are the titles, with lookalike substitutions only
**Decision:** Replace only characters macOS cannot store (`/`, `:`), with visually similar Unicode characters. Track files by video ID, never by name.
**Why:** The user wants names exactly like titles. Tracking by ID makes renames, duplicates and title changes safe.
**Consequences:** Rules in R-FN-*. A title change renames the file.

### D-010 Three separate dates, and file dates equal the published time
**Decision:** Store published, downloaded and last-seen times separately. Set both creation and modification date of every file to the exact published time, verify, and repair on every check.
**Why:** Dates are the user's highest priority. Finder must sort a folder like the channel.
**Consequences:** A macOS-specific adapter for creation dates. Approximate dates are never written to files.

### D-011 Exact dates from several sources, API key strictly optional
**Decision:** Channel feed for the newest videos, a slow background fetch by default, and an optional YouTube API key for speed.
**Why:** The channel listing gives only approximate dates. The slow path can take up to an hour for 1,000 videos. The API returns 50 videos per request for 1 quota unit.
**Consequences:** The app must work fully without a key. A guide explains how to get one.

### D-012 English subtitles, auto-generated as a fallback
**Decision:** Embed English creator subtitles. If none exist, embed auto-generated English.

### D-013 Thumbnails are embedded and also kept as files
**Decision:** Cover image inside the MKV, original in the hidden folder, optional visible image next to the video.

### D-014 Hidden `.yt-mirror` folder per channel folder
**Why:** The user-visible folder should contain only videos. Metadata next to the videos keeps the folder self-describing and lets a moved folder be re-linked.

### D-015 Exclusion is permanent, reversible, and can be rule-based
**Decision:** Manual excludes plus per-channel rules (title words, minimum length) with a preview and exceptions. Behaviour for already downloaded files is a setting: always ask, keep, delete.

### D-016 Deletions go to the Trash
**Why:** Nothing the user owns should be unrecoverable because of one click.

### D-017 yt-dlp updates independently of the app
**Why:** When YouTube changes, a fix must reach users within hours, without an app release.
**Consequences:** An overlay install of yt-dlp with a self-check and fallback.

### D-018 Everything in one portable folder, tools downloaded by the app
**Decision:** uv, Python, ffmpeg and Deno live in `tools/` inside the app folder. Nothing is installed system-wide.
**Why:** A new user does not know which tools are needed. A portable folder can be moved or copied.
**Consequences:** The app maintains a tool manifest with checksums. The Python environment is rebuilt after a move.

### D-019 macOS only for V1

### D-020 Dedicated window, closing it quits
**Decision:** The UI runs in its own window (pywebview). Closing the window quits the app, with a confirmation if downloads are running. A `--browser` flag exists.
**Why:** It makes "the app is open" unambiguous and feels like an app to non-technical users.
**Consequences:** The UI must be tested in WebKit as well as Chromium.

### D-021 Distribution through GitHub Releases, a one-line installer and an in-app updater
**Decision:** As in [RELEASE-AND-UPDATE.md](RELEASE-AND-UPDATE.md). Clone remains for developers. ZIP and installer installs update from release archives.
**Why:** Non-technical users cannot be asked to use git. An unsigned downloaded app is blocked by macOS, and a paid Apple Developer account is not planned for V1. Homebrew alone would freeze yt-dlp, require Homebrew, and remove the portable folder and in-app updates.
**Consequences:** Homebrew tap and a signed app are possible later additions.

### D-022 The built frontend is not committed
**Decision:** `frontend/dist` is produced by CI and shipped in release archives. A clone builds it with Node on `./start --dev`, or downloads the matching prebuilt bundle on a plain `./start`.
**Why:** Committed build output creates noisy diffs and can silently go stale. This replaces an earlier idea of committing the built files.
**Consequences:** Developers need Node. Users never do.

### D-023 Layered architecture with ports and adapters
**Why:** Every external dependency (YouTube, ffmpeg, file system, GitHub) can be faked, so the whole app is testable without the network, and agents can change one layer without understanding all of it.

### D-024 Structured logging with job IDs, status history and stable error codes
**Why:** Debugging by people and agents who were not present. See [LOGGING.md](LOGGING.md).

### D-025 Requirement IDs link spec, tests and commits
**Why:** Lets a script prove that every testable requirement has a test, and lets an agent find everything related to a behaviour.

### D-026 Two views (list and grid) in one sidebar shell, light and dark
**Decision:** The sidebar shell is used for both views. No separate start page: the app opens on the last channel.
**Why:** A top bar of channels does not scale past a few channels.

### D-027 The audience includes non-technical users
**Decision:** After the install line, everything is graphical: tool setup, updates, errors in plain language, uninstall, help, bug reporting.

### D-028 Bug reports go to GitHub Issues
**Decision:** "Report a problem" prepares a debug report and opens a pre-filled GitHub issue in the browser. The app sends nothing by itself.

### D-029 Documentation and website from one source
**Decision:** The website is a VitePress site built from `docs/` and deployed to GitHub Pages.

### D-030 MIT license, public repository

### D-031 Repository and website location
**Decision:** The repository is https://github.com/mderis/yt-mirror. The website is its GitHub Pages site at https://mderis.github.io/yt-mirror/.

### D-032 Auto-exclude rules also apply to downloaded videos
**Decision:** A rule excludes matching videos whether or not they are already downloaded. Their files follow the "when excluding a downloaded video" setting (always ask, keep, delete).

### D-033 The app tells users the YouTube API key is free
**Decision:** Wherever the optional API key is mentioned (setting, guide, website), the text says that it costs nothing, needs no payment details, and has only a daily usage limit.
**Why:** A request to "get an API key from Google Cloud" makes many people expect a bill.

### D-034 Copyright holder
**Decision:** The license names "Moslem Deris and contributors". The name is the one the maintainer uses publicly.

### D-035 The minimum is macOS 15, the oldest version that is tested
**Decision:** yt-mirror states macOS 15 as its minimum version. This answers open question Q-01.
**Why:** The oldest macOS that can be tested is 15: it is the oldest runner GitHub offers, and the maintainer's Mac is newer. The tools publish lower minimums (uv: macOS 13, pyobjc: 10.13), but nobody has run yt-mirror there. Stating only what is tested is honest and can be checked.
**Consequences:** CI runs on macOS 15 (Apple Silicon and Intel) and on the newest runner. The minimum is provisional until milestone M1 confirms that the chosen ffmpeg build and Deno run on macOS 15. It can be lowered later if someone tests an older Mac.

### D-036 One theme center for every visual value
**Decision:** Everything visual lives in `frontend/src/design/`: tokens as CSS variables with semantic names, the Tailwind preset, the bundled fonts and the brand icon source. A theme is one block of token values. Components may use only tokens, and a lint check in CI enforces it. The website uses the same token file. Requirements R-TH-01 to R-TH-09.
**Why:** The maintainer wants to change fonts, colours and other visual values in one place. Values scattered through components cannot be changed safely, and a second copy for the website would drift.
**Consequences:** Tailwind's default palette and scales are switched off, so only token-based classes exist. Fonts are committed as files with their licenses instead of coming from a package. "Same as system" is resolved by a few lines of script, because a media query would need the dark values twice. Each theme costs one block in `tokens.css`. The app-side parts are built in milestone M0, the website part (R-TH-07) in M10.

### D-037 A clone builds the interface with Node.js until releases exist
**Decision:** A plain `./start` in a clone builds `frontend/dist` with the local Node.js when it is missing or older than the sources, and stops with a clear message when Node.js is not installed. This changes one detail of D-022, which said a plain `./start` downloads the prebuilt bundle.
**Why:** There is no release to download a bundle from before milestone M9, and a fresh clone must start from M0 on. A clone of an unpushed commit could never get a matching bundle anyway.
**Consequences:** Developers need Node.js, as D-022 already said. Users of an installed copy still never do. Milestone M9 decides whether a clone should prefer a downloaded bundle when one matches.

### D-038 The session token is exchanged for a cookie
**Decision:** The token of the first URL is turned into an HttpOnly, SameSite=Strict cookie by the server, which then redirects to `/`. Every API call carries the cookie. A bearer header with the same token is accepted for tests and tools.
**Why:** The architecture required the token on every API call but did not say how. A cookie works with the browser's event stream (SSE), survives a reload, keeps the token out of the address bar and out of reach of scripts. A custom header would need a hand-written stream reader and a place to keep the token.
**Consequences:** The frontend contains no token handling at all. Cookies are not separated by port, so the cookie has a name of its own (`ytm_session`).

### D-039 Versions chosen at the start of implementation
**Decision:** Python 3.14 (managed by uv 0.13), FastAPI 0.162, SQLAlchemy 2.1, Alembic 1.20, structlog 26, pywebview 6.2, Node.js 26, Vue 3.5, Vite 8, Tailwind CSS 4.3, Vitest 5, Playwright 1.65, TypeScript 5.9. Exact versions are in `uv.lock` and the `package-lock.json` files.
**Why:** ARCHITECTURE section 2 asks for the current stable versions at the start. TypeScript is the exception: 7.0 is current, but the API type generator supports 5.x only and the lint tooling stops below 6.1, so 5.9 is the newest version every tool accepts.
**Consequences:** `requires-python` is 3.14 or newer: uv always installs the pinned Python, so older versions are never used and are not tested. The test client of FastAPI now needs `httpx2`, the successor of `httpx`. The first milestone that adds an HTTP client to the app itself (M1) decides between the two and updates ARCHITECTURE section 2.

### D-040 One database connection per unit of work
**Decision:** The SQLite engine uses no connection pool. A connection is opened for each unit of work and closed after it.
**Why:** Opening SQLite is cheap. Without a pool no connection stays open when the app stops or crashes, which fits the crash safety goal (R-QA-06) and keeps tests free of leaked connections.
**Consequences:** The WAL and foreign key settings are applied on every connection.

### D-041 httpx2 is the HTTP client of the app
**Decision:** The app uses `httpx2` for every HTTP call of its own: YouTube API, channel feed, GitHub releases, tool downloads. This settles the point D-039 left to milestone M1.
**Why:** `httpx2` is the maintained successor of `httpx`, and FastAPI's test client already requires it. One HTTP library for the app and the tests is simpler than two.
**Consequences:** ARCHITECTURE section 2 names `httpx2`. It moves from the development packages to the app's own packages in the milestone that makes the first HTTP call (M1).

### D-042 The generated brand icons are built in three milestones
**Decision:** The icon build script, its freshness test and the favicon belong to milestone M2, the macOS launcher icon (`.icns`) to M9, and the social preview image to M10.
**Why:** DESIGN section 5 describes the generated assets but no milestone contained them. Each asset is built where it is first needed.
**Consequences:** Until M2 the app has no favicon and draws its logo directly from `icon.svg`.

### D-043 Infrastructure tests carry a marker instead of a requirement ID
**Decision:** A test starts either with the requirement IDs it covers or with `infra:`. Tests of infrastructure (clock, scripts, tooling, wiring) use the marker and never borrow a requirement ID. The requirements coverage script ignores them, and fails on a test that has neither.
**Why:** In milestone M0 infrastructure tests were given the closest requirement ID. That made requirements look covered that no test really checked, for example R-QA-01 through the tests of the coverage script itself.
**Consequences:** The coverage report counts only real requirement tests. Every test must be labelled one way or the other, and CI checks it.

### D-044 A native Mac app through a locally built app bundle
**Decision:** yt-mirror appears and behaves as a native Mac app: its own name and icon everywhere, a real app bundle built on the user's Mac by the installer and by `./start`, a full menu bar, an About window, one quit path, one instance. Requirements R-NA-01 to R-NA-09. The parts are built in M1 (bundle, identity, one instance), M5 (menu bar, quit path), M7 (About window and the items of that milestone) and M9 (installer). Open question Q-24 is answered by experiment before any of it is built.
**Why:** The audience includes non-technical users (D-027). An app that shows up as "Python" with a generic icon and without the usual menus does not feel trustworthy. Building the bundle locally keeps D-021: no Apple Developer account, no signing.
**Consequences:** The window library must support custom menus, a custom app identity and single-instance behaviour from an unsigned bundle. If the experiment shows it cannot, work stops and the maintainer decides. The menu bar becomes the source of truth for shortcuts, and `Shortcuts.html` is read through DESIGN section 7.3. A signed, notarized DMG stays a roadmap item.

### D-045 The icon build script and the macOS icon move to M1
**Decision:** The icon build script, its freshness test and the macOS icon (`.icns`) are built in M1, together with the app bundle that needs them. The favicon stays in M2 and the social preview image in M10. This replaces the M2 and M9 parts of D-042.
**Why:** The app bundle of M1 needs the icon (R-NA-01, R-NA-02), so the icon cannot wait for M9, and the script that makes it cannot wait for M2.
**Consequences:** M2 only uses the script for the favicon. M9 reuses the bundle program of M1 for the installer.

