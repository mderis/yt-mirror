# yt-mirror V1: Design

The designs for V1 are attached to this version of the repository in `docs/design/v1/`. Open `docs/design/v1/index.html` in a browser to see all of them. They are static HTML mockups: they define layout, wording and states. They contain no logic and are not the app.

The editable source of the designs is a design canvas outside the repository: https://claude.ai/artifact/HJuQA3PaS2Em4b9vgCL4MK (private to the maintainer). When a design changes, the HTML export in this folder must be regenerated so the repository stays the reference.

When a mockup and [SPEC.md](SPEC.md) disagree, the spec wins and the mockup must be fixed.

**Review status:** every screen in this folder was rendered in a headless Chrome and reviewed on 14 November 2026. Fixes from that review: bars that overlapped list rows, a dangling separator in the channel header, long status chips that pushed row actions onto a second line, a wrong default in the parallel downloads control, and frame heights that clipped or left empty space. The review used Chrome only. The app window uses WebKit, so the implementer must still check the real UI there. The app icon is a rough draft. Spacing and exact sizes are guidance. Structure, wording and states are binding.

## 1. Screen inventory

| File | Screen | Requirements |
|---|---|---|
| `Main.html` | Channel, list view, dark | R-UI-01 to R-UI-07, R-FB-01, R-FB-02 |
| `WebGrid.html` | Channel, grid view, dark | R-UI-03 |
| `ListLight.html`, `GridLight.html` | The same in the light theme | R-PL-05 |
| `Details.html` | Video details panel | R-UI-08, R-UI-09 |
| `Menus.html` | Context menus: synced video, other video, channel | R-UI-09, R-CH-30 |
| `StateLoading.html` | First listing of a channel | R-CH-11 |
| `StateError.html` | Check failed | R-CH-25 |
| `StateEmpty.html` | Empty filter result | R-UI-04 |
| `Setup.html` | First run: installing tools | R-IN-03 |
| `Welcome.html` | No channels yet | R-UI-02 |
| `AddChannel1.html`, `AddChannel2.html` | Add channel | R-CH-01 to R-CH-06 |
| `Adopt.html` | Match and repair existing files | R-AD-* |
| `Installer.html` | Terminal output of the installer | R-IN-01 |
| `Settings.html` | General settings | Section 10 of the spec |
| `ChannelSettings.html` | Per-channel settings | R-CH-30 to R-CH-33, R-EX-05 |
| `ExcludeConfirm.html` | Exclude a downloaded video | R-EX-04 |
| `ExcludePreview.html` | Auto-exclude preview | R-EX-06, R-EX-07 |
| `RemoveChannel.html` | Remove a channel | R-CH-32 |
| `QualityChange.html` | Quality changed | R-QL-05 |
| `Shortcuts.html` | Keyboard shortcuts | R-UI-13 |
| `AppUpdate.html` | App update | R-UP-01 to R-UP-03 |
| `Uninstall.html` | Uninstall | R-UN-01 |
| `ApiKeyGuide.html` | Optional API key guide | R-DT-12 |
| `ErrorDetails.html` | The pattern for every error | R-ER-01 |
| `ReportProblem.html` | Report a problem | R-HE-02 |
| `QuitConfirm.html` | Quit while downloading | R-QU-12 |
| `Downloads.html` | Queue panel | R-QU-* |
| `Activity.html` | Activity log | R-AC-* |
| `States.html` | Every indicator, banner, toast and notification | R-FB-* |
| `Help.html` | Built-in help | R-HE-01 |
| `SiteHome.html`, `SiteDocs.html` | Website | R-WS-* |
| `AppIcon.html` | App icon and logo | |

Not drawn, by decision: layouts narrower than the minimum window (R-PL-03), the native macOS folder picker, and the remaining website documentation pages (they use the `SiteDocs.html` template).

## 2. Design tokens

