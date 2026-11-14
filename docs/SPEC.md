# yt-mirror V1: Product Specification

Status: approved for implementation planning. No application code exists yet.
Scope: version 1.0. Anything not listed here is out of scope (see [ROADMAP.md](ROADMAP.md)).

This document says **what** the app does. How it is built is in [ARCHITECTURE.md](ARCHITECTURE.md). What it looks like is in [DESIGN.md](DESIGN.md) and `docs/design/v1/`. Terms in **bold** on first use are defined in [GLOSSARY.md](GLOSSARY.md).

Every requirement has an ID (for example `R-CH-03`). Tests, commits and issues refer to these IDs. Never renumber an ID. A removed requirement keeps its ID and is marked "Removed".

Words used on purpose: **must** is mandatory for V1. **Should** is expected unless a documented reason prevents it. **May** is optional.

---

## 1. Purpose

yt-mirror is a local macOS app that keeps folders on the user's disk in sync with YouTube channels. For each channel it shows every regular video with its status, lets the user download a selection or everything, keeps new uploads coming, and lets the user permanently exclude videos they never want.

### 1.1 Users

- Primary: the maintainer, a developer.
- Also: non-technical Mac users. After the one-line install, **no step may require a terminal or technical knowledge**. Every fix is a button. Every error is explained in plain language first.

### 1.2 Principles

1. **The files are the product.** A downloaded video is an ordinary file that is complete and useful without yt-mirror: correct name, correct dates, all metadata inside.
2. **Dates are sacred.** The exact YouTube publish time is the single most important piece of metadata (see section 8).
3. **Nothing is silently lost.** No user file is deleted without an explicit choice. Deletions go to the Trash.
4. **Always show state.** Every channel and video shows what is happening to it right now, with a label, never by colour alone.
5. **Self-contained.** App, tools and data live in one folder. Nothing is installed system-wide.

---

## 2. Platform and constraints

| ID | Requirement |
|---|---|
| R-PL-01 | Runs on macOS only, Apple Silicon and Intel. The minimum version is macOS 15, the oldest version the automated checks run on (see DECISIONS D-035). It is stated in the README and website. |
| R-PL-02 | The UI runs in a dedicated app window (not a browser tab). A `--browser` flag opens it in the default browser instead. |
| R-PL-03 | Minimum window size 1100 x 700 points. Layouts are not required to work below that. |
| R-PL-04 | The local server listens on 127.0.0.1 only and must reject requests from other origins. |
| R-PL-05 | Light and dark themes. Default follows the system setting. |
| R-PL-06 | UI language is English. All user-visible text lives in one place per feature so translation can be added later. |
| R-PL-07 | The app works with no Google account and no API key. |
| R-PL-08 | No proxy setting in V1. The app must still honour the standard `HTTP_PROXY` and `HTTPS_PROXY` environment variables and system proxy behaviour of its HTTP libraries. |
| R-PL-09 | Background work happens only while the app is running. There is no background service or scheduler in V1. |
| R-PL-10 | Every call to the local API must carry a session token created at random at each start. The window receives it in its first address, where it is exchanged for a cookie that scripts cannot read. A missing or wrong token is refused. The server also accepts the same token in an `Authorization: Bearer` header, which tools and tests use. No other credential opens the API. |
| R-PL-11 | The local server serves the built interface, the app's own icon and, through the API, the cached thumbnails and avatars (R-CH-16), and nothing else from the disk. It does not expose its API description. |
| R-PL-12 | A health endpoint reports that the server runs, with the app version and the database schema version. |
| R-PL-13 | The app stops cleanly however it is asked to quit: Quit in the menu bar, Cmd+Q, Quit in the Dock, closing the window, logout, restart, shutdown, Ctrl+C or a termination signal. It stops its work and closes the database before the process ends. This requirement is the shutdown work of the quit path only: whether a quit is first held for a question is R-NA-06 and R-QU-12. A server that cannot start is reported, not a hang. |

### 2.1 Native Mac app

yt-mirror must feel like a native Mac app. Details: [ARCHITECTURE.md](ARCHITECTURE.md) section 7.10 and [DESIGN.md](DESIGN.md) section 7. That the window library can do all of this from a locally built, unsigned app bundle was shown by experiment in milestone M1 (DECISIONS D-048 to D-052).

The quit path is built in two steps (D-052). Milestone M1 builds the shutdown work: R-PL-13. Milestone M5 builds the decision whether a quit is held, with the "quit while downloading" confirmation: R-NA-06 and R-QU-12. Until M5 the app never holds a quit and never asks before it.

