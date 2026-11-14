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

### D-046 Three groups decide how a test is labelled
**Decision:** A test that verifies behaviour a requirement states carries that requirement's ID. A test that verifies real behaviour no requirement states is a gap in the spec: the requirement is proposed to the maintainer first. Only a test that verifies no product behaviour at all is an infrastructure test with the `infra:` marker. No test carries an ID that is merely the closest fit. This replaces the scope given in D-043, which had counted the wiring of the app and whole areas such as the health endpoint as infrastructure.
**Why:** The first use of the marker in milestone M0 put 114 tests under it, among them tests of the launcher flags, the health endpoint and the setting defaults. That hid gaps in the spec. Sorting those tests by this rule led to twelve new requirements (R-PL-10 to R-PL-13, R-IN-06, R-IN-07, R-SE-04, R-ER-04, R-LG-06 to R-LG-08, R-QA-07).
**Consequences:** The `infra` marker stays rare. A missing requirement is found when its test is written, and is added to the spec instead of being hidden behind a marker or a borrowed ID.

### D-047 The bundle identifier is io.github.mderis.yt-mirror and never changes
**Decision:** The macOS app bundle uses the bundle identifier `io.github.mderis.yt-mirror`.
**Why:** It follows the address of the project's website, which the maintainer controls. macOS ties an app's identity, its saved window state and its permissions to this identifier.
**Consequences:** The identifier must never change, not even if the repository moves. A change would make macOS treat yt-mirror as a different app.

### D-048 The app runs inside its bundle through a link to its own Python
**Decision:** The program that macOS starts in the app bundle is a small shell script. It starts the app's Python through a symbolic link that lies inside `Contents/MacOS` and is named after the app. Finder and `./start` both start the app through the bundle. This answers point (b) of open question Q-24.
**Why:** macOS decides which app a process belongs to from the place of its program file. In the experiment (macOS 15 on Apple Silicon and Intel, macOS 27) this bundle appeared as "yt-mirror" with its icon in Launch Services, the menu bar and the process list, for a start from Finder and for a start from a terminal. A launcher that starts Python at its own place outside the bundle appeared as "python" when started from a terminal.
**Consequences:** The link holds an absolute path, so the bundle is rebuilt when the folder moved. The Python must be the one uv manages: a framework build of Python (Homebrew, python.org) restarts itself as its own `Python.app` and appears as "Python". `./start` allows only the managed Python already. The bundle is not signed and needs no signing, because it is built on the Mac that runs it.

### D-049 The menu bar is built with AppKit, and pywebview is pinned exactly
**Decision:** yt-mirror builds its whole menu bar with AppKit and puts it in place of pywebview's menus when the window is shown. The code lives in one adapter and uses only public calls of pywebview and AppKit. The pywebview version is pinned exactly, and a test asserts the structure of the menu bar. This answers point (a) of open question Q-24.
**Why:** pywebview's own menu API has no shortcuts and no way to enable or disable an item, and pywebview always adds menus of its own: an About item, Services, a View menu, and an Edit menu without Undo and Redo. The experiment showed that a menu bar built with AppKit replaces all of them, that its shortcuts work (Undo, Redo, Cut, Copy, Paste and Select All in a text field of the web view included), that an item can be enabled and disabled while the app runs, and that this still holds after a window was closed and another opened, and on a second launch. AppKit comes with pyobjc, which pywebview needs anyway.
**Consequences:** The approach relies on pywebview setting its own menus only once, when the first window is shown. An update of pywebview could change that, hence the exact pin and the test. macOS adds items of its own to menus called File, Edit and Window (for example Close All, AutoFill, Start Dictation, Emoji & Symbols). They are left alone. Quit ends the process inside AppKit without returning to the code after the window loop, so the clean stop is tied to AppKit's "will terminate" notification as well.

