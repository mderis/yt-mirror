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
| Signed and notarized Mac app | Needs an Apple Developer Program membership |
| Windows and Linux | The macOS-specific parts are isolated in two adapters |
| Command line interface | For scripting |
| Comments, live chat | Large data, low priority |

## Process for a new version

1. Copy `docs/design/vN/` to `docs/design/vN+1/` and change the designs there.
2. Add requirements to the spec with new IDs. Never reuse or renumber IDs.
3. Record decisions.
4. Add milestones to the implementation plan.
5. Implement with tests, migrate the database with a tested migration, update the changelog.