Implement these as CSS variables and expose them through the Tailwind preset in `frontend/src/design/`. Components never use raw hex values.

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | `#0E1014` | `#F6F7F9` | Window background |
| `surface-side` | `#13161C` | `#FFFFFF` | Sidebar, panels |
| `surface` | `#161A21` | `#FFFFFF` | Cards, dialogs, fields |
| `surface-raised` | `#1E2633` | `#E3EDFF` | Selected item, menus, toasts |
| `line` | `#262C36` | `#E1E5EB` | Dividers |
| `line-strong` | `#323A47` | `#C2C9D3` | Control borders |
| `text` | `#E8EBF0` | `#1A1D23` | Primary text |
| `text-dim` | `#C6CCD6` | `#454D5A` | Secondary text |
| `text-muted` | `#9BA4B3` | `#5A6372` | Labels, metadata |
| `accent` | `#5B9BFF` | `#1F5FD1` | Primary buttons, focus, links |
| `on-accent` | `#0B1220` | `#FFFFFF` | Text on accent |
| `ok-bg` / `ok-text` | `#1B2A44` / `#A9C9FF` | `#E3EDFF` / `#123A85` | Synced, success |
| `warn` | `#F2A14A` | `#F2A14A` | Progress bars, "new" badge |
| `warn-bg` / `warn-text` | `#3A2A14` / `#F7C078` | `#FDEBD3` / `#7A4200` | In progress, attention |
| `err-bg` / `err-text` | `#3A1A1C` / `#FFA39B` | `#FDE7E5` / `#8E1B12` | Failures |
| `neutral-bg` / `neutral-text` | `#22262E` / `#B4BBC7` | `#ECEEF2` / `#454D5A` | Queued, excluded |
| `track` | `#2A303B` | `#DDE1E7` | Progress track, skeletons |

Type: Inter for text, Space Grotesk (600) for headings and the wordmark, the system monospace font for technical details. Fonts are bundled with the app. The app must not load fonts from the network.

Sizes: body 14 px, metadata 13 px, labels 12 px uppercase, page title 28 px, dialog title 22 px.
Shape: 8 px radius for controls, 12 to 16 px for cards and dialogs, pills for status chips.
Spacing: multiples of 4 px.
Targets: interactive elements are at least 44 px high, except dense table and toolbar controls (36 px minimum).

## 3. Rules for all screens

1. **Status is never colour alone.** Every status has an icon and a text label. Blue (synced) and orange (in progress) also differ in lightness.
2. **One primary button per view or dialog.**
3. **Dialogs** have a title that states the question or the outcome, a short body, and buttons whose labels are verbs ("Exclude", "Remove channel"), never "OK" or "Yes".
4. **Destructive actions** use the danger style and are never the default button.
5. **Errors** follow the four-part pattern in `ErrorDetails.html`.
6. **Dates** are absolute. An approximate date is always marked as such.
7. **Empty, loading and error states** exist for every list and panel.
8. **Icons** are inline stroke icons from one set. No emoji.
9. **Wording** uses the terms in [GLOSSARY.md](GLOSSARY.md) exactly. The same thing is never called two names.
10. **Motion** is short (150 to 200 ms) and respects the system "reduce motion" setting.

## 4. Component list

The frontend builds these shared components first, each with tests and a story-like demo page used for visual checks: Button, IconButton, Chip (status), ProgressBar, Checkbox, Radio group, Select, TextField, Toggle row, Dialog, Menu, Toast, Banner, Tabs, Sidebar item, Video row, Video card, Details panel, Skeleton, Empty state, Key cap.

## 5. App icon and logo

The icon in `AppIcon.html` is a draft and is expected to change. To make changing it a one-file job:

- There is exactly one source file: `frontend/src/design/brand/icon.svg` (square, single colour on a rounded square).
- Everything else is generated from it by a build script and never edited by hand: the macOS launcher icon (`.icns`), the window icon, the favicon, the logo in the sidebar and on the website, and the social preview image.
- Colours in the SVG come from the `accent` and `on-accent` tokens.
- Replacing the icon means replacing that file and running the build. A test checks that every generated asset is newer than the source.

## 6. Versioning of designs

Each released version keeps its own folder: `docs/design/v1/`, later `docs/design/v2/`. A version's designs are frozen when it is released. Work on the next version starts by copying the folder.