### D-050 One instance per data folder, and a second start reopens the bundle
**Decision:** A running app holds a lock on a file in its data folder, in every mode: window, `--browser` and without a window. A second start for a window that finds the lock held asks macOS to open the app bundle again and ends. A second start with `--browser` or without a window ends with a plain message. This answers point (c) of open question Q-24.
**Why:** Two apps on one database would run every check and every download twice. Opening the bundle again is what a click on the Dock icon does: macOS brings the window of the running app to the front, also when it is minimized or the app is hidden. The experiment showed this for a second start from Finder and from a terminal. The second start decides before it loads the window library, so no second Dock icon appears.
**Consequences:** The lock is tied to the data folder, not to the Mac: a test run with its own data folder is not affected by an open app. The lock is released by the system when the process ends, also after a crash, so no stale lock can block a start.

### D-051 A clone has its own identity: "yt-mirror (dev)"
**Decision:** The app bundle that `./start` builds on a clone has the bundle identifier `io.github.mderis.yt-mirror.dev` and the name "yt-mirror (dev)". An installed copy keeps the identifier of D-047 and the name "yt-mirror".
**Why:** A developer has an installed copy and a clone on the same Mac. With one identifier macOS would treat them as the same app: one Dock icon, shared saved state, and a start of one could bring the other to the front. With two identities both can run and are told apart in the Dock.
**Consequences:** D-047 still holds for the installed app: its identifier never changes. The `.dev` identifier is fixed in the same way. Everything that shows the app name on a clone shows "yt-mirror (dev)".

### D-052 One quit path for every way of quitting
**Decision:** Every way of quitting ends in one quit path with two parts: a decision whether the app may quit now, and the shutdown work, which runs once. The decision hangs on the `closing` event of the pywebview window. The shutdown work hangs on the end of the window loop and on AppKit's "will terminate" notification. Ctrl+C and a termination signal are turned into the same quit request with Python's `signal` module. Logout, restart and shutdown are recognised by the reason that the quit request of macOS carries: they are never held for a question, only for the shutdown work. This is point (d) of open question Q-24, added by the maintainer after the experiment showed that Quit ended the test app at once.
**Why:** In milestone M0 the shutdown code ran only when the window was closed. On Cmd+Q, Quit in the Dock, Ctrl+C and a termination signal the app ended without stopping its server and without its last log line, because Quit ends the process inside AppKit and the code after the window loop never runs. The experiment showed, on macOS 15 (Apple Silicon and Intel) and on macOS 27, that with this quit path our code runs before the process ends for Cmd+Q, the Quit item, Quit in the Dock, the window button, Cmd+W, Ctrl+C, a termination signal and the quit requests of logout, restart and shutdown, that it has time to stop a worker and close a database, and that the quit can be held and later confirmed. One real logout on macOS 15 ran through it. Only public calls of pywebview, AppKit and Python are used.
**Consequences:** The approach relies on pywebview asking the `closing` event when AppKit asks whether the app may terminate. An update of pywebview could change that, which the exact pin (D-049) and a test guard against. The app replaces the Ctrl+C handling that pywebview sets up with its own, so that both signals take the same path. The shutdown work at a logout must be short, because macOS does not wait without limit. A handler of an AppKit notification must return nothing, or AppKit drops the event being handled. R-PL-13 names every way of quitting now. The quit path is built in two steps. Milestone M1 builds the shutdown work for every way of quitting, and the turning of Ctrl+C and a termination signal into a quit request. Milestone M5 builds the decision part: the handler of the `closing` event, the "quit while downloading" confirmation (R-NA-06, R-QU-12), and the reading of the reason so that a logout, a restart and a shutdown are never held for a question. After M1 nothing in the app listens to the `closing` event: no quit is held, the app never asks, and every quit gets the same shutdown work. The decision part exists only as the throwaway code of the experiment, which is not in the repository.

