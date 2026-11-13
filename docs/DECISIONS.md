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
