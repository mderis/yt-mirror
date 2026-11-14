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
**Consequences:** The approach relies on pywebview asking the `closing` event when AppKit asks whether the app may terminate. An update of pywebview could change that, which the exact pin (D-049) and a test guard against. The app replaces the Ctrl+C handling that pywebview sets up with its own, so that both signals take the same path. The shutdown work at a logout must be short, because macOS does not wait without limit. A handler of an AppKit notification must return nothing, or AppKit drops the event being handled. R-PL-13 names every way of quitting now, and the confirmation itself (R-QU-12) is built in M5 on this path.

### D-053 Where ffmpeg, ffprobe and Deno come from
**Decision:** ffmpeg and ffprobe come from Martin Riedl's build server (https://ffmpeg.martin-riedl.de): unpatched upstream FFmpeg, release 9.0.2 at the time of this decision. The tool manifest allows a second source per tool, tried when the first fails or its file does not match its checksum. For ffmpeg and ffprobe the second source is the portable build of jellyfin-ffmpeg from its GitHub releases (8.1.3-2 at the time of this decision). Each source has its own pinned version, address and SHA-256. The second source publishes no checksum files, so its checksums are computed and pinned by us. Whichever file is installed must pass the same self-check, and `./start --doctor` and the activity log say which source was used. Deno comes from its official GitHub releases, with the checksums published there. The project mirrors no binaries itself. This answers the first part of open question Q-05.
**Why:** Of eight sources compared in November 2026, the first is the only one with native builds for Apple Silicon and Intel, both tools, unpatched upstream code, version-pinned addresses, published SHA-256 files and signed binaries. It links only system libraries, states macOS 12 as its minimum, is GPL version 3 without nonfree parts, and offers addresses for automated downloads. The second is run by an organisation with a public build on GitHub. The others fail on one point each: no Apple Silicon build, a stale Intel build with unclear terms, a build that may not be redistributed, a minimum of macOS 26, or no macOS build at all. yt-mirror only downloads these programs and runs them as separate programs, so their license does not touch its own.
**Consequences:** Known risks, accepted by the maintainer. The first source is one person's server: that old addresses stay is observed since 2022, not promised, and if the server goes away, first-run setup depends on the second source until an app update pins another. From January 2027 it builds no new Intel releases, so Intel stays at the pinned version. The second source is a patched fork on an older branch, and its Intel binary is not signed. CI therefore runs the self-checks against both sources, and from milestone M3 the gateway tests run against both. No source states a limit for automated downloads. Downloads from GitHub releases can be slow: from the maintainer's network 35 to 40 MB took about five minutes, so download timeouts must be generous and progress must be visible. Mirroring the binaries would make the project a distributor under the GPL, with the duty to offer the source code, so it is not done.

### D-054 The macOS icon uses the light theme's colours
**Decision:** The app icon (`.icns`) is drawn with the values of the light theme: the accent `#1F5FD1` with a white mark.
**Why:** The Dock icon is one image and cannot follow the theme. The maintainer chose the light pair.
**Consequences:** The icon build script reads the two values from the light block of the token file, so a change of the tokens still changes the icon. A dark variant of the icon is not built.