### D-053 Where ffmpeg, ffprobe and Deno come from
**Decision:** ffmpeg and ffprobe come from Martin Riedl's build server (https://ffmpeg.martin-riedl.de): unpatched upstream FFmpeg, release 9.0.2 at the time of this decision. The tool manifest allows a second source per tool, tried when the first fails or its file does not match its checksum. For ffmpeg and ffprobe the second source is the portable build of jellyfin-ffmpeg from its GitHub releases (8.1.3-2 at the time of this decision). Each source has its own pinned version, address and SHA-256. The second source publishes no checksum files, so its checksums are computed and pinned by us. Whichever file is installed must pass the same self-check, and `./start --doctor` and the activity log say which source was used. Deno comes from its official GitHub releases, with the checksums published there. The project mirrors no binaries itself. This answers the first part of open question Q-05.
**Why:** Of eight sources compared in November 2026, the first is the only one with native builds for Apple Silicon and Intel, both tools, unpatched upstream code, version-pinned addresses, published SHA-256 files and signed binaries. It links only system libraries, states macOS 12 as its minimum, is GPL version 3 without nonfree parts, and offers addresses for automated downloads. The second is run by an organisation with a public build on GitHub. The others fail on one point each: no Apple Silicon build, a stale Intel build with unclear terms, a build that may not be redistributed, a minimum of macOS 26, or no macOS build at all. yt-mirror only downloads these programs and runs them as separate programs, so their license does not touch its own.
**Consequences:** Known risks, accepted by the maintainer. The first source is one person's server: that old addresses stay is observed since 2022, not promised, and if the server goes away, first-run setup depends on the second source until an app update pins another. From January 2027 it builds no new Intel releases, so Intel stays at the pinned version. The second source is a patched fork on an older branch, and its Intel binary is not signed. CI therefore runs the self-checks against both sources, and from milestone M3 the gateway tests run against both. No source states a limit for automated downloads. Downloads from GitHub releases can be slow: from the maintainer's network 35 to 40 MB took about five minutes, so download timeouts must be generous and progress must be visible. Mirroring the binaries would make the project a distributor under the GPL, with the duty to offer the source code, so it is not done.

### D-054 The macOS icon uses the light theme's colours
**Decision:** The app icon (`.icns`) is drawn with the values of the light theme: the accent `#1F5FD1` with a white mark.
**Why:** The Dock icon is one image and cannot follow the theme. The maintainer chose the light pair.
**Consequences:** The icon build script reads the two values from the light block of the token file, so a change of the tokens still changes the icon. A dark variant of the icon is not built.

### D-055 When the first-run screen is shown
**Decision:** The first-run screen is shown until every tool was in order once. That moment is stored in the database (`app_meta`, key `setup_completed_at`). After that, a start at which two or more tools are missing or broken shows the first-run screen again. A single missing or broken tool gets the banner with "Install now" instead.
**Why:** The spec named a first-run screen (R-IN-03) and a banner for later starts (R-IN-04), but not how the app tells the two apart. Two missing tools mean that the tools folder is gone or was never there, for example after the app folder was copied without it: that is a first run again in everything but name. One missing tool is a repair.
**Consequences:** Migration 0003 creates `app_meta`. The rule itself is one function in `core/toolchain.py`. The interface keeps the first-run screen open until the user presses "Continue", also after the last tool was installed.

### D-056 Generated icon assets are not committed
**Decision:** The macOS icon is drawn from the icon source file on the user's Mac, by AppKit, when the app bundle is built. It is not committed and not shipped. Tests draw the real source and compare the picture with it: the two token colours, the area the source gives the rounded square, transparency outside of it, and that macOS reads the icon file with every size. They run on macOS 15 in CI.
**Why:** A committed asset can go stale without anyone noticing, as with the built interface (D-022). AppKit reads SVG by itself, so the user's Mac needs neither Node.js nor another tool. DESIGN section 5 asked for a test that every asset is newer than its source, but file times do not survive a git checkout. The bundle records what it was built from instead and is rebuilt when the source or the token file changed.
**Consequences:** The icon build is Python code of the app (`core/icon.py`, `app/bundle.py`), not a script of the frontend. The favicon of M2 and the images of M10 are built from the same source file. An archive install has no `frontend/src`, so milestone M9 must ship the icon source file and the token file with the release archive, or the installer cannot build the bundle.