| ID | Requirement |
|---|---|
| R-NA-01 | **App identity.** The running app appears as "yt-mirror" with the yt-mirror icon in the Dock, the app switcher (Cmd+Tab), the menu bar and Activity Monitor. It must never appear as "Python". A clone started with `./start` appears as "yt-mirror (dev)" instead, so that it can be told apart from an installed copy. |
| R-NA-02 | **App bundle.** Both the installer and `./start` on a clone create a real macOS app bundle locally, with an `Info.plist`, a bundle identifier, and an icon generated from the single icon source file ([DESIGN.md](DESIGN.md) section 5). The bundle is built on the user's Mac, so it needs no Apple signing. An installed copy and a clone have different bundle identifiers, so both can run on one Mac. |
| R-NA-03 | **Menu bar** with the standard macOS items and shortcuts. **yt-mirror:** About yt-mirror, Check for Updates..., Settings... (Cmd+,), Hide, Hide Others, Quit yt-mirror (Cmd+Q). **File:** Add Channel... (Cmd+N), Close Window (Cmd+W). **Edit:** Undo, Redo, Cut, Copy, Paste, Select All, so that text fields behave normally. **View:** List, Grid, Show Downloads, Show Activity, Reload (debug only). **Channel:** Check Now (Cmd+R), Check All Channels, Mirror Everything Missing, Pause Channel, Open Folder, Channel Settings.... **Window:** Minimize, Zoom, and the standard window list. **Help:** yt-mirror Help, Keyboard Shortcuts, Report a Problem.... |
| R-NA-04 | A menu item is enabled only when it applies. For example the Channel menu needs an open channel, and "Pause Channel" reads "Resume Channel" for a paused one. |
| R-NA-05 | **About window:** app name, version, license, and links to the website and the repository. |
| R-NA-06 | Cmd+Q and closing the window both go through the same quit path, including the "quit while downloading" confirmation (R-QU-12). |
| R-NA-07 | Clicking the Dock icon brings the window to the front. |
| R-NA-08 | Only one instance can run per data folder, in every mode. Starting the app again focuses the existing window. A second start with `--browser` ends with a plain message that yt-mirror is already running. |
| R-NA-09 | The menu bar shortcuts and the in-app shortcuts of `Shortcuts.html` must not conflict. Where they overlap, the menu bar is the source of truth and the in-app list is updated. |

---

## 3. Channels

### 3.1 Adding a channel
Design: `AddChannel1.html`, `AddChannel2.html`, `Welcome.html`.

| ID | Requirement |
|---|---|
| R-CH-01 | The user adds a channel by pasting a channel URL (`/@handle`, `/channel/UC...`, `/c/name`, `/user/name`, with or without a tab suffix such as `/videos`), a bare `@handle`, or a bare channel ID. |
| R-CH-02 | A video URL, playlist URL or anything else is rejected with a plain message that says what is accepted. |
| R-CH-03 | The app looks the channel up and shows its name, handle and avatar before the user confirms, and its video count when YouTube gives one. The count never delays or fails the lookup: without it the same dialog is shown, worded without a number. It is a preview only. Once the channel is listed, the number of the catalogue is shown everywhere. |
| R-CH-04 | Adding a channel that already exists opens the existing channel and says so. |
| R-CH-05 | In step 2 the user chooses: save folder (default `<library>/<channel name>`), quality (default "Use default"), and what to mirror: "pick myself" (default), "auto-mirror everything", or "auto-mirror videos uploaded after a date". |
| R-CH-06 | If the chosen folder already contains video files, the app says how many and offers to match them after adding (section 9). Video files are the files directly in the folder whose names end in `.mkv`, `.mp4`, `.webm`, `.mov`, `.m4v` or `.avi`. |
| R-CH-07 | Only regular videos are listed. Shorts and live streams (including past streams from the Live tab) are not listed in V1. |

### 3.2 The video catalogue

| ID | Requirement |
|---|---|
| R-CH-10 | For every regular video of the channel the app stores and shows: thumbnail, title, duration, upload date, view count, and status. After download it also shows quality, file size, codecs and subtitle availability. |
| R-CH-11 | The first listing of a large channel must not block the UI. Progress is shown ("120 videos found so far") and the user can use the rest of the app (design: `StateLoading.html`). A first listing that was interrupted, for example by quitting, starts again the next time the app starts. |
| R-CH-12 | A **check** refreshes the catalogue. There are two kinds. A **quick check** reads the channel's video list from the newest video and stops when it has read a full page (30 videos in a row) that the catalogue already has. It adds new videos and updates the title, duration and view count of the videos it read. A **full check** reads the whole list and does the same for every video, and only a full check finds videos that are no longer listed: they count towards **removed from YouTube** (R-CH-13). Every successful check also takes over the channel's current name, handle and avatar. The channel folder keeps its name. |
| R-CH-13 | A video is marked removed from YouTube only after it has been missing from two consecutive successful full checks. A quick check never marks anything as removed, and it neither counts as one of the two nor breaks their sequence. A failed, cancelled or empty check never marks anything as removed. A video that is listed again is no longer removed. |
| R-CH-14 | A removed video keeps its local file and stays in the list with a "Removed from YouTube" marker. It is never deleted automatically. |
| R-CH-15 | A video first seen in a check after the channel's first listing is **new**. It stays new until it is synced, excluded, or 14 days have passed since the app first saw it. The video's own date plays no part in this. |
| R-CH-16 | Thumbnails for the catalogue are cached locally so the list works offline and for removed videos. |

### 3.3 Checking for new videos

