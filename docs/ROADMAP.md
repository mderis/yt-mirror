# yt-mirror: Roadmap

## Version 1.0 (current scope)

Everything in [SPEC.md](SPEC.md). The build order is in [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md).

## To decide before the first public release

Not in the specification and in no milestone yet. Each needs the maintainer's decision, requirements in the spec and a milestone before work starts.

| Idea | Notes |
|---|---|
| Optional crash reports and anonymous usage counts | Opt-in, off by default, asked once at first start, a switch for each in Settings. Sent to Sentry or a service that speaks its protocol. Never sent: paths, the user name, channel names, video titles or IDs, the API key. Behind a Telemetry port, with an adapter that sends nothing in tests and CI. Conflicts with R-HE-03 as it stands. Proposed requirements and the privacy page: [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md), Q-28 |

## Candidates for later versions

Not committed. Each needs its own spec section, designs and decision record before work starts.

| Idea | Notes |
|---|---|
| SponsorBlock | Mark sponsor segments as chapters. Declined for V1 |
| A video in two channels | A video that two channels list (a collaboration) is shown in both, with one file on disk. Version 1 gives it to the channel that listed it first (R-CH-17, D-075) |
| Shorts and live streams | Per-channel toggles for the other tabs |
| Playlists and single videos as sources | |
| Proxy setting | |
| Background operation | Menu bar agent or scheduled runs while the window is closed |
| Sign-in with cookies | Members-only and age-restricted videos. Signing in with the cookies of a browser is also the usual way around YouTube's "confirm you're not a bot" check, which refuses requests from some network addresses (R-ER-05). Version 1 only explains the check and pauses. If the check turns out to be common for users, this may have to move into version 1 |
| MP4 output, audio-only output | |
| More subtitle languages, UI translations | Strings are already centralised (R-PL-06) |
| Per-channel overrides for subtitles and check interval | |
| Homebrew tap | Second distribution channel |
| Signed and notarized DMG for drag-and-drop install | See "A signed app in a DMG" below. Needs an Apple Developer Program membership |
| Windows and Linux | The macOS-specific parts are isolated in two adapters |
| Command line interface | For scripting |
| Comments, live chat | Large data, low priority |
| A YouTube player inside the app for videos not mirrored yet | After 1.0. Starts with the experiment of Q-29 in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md): whether YouTube allows its embedded player in the app's window at `127.0.0.1`, and what the app shows for a video that forbids embedding. "Play" for a downloaded file keeps opening the user's own player (R-UI-10) |
| A storyboard preview when the pointer rests on a video | After 1.0, lowest priority. Shown only after a hover delay, and cached. Starts with the experiment of Q-30 in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md), which measures what the preview costs in requests to YouTube |

### A signed app in a DMG

In V1 the app bundle is built on the user's Mac and is not signed (R-NA-02). A later version could ship a finished, signed and notarized `yt-mirror.app` in a DMG that the user drags to Applications. Three ways to package it:

| Option | What it means |
|---|---|
| Bundle the current app | Put the Python backend, its packages and the built interface into one signed bundle. The code stays as it is. The bundle is large, and every binary inside it has to be signed |
| Tauri | A small native shell in Rust with the system web view. The interface stays. The Python backend would run as a bundled helper program or be rewritten |
| Electron | A shell with its own Chromium. The interface stays, and it no longer depends on the system's WebKit. The largest download. The Python backend would run as a bundled helper program |

Consequence of all three: a signed bundle in Applications must not change after it is signed, so the app could no longer keep its tools and data inside its own folder. App data (database, settings, logs, caches) and the downloaded tools would move to the user's Library folder (`~/Library/Application Support/yt-mirror`, `~/Library/Logs`, `~/Library/Caches`). That gives up the "one portable folder" principle of V1 (D-018) and needs a migration for existing installs, and the in-app updater would have to replace a signed bundle.

## Ideas for later versions (not planned)

Ideas to plan for version 2 or 3. Nothing here is decided: each one needs its open questions answered, its own spec section, designs and a decision record before work starts.

### Storage manager

- Space used per channel and in total, the free space of each drive, and how fast the library grows.
- The largest and the oldest videos, and videos never played, as sorted lists.
- Making room: send chosen videos to the Trash and keep them as "removed by me", so that they are not downloaded again, or allow a later download again.
- Rules per channel: keep only the newest N videos, or only those newer than a date, or stay under a size limit; older ones go to the Trash.
- Move a channel's folder to another drive, with its files.
- Maybe: download a video again at a lower quality to save space.

Open questions:
- How it relates to the disk guard (R-QU-10) and to the exclude rules.
- Whether a rule ever moves files to the Trash without asking first.
- How the app knows that a video was played.

### Channel groups

- Groups (or tags) of channels in the sidebar, which can be collapsed.
- Actions on a group: check now, mirror all new videos, pause, resume.
- Default settings per group (quality, auto-mirror), which a channel can override.

Open questions:
- Groups or tags: can a channel be in two?
- How group settings sit between the general settings and the settings of a channel.
- Whether a group has a folder on disk, or exists only in the app.

## Process for a new version

1. Copy `docs/design/vN/` to `docs/design/vN+1/` and change the designs there.
2. Add requirements to the spec with new IDs. Never reuse or renumber IDs.
3. Record decisions.
4. Add milestones to the implementation plan.
5. Implement with tests, migrate the database with a tested migration, update the changelog.