### D-057 The event stream and yt-dlp arrive in M1
**Decision:** The event bus, `GET /api/events` and the event stream of the interface are built in milestone M1, with the one event M1 needs (`tool.updated`). yt-dlp becomes a locked package of the app in M1. Both were planned for later milestones.
**Why:** The first-run screen must show the progress of a download (R-IN-03), and the architecture sends progress over the event stream. Asking the server again and again was not an option the architecture describes. The first-run screen lists yt-dlp and checks it at every start (R-IN-04), so the package has to be there.
**Consequences:** Milestone M2 adds its events to an existing stream instead of building it. Updating yt-dlp on its own stays in M9 (D-017). The activity log does not exist before M7: until then the source of a downloaded tool is in the debug log (`tool.install.finished`), in `./start --doctor` and in the answer of `/api/tools`. M7 adds the activity entry that R-IN-03 names.

### D-058 macOS 15 is confirmed as the minimum
**Decision:** The minimum of macOS 15 (D-035) is no longer provisional.
**Why:** D-035 left one thing open: whether the chosen ffmpeg build and Deno run on macOS 15. The smoke test of a fresh clone now downloads the pinned ffmpeg and ffprobe from both sources and the pinned Deno, and the app runs the self-check of each. It passed on macOS 15 on Apple Silicon and on Intel, on macOS 26, and on the maintainer's Mac with macOS 27.
**Consequences:** This check runs in CI on every pull request, so a newly pinned tool that does not run on the oldest supported macOS is found before it is merged. It downloads about 170 MB per runner.


### D-059 Two kinds of check: quick and full
**Decision:** A check is a quick check or a full check. A quick check reads the channel's video list from the newest video and stops after a full page (30 videos in a row) that the catalogue already has. It adds new videos, updates what it read, and never marks anything as removed. A full check reads everything, and only a full check counts towards "removed from YouTube" (R-CH-13) and finds a changed title on an older video. "Check now", the checks on opening the app, on selecting a channel and on the interval are quick. A full check runs when a channel is added, on demand from the channel menu, and by itself when the last one is older than a setting (default 7 days). It shows progress and can be cancelled. Requirements R-CH-12, R-CH-13, R-CH-20 to R-CH-23, R-CH-26 to R-CH-28.
**Why:** Measured in milestone M2 on real channels with the pinned yt-dlp: a complete listing took 12 seconds for 149 videos, 30 seconds for 453 and 7 minutes 9 seconds for 6,597, about 15 videos per second. The plan had every check read the whole list, also the check on selecting a channel and the one every 30 minutes. yt-dlp hands out a listing video by video and fetches the next page only when asked, so a listing can be stopped: a quick check with nothing new took 3.5 to 5 seconds on all four channels, and one more page for every 30 new videos.
**Consequences:** A video that was removed from YouTube is noticed only by full checks, so at the earliest after the second one. A new video that YouTube places below a full page of known videos is found only by the next full check. The catalogue stores the time of the last check and of the last full check, and the channel header shows both. Milestone M2 builds both kinds as manual actions. The schedule (quick checks by themselves, the automatic full check, the retry with backoff) is built in M4 on one scheduler that also serves the exact date fetch. The stop rule counts videos, not pages, so it does not depend on the page size of YouTube.