| ID | Requirement |
|---|---|
| R-CH-20 | When the app opens, it checks all non-paused channels, one after another, with a quick check (setting, default on). A global indicator shows "Checking channels: 3 of 5". |
| R-CH-21 | Selecting a channel triggers a quick check if the last successful check is older than 5 minutes. |
| R-CH-22 | While the app is open, all non-paused channels are re-checked with a quick check on an interval (setting: 30 min, 1 h, 3 h, never. Default 30 min). |
| R-CH-23 | "Check now" on a channel and "Check all channels now" in the sidebar start a quick check immediately. "Full check" in the channel menu starts a full check of that channel. |
| R-CH-24 | Checks run sequentially with a short random delay between channels to avoid rate limiting. |
| R-CH-25 | A failed check shows a banner on the channel with a retry button, keeps the previous catalogue, and is retried automatically with backoff (5, 15, 60 minutes). Design: `StateError.html`. |
| R-CH-26 | A full check runs by itself for a channel whose last full check is older than a setting (default 7 days): at most one channel at a time, and never while downloads of that channel are running. Adding a channel is a full check: its first listing (R-CH-11). |
| R-CH-27 | A full check shows its progress ("Full check: 1,200 of about 6,600") and can be cancelled. A cancelled check changes nothing. |
| R-CH-28 | The work of a check that needs no listing runs with every check, quick or full: verifying that the files of synced videos exist (R-MI-06) and repairing file dates (R-DT-09). |

### 3.4 Channel management
Design: `ChannelSettings.html`, `RemoveChannel.html`, `Menus.html`.

| ID | Requirement |
|---|---|
| R-CH-30 | Per channel the user can: open its folder in Finder, check now, run a full check, pause and resume, open it on YouTube, open channel settings, and remove it. |
| R-CH-31 | A paused channel is not checked, neither automatically nor by hand, and its downloads do not run. Its queued downloads stay queued. |
| R-CH-32 | Removing a channel asks whether to keep the files (default) or move them to the Trash. The channel's catalogue, exclude list and settings are deleted from the database either way. |
| R-CH-33 | Changing a channel's folder moves its downloaded files and its hidden metadata folder to the new location, with progress, and rolls back on failure. |
| R-CH-34 | The sidebar shows per channel: avatar, name, a status line (section 12.1) and a count of new videos. |
| R-CH-35 | The channel header shows totals: videos, synced, excluded, size on disk, and the last check result, with the time of the last check and the time of the last full check. |

---

## 4. Mirroring (downloading)

| ID | Requirement |
|---|---|
| R-MI-01 | The user selects one or more videos and clicks "Mirror". They enter the download queue. |
| R-MI-02 | **Auto-mirror** (per channel, default off): every listed video that is not excluded, not synced and not removed from YouTube is queued, now and after every check. |
| R-MI-03 | "Only mirror videos uploaded after" (per channel, optional date): auto-mirror ignores older videos. They stay listed and can be mirrored by hand. A video whose date is approximate (R-DT-04) is decided at once only when its whole possible range lies before or after that date. When the range includes the date, the app does not decide from the approximate date: it gets the exact date first, ahead of all other videos, and decides then. |
| R-MI-04 | "Mirror everything missing" (channel menu) queues all eligible videos once without turning auto-mirror on. |
| R-MI-05 | Excluded videos are never queued, by any path. |
| R-MI-06 | A synced video whose file has disappeared from disk gets the status "File missing". It is re-downloaded automatically only if the channel has auto-mirror on. Otherwise the user decides. |
| R-MI-07 | Selection supports: checkbox per video, select all shown, shift-click range, and keyboard (see `Shortcuts.html`). A bulk action bar appears while anything is selected. |

### 4.1 Quality

| ID | Requirement |
|---|---|
| R-QL-01 | Quality options: Best available, 2160p, 1440p, 1080p, 720p, 480p. A numeric option means "the best quality not above this height". If nothing at or below it exists, the lowest available is used. |
| R-QL-02 | There is a global default quality and an optional per-channel override. |
| R-QL-03 | The container is always MKV. There is no container setting in V1. |
| R-QL-04 | Video and audio are downloaded in the best available codecs for the chosen height and merged without re-encoding. |
| R-QL-05 | A quality change applies to new downloads. If existing videos of that channel (or all channels, for the global default) have a different height, the app offers to re-download them (design: `QualityChange.html`). Default is to leave them. |
| R-QL-06 | A re-download replaces the old file only after the new file is complete and verified. |
| R-QL-07 | The list shows the downloaded height for every synced video and marks videos whose height is below the current target. |

### 4.2 The queue
Design: `Downloads.html`.

| ID | Requirement |
|---|---|
| R-QU-01 | Downloads run in parallel up to a setting (1 to 5, default 2). |
| R-QU-02 | The user can pause all, resume all, cancel one, remove a waiting item, clear all waiting items, and reorder waiting items by drag and drop. "Mirror first" puts a video at the top. |
| R-QU-03 | A global speed limit (unlimited or a value in MB/s) applies to the sum of all downloads. |
| R-QU-04 | Each download shows stage (Video, Audio, Processing), percent, speed and time left. |
| R-QU-05 | An interrupted download (quit, crash, network loss) continues from the partial file the next time it runs. |
| R-QU-06 | On start, items that were downloading or queued are queued again in their previous order. |
| R-QU-07 | Transient failures (network, rate limit, server errors) are retried up to 3 times with increasing delays. Permanent failures (members-only, private, age-restricted, removed, geo-blocked) are not retried automatically. |
| R-QU-08 | A failed video shows "Failed" with a plain reason and offers Retry, Exclude and Details (design: `ErrorDetails.html`). |
| R-QU-09 | With auto-mirror on, a failed video is retried automatically at most once every 6 hours, and never if the failure is permanent. |
| R-QU-10 | **Disk space guard:** before each download starts and while it runs, if free space on the target volume falls below a threshold (setting, default 10 GB) the queue pauses, a banner explains why, and the user can resume anyway or change the limit. |
| R-QU-11 | If the library or channel folder is unavailable (for example an unplugged drive) the queue pauses for that channel and a banner offers "Choose folder" and "Try again". Nothing is marked as missing while the folder itself is unavailable. |
| R-QU-12 | Closing the app window while downloads run asks for confirmation (design: `QuitConfirm.html`). |

