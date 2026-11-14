# yt-mirror V1: Open Questions and Things to Verify

Everything here must be resolved before or during the milestone named. When an item is resolved, move the answer into the right document, add a decision record if it was a real choice, and delete the item.

## To verify by experiment (assumptions made during planning)

| ID | Assumption | How to verify | Needed by |
|---|---|---|---|
| Q-02 | The creation date of a file can be set from Python with `setattrlist` (`ATTR_CMN_CRTIME`), and Finder shows it | Write the adapter and an integration test on a macOS runner. Check APFS, and exFAT for external drives. Fallback: set the modification time earlier than the creation time and confirm the creation time follows | M3 |
| Q-03 | A launcher app bundle created locally by the installer, and files fetched with `curl`, are not blocked by Gatekeeper | Test the installer on a clean Mac, on the two newest macOS versions | M9 |
| Q-04 | yt-dlp option names and behaviour in [ARCHITECTURE.md](ARCHITECTURE.md) section 7.3: format selectors, subtitle options, embedding order, attaching the info JSON to MKV, passing the Deno path, cancelling from a progress hook | Check against the pinned yt-dlp version and write gateway tests with recorded data | M3 |
| Q-07 | macOS notifications can be sent from an unsigned Python process started by a local launcher | Try the candidate mechanisms. If none works without signing, notifications fall back to in-app toasts only and R-FB-06 is moved to a later version | M7 |
| Q-08 | The exact date fetch can ask YouTube for many videos in a row without being slowed down or refused. Measured in M2: one lookup takes 3.5 seconds with the lightest options, and four in parallel bring it to 0.9 seconds per video, without an error in about 260 lookups within 12 minutes. No run was longer than 32 videos | Fetch the exact dates of a 1,000-video channel, at two and at four lookups in parallel, and watch for `RATE_LIMITED` and `BOT_CHECK`. Set the number of parallel lookups from that. The time shown to the user comes from the rate the app measures, so no fixed number depends on the answer | M4 |
| Q-09 | The native folder picker of pywebview returns the folder the user chose. The rest of this question was answered in M0 (see ARCHITECTURE section 7.8): the picker opens and returns to Python, but choosing a folder needs a real click, which the automated probe could not do | Open the picker once by hand and check the returned path | M2 |
| Q-27 | A scheduled premiere and a members-only video appear in the listing of the Videos tab in a form the gateway handles. None of the four channels listed in M2 had one, so the shape of such an entry is not known. The gateway leaves out what yt-dlp marks as a live stream or a past live stream and lists everything else | Find a channel with each kind, record its listing, and add the cases to the gateway tests | M3 |
| Q-29 | A YouTube player inside the app (ROADMAP) can work: YouTube's embedded player plays in the app's window, whose pages come from `http://127.0.0.1:<port>` | Load the embedded player in the real window for public videos and for a video that forbids embedding. Note any error (such as error 153 when no referrer is sent), whether the `origin` parameter or `youtube-nocookie.com` changes it, what the player shows for a video that forbids embedding, and every host the player contacts, compared with the destinations R-HE-03 allows | After 1.0, before its spec |
| Q-30 | A storyboard preview on hover (ROADMAP) is cheap enough to offer | Measure for 20 videos: how many requests one preview needs, how many bytes, whether it needs the metadata lookup of a video first (3.5 to 10 seconds, Q-08), and whether many previews in a row bring YouTube's "not a bot" check (R-ER-05). Choose the hover delay and the cache size from the numbers | After 1.0, before its spec |