### D-060 An approximate date carries its precision and is shown from the middle of its range
**Decision:** With every approximate date the app stores the unit YouTube gave it in: day, week, month or year (`videos.published_precision`). The date is shown as its precision allows ("around 2005", "around Mar 2026", "around 11 Nov 2026"), taken from the middle of the range the real date lies in. An approximate date looks like a placeholder with three states (waiting, updating, unavailable), and is replaced visibly when the exact date arrives. Sorting and the limit of auto-mirror never decide from an approximate date. Requirements R-DT-04, R-DT-13, R-UI-06, R-MI-03, R-DT-05. This answers open question Q-12.
**Why:** Measured in milestone M2: the channel listing has a date for every video, old and new (about 10,000 entries, none without), but only when yt-dlp is asked for it, and only as "now minus N units". For 89 videos of four channels, from 2 days to 16 years old, the real date was read from the video's page. It always lay between one unit before the listed point and the point itself: up to 6 days earlier for weeks, 29 days for months and a full year for years. The listed point is the latest possible date, never the middle. The example of the spec, "around Sep 2026", promised a month for every video, which a video of several years does not have.
**Consequences:** yt-dlp passes on the point but not the unit. The unit is found again from the point and the time of the listing (`core/dates.py`), which was right for every one of 2,500 real entries and is tested against recorded listings. Where two units fit, the coarser one is stored. The first approximate date of a video is kept, because a later one can only be coarser. From the middle of the range the worst error is half a unit. "New" (R-CH-15) does not use the date at all. Milestone M2 builds the storage, the display and the waiting state, M3 the highlight when an exact date arrives, M4 the updating and unavailable states and the order of the fetch, M5 the sorting rule, the auto-mirror rule and the grid.

### D-061 The video count of a channel preview comes from an undocumented playlist
**Decision:** The number of videos that the add channel dialog shows before the user confirms (R-CH-03) is read from the YouTube playlist `UULF` followed by the channel ID without its `UC`. It is behind one method of the YouTube gateway. It has its own time limit of 8 seconds and never fails or delays the lookup. A missing, late or implausible answer means "no count", with the reason in the log. The count is a preview only and is not stored: once the channel is listed, the number of the catalogue is shown everywhere, and a difference between the two is logged.
**Why:** The channel data that yt-dlp reads has no video count. Counting by listing the channel takes minutes for a large one. In milestone M2 the playlist reported 453 for a channel with 453 videos on its Videos tab, in about 5 seconds. It holds the channel's long videos only, without Shorts and streams, which is what yt-mirror lists.
**Consequences:** The playlist is a convention of YouTube that is documented nowhere and can stop working at any time. When it does, the preview has no count and the dialog reads "All videos now" instead of "All 57 videos now". Nothing else depends on it. The interface shows the preview as soon as name, handle and avatar are known and fills the count in when it arrives.

### D-062 The fake YouTube is an adapter of the app
**Decision:** The fake YouTube gateway lives in `backend/ytmirror/adapters/fixture_youtube.py`, not with the other fakes in `backend/tests/fixtures/fakes/`. The container uses it when `YTM_FAKE_YOUTUBE` names a folder with a recorded world of channels.
**Why:** ARCHITECTURE section 10 and TESTING rule 8 said that fakes live only in the tests, and also that `YTM_FAKE_YOUTUBE=<dir> ./start` starts the real app with the fake gateway. Both cannot hold: the app is installed without its tests, and the layer check does not see an import of the tests.
**Consequences:** It is the one fake that ships. It must pass the same contract test as the real gateway, like every fake. Its own tests are infrastructure tests.

### D-063 Vue Router with hash addresses
**Decision:** The interface uses Vue Router with addresses behind a hash sign (`/#/channels/<id>`).
**Why:** ARCHITECTURE section 2 names Vue Router, and milestone M2 builds the first navigation. The local server serves files and has no fallback that would answer an address such as `/channels/<id>` with the interface. With hash addresses it needs none.
**Consequences:** The channel that was open last (R-UI-02) is not kept in the address or in the browser's storage: the port changes at every start, and with it the storage. The server keeps it (`app_meta`).