---

## 5. Excluding videos
Design: `ExcludeConfirm.html`, `ExcludePreview.html`, `ChannelSettings.html`.

| ID | Requirement |
|---|---|
| R-EX-01 | The user can exclude one or many videos "forever". An excluded video is never downloaded and is hidden from all tabs except "Excluded" (it is shown dimmed and struck through in "All"). |
| R-EX-02 | Excluding is undoable: a toast offers Undo, and "Restore" on the Excluded tab reverses it at any time. |
| R-EX-03 | Excluding a video that is queued or downloading cancels that download. |
| R-EX-04 | Excluding a video that is already downloaded follows a setting: always ask (default), keep the file, or delete the file (move to Trash). The dialog can set the setting ("remember my choice"). |
| R-EX-05 | **Auto-exclude rules** per channel: "title contains any of these words" (case-insensitive, whole phrase match) and "shorter than N minutes". |
| R-EX-06 | Rules apply to existing videos when saved, and to new videos at every check. Before saving, a preview lists the matching videos and the rule each one matched. Rules also apply to videos that are already downloaded. What happens to their files follows the setting in R-EX-04. |
| R-EX-07 | In the preview the user can untick videos. Unticked videos are stored as exceptions and are never auto-excluded by a rule again. |
| R-EX-08 | A video excluded by a rule records which rule did it. Restoring it by hand makes it an exception. |
| R-EX-09 | Exclusions survive checks, title changes and app updates. |

---

## 6. Files on disk

### 6.1 Layout

```
<library folder>/
  <Channel name>/
    <Video title>.mkv
    <Video title>.jpg            (only if the "thumbnail next to video" setting is on)
    .yt-mirror/                  (hidden)
      channel.json               (channel id, url, name: lets a moved folder be re-linked)
      <video id>.info.json       (complete raw metadata)
      <video id>.jpg             (original thumbnail, best resolution)
```

| ID | Requirement |
|---|---|
| R-FI-01 | There is one library folder (setting, default `~/Movies/YouTube`). Each channel gets a subfolder named after the channel: the channel name with the substitutions of R-FN-02. When that folder already belongs to another channel, ` [<channel id>]` is appended. A channel can instead use any custom folder. The channel folder is created when the channel is added. |
| R-FI-02 | The user-visible channel folder contains only video files (and optional thumbnail images). All other files live in the hidden `.yt-mirror` subfolder. |
| R-FI-03 | Temporary and partial files live in the hidden subfolder, never next to finished videos. |
| R-FI-04 | The database stores each file path relative to its channel folder, so moving the library needs only a settings change. |

### 6.2 File names

| ID | Requirement |
|---|---|
| R-FN-01 | The file name is the video title plus `.mkv`. Nothing else is added by default. |
| R-FN-02 | Only characters that macOS cannot store or that break Finder are substituted, each by a visually similar character: `/` becomes `⧸` (U+29F8) and `:` becomes `：` (U+FF1A). Control characters are removed. A leading `.` gets a preceding `_`. Leading and trailing spaces are trimmed. |
| R-FN-03 | Names are stored in Unicode NFC. |
| R-FN-04 | If the name would exceed 255 bytes in UTF-8, the title part is shortened on a character boundary and ` [<video id>]` is appended. |
| R-FN-05 | If another video in the same channel folder has the same resulting name (compared case-insensitively), the later one gets ` [<video id>]` appended. A file that already exists and belongs to no known video is never overwritten: the new file gets the ID suffix. |
| R-FN-06 | When a video's title changes on YouTube, the app renames the local file to match at the next check, keeps its dates, and records the rename in the activity log. |
| R-FN-07 | Sync status never depends on the file name. Files are tracked by video ID in the database and in the embedded metadata. |

### 6.3 Embedded metadata

| ID | Requirement |
|---|---|
| R-MD-01 | Each MKV contains: title, channel name, description, publish date and time, video URL, video ID, chapters (when the video has them), and the thumbnail as cover image. |
| R-MD-02 | Each MKV has the complete raw metadata JSON attached inside the file, and the same JSON is saved in the hidden folder. |
| R-MD-03 | Subtitles: English subtitles are embedded as a subtitle track when available. If no creator-provided English subtitles exist, YouTube's auto-generated English subtitles are embedded and labelled as auto-generated. Both behaviours are settings, default on. |
| R-MD-04 | A subtitle download failure never fails the video. The video is completed without subtitles, the fact is logged, and a later "Repair metadata" can add them. |
| R-MD-05 | The original thumbnail is saved in the hidden folder at its best resolution. Optionally (setting, default off) it is also saved next to the video with the same base name. |
| R-MD-06 | "Repair metadata" on a synced video re-fetches metadata, thumbnail and subtitles and rewrites them into the file without downloading the video again. |

