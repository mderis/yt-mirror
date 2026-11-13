# yt-mirror V1: Open Questions and Things to Verify

Everything here must be resolved before or during the milestone named. When an item is resolved, move the answer into the right document, add a decision record if it was a real choice, and delete the item.

## To verify by experiment (assumptions made during planning)

| ID | Assumption | How to verify | Needed by |
|---|---|---|---|
| Q-02 | The creation date of a file can be set from Python with `setattrlist` (`ATTR_CMN_CRTIME`), and Finder shows it | Write the adapter and an integration test on a macOS runner. Check APFS, and exFAT for external drives. Fallback: set the modification time earlier than the creation time and confirm the creation time follows | M3 |
| Q-03 | A launcher app bundle created locally by the installer, and files fetched with `curl`, are not blocked by Gatekeeper | Test the installer on a clean Mac, on the two newest macOS versions | M9 |
| Q-04 | yt-dlp option names and behaviour in [ARCHITECTURE.md](ARCHITECTURE.md) section 7.3: format selectors, subtitle options, embedding order, attaching the info JSON to MKV, passing the Deno path, cancelling from a progress hook | Check against the pinned yt-dlp version and write gateway tests with recorded data | M3 |
| Q-05 | A trustworthy source of static ffmpeg and ffprobe builds for macOS arm64 and x86_64, with a license that allows downloading them at first run | Compare the available sources. Pin versions and checksums in the tool manifest. Record the choice as a decision. Also confirm that the chosen ffmpeg build and Deno run on macOS 15, the minimum set in D-035 | M1 |
| Q-06 | The channel feed returns exact published times for the newest videos (believed to be about 15 entries) and is stable enough to rely on | Fetch feeds for several channels and compare with full metadata | M4 |
| Q-07 | macOS notifications can be sent from an unsigned Python process started by a local launcher | Try the candidate mechanisms. If none works without signing, notifications fall back to in-app toasts only and R-FB-06 is moved to a later version | M7 |
| Q-08 | Slow-path exact date fetching at one request per 2 seconds does not trigger YouTube rate limits for typical channels | Measure on a 1,000-video channel. Adjust the rate and the estimate shown in the UI | M4 |
| Q-09 | The native folder picker of pywebview returns the folder the user chose. The rest of this question was answered in M0 (see ARCHITECTURE section 7.8): the picker opens and returns to Python, but choosing a folder needs a real click, which the automated probe could not do | Open the picker once by hand and check the returned path | M2 |
| Q-11 | The Google Cloud Console steps in the API key guide match the current console. A third-party guide from 2026 lists the same six steps, but nobody has followed them in the console for this project yet | Follow them once and correct the wording | M4 |
| Q-12 | Approximate dates from the flat channel listing are available for all videos | Check the listing output for old and new videos. If missing, show "date pending" instead of an approximate date | M2 |

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