### D-064 The favicon is made by the backend from the icon source
**Decision:** The local server answers `/favicon.svg` with the icon source file, coloured from the token file by the code that also colours the macOS icon (`core/icon.py`), and `/favicon.png` with the same picture drawn by the image renderer, for browsers that take no SVG icon.
**Why:** DESIGN section 5 wants every icon generated from the one source file and nothing generated committed. D-056 made the icon build Python code of the app. The page itself is built by Vite, which has no access to that code.
**Consequences:** The favicon follows a new icon source and new token colours without a build step. Like the macOS icon it uses the colours of the light theme (D-054). The app window shows no favicon: it matters for `--browser` and for the development server, which passes the two addresses on to the backend.

### D-065 Spacing uses 2 px or multiples of 4 px, and a rounding rule for the mockups
**Decision:** The spacing scale gets a second step: 2 px, half the spacing step, for gaps between items that must stay visibly separate, such as sidebar entries and the segments of a toggle. A mockup value that is neither 2 px nor a multiple of 4 px takes the nearest step, and a value exactly between two steps takes the smaller one (6 to 4, 10 to 8, 14 to 12, 18 to 16, 22 to 20). It is never rounded down where that would put an interactive control under its minimum height or a touch target under its minimum size: there it is rounded up.
**Why:** The mockups predate the scale and use 2, 6, 10, 14, 18 and 22 px. DESIGN section 2.5 had rounding rules for font sizes and radii but none for spacing, and milestone M1 rounded case by case, once up (14 to 16) and otherwise down.
**Consequences:** The theme lint allows exactly the half step and no other fraction. The one place of M1 that went up, the gap inside a tool row of the first-run screen, follows the rule now and is 12 px: it is no minimum-size exception. Sizes that are not spacing, such as the height of the progress bar and the size of an icon, are not touched by this rule.

### D-066 A control appears with its target, and the channel menu has a visible button
**Decision:** An element of a mockup whose target a later milestone builds is added by that milestone, never shown disabled or dead before. Each such element is listed in IMPLEMENTATION-PLAN under the milestone that adds it. The channel menu of `Menus.html` is built in milestone M2 with the items that work. It opens by a right-click on a channel in the sidebar and by a visible "More actions" button in the channel header, which the header mockup does not have. The video menus of M5 use the same Menu component and the same pattern.
**Why:** The plan already had this rule for the items of the menu bar. The screens of M2 contain entries for the activity log, the settings, the help and the error details of M7 and for matching files of M8. Pausing, removing and opening a channel on YouTube (R-CH-30 to R-CH-32) are in the mockups only in a context menu, which nobody finds without knowing it and which the keyboard does not reach (R-UI-13, R-UI-14).
**Consequences:** Until M7 the screens differ from the mockups in the listed places, and their stored screenshots change again when the elements arrive. The milestones that add them must cover them in their requirement coverage and end-to-end tests.

### D-067 Thumbnails are cached right after a listing and served through the API
**Decision:** After a listing the app downloads the thumbnail of every listed video and the avatar of the channel into `data/cache/`, newest first, in the background. The interface gets them from the local API by video ID and channel ID. A request for a picture that is not cached yet is answered with "not found" at once and never waits for YouTube. R-PL-11 names these pictures.
**Why:** R-CH-16 wants the list to work offline and for removed videos, so every picture must be on disk, not only the ones the user scrolled past. A browser opens only a few connections to one server, and the event stream holds one of them: pictures that waited for a slow YouTube would hold up every other call of the interface.
**Consequences:** The cache of a large channel is some tens of megabytes. It is removed with the channel. The pictures are fetched through the YouTube gateway, so the fake YouTube serves them without the network.