---

## 7. Views and navigation
Design: `Main.html`, `WebGrid.html`, `ListLight.html`, `GridLight.html`, `Details.html`, `Menus.html`, `StateEmpty.html`.

| ID | Requirement |
|---|---|
| R-UI-01 | One shell for the whole app: a sidebar (channels, add channel, activity, settings, help, report a problem, free disk space) and a main area. |
| R-UI-02 | The app opens on the channel that was open last. With no channels it shows the welcome screen. |
| R-UI-03 | A channel has two views, list and grid, with a toggle. The default view is a setting. The choice is remembered per app, not per channel. |
| R-UI-04 | Filter tabs with counts: All, New, Not downloaded, Synced, Failed, Excluded. |
| R-UI-05 | Search filters the current tab by title as the user types. |
| R-UI-06 | Sort: newest first (default), oldest first, title, duration, size on disk. Sorting by date never uses an approximate date (R-DT-04): while any date in the channel is approximate, "newest first" and "oldest first" follow the position of the videos on the channel, which is exact. |
| R-UI-07 | Lists must stay smooth with 5,000 videos in one channel. |
| R-UI-08 | A details panel shows, for one video: thumbnail, title, status, actions, file facts (name, folder, size, video and audio format, upload time, download time, thumbnail, video ID), description and chapters. |
| R-UI-09 | Per-video actions, shown according to status: Mirror, Mirror first, Cancel, Retry, Play, Show in Finder, Details, Open on YouTube, Copy link, Re-download, Repair metadata, Exclude forever, Restore. |
| R-UI-10 | "Play" opens the file in the system default player. "Show in Finder" reveals and selects the file. |
| R-UI-11 | Every action that can take more than half a second shows progress or a busy state on the control that started it. |
| R-UI-12 | Destructive or bulk actions confirm with a toast that offers Undo for a few seconds, or with a dialog when they cannot be undone. |
| R-UI-13 | Keyboard shortcuts as listed in `Shortcuts.html`, changed where the menu bar decides otherwise (R-NA-09, [DESIGN.md](DESIGN.md) section 7.3). All functions are reachable by keyboard. |
| R-UI-14 | Accessibility: real buttons, links and form controls with labels, visible focus, text contrast of at least 4.5:1, and no information carried by colour alone. |

### 7.1 Theme center

Fonts, colours and every other visual value can be changed in one place. Details: [DESIGN.md](DESIGN.md) section 2.

| ID | Requirement |
|---|---|
| R-TH-01 | One folder, `frontend/src/design/`, is the **theme center**. It holds everything visual: the tokens, the Tailwind preset that maps the tokens to utility classes, the bundled font files, and the brand icon source. No visual value is defined anywhere else. |
| R-TH-02 | **Tokens** are named CSS variables. They cover every colour (light and dark), font family, font size, font weight, line height, the spacing step, radius, shadow and animation duration. |
| R-TH-03 | Token names are semantic: they say what a value is for (`text-muted`, `surface-raised`, `accent`). A token is never named after its value (`blue-500`, `gray-2`). |
| R-TH-04 | A **theme** is one block of token values. Light and dark are two blocks. Adding a third theme must need no change to any component. |
| R-TH-05 | Changing the app font must take one changed line plus the font files. |
| R-TH-06 | Components and feature code may use only tokens: no raw colour values, font names, pixel font sizes or one-off spacing values. A lint rule in CI enforces this. |
| R-TH-07 | The website uses the same token file as the app, so the app and the site cannot drift apart. |
| R-TH-08 | A theme preview page, available in development mode, shows every token and every shared component in both themes on one screen. |
| R-TH-09 | A test fails if a token used in code is not defined. The visual regression screenshots cover both themes. |

---

## 8. Dates

Dates are the most important metadata in this app. These rules have dedicated tests.