Facts verified in milestone M2 (November 2026), against the real YouTube with the pinned yt-dlp 2026.10.26:
- Q-12 is answered (D-060). The flat listing of a channel has a date for every video, old and new: about 10,000 entries of five channels, none without. It has them only when yt-dlp is asked with the extractor argument `youtubetab: approximate_date`, and only as "now minus N units". Compared with the exact dates of 89 videos, the real date always lay between one unit before the listed point and the point: up to 6 days earlier for weeks, 29 days for months, a full year for years. So the app stores the unit and shows the date from the middle of that range. If a listing ever gives no date, the video shows "date pending".
- What a listing gives per video: ID, title, duration, a rounded view count, one or two thumbnail addresses. Duration was missing on 3 of 6,597 videos, the view count on about 1 in 100. It gives no description, no exact date, and no hint whether a video is public.
- How fast a listing is: about 15 videos per second, 30 per page. 149 videos in 12 seconds, 453 in 30 seconds, 6,597 in 7 minutes 9 seconds. A listing that stops after its first page takes 3 to 5 seconds whatever the size of the channel, which is what a quick check does (D-059).
- No rate limiting was seen in about 10,000 listed videos and 150 other requests within an hour.
- The channel data has no video count. The playlist `UULF<channel id without UC>` gave the exact number of long videos (D-061).
- A stalled connection is reported by yt-dlp only after about 160 seconds with its default retries. The gateway sets its own (D-069).
- From the maintainer's network YouTube is reachable only part of the time: within one morning it answered in 1 to 4 seconds for half an hour and then not at all. Live tests can fail there for that reason alone.
- Q-06 is answered: the channel feed is not used (D-072). `https://www.youtube.com/feeds/videos.xml?channel_id=...` answered "not found" for every channel tried, at three times within 40 minutes, from the maintainer's network and from two CI runners of GitHub, and one request got a server error. Reports on the web from 2026 describe the same: the feed is not switched off, but it answers "not found" for hours at a time. R-DT-05 and ARCHITECTURE 7.4 no longer name it.
- Exact dates without a key come only from one metadata lookup per video. Measured on 32 videos of four channels from the maintainer's network: 10.3 seconds per video with yt-dlp's default options, 3.5 seconds with the lightest options that still return the exact time, 4.7 seconds with the next best client. Of 21 combinations of client and skipped requests, three returned the exact time, and each of them still loads the video's page. In parallel with the lightest options: 2.0 seconds per video with two lookups at a time, 1.4 with three, 0.9 with four. Every exact time was the same in all variants. What is still open is Q-08.
- There is no source of exact dates in bulk without a key: the flat listing of the uploads playlist has the same approximate dates as the channel listing, and a listing that is not flat is one lookup per video.
- YouTube's "not a bot" check (R-ER-05, D-071). From the two CI runners of GitHub every metadata lookup of a video was refused with "Sign in to confirm you're not a bot": 23 combinations of options, 32 videos, one at a time and in parallel. Listings of channels and playlists worked from the same runners. From the maintainer's network during this milestone: never in a listing (about 13,000 listed videos), never in a lookup with the default or the lightest options (about 260 lookups), and in 12 of 12 lookups with two unusual clients that skip the video's page, which the app does not use. The count at the end of the milestone is the same: the three live tests (a lookup, a listing, a video count and two pictures) were answered too. No request of the kinds the app makes in milestone M2 was ever refused from this network.
- Seen on the side for Q-04 (M3): with the path of Deno given, yt-dlp still warned that its JavaScript challenge solver component is not installed ("Some formats may be missing"). Reading metadata worked. Downloading needs this looked at.

- Q-11 is answered: the maintainer followed the steps of the API key guide (`ApiKeyGuide.html`) in the Google Cloud console in November 2026, and they matched the console. The wording of the guide needs no change.
- Exact dates with the free YouTube API key, measured on 15 November 2026 from the maintainer's network with the maintainer's key (162 requests, 162 quota units of the 10,000 a day). The playlist of a channel's regular videos (`UULF` followed by the channel ID without `UC`) gives the exact time of every video, 50 per request, with `playlistItems.list` and `contentDetails.videoPublishedAt`. One request took about 1.1 seconds there.

  | Channel | Regular videos | Requests (= units) | Time | Videos without a date |
  |---|---|---|---|---|
  | @jawed | 1 | 1 | 0.9 s | 0 |
  | @CGPGrey | 149 | 3 | 3.4 s | 0 |
  | @veritasium | 453 | 10 | 10.3 s | 0 |
  | @LinusTechTips | 6,599 | 132 | 153 s | 0 |

  Finding the channel takes one more request (`channels.list` by handle). Looking videos up by ID (`videos.list`, 50 per request) took 4 requests and about 10 seconds for 200 videos. For 549 videos of four channels, the day from the playlist and the day from `videos.list` (with the start time of a premiere where there was one) were the same in every case. The counts of the playlist were those of the channel listing through yt-dlp, which found 6,597 for the largest channel two days earlier. Whether the playlist time equals the release time of a premiere to the second (R-DT-03) was not checked.