### D-068 Requirements that no milestone named
**Decision:** R-CH-20 to R-CH-25 are split: milestone M2 builds the manual checks (R-CH-23, R-CH-24, and of R-CH-25 the banner with "Try again" and the kept catalogue), M4 builds the checks that run by themselves and the retry with backoff. Eight more requirements get a milestone: R-PL-07 in M4, R-PL-08 in M2, R-PL-09 in M9, R-LG-02 and R-LG-03 in M3, R-QA-01 in M11, R-QA-02 from M2 on, and R-UI-14 in every milestone that builds screens with a final pass in M11. M4 is renamed "Exact dates and automatic checks". A requirement that a milestone builds only in part is named there as "partly".
**Why:** An audit in milestone M2 compared every requirement ID of the spec with the requirement lines of the plan. These 14 were in none. M2 could not be built without "Check now", and the failed check state was among its screens.
**Consequences:** The plan and the spec agree again. The status machine got a requirement of its own (R-QA-08), because its tests had none to name.

### D-069 How the gateway asks yt-dlp for a listing
**Decision:** The gateway always lists the Videos tab of a channel, flat, with `process=False`, with the extractor arguments `youtubetab: approximate_date` and `youtube: raise_incomplete_data`, with its own timeouts and retry counts, and without a cache outside the app folder. A channel without a Videos tab has an empty catalogue. An error text of yt-dlp that the gateway does not know becomes `YOUTUBE_CHANGED` and is logged in full.
**Why:** Checked in milestone M2 against the pinned yt-dlp and the real YouTube. Without the tab a channel can come back as a list of tabs. Without `process=False` the whole listing arrives at once and can show no progress. Without the first argument a listing has no dates. Without the second, yt-dlp ends a listing that was cut off as if it were complete, and the missing videos would count towards "removed from YouTube". With yt-dlp's default retries a stalled connection was reported after 160 seconds.
**Consequences:** These options are asserted by a test. An unknown error text most likely means that YouTube changed something yt-dlp does not know yet, which is what `YOUTUBE_CHANGED` says and what the update offer of R-UP-06 is for.

### D-070 Three colour tokens for text on a badge and for overlays
**Decision:** The token file gets `on-warn` (text on the `warn` colour of the "New" badge), `scrim` (a dark overlay: the backdrop behind a dialog and the duration badge on a thumbnail) and `on-scrim` (text on it). Each has the same value in both themes, taken from the mockups.
**Why:** The mockups use these colours and no token had them. `on-accent` is white in the light theme, which on the orange badge misses the contrast of R-UI-14. A thumbnail and the page behind a dialog are not in a theme's colours, so what lies on them cannot be either.
**Consequences:** DESIGN section 2.2 has three more rows, and the token tests count them.

### D-071 YouTube's "not a bot" check is one condition of the whole app
**Decision:** When YouTube refuses a request with "Sign in to confirm you're not a bot", the app gives it an error code of its own, `BOT_CHECK`, apart from `RATE_LIMITED` and `NETWORK_UNREACHABLE`. One place in the app, not each video or channel, remembers the refusal: everything the app would ask of YouTube by itself waits, first 15 minutes, then twice as long each time up to 6 hours. One banner explains it. An action the user starts by hand is still tried, and the first answer of YouTube ends the pause. Requirement R-ER-05.
**Why:** In milestone M2 every metadata lookup of a video from the CI runners of GitHub was refused this way, with every option of yt-dlp that was tried, while the listings of channels from the same runners worked. The check depends on the network address, so it can hit a real user behind a VPN, a shared address or a data centre. Then every video fails for the same reason: retrying each one makes it worse, and one error per video would bury the real message.
**Consequences:** What the user can do is limited in version 1: another network or VPN location, waiting, and for exact dates the optional API key, which does not go through this check. The usual way around the check is to sign in with the cookies of a browser, which is on the roadmap and may have to move into version 1 if the check turns out to be common. Every milestone that adds work that asks YouTube by itself (downloads, the exact date fetch, the scheduler) puts it under the same pause.