| ID | Requirement |
|---|---|
| R-DT-01 | Three dates per video are stored separately and never mixed: **published** (YouTube), **downloaded**, **last seen** on YouTube. |
| R-DT-02 | All timestamps are stored in UTC with second precision. They are displayed in the Mac's local time zone as absolute dates ("11 Nov 2026", with the time in the details panel). Relative dates ("2 weeks ago") are not used for publish dates. |
| R-DT-03 | The published time is the moment the video became public. For premieres and scheduled videos this is the release time, not the upload time. |
| R-DT-04 | A date known only approximately (from the channel listing) is stored with its precision: the unit YouTube gave it in (day, week, month or year). So the app knows the range the real date lies in, not only one point. An approximate date is never written to a file. It is shown as its precision allows, from the middle of that range: "around 2005" for years, "around Mar 2026" for months, "around 11 Nov 2026" for weeks and days. A video for which the listing gave no date at all shows "date pending" and no date. |
| R-DT-05 | Exact dates are obtained from, in order of preference: the optional YouTube API key (fast, in batches), a background fetch of each video's metadata (slow, throttled, setting default on), and always from the full metadata at download time. The background fetch takes the newest videos first. Videos whose exact date a decision is waiting for (R-MI-03) go to the front. |
| R-DT-06 | The background fetch shows progress on the channel ("Exact dates: 340 of 1,000"), yields to downloads, survives restarts, and never causes rate-limit failures for downloads (it backs off first). |
| R-DT-07 | Every downloaded file has both its **creation date** and its **modification date** set to the exact published time. After setting them the app reads them back and verifies them. |
| R-DT-08 | The published time is also embedded in the MKV metadata and present in the raw metadata JSON. |
| R-DT-09 | At every check the app compares the dates of each synced file with the stored published time and repairs any difference (setting, default on). A "Repair dates" action does the same on demand for a channel. |
| R-DT-10 | Renaming, moving, repairing metadata and re-downloading must all leave the file dates equal to the published time. |
| R-DT-11 | Sorting a channel folder in Finder by Date Created or Date Modified must give the same order as "newest first" in the app. Videos with identical published times are ordered consistently by their position on the channel. |
| R-DT-12 | Optional YouTube API key: off by default, entered in Settings, with an in-app step-by-step guide and a "Test key" button (design: `ApiKeyGuide.html`). The key is stored only locally. Removing it changes nothing except speed. If the key fails or its quota is used up, the app falls back to the slow path without any error dialog. The guide, the setting and the website must state plainly that the key is free: Google charges nothing for this API, no payment details are needed, and there is only a daily usage limit that yt-mirror stays far below. |
| R-DT-13 | An approximate date must look like a placeholder that is being replaced, not like a final value, in the list, the grid and the details panel. It has three states, each with an icon and a tooltip, never told apart by colour alone. **Waiting:** the exact date is not being fetched yet. Dimmed text, a clock icon, tooltip "Exact date pending". **Updating:** the exact date is being fetched now. The same dimmed text, an animated loading icon, tooltip "Getting the exact date...". **Unavailable:** fetching failed or is paused. Dimmed text, a warning icon, a tooltip that says why and that it will be tried again. When the exact date arrives, it replaces the approximate one in normal text, with a short highlight that fades. With the system "reduce motion" setting nothing moves, and the icons still differ. |

---

## 9. Adopting existing files
Design: `Adopt.html`.

| ID | Requirement |
|---|---|
| R-AD-01 | The user can ask the app to match video files that already exist in a channel's folder to the channel's videos, when adding a channel or later from the channel menu. |
| R-AD-02 | Matching order: the video ID embedded in the file's metadata, then a video ID in the file name (`[id]` or `-id` patterns), then title similarity plus duration within 2 seconds. |
| R-AD-03 | A match by ID is certain. A match by title and duration with exactly one candidate is proposed. Zero or several candidates are never guessed: the user chooses from a list or marks the file "not from this channel". |
| R-AD-04 | For each matched file the app lists what differs from what yt-mirror would produce: file name, dates, embedded metadata, subtitles, thumbnail, container, quality. |
| R-AD-05 | Per file the user chooses: **Keep as is** (count as synced, change nothing), **Fix in place** (rename, set dates, convert the container to MKV without re-encoding if needed, embed metadata, thumbnail and subtitles), or **Re-download**. A default is a setting. "Set all to" applies one action to all. |
| R-AD-06 | Files that match nothing are left untouched and never listed as channel videos. |
| R-AD-07 | Fix in place never re-encodes and never downloads the video stream. If a file cannot be fixed without re-encoding, it is reported and left unchanged. |
| R-AD-08 | The process is resumable and shows progress on the channel. |

---

## 10. Settings

There are **general settings** and **per-channel settings**. A channel uses the general value unless it overrides it. Design: `Settings.html`, `ChannelSettings.html`.

| Setting | General (default) | Per channel |
|---|---|---|
| Save folder | Library folder (`~/Movies/YouTube`) | Custom folder |
| Quality | Default quality (Best available) | Override |
| Auto-mirror | n/a | On or off (off) |
| Only mirror videos uploaded after | n/a | Optional date |
| Auto-exclude rules | n/a | Rules |
| Paused | Pause all downloads | Pause this channel |
| Parallel downloads | 1 to 5 (2) | n/a |
| Speed limit | Unlimited | n/a |
| Disk space guard | 10 GB | n/a |
| Embed English subtitles | On | n/a |
| Auto-generated subtitles as fallback | On | n/a |
| Thumbnail image next to video | Off | n/a |
| Check all channels on open | On | n/a |
| Re-check interval | 30 minutes | n/a |
| Full check at least every | 7 days | n/a |
| Fetch exact dates in background | On | n/a |
| YouTube API key | Empty | n/a |
| Repair file dates on every check | On | n/a |
| When excluding a downloaded video | Always ask | n/a |
| Default adopt action | Ask per file | n/a |
| Theme | Same as system | n/a |
| Default view | List | n/a |
| Notifications: new videos, downloads finished, failures | All on | n/a |
| Check for app and yt-dlp updates on open | On | n/a |
| Log detail | Normal | n/a |

| ID | Requirement |
|---|---|
| R-SE-01 | Settings save immediately. There is no global Save button. Channel settings use Save and Cancel because they can trigger large operations. |
| R-SE-02 | A setting change that affects existing files always asks before touching them. |
| R-SE-03 | Settings are stored in the database and included in the debug report (the API key is redacted). |
| R-SE-04 | Every setting has the default of the table in section 10. A setting that was never stored, or whose stored value cannot be read, has its default. |

---

## 11. Installation, tools, updates, uninstall