Facts verified in milestone M1 (November 2026):
- Q-24 is answered: from a locally built, unsigned app bundle, pywebview with AppKit does all three, on macOS 15 (Apple Silicon and Intel) and on macOS 27. Custom menus with shortcuts and items that are enabled and disabled while the app runs work when the menu bar is built with AppKit (pywebview's own menu API cannot do it, D-049). The app appears as "yt-mirror" with its icon and never as "Python" (D-048). A second start brings the first window to the front, also when it is minimized or hidden (D-050). A fourth point was added during the experiment: every way of quitting goes through one quit path that the app controls, checked with a real logout on macOS 15 as well (D-052). Details: [ARCHITECTURE.md](ARCHITECTURE.md) section 7.10.
- AppKit renders the icon source file (SVG) correctly on macOS 15 and macOS 27, so the icon can be built on the user's Mac without Node.js.
- Q-05 is answered (D-053, D-058): the sources of ffmpeg, ffprobe and Deno are chosen, and every download address was reachable from the maintainer's network. Downloads from GitHub releases were slow there: about five minutes for 35 to 40 MB. The pinned builds of both ffmpeg sources and of Deno download and run on macOS 15 (Apple Silicon and Intel), on macOS 26 and on macOS 27.

Facts verified in milestone M0 (November 2026):
- uv states macOS 13 as its minimum. pyobjc, which pywebview uses, ships builds for macOS 10.13 and newer. Neither is above the minimum of macOS 15 (D-035).
- GitHub's oldest hosted macOS runner is macOS 15. macOS 14 runners were retired on 2 November 2026.

Facts already verified during planning (November 2026):
- yt-dlp needs an external JavaScript runtime for full YouTube support since release 2025.11.12, and recommends Deno.
- yt-dlp stopped setting file modification times by default in release 2025.07.21, so yt-mirror must set dates itself.
- The YouTube Data API `videos.list` accepts up to 50 IDs per request and costs 1 quota unit. The default quota is 10,000 units per day.
- The YouTube Data API is free: no charge per request and no payment details needed to create a key. When the daily quota is used up, requests fail until it resets.

## Proposed design of the exact date fetch (milestone M4)

A proposal from milestone M2, not in the specification. It is decided in the plan of M4. The numbers come from the facts above.

**Two ways, chosen by whether a key is set (R-DT-05, R-DT-12).**

| | With the free API key | Without a key |
|---|---|---|
| Source | The playlist of regular videos, 50 exact times per request. New videos of a check: `videos.list`, 50 per request | One metadata lookup per video through yt-dlp, with the lightest options that still return the exact time |
| 1,000 videos | about 20 requests, about 25 seconds, 20 of 10,000 daily units | about 58 minutes one at a time, about 33 at two in parallel, about 15 at four |
| 6,600 videos | 132 requests, about 2.5 minutes, 132 units | about 6.4 hours one at a time, about 3.7 at two, about 1.7 at four |
| Risk | The daily quota. A full channel of 6,600 videos costs 1.3 % of it | YouTube slowing the app down or showing its "not a bot" check (Q-08, R-ER-05). From CI every lookup was refused |

**Without a key**
- Start at two lookups in parallel. Not four: no error appeared in 96 parallel lookups, but no run was longer than 32 videos (Q-08). M4 settles it on a real channel of 1,000 videos.
- Order: videos a decision waits for (R-MI-03), then videos on the screen, then selected or queued videos, then newest to oldest.
- The time left is computed from the rate the app measures while it runs ("Exact dates: 340 of 1,000, about 50 minutes left"). No fixed number is promised anywhere.
- When the estimate for a channel is longer than 10 minutes, the app offers the key, with the measured comparison of this table.
- The fetch yields to downloads and stops with the pause of R-ER-05. While it is held up by that pause, the channel says "Waiting for YouTube", not "Exact dates" (R-FB-01: held-up work is not running work).

**With a key**
- The first listing of a channel is followed by one pass over its playlist: every exact date at once.
- After every check, the new videos are looked up by ID, 50 per request.
- A key that fails or whose quota is used up falls back to the way without a key, without an error dialog (R-DT-12).
- The key is a secret of the logs (R-LG-07). Since M2 the logger already removes the value of `YTM_YOUTUBE_API_KEY`, the variable that live tests and probes take it from. The app itself reads the key from its settings.

**To check in M4 before this is built:** that the playlist time is the release time of a premiere to the second (R-DT-03), and how the playlist treats a video that was public and became private.

## Decisions the maintainer still has to make

| ID | Question | Default if not decided |
|---|---|---|
| Q-22 | Contact for the code of conduct and for security reports | GitHub private vulnerability reporting, no email |
| Q-23 | Should the app check for updates on first run before the user has seen the setting? | Yes, it is one request to GitHub with no personal data |
| Q-25 | Should "Full Check" also be an item of the Channel menu in the menu bar (R-NA-03, [DESIGN.md](DESIGN.md) section 7.1)? In M2 it is an item of the channel menu inside the interface. Needed by M5 | No. It stays in the channel menu of the interface |
| Q-28 | Should version 1.0 offer optional crash reports and anonymous usage counts? The proposal is in the section "Proposed: crash reports and usage counts" below. Needed before the first public release | Nothing is sent: no crash reports and no counts, as R-HE-03 says today |
| Q-26 | Can removing a channel be undone? `States.html` shows a toast "removed, files kept" with Undo, but R-CH-32 deletes the catalogue, the exclude list and the settings of the channel. Needed by M7 | No Undo. The toast only confirms the removal |

## Proposed: crash reports and usage counts (Q-28)

Raised by the maintainer in the review of milestone M2, for before the first public release. Not in the specification, in no milestone, and no SDK is added until it is decided.

**What stands against it today.** R-HE-03 says that the app never sends any data anywhere on its own and names every destination. Principle 3 of the spec ("nothing is silently lost") and the promise of a local app make silence the default. So the proposal changes R-HE-03 rather than working around it, and keeps everything off until the user says yes.

### Proposed requirements

New IDs are given only when the maintainer takes them into the spec. Prefix `R-TL` (telemetry) is a placeholder.

| Proposed | Requirement |
|---|---|
| R-TL-01 | Two separate choices: crash reports and usage counts. Both are off by default. Nothing is sent before the user turned one on. |
| R-TL-02 | The app asks once, at the first start after the first-run screen: one dialog, two switches, both off, with "Continue" and a link to the privacy page. Closing the dialog leaves both off. It never asks again. Settings has the same two switches. |
| R-TL-03 | A crash report holds only: the kind of error, its error code, the stack trace with file names reduced to the module names of the app's own code, the versions of the app, yt-dlp, ffmpeg and Deno, the macOS version, the processor and the install kind (clone, installer). |
| R-TL-04 | Never sent, in any report or count: a path (home folder, library, channel folder, app folder), the user name or computer name, a channel name, handle or ID, a video title or ID, an address (URL), the API key, the session token, the text of a log line, the values of variables. A report is built from an allow-list of fields, and every value passes the redactor of R-LG-07 before it leaves. |
| R-TL-05 | Usage counts are numbers only, sent at most once a day: how many channels (in ranges such as 1, 2 to 5, 6 to 20, more), how many videos were mirrored that day (in ranges), whether auto-mirror and exclude rules are used, the app version and the macOS major version. They carry no ID that stays the same from one day to the next. |
| R-TL-06 | Turning a switch off stops sending at once and drops what waits to be sent. |
| R-TL-07 | Sending never delays the app and never shows an error. A report that cannot be sent is dropped after one retry. |
| R-TL-08 | "Report a problem" and the debug report (R-HE-02, R-LG-04) stay manual and are not affected by these switches. |
| R-TL-09 | Tests, CI, the end-to-end tests and a clone started with `./start` never send: there the app uses an adapter that sends nothing, whatever the settings say. Only an installed release can send. |
| R-HE-03 (changed) | Add to the destinations: "the crash report service and the usage count service, each only when the user turned it on (R-TL-01)." |

Settings of section 10 (proposed): "Send crash reports", general, default Off. "Send usage counts", general, default Off.

### Proposed architecture

- A port `ports/telemetry.py`: `report_crash(report)` and `count(day_counts)`, both taking values of `core` types that can only hold the fields of R-TL-03 and R-TL-05. Services depend on the port, never on an SDK (rule 4 of AGENTS.md).
- `adapters/telemetry_none.py`: sends nothing. The default of the container, the adapter of every test, of CI and of a clone (R-TL-09). Its contract test is the same as the real adapter's.
- Later, `adapters/telemetry_sentry.py`: the only module that imports the SDK, chosen by the container only for an installed release with a switch on. The address of the service is part of the release, not a setting.
- Tests that prove R-TL-04: a report built from a crash in a world full of planted values (a path, a user name, a channel name, a video ID, a stand-in key) contains none of them. The same check runs on the frontend's error reports, if the window reports too.
- A CI check that fails when an SDK of a telemetry service is imported anywhere but in its adapter.

### Proposed privacy page

One page on the website (milestone M10) and the same text in the help (R-HE-01), linked from the dialog of R-TL-02 and from Settings:

1. What yt-mirror sends by default: nothing but the requests it needs to work, to YouTube, the optional YouTube API, GitHub and the download sources of its tools (R-HE-03).
2. Crash reports, if you turn them on: the list of R-TL-03, word for word, and an example report.
3. Usage counts, if you turn them on: the list of R-TL-05, word for word, and an example.
4. What is never sent: the list of R-TL-04.
5. Where it goes: the name of the service, the country of its servers, who can read the reports, and how long they are kept.
6. How to turn it off, and that turning it off takes effect at once.
7. That "Report a problem" is separate and always shows you what you send before you send it.
8. Your YouTube API key stays on your Mac (R-DT-12).

### Still to decide within Q-28

- Whether usage counts are worth it at all, or crash reports alone are enough.
- Which service: Sentry's own (with servers in the EU), or one that speaks its protocol and can be run by the maintainer, such as GlitchTip.
- How long reports are kept, and who can read them.
- Whether errors of the window (the interface) are reported too, or only of the backend.
- The milestone that builds it: the dialog and the switches fit M7 (settings), the adapter and its checks M11 (hardening), the privacy page M10.

