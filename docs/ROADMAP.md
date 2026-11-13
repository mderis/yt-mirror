# yt-mirror: Roadmap

## Version 1.0 (current scope)

Everything in [SPEC.md](SPEC.md). The build order is in [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md).

## Candidates for later versions

Not committed. Each needs its own spec section, designs and decision record before work starts.

| Idea | Notes |
|---|---|
| SponsorBlock | Mark sponsor segments as chapters. Declined for V1 |
| Shorts and live streams | Per-channel toggles for the other tabs |
| Playlists and single videos as sources | |
| Proxy setting | |
| Background operation | Menu bar agent or scheduled runs while the window is closed |
| Sign-in with cookies | Members-only and age-restricted videos |
| MP4 output, audio-only output | |
| More subtitle languages, UI translations | Strings are already centralised (R-PL-06) |
| Per-channel overrides for subtitles and check interval | |
| Homebrew tap | Second distribution channel |
| Signed and notarized DMG for drag-and-drop install | See "A signed app in a DMG" below. Needs an Apple Developer Program membership |
| Windows and Linux | The macOS-specific parts are isolated in two adapters |
| Command line interface | For scripting |
| Comments, live chat | Large data, low priority |

### A signed app in a DMG

In V1 the app bundle is built on the user's Mac and is not signed (R-NA-02). A later version could ship a finished, signed and notarized `yt-mirror.app` in a DMG that the user drags to Applications. Three ways to package it:

| Option | What it means |
|---|---|
| Bundle the current app | Put the Python backend, its packages and the built interface into one signed bundle. The code stays as it is. The bundle is large, and every binary inside it has to be signed |
| Tauri | A small native shell in Rust with the system web view. The interface stays. The Python backend would run as a bundled helper program or be rewritten |
| Electron | A shell with its own Chromium. The interface stays, and it no longer depends on the system's WebKit. The largest download. The Python backend would run as a bundled helper program |

Consequence of all three: a signed bundle in Applications must not change after it is signed, so the app could no longer keep its tools and data inside its own folder. App data (database, settings, logs, caches) and the downloaded tools would move to the user's Library folder (`~/Library/Application Support/yt-mirror`, `~/Library/Logs`, `~/Library/Caches`). That gives up the "one portable folder" principle of V1 (D-018) and needs a migration for existing installs, and the in-app updater would have to replace a signed bundle.

## Process for a new version

1. Copy `docs/design/vN/` to `docs/design/vN+1/` and change the designs there.
2. Add requirements to the spec with new IDs. Never reuse or renumber IDs.
3. Record decisions.
4. Add milestones to the implementation plan.
5. Implement with tests, migrate the database with a tested migration, update the changelog.