Details: [RELEASE-AND-UPDATE.md](RELEASE-AND-UPDATE.md). Design: `Installer.html`, `Setup.html`, `AppUpdate.html`, `Uninstall.html`.

| ID | Requirement |
|---|---|
| R-IN-01 | A user installs with one pasted Terminal line. The installer downloads the latest release, verifies its checksum, sets up Python inside the app folder, creates a `yt-mirror` command and a "yt-mirror" icon in Applications, and starts the app. No admin password. |
| R-IN-02 | A developer can instead clone the repository and run `./start`. |
| R-IN-03 | On first start the app shows which tools it needs (Python environment, yt-dlp, ffmpeg, Deno), downloads the missing ones into the app folder with visible progress, verifies checksums, and offers a retry per failed step. A downloaded tool can have a second source, which is tried when the first one fails or its file does not match its checksum. Each source has its own pinned version, address and checksum, and whichever file is installed must pass the same self-check. `./start --doctor` and the activity log say which source a tool came from. The first-run screen is shown until every tool was in order once. It is shown again at a start at which two or more tools are missing or broken. A single missing or broken tool is handled by R-IN-04. |
| R-IN-04 | On every start the app verifies the tools still work. A missing or broken tool produces a banner with an "Install now" button, never a crash. |
| R-IN-05 | The whole app folder can be moved or copied to another location on a Mac and still works. Environment parts that contain absolute paths are rebuilt automatically on the next start. |
| R-IN-06 | `./start` accepts `--dev`, `--debug`, `--browser`, `--doctor`, `--update` and `--help`. An unknown flag shows the usage and changes nothing. `--dev` reloads the interface on changes, `--debug` writes verbose logs and makes the developer tools available in the window, and `--doctor` only reports and changes nothing. |
| R-IN-07 | `./start` prepares everything inside the app folder: a pinned uv verified by checksum before use, Python and packages in `tools/`, the interface built when missing. Each failure (no connection, checksum mismatch, Node.js missing) ends with a plain message. |
| R-UP-01 | The app checks for a new yt-mirror release on open (setting). A banner announces it. The update dialog shows the version, the release notes, and what will happen. |
| R-UP-02 | Updating: downloads and verifies the release, backs up the database, replaces the code, updates dependencies, migrates the database, restarts. Progress is shown per step. |
| R-UP-03 | If any step fails, the previous version and the database backup are restored and the app starts in the old version with an explanation. |
| R-UP-04 | An install made by cloning updates with git. Installs made by the installer or a ZIP update from the release archive. The user sees the same dialog in all cases. |
| R-UP-05 | The app refuses to open a database made by a newer version and explains how to update. |
| R-UP-06 | yt-dlp can be updated independently of the app with one click, and the app offers this automatically when downloads start failing in a way that suggests yt-dlp is outdated. After a yt-dlp update, failed downloads are retried. |
| R-UP-07 | "Skip this version" hides the banner until the next release. |
| R-UN-01 | Settings has "Uninstall yt-mirror". It removes the app, its tools and its Applications icon. The user chooses whether to keep or remove the app's data (database, settings, logs). Downloaded videos are never touched. |

---

## 12. Feedback, logs and help

### 12.1 Status indicators
Design: `States.html` (the complete catalogue).

| ID | Requirement |
|---|---|
| R-FB-01 | Channel statuses: Checking, Up to date, N new videos, Mirroring X of Y, Paused, Could not check, Matching files X of Y, Exact dates X of Y. One status line is shown at a time, by priority: error, mirroring, checking, matching, exact dates, new, paused, up to date. |
| R-FB-02 | Video statuses: Not downloaded, Queued, Downloading (percent in the status chip. Quality, speed and time left next to it), Processing, Synced (with height), File missing, Failed (with reason), Excluded. Markers that combine with a status: New, Removed from YouTube, Approximate date, Lower than target quality. |
| R-FB-03 | Status changes appear in the UI within one second without a manual refresh. |
| R-FB-04 | Banners for app-wide conditions: tool missing, yt-dlp update available, app update available, queue paused by the disk guard, cannot reach YouTube, YouTube asks to confirm that you are not a bot (R-ER-05), library folder not found, and success confirmations. Each banner has the action that fixes it. |
| R-FB-05 | Toasts confirm user actions and offer Undo where possible. |
| R-FB-06 | macOS notifications (each can be turned off): new videos found, a batch of downloads finished (one per batch), a failure or queue pause. |

### 12.2 Errors

| ID | Requirement |
|---|---|
| R-ER-01 | Every error shown to the user has four parts: what happened, what yt-mirror is doing about it, what the user can do, and technical details behind a disclosure (design: `ErrorDetails.html`). |
| R-ER-02 | Every error has a stable code (see [LOGGING.md](LOGGING.md)). User text is written per code, never taken from a raw exception. Every error response of the local API carries its code and its technical details. |
| R-ER-03 | No error may leave a video, channel or the queue in a state the user cannot get out of from the UI. |
| R-ER-04 | When the window cannot reach its own server it says so and offers a retry, under an error code of its own. |
| R-ER-05 | YouTube sometimes refuses requests with a check of its own: "Sign in to confirm you're not a bot". The check depends on the network address the requests come from, not on the channel or the video. The app treats it as one condition of the whole app, under an error code of its own. It stops everything it would ask of YouTube by itself and tries again later, with a pause that grows (15 minutes, doubling up to 6 hours). It shows one banner, never one error per video. The banner says in plain words what the check is, that it depends on the network address in use, and what the user can try: another network or another VPN location, waiting, and the optional API key for exact dates (R-DT-12). An action the user starts by hand is still tried, and as soon as YouTube answers the kind of request it had refused, the pause ends and the banner goes. |

