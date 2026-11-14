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
| Q-11 | The Google Cloud Console steps in the API key guide match the current console. A third-party guide from 2026 lists the same six steps, but nobody has followed them in the console for this project yet | Follow them once and correct the wording | M4 |
| Q-27 | A scheduled premiere and a members-only video appear in the listing of the Videos tab in a form the gateway handles. None of the four channels listed in M2 had one, so the shape of such an entry is not known. The gateway leaves out what yt-dlp marks as a live stream or a past live stream and lists everything else | Find a channel with each kind, record its listing, and add the cases to the gateway tests | M3 |

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
- YouTube's "not a bot" check (R-ER-05, D-071). From the two CI runners of GitHub every metadata lookup of a video was refused with "Sign in to confirm you're not a bot": 23 combinations of options, 32 videos, one at a time and in parallel. Listings of channels and playlists worked from the same runners. From the maintainer's network during this milestone: never in a listing (about 13,000 listed videos), never in a lookup with the default or the lightest options (about 260 lookups), and in 12 of 12 lookups with two unusual clients that skip the video's page, which the app does not use. This count is brought up to date at the end of the milestone.
- Seen on the side for Q-04 (M3): with the path of Deno given, yt-dlp still warned that its JavaScript challenge solver component is not installed ("Some formats may be missing"). Reading metadata worked. Downloading needs this looked at.

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

## Decisions the maintainer still has to make

| ID | Question | Default if not decided |
|---|---|---|
| Q-22 | Contact for the code of conduct and for security reports | GitHub private vulnerability reporting, no email |
| Q-23 | Should the app check for updates on first run before the user has seen the setting? | Yes, it is one request to GitHub with no personal data |
| Q-25 | Should "Full Check" also be an item of the Channel menu in the menu bar (R-NA-03, [DESIGN.md](DESIGN.md) section 7.1)? In M2 it is an item of the channel menu inside the interface. Needed by M5 | No. It stays in the channel menu of the interface |
| Q-26 | Can removing a channel be undone? `States.html` shows a toast "removed, files kept" with Undo, but R-CH-32 deletes the catalogue, the exclude list and the settings of the channel. Needed by M7 | No Undo. The toast only confirms the removal |