### 12.3 Activity log
Design: `Activity.html`.

| ID | Requirement |
|---|---|
| R-AC-01 | A user-facing activity log lists, newest first: downloads finished and failed, checks, new videos, auto-exclusions, renames, queue pauses, tool and app updates, app starts. |
| R-AC-02 | It can be filtered by type (everything, errors, downloads, checks) and by channel. |
| R-AC-03 | Entries with an error link to the error details. Auto-exclusions offer Restore. |

### 12.4 Debug logging
Full specification: [LOGGING.md](LOGGING.md).

| ID | Requirement |
|---|---|
| R-LG-01 | Structured logs are written to `data/logs/`, rotated daily, kept 14 days. Only the app's own daily log files are ever deleted. |
| R-LG-02 | Each download has a job ID that ties together all its log lines, its activity entries and its yt-dlp and ffmpeg output. |
| R-LG-03 | Every status change of a video is recorded in the database with time, old status, new status, reason and job ID. |
| R-LG-04 | "Export debug report" produces one file with recent logs, settings (secrets redacted), tool versions, app version, database schema version and macOS version. |
| R-LG-05 | "Run health check" tests tools, folders, permissions, network and the database, and shows the result with fix buttons. It also shows the macOS version, the processor and the free disk space. |
| R-LG-06 | Every log line has the required fields of [LOGGING.md](LOGGING.md) section 1, and each use case logs its start, end and errors with catalogue events. The console shows the same lines in a readable one-line form. |
| R-LG-07 | Secrets never reach the log or the console. Nothing but secrets is removed from a line. |
| R-LG-08 | "Log detail" Normal writes info and above, Verbose and `--debug` write debug and above. Lines written by libraries appear from warning at Normal and from info at Verbose. |

### 12.5 Help and reporting problems
Design: `Help.html`, `ReportProblem.html`.

| ID | Requirement |
|---|---|
| R-HE-01 | A built-in help page explains the main actions and concepts, searchable, and works offline. |
| R-HE-02 | "Report a problem" is available from the sidebar, Settings, Help, the activity log and every error dialog. It offers to copy or save the debug report, then opens a new issue at https://github.com/mderis/yt-mirror/issues in the default browser with the app version and macOS version pre-filled. |
| R-HE-03 | The app never sends any data anywhere on its own. The only network destinations are YouTube and its media servers, the optional YouTube API, GitHub (updates and the issue page the user opens), and the download sources of its tools. |

---

## 13. Quality requirements

| ID | Requirement |
|---|---|
| R-QA-01 | Automated tests cover every requirement in this document that can be tested without the real YouTube. Each test names the requirement IDs it covers. See [TESTING.md](TESTING.md). |
| R-QA-02 | A small opt-in live test suite and a manual checklist cover behaviour that needs the real YouTube. |
| R-QA-03 | Code is documented and structured as described in [CODING-STANDARDS.md](CODING-STANDARDS.md). CI enforces it. |
| R-QA-04 | Every database change is a migration with a test that upgrades a database from every earlier released version. |
| R-QA-05 | The app starts and is usable within 3 seconds on a typical Mac with 20 channels and 20,000 videos in the database. |
| R-QA-06 | A crash or forced quit at any moment must not corrupt the database or leave a half-written file that looks like a finished video. |
| R-QA-07 | At start the app creates its database when missing and brings it to the current schema through the migrations. A current database is left alone. The database runs in WAL mode with foreign keys enforced. |
| R-QA-08 | The status of a video changes only along the transitions of [ARCHITECTURE.md](ARCHITECTURE.md) section 6.1. Any other change is refused and changes nothing. |

---

## 14. Website
Design: `SiteHome.html`, `SiteDocs.html`, `AppIcon.html`.

| ID | Requirement |
|---|---|
| R-WS-01 | A public website on GitHub Pages presents the app. The home page shows what it does and how to install it (the install line with a copy button, and three steps) without scrolling past the first screen. |
| R-WS-02 | The website contains the full documentation: a user guide and a developer section. It is generated from the Markdown files in the repository, so the repository and the website can never disagree. |
| R-WS-03 | The website is built and deployed automatically when the main branch changes. |
| R-WS-04 | The install script is served from the website. |
| R-WS-05 | Screenshots on the website are generated from the real app by an automated script, in light and dark, so they stay current. |

---

## 15. Out of scope for V1

Shorts and live streams. Playlists and single videos as sources. Windows and Linux. A proxy setting. Running in the background or on a schedule while the app is closed. Cookies or sign-in for members-only and age-restricted videos. SponsorBlock. Audio-only downloads. MP4 output. Comments. Multiple languages for subtitles or UI. Homebrew, and a signed and notarized app delivered as a DMG (the app bundle of V1 is built locally and unsigned, R-NA-02). See [ROADMAP.md](ROADMAP.md).
